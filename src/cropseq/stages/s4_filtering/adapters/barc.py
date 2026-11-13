"""S4 BARC catalog: read one upazila's crop suitability, fetch it on a cache miss.

1. Read cached rows from `data/bangladesh/crop_recommender.db`.
2. On a cache miss, call the BARC CZIS endpoint through the shared HttpClient.
3. Save the fetched rows back to SQLite (write-through), with the taxonomy
   resolved now instead of trusting stale family/root columns.
4. If the call fails, borrow a cached upazila from the same district.
5. Re-check every row at read time: effective area and tier are recomputed;
   family/root/legume come from the taxonomy table; duration, yield and land
   types come from the BARC columns (never estimated here).
6. Skip a crop whose taxonomy or land-type data is missing, so S4 never
   selects a crop with family "Unknown".
7. Never disable TLS verification; the shared HttpClient uses normal checks.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import sqlite3
import zlib
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from cropseq.http import HttpClient

from ..ports import CatalogResult
from ..taxonomy import resolve_taxonomy

DEFAULT_DB = (
    Path(__file__).resolve().parents[5] / "data" / "bangladesh" / "crop_recommender.db"
)
BARC_URL = "https://dashboard.cropzoning.gov.bd/czis/suitable/area/upazila/{code}"

SEASONS = {"rabi": "Rabi", "kharif-1": "Kharif-1", "kharif-2": "Kharif-2"}


def _run_coroutine[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync code, also when a loop is running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def normalize_season(value: Any) -> str:
    """Map BARC season spellings to the names used by config.seasons."""
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if "rabi" in text:
        return "Rabi"
    if "kharif" in text:
        return "Kharif-2" if "2" in text else "Kharif-1"
    return ""


def _crop_id(value: Any, name: str, season: str) -> int:
    """Keep the BARC id when present, otherwise make a stable one."""
    try:
        return int(value)
    except TypeError, ValueError:
        return 100_000 + zlib.crc32(f"{name}|{season}".encode()) % 800_000


def _tier(very_suitable: float, suitable: float) -> str:
    if very_suitable > 0:
        return "Ideal"
    if suitable > 0:
        return "Suitable"
    return "Marginal"


def _clean_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Recompute taxonomy and scores for raw BARC rows.

    Returns the usable records plus the names that had no taxonomy entry.
    """
    cleaned: list[dict[str, Any]] = []
    unknown: list[str] = []

    for row in rows:
        name = str(row.get("crop_name") or "").split("(")[0].strip()
        if not name:
            continue
        season = normalize_season(row.get("season") or row.get("crop_season"))
        taxonomy = resolve_taxonomy(name)
        land_types = [
            part.strip()
            for part in str(row.get("allowable_land_types") or "").split(",")
            if part.strip()
        ]
        if taxonomy is None or not land_types:
            unknown.append(name)
            continue

        very_suitable = float(row.get("very_suitable_ha", row.get("vs")) or 0)
        suitable = float(row.get("suitable_ha", row.get("s")) or 0)
        marginal = float(row.get("mod_suitable_ha", row.get("ms")) or 0)
        effective = round(very_suitable + 0.70 * suitable, 1)
        if effective == 0 and marginal == 0:
            continue

        cleaned.append(
            {
                "crop_id": _crop_id(row.get("crop_id"), name, season),
                "crop_name": name,
                "season": season,
                "very_suitable_ha": very_suitable,
                "suitable_ha": suitable,
                "mod_suitable_ha": marginal,
                "effective_area": effective,
                "suitability_tier": _tier(very_suitable, suitable),
                "duration_days": float(row.get("duration_days") or 0),
                "yield_t_ha": float(row.get("yield_ton_ha") or 0),
                "land_types": land_types,
                **taxonomy,
            }
        )

    return cleaned, sorted(set(unknown))


def _unknown_warning(unknown: list[str]) -> list[str]:
    """One short warning instead of one warning per skipped crop."""
    if not unknown:
        return []
    preview = ", ".join(unknown[:5])
    suffix = "" if len(unknown) <= 5 else f" (+{len(unknown) - 5} more)"
    return [
        (
            f"Skipped {len(unknown)} BARC crop rows with unknown taxonomy or "
            f"no land-type data: "
            f"{preview}{suffix}."
        )
    ]


class BarcCatalog:
    """BARC CZIS crop suitability, local cache first, API on a miss."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        url: str = BARC_URL,
        http_client: HttpClient | None = None,
    ) -> None:
        self.db_path = Path(db_path or DEFAULT_DB)
        self.url = url
        self.http_client = http_client or HttpClient()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def get_records(self, upazila_code: str) -> CatalogResult:
        """Return every usable crop row for one upazila."""
        code = str(upazila_code)
        cached = self._cached_rows(code)
        if cached:
            return self._result(cached, warnings=[], source=f"barc:cache:{code}")

        fetched, unknown = _run_coroutine(self._fetch_and_save(code))
        if fetched:
            return CatalogResult(
                records=fetched,
                warnings=_unknown_warning(unknown),
                source=f"barc:api:{code}",
            )

        borrowed, neighbor = self._borrow_from_district(code)
        if borrowed:
            warning = (
                f"BARC CZIS data was unavailable for upazila {code}; "
                f"using cached crop data from {neighbor} in the same district."
            )
            return self._result(
                borrowed, warnings=[warning], source=f"barc:district:{code}<-{neighbor}"
            )

        return CatalogResult(
            records=[],
            warnings=[
                (
                    f"No BARC crop data for upazila {code} and no cached upazila "
                    "in the same district. All seasons will be Fallow."
                )
            ],
            source=f"barc:empty:{code}",
        )

    def _enrich_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add duration, yield and land types from the local BARC database.

        The API payload has only area figures. We do not invent the other
        values: a crop that is not in the database is left without land types
        and `_clean_rows` skips it.
        """
        enriched: list[dict[str, Any]] = []
        connection = self._connect()
        try:
            for row in rows:
                if row.get("allowable_land_types"):
                    enriched.append(row)
                    continue
                name = str(row.get("crop_name") or "").split("(")[0].strip()
                meta = connection.execute(
                    """
                    SELECT allowable_land_types, duration_days, yield_ton_ha
                    FROM upazila_suitable_crops
                    WHERE crop_name = ? COLLATE NOCASE
                      AND allowable_land_types IS NOT NULL
                      AND trim(allowable_land_types) != ''
                    ORDER BY upazila_code, id
                    LIMIT 1
                    """,
                    (name,),
                ).fetchone()
                enriched.append({**row, **dict(meta)} if meta else row)
        finally:
            connection.close()
        return enriched

    def _cached_rows(self, code: str) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM upazila_suitable_crops WHERE upazila_code = ?",
                (code,),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def _result(
        self, rows: list[dict[str, Any]], *, warnings: list[str], source: str
    ) -> CatalogResult:
        records, unknown = _clean_rows(rows)
        return CatalogResult(
            records=records,
            warnings=[*warnings, *_unknown_warning(unknown)],
            source=source,
        )

    async def _fetch_and_save(
        self, code: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Call BARC CZIS, clean the rows, save them, and return the records."""
        try:
            payload = await self.http_client.get_json(
                self.url.format(code=code),
                headers={"Accept": "application/json"},
            )
        except Exception:  # noqa: BLE001 - any BARC failure uses the fallback
            return [], []

        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not rows:
            return [], []

        records, unknown = _clean_rows(self._enrich_rows(rows))
        if not records:
            return [], unknown

        connection = self._connect()
        try:
            connection.executemany(
                """
                INSERT OR REPLACE INTO upazila_suitable_crops
                (upazila_code, crop_id, crop_name, season, very_suitable_ha,
                 suitable_ha, mod_suitable_ha, effective_area, suitability_tier,
                 allowable_land_types, botanical_family, root_type, is_legume,
                 duration_days, yield_ton_ha, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BARC_CZIS_GOV')
                """,
                [
                    (
                        code,
                        row["crop_id"],
                        row["crop_name"],
                        row["season"],
                        row["very_suitable_ha"],
                        row["suitable_ha"],
                        row["mod_suitable_ha"],
                        row["effective_area"],
                        row["suitability_tier"],
                        ",".join(row["land_types"]),
                        row["family"],
                        row["root_type"],
                        1 if row["is_legume"] else 0,
                        int(row["duration_days"]),
                        row["yield_t_ha"],
                    )
                    for row in records
                ],
            )
            connection.commit()
        finally:
            connection.close()
        return records, unknown

    def _borrow_from_district(self, code: str) -> tuple[list[dict[str, Any]], str]:
        """Use a cached upazila from the same district when the API fails."""
        connection = self._connect()
        try:
            meta = connection.execute(
                "SELECT district_name FROM upazila_boundaries WHERE upazila_code = ?",
                (code,),
            ).fetchone()
            district = meta["district_name"] if meta else ""
            if not district:
                return [], ""
            neighbor = connection.execute(
                """
                SELECT b.upazila_code, b.upazila_name
                FROM upazila_boundaries b
                JOIN upazila_suitable_crops c ON c.upazila_code = b.upazila_code
                WHERE b.district_name = ? AND b.upazila_code != ?
                ORDER BY b.upazila_code
                LIMIT 1
                """,
                (district, code),
            ).fetchone()
            if not neighbor:
                return [], ""
            rows = connection.execute(
                "SELECT * FROM upazila_suitable_crops WHERE upazila_code = ?",
                (neighbor["upazila_code"],),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows], str(neighbor["upazila_name"])
