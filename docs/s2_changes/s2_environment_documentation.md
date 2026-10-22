# S2 Environment Subsystem Documentation & Audit Report

## 1. Executive Summary

The `s2_environment` module is the second stage in the **cropseq** 8-stage crop-rotation decision support pipeline. Its sole responsibility is to acquire untouched, raw environmental data—specifically geo-located soil profile layers and historical daily agroclimatology—for a given farm location.

In strict compliance with the **cropseq** modular monolith architecture:
- **Pure I/O Responsibility**: Stage 2 only **fetches** and caches external raw data. It performs zero unit scaling, data normalization, or agronomic filtering (unit transformations and seasonal aggregations are strictly deferred to Stage 3 `s3_normalization`).
- **Ports and Adapters Pattern**: External network dependencies (ISRIC SoilGrids and Open-Meteo) sit behind Python `Protocol` interfaces with swappable offline (`fake`) and online (`live`) implementations.
- **Fail-Safe & Offline-First**: Built with deterministic local SQLite caching and automatic fallbacks to offline profiles when external APIs experience outages, rate limits, or network timeouts.

---

## 2. Architectural Boundaries & Contracts

### Rule Conformance
- **Rule 1 (Single Public Entrypoint)**: Stage 2 exposes exactly one public entrypoint:
  [`run(location: Location) -> RawEnvironment`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/service.py#L208) in [`service.py`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/service.py).
- **Rule 2 (Strict Import Isolation)**: Modules within Stage 2 import exclusively from [`cropseq.contracts`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/contracts), [`cropseq.config`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/config.py), standard libraries, and its own package. Cross-stage imports are strictly prohibited and verified by AST-based unit tests ([`test_rule2_imports.py`](file:///e:/Project_Files/Farmer-decision-support-tool/tests/stages/test_rule2_imports.py)).

### Shared Contracts
- **Input Contract**: [`Location`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/contracts/farmer.py#L6)
  ```python
  class Location(BaseModel):
      latitude: float = Field(ge=-90, le=90)
      longitude: float = Field(ge=-180, le=180)
  ```
- **Output Contract**: [`RawEnvironment`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/contracts/environment.py#L10) (inherits from [`StageOutput`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/contracts/common.py#L22))
  ```python
  class RawEnvironment(StageOutput):
      soil_raw: dict = {}      # Untransformed SoilGrids GeoJSON payload
      weather_raw: dict = {}   # Untransformed Open-Meteo daily JSON payload
      fetched_at: str = ""     # ISO 8601 UTC timestamp
      warnings: list[str] = [] # Captured provider warnings and fallback notifications
      source: str = ""         # Data provenance trace (e.g. 'soil:soilgrids (api), weather:open_meteo (cache)')
  ```

---

## 3. Subsystem Architecture: Ports & Adapters

```
[pipeline.py]
      │
      ▼
[s2_environment.service.run(location)]
      │
      ├──────────────────────┬──────────────────────┐
      ▼                      ▼                      ▼
[SoilDataPort]         [WeatherDataPort]       [CachePort]
      │                      │                      │
   ├── FakeSoilProvider   ├── FakeWeatherProvider   └── SQLiteCache
   └── SoilGridsAdapter   └── OpenMeteoAdapter
              │                      │
              └──────────────┬───────┘
                             ▼
                        [HttpClient] (httpx + tenacity retry)
```

### 3.1 Ports ([`ports.py`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/ports.py))
- [`SoilDataPort`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/ports.py#L9): Protocol defining `fetch(latitude: float, longitude: float) -> dict[str, Any]` and identifier property `name`.
- [`WeatherDataPort`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/ports.py#L23): Protocol defining `fetch(latitude: float, longitude: float, start_date: date, end_date: date) -> dict[str, Any]`.
- [`CachePort`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/ports.py#L39): Protocol for `get(key: str)` and `set(key: str, provider: str, request: dict, response: dict)`.

### 3.2 Adapters
- [`FakeSoilProvider`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/fake.py#L11) & [`FakeWeatherProvider`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/fake.py#L28): Provide instant offline payloads loaded from [`data/data_shape/s2_output.json`](file:///e:/Project_Files/Farmer-decision-support-tool/data/data_shape/s2_output.json).
- [`SoilGridsAdapter`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/soilgrids.py#L10):
  - Endpoint: `https://rest.isric.org/soilgrids/v2.0/properties/query`
  - Target Properties: `phh2o`, `clay`, `sand`, `silt`, `soc`, `nitrogen`
  - Depths: `0-5cm`, `5-15cm`, `15-30cm`, `30-60cm`, `60-100cm`, `100-200cm`
- [`OpenMeteoAdapter`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/open_meteo.py#L11):
  - Endpoint: `https://archive-api.open-meteo.com/v1/archive`
  - Variables: `temperature_2m_mean`, `precipitation_sum`, `et0_fao_evapotranspiration` (FAO Penman–Monteith)
  - Timezone: `auto`, Metric units (`celsius`, `mm`)
- [`HttpClient`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/http.py#L25): Asynchronous wrapper around `httpx.AsyncClient` with `tenacity` exponential backoff retrying on HTTP 429 (rate-limiting) and transient 5xx server errors.

### 3.3 Cache Engine ([`cache/sqlite.py`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/cache/sqlite.py))
- [`make_cache_key`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/cache/sqlite.py#L13): Produces a deterministic SHA256 digest from the provider name and serialized request parameters (sorted keys, compact separators).
- [`SQLiteCache`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/cache/sqlite.py#L23): Manages local SQLite table `environment_cache` storing `cache_key`, `provider`, `request_json`, `response_json`, and UTC `created_at`.

---

## 4. Execution Lifecycle & Orchestration

The orchestrator is [`EnvironmentService`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/service.py#L36):

1. **Date Range Resolution**: Calls `_get_planning_date_range()` across configured growing seasons.
2. **Deterministic Key Generation**: Generates SHA256 cache keys for soil and weather queries.
3. **Cache Lookup**: Queries `SQLiteCache` for existing responses.
4. **Concurrent Async Fetching**: Gathers missing API calls concurrently using `asyncio.gather(*tasks, return_exceptions=True)`.
5. **Fallback Handling**: If an external provider throws an exception (network timeout, HTTP error), `EnvironmentService` falls back to offline providers, tags the provenance source as `(fallback)`, and appends an informative string to `warnings`.
6. **Cache Write**: Stores successful live API responses into the SQLite database.
7. **Sync-Bridge Execution**: [`_run_coroutine`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/service.py#L23) safely dispatches the asynchronous pipeline on existing running event loops (e.g. within FastAPI or test runners) via `concurrent.futures.ThreadPoolExecutor`.

---

## 5. Summary of Recent Changes & Fixes

### Fix 1: Chronological Date Range Handling for Year-Wrapping Seasons
- **Issue**: `_get_planning_date_range` previously used `min(start_month)` and `max(end_month)` within a hardcoded single calendar year. If a season wrapped across year-end (e.g., Rabi season: November to February, where `end_month < start_month`), the computed date range was reversed or corrupted.
- **Solution**: Replaced with sequential chronological rotation traversal in [`service.py`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/service.py#L176): advances calendar year whenever a season wraps or when a subsequent season starts earlier than the previous season ended.
- **Testing**: Added unit test `test_get_planning_date_range_standard_and_wrapping` in [`tests/stages/test_s2_service.py`](file:///e:/Project_Files/Farmer-decision-support-tool/tests/stages/test_s2_service.py#L102).

### Fix 2: Environment Variable Configuration with `pydantic-settings`
- **Issue**: [`Config`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/config.py#L11) was a static `BaseModel` that could not read environment variables or `.env` files dynamically.
- **Solution**: Upgraded `Config` to inherit from `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_file=".env", case_sensitive=False)`. Added support for `ADAPTER_SOIL`, `ADAPTER_WEATHER`, `ADAPTER_CROPS`, `ADAPTER_EXPLAINER`, `CACHE_DB`, and the global preset `ENV_PROVIDER=real` (which maps soil & weather adapters to `soilgrids` and `openmeteo`).
- **Testing**: Added unit test suite in [`tests/test_config.py`](file:///e:/Project_Files/Farmer-decision-support-tool/tests/test_config.py).

### Fix 3: Strict Offline Test Isolation
- **Issue**: If a developer set `ADAPTER_SOIL=soilgrids` in their local `.env`, running `pytest` would trigger slow external live network calls during unit testing.
- **Solution**: Created [`tests/conftest.py`](file:///e:/Project_Files/Farmer-decision-support-tool/tests/conftest.py) with an autouse fixture `isolated_test_config` that forces all adapters to `fake` and directs caching to an isolated temporary directory during tests.

### Fix 4: Schema Alignment of Fake Fixture with SoilGrids 2.0 GeoJSON
- **Issue**: [`data/data_shape/s2_output.json`](file:///e:/Project_Files/Farmer-decision-support-tool/data/data_shape/s2_output.json) previously stored a hand-simplified dictionary (`properties.phh2o.value`), whereas live SoilGrids API returns a nested GeoJSON feature (`properties.layers[i].depths[j].values.mean`). S3 normalization code would crash if switched between fake and real data.
- **Solution**: Updated `s2_output.json` to mirror the authentic ISRIC GeoJSON layer format, while aligning exact numeric values with [`s3_output.json`](file:///e:/Project_Files/Farmer-decision-support-tool/data/data_shape/s3_output.json) (e.g. `phh2o` mean 64 with `d_factor` 10 = 6.4 pH).
- **Testing**: Updated [`tests/stages/test_s2_adapters.py`](file:///e:/Project_Files/Farmer-decision-support-tool/tests/stages/test_s2_adapters.py#L78) to assert that `layers` exists under `properties`.

---

## 6. Audit Findings & Architecture Alignment

A comparison between Stage 2 implementation and [`docs/Crop Rotation System Architecture.md`](file:///e:/Project_Files/Farmer-decision-support-tool/docs/Crop%20Rotation%20System%20Architecture.md):

| Architecture Requirement | Verification / Status | Audit Verdict |
| :--- | :--- | :--- |
| **ISRIC SoilGrids 2.0 Endpoint** (Line 199) | `https://rest.isric.org/soilgrids/v2.0/properties/query` | **Fully Compliant** |
| **Soil Properties & Depths** (Line 199) | Queries `phh2o`, `clay`, `sand`, `silt`, `soc`, `nitrogen` across 6 depth intervals from 0 to 200 cm | **Fully Compliant** |
| **Open-Meteo Archive API** (Line 200) | `https://archive-api.open-meteo.com/v1/archive` | **Fully Compliant** |
| **Reference ET0 (Penman-Monteith)** (Line 12, 200) | Queries pre-computed daily `et0_fao_evapotranspiration` | **Fully Compliant** |
| **Daily Precipitation & Mean Temp** (Line 201) | Queries `precipitation_sum`, `temperature_2m_mean` | **Fully Compliant** |
| **Local SQLite Caching** (Lines 33, 58, 503) | SHA256 hashed queries in SQLite DB, zero network calls on repeat | **Fully Compliant** |
| **Rate Limit / Timeout Resilience** (Lines 58, 503) | HTTP status 429 & 5xx retry with tenacity backoff + fallback provider | **Fully Compliant** |
| **Zero Transformation in S2** (AGENTS.md) | Pure I/O pass-through; raw integers untouched for S3 | **Fully Compliant** |
| **Thermal Range Variables** (Line 201) | Currently missing `temperature_2m_max` and `temperature_2m_min` | **Gap Identified** |
| **Multi-Year Rolling Baseline** (Line 251) | Queries 1 year instead of rolling 5-year historical average | **Gap Identified** |
| **Ocean / Water Coordinates** (Lines 58, 325) | SoilGrids returns 200 OK with `mean: null`; handled in S3 | **Observed Specification** |

---

## 7. Identified Gaps & Recommended Next Steps

### Gap 1: Daily Temperature Min/Max for Thermal Planting Windows
- **Background**: Architecture Doc lines 44 & 201 highlight evaluating thermal planting windows, minimum germination thresholds, and frost risks.
- **Current State**: [`OpenMeteoAdapter.DAILY_VARIABLES`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/open_meteo.py#L15) only queries `temperature_2m_mean`.
- **Recommendation**: Add `"temperature_2m_max"` and `"temperature_2m_min"` to `DAILY_VARIABLES` in [`open_meteo.py`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/stages/s2_environment/adapters/open_meteo.py#L15).

### Gap 2: Multi-Year Historical Climate Aggregation Window
- **Background**: Architecture Doc line 251 states: *"Future weather patterns are approximated using a rolling five-year historical average of daily Open-Meteo observations for the parcel coordinates."*
- **Current State**: S2 currently queries a single reference year (`2025`).
- **Recommendation**: Introduce a configurable parameter `history_years: int = 5` in [`Config`](file:///e:/Project_Files/Farmer-decision-support-tool/src/cropseq/config.py#L11), allowing S2 to request a multi-year window (e.g. `2020-01-01` to `2024-12-31`) so S3 can aggregate multi-year monthly statistics.

---

## 8. Test Execution Verification

All unit, adapter, caching, and end-to-end integration tests were executed:

```powershell
$env:PYTHONPATH="src"; python -m pytest
```

### Results Summary
- **Test Session**: Python 3.10.0, pytest-9.1.1
- **Total Tests Collected**: 32
- **Results**: **32 passed in 0.55s**
  - `tests/contracts/test_fixtures.py`: 16 passed
  - `tests/e2e/test_pipeline.py`: 1 passed
  - `tests/stages/test_rule2_imports.py`: 1 passed (Rule 2 import isolation verified)
  - `tests/stages/test_s2_adapters.py`: 4 passed (SoilGrids, Open-Meteo, Fake, HTTP retry)
  - `tests/stages/test_s2_cache.py`: 3 passed (Cache key hashing, SQLite lifecycle)
  - `tests/stages/test_s2_service.py`: 4 passed (Cache hit/miss, API fallback, entrypoint, date range)
  - `tests/test_config.py`: 3 passed (Defaults, `ENV_PROVIDER=real`, adapter overrides)
