"""S4 crop taxonomy: fill only the three botanical fields the spec requires.

1. Normalize a BARC crop name (lowercase, drop variety text in brackets).
2. Look it up in `data/bangladesh/crop_taxonomy.json`.
3. Follow a small alias table for spelling variants (Mung Bean, Groundnut, ...).
4. Return only family, root type and legume flag. Duration, yield and land
   types are NOT estimated here; they come from the BARC database rows.
5. Return None when the crop is not known, so S4 skips it instead of selecting
   a crop with family "Unknown".
6. `is_perennial` marks tree/plantation crops that must never enter a rotation.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[4] / "data" / "bangladesh"
TAXONOMY_FILE = DATA / "crop_taxonomy.json"

ALIASES = {
    "groundnut": "ground nut",
    "mung bean": "mungbean",
    "mung": "mungbean",
    "blackgram": "black gram",
    "chickpea": "gram / chickpea",
    "gram": "gram / chickpea",
    "gram/chickpea": "gram / chickpea",
    "chick pea": "gram / chickpea",
    "lady's finger": "ladys finger",
    "ladies finger": "ladys finger",
    "okra": "ladys finger",
    "sweetpotato": "sweet potato",
    "watermelon": "water melon",
    "muskmelon": "musk melon",
    "t. aman": "t. aman dhan",
    "t aman": "t. aman dhan",
    "aman dhan": "t. aman dhan",
    "boro": "boro dhan",
    "boro rice": "boro dhan",
    "yardlong bean": "yard long bean",
    "countrybean": "country bean",
    "potol": "pointed gourd",
    "taro": "aroid",
    "kochu": "aroid",
    "data shak": "stem amaranth",
    "lal shak": "red amaranth",
}

# Multi-word terms are matched anywhere in the name; single words must be exact.
PERENNIAL_TERMS = (
    "date palm",
    "palmyra palm",
    "guava",
    "jackfruit",
    "coconut",
    "mango",
    "banana",
    "papaya",
    "betel leaf",
    "litchi",
    "lemon",
    "jujube",
    "dragon fruit",
    "sapota",
    "golden apple",
    "sweet orange",
    "pineapple",
)
PERENNIAL_EXACT = {"tea"}


def normalize_name(value: str) -> str:
    """Lowercase, drop the variety text and collapse whitespace."""
    clean = value.split("(")[0]
    clean = " ".join(clean.lower().split())
    return clean.strip(" .,")


@lru_cache(maxsize=1)
def load_taxonomy(path: str = str(TAXONOMY_FILE)) -> dict[str, dict[str, Any]]:
    """Load the editable taxonomy JSON once per process."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_taxonomy(name: str) -> dict[str, Any] | None:
    """Return family/root/legume for a crop name, or None if it is unknown."""
    normalized = normalize_name(name)
    table = load_taxonomy()
    entry = table.get(normalized) or table.get(ALIASES.get(normalized, ""))
    if entry is None:
        return None
    return {
        "family": entry["family"],
        "root_type": entry["root_type"],
        "is_legume": bool(entry["is_legume"]),
    }


def is_perennial(name: str) -> bool:
    """True for tree, palm and plantation crops that do not belong in a rotation."""
    normalized = normalize_name(name)
    words = set(re.findall(r"[a-z]+", normalized))
    if normalized in PERENNIAL_EXACT or words & PERENNIAL_EXACT:
        return True
    return any(term in normalized for term in PERENNIAL_TERMS)
