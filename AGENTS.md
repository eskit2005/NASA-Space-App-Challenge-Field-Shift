# AGENTS.md

## Project 

You are setting up the initial skeleton for "cropseq": a backend-only, deterministic crop-rotation decision-support system. Do NOT implement real agronomic logic. Build structure, contracts, stubs, fixtures, tooling, and tests only.

## Architecture (must follow)
Modular monolith: one Python codebase, one process. The top-level structure is a pipeline of 8 stages. External dependencies (stage 2: soil/weather APIs, stage 7: LLM) sit behind ports (Protocol interfaces) with swappable adapters. Stages 3-6 and 8 are pure functions with no I/O.

Rules:
1. Each stage exposes exactly one public function: `run(input) -> output`, in `stages/sN_name/service.py`.
2. Stages import ONLY from `cropseq.contracts` (and their own folder). Never from other stages.
3. Only `pipeline.py` calls stages and wires them in order.
4. `contracts/` holds all shared Pydantic v2 models for stage inputs/outputs.
5. The API layer is thin: no logic, only calls `pipeline.run`.
6. Every stage has a fixture JSON in `data/fixtures/`, and its stub returns that fixture (validated through the contract).

## Stack
Python 3.11+, uv (package manager, lockfile), FastAPI + uvicorn, Pydantic v2 + pydantic-settings, NumPy, Pandas, httpx, tenacity, LiteLLM, Jinja2, Typer, pytest, pytest-cov, ruff, pre-commit.
Dev dependencies go in a dev group. No frontend. No SQLAlchemy yet (SQLite via stdlib sqlite3 only when needed).

## Folder structure
cropseq/
├── pyproject.toml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── .github/workflows/ci.yml        # ruff check, ruff format --check, pytest on PRs
├── data/
│   ├── crops/crops.json            # 3 placeholder crops, valid against Crop contract
│   └── fixtures/                   # one input/output JSON per stage (s1..s8)
├── src/cropseq/
│   ├── contracts/
│   │   ├── farmer.py       # FarmerProfile, SoilOverrides, OptimizationPriorities
│   │   ├── environment.py  # RawEnvironment, SoilProfile, SeasonalAgroclimate, EnvironmentalObservation
│   │   ├── crops.py        # Crop, CropGrowthStageKc, BotanicalFamily, FeasibleCrops
│   │   ├── sequences.py    # CandidateSequence, SequencePool
│   │   ├── evaluation.py   # EvaluatedSequence, EvaluationResult
│   │   └── explanation.py  # EvidenceReference, Explanation, RecommendationResponse
│   ├── stages/
│   │   ├── s1_intake/
│   │   ├── s2_environment/  # ports.py (SoilProvider, WeatherProvider), adapters/{soilgrids.py, openmeteo.py}, service.py
│   │   ├── s3_normalization/
│   │   ├── s4_filtering/
│   │   ├── s5_sequences/
│   │   ├── s6_optimization/
│   │   ├── s7_explanation/  # ports.py (Explainer), adapters/{template.py, llm.py}, service.py
│   │   └── s8_audit/
│   ├── pipeline.py   # run(profile) -> RecommendationResponse; wires s1..s8
│   ├── config.py     # pydantic-settings; selects adapters (e.g. ADAPTER_SOIL=soilgrids, EXPLAINER=llm)
│   ├── api/{main.py, routes.py}
│   └── cli.py        # Typer: `cropseq run <profile.json>`, `cropseq stage <name> <input.json>`
└── tests/
    ├── contracts/      # each fixture validates against its contract
    ├── stages/         # one test file per stage: fixture in -> assert output type/shape
    └── e2e/            # full pipeline with fake adapters

## Contract chain (stage input -> output)
s1: FarmerProfile -> FarmerProfile (validated, defaults applied)
s2: farmer.location -> RawEnvironment (raw soil + weather payloads)
s3: (FarmerProfile, RawEnvironment) -> EnvironmentalObservation
s4: EnvironmentalObservation -> FeasibleCrops (feasible crops per season; loads data/crops/crops.json)
s5: FeasibleCrops -> SequencePool (3-season sequences) Note: Update needs on season count.
s6: (SequencePool, EnvironmentalObservation, FarmerProfile) -> EvaluationResult (evaluated sequences + Pareto flags)
s7: EvaluationResult -> Explanation
s8: (Explanation, EvaluationResult) -> RecommendationResponse
Base the models on typical fields: FarmerProfile (farm_id, lat, lon, area_hectares, budget_usd, irrigation_quota_m3, priorities, optional soil_overrides), SoilProfile (ph, clay/sand/silt fractions, organic_carbon_g_kg, total_nitrogen_g_kg, is_field_tested), Crop (crop_id, common_name, botanical_family, suitable_seasons, ph tolerance range, growth_days, kc coefficients, baseline yield/price/cost, nitrogen_balance, root_depth_class), EvaluatedSequence (sequence_id, crops, gross_margin_usd, irrigation_demand_m3, soil_health_score, is_pareto_optimal). Use sensible validation (ge/le bounds). Keep models small; they will evolve.

## Stubs
Each stage's `run` returns data loaded from its fixture, validated by the output contract. S2 is the exception: it calls the real SoilGrids/Open-Meteo APIs through its ports, and there is no fake provider. `template.py` is the default explainer adapter.

## API
FastAPI app with:
- GET /health -> {"status": "ok"}
- POST /api/v1/recommendations/optimize (FarmerProfile -> FinalResponse)
Routes call `pipeline.run` only. No debug stage endpoint (dropped by decision).
OpenAPI docs at /docs.

## Setup steps to execute
1. `uv init` (src layout, package name cropseq), add dependencies and dev group, generate lockfile.
2. Create all folders/files above (with __init__.py where needed).
3. Install pre-commit hooks (ruff check + ruff format).
4. Run `uv run ruff check . && uv run ruff format .`
5. Run `uv run pytest` until green.
6. Smoke test: `uv run cropseq run data/fixtures/s1_input.json` and `uv run uvicorn cropseq.api.main:app`, hit /health and /docs.

## README must contain
Architecture rules above (short), how to run (CLI, API, tests), how to add a stage, how to add an adapter, how to add an experiment inside a stage (extra file + select in config.py), and a "stage ownership" table with empty owner column.

## Acceptance criteria
- `uv sync && uv run pytest` passes from a clean clone.
- `uv run cropseq run <fixture>` returns a valid RecommendationResponse using fake adapters, with no network access.
- A test enforces rule 2: no module in `stages/` imports from another stage (AST or grep based check).
- Ruff clean, CI workflow present.
- No real agronomic logic and no secrets committed.

When done, give a short summary of what was created and any decisions you made that deviate from this spec.

## current work:

# Task: Build Stage 3 (crop candidate pools) in this repo, with land-type validation from soil and weather data

## 1. Goal
Given a farm location, return the list of crops that can grow there, per season. This is **Stage 3** of our Crop Sequence Recommender.

A teammate already built Stage 3 in a separate repo: https://github.com/eskit2005/crop_sequence_recommender. It was meant to live in this repo. Do two things:
1. Bring that Stage 3 logic into this repo, **Bangladesh path only**.
2. Add a **land-type validation layer** that uses the data we already fetch (SoilGrids, NASA POWER, Open-Meteo) to check the land type the farmer gives.

Inspect this repo first and follow its conventions. Reuse the existing data fetchers here instead of writing new ones. You decide where everything goes.

**Out of scope for now:** the global (non-Bangladesh) path, and anything after Stage 3. For a location outside Bangladesh, return a clear "not supported yet" result. Keep the Stage 3 output format stable because a later stage will consume it.

## 2. Stage 3 behaviour to reproduce (read the teammate's code and `crop_sequence_recommender_architecture.md` in that repo)
**Input:** latitude, longitude, `land_type` (HL, MHL, MLL, LL/VLL). Default is MHL.

**Flow:**
1. **Locate.** Match the point to one of 505 Bangladesh upazilas (local districts) using boundary polygons (bounding-box prefilter, then point-in-polygon). Get the upazila code and district name.
2. **Load crop data.** Read that upazila's crop suitability from the local BARC CZIS database. If it is missing, fetch it from the BARC endpoint, save it, and use it. If the fetch fails, borrow another upazila's data from the same district.
3. **Score.** For each crop, `effective area = very suitable ha + 0.70 × suitable ha`.
4. **Filter by land type.** Remove crops that cannot survive the flood level: no Boro rice on HL, no potato or cole crops on LL, and so on. Accept ML as MLL. Remove perennial tree crops.
5. **Region rules (hard-coded district lists):**
   - **Haor:** LL land in haor districts keeps only Boro and rice-type crops, one crop per season, K=1, summer seasons Fallow.
   - **Coastal saline:** MLL or LL land in coastal districts. On deep land, dry seasons become Fallow, Boro is removed and only monsoon T. Aman stays.
   - **High Barind:** HL land in Rajshahi, Chapai Nawabganj and Naogaon protects Chickpea in the Rabi list.
6. **Bucket.** Pick the best crops per season: Rabi 7, Kharif-1 5, Kharif-2 3. Take the top crop of each plant group (pulses, tubers, oilseeds, fibres, cereals, vegetables) with effective area ≥ 300 ha first, then fill the rest by area. If a charland (MLL) upazila has no data, use the teammate's alluvial fallback crops.
7. **K** = max(1, min(cap by land type, number of non-empty seasons)). The cap is 3 for HL and MHL, 2 for MLL, and 1 for haor and coastal LL.
8. **Fallow.** Any empty season gets a Fallow placeholder (`crop_id` 999) so no list is ever empty.

**Output:** K, flags (haor, coastal saline, deep wetland), the three crop lists (name, family, root type, legume flag, duration, yield, effective area, tier, score), and the routing details.

**Known issues to handle:**
- About half of the cached BARC rows have botanical family "Unknown" (for example Pumpkin, Cucumber, Barley, and "Ground Nut" as a legume). Every crop must get a correct family, root type and legume flag. The teammate has a taxonomy helper file that was never pushed. Use it if you get it, otherwise fill the missing crops yourself, and some cached rows are stale, so re-check them at read time.
- Only about 190 of 505 upazilas are cached locally. Online fetching must work and save results.
- Crop ids in the charland fallback must be the same on every run.
- Do not copy the teammate's disabled TLS certificate checks.

## 3. Land-type validation (new)
The farmer's land type is the main input. Use the data below only to **check** it, never to silently replace it.

**Data we already fetch:**
- **SoilGrids:** `clay, sand, silt, bdod, soc, phh2o, cec` at 6 depths (0–5, 5–15, 15–30, 30–60, 60–100, 100–200 cm). Raw values need converting: clay, sand, silt, soc and phh2o ÷ 10, bdod ÷ 100. Values can be null.
- **NASA POWER:** `GWETTOP` and `GWETROOT` (soil wetness, 0–1), `PRECTOTCORR` (rain), `EVLAND`.
- **Open-Meteo (daily archive):** `precipitation_sum`, `et0_fao_evapotranspiration`, and the grid point's `elevation`.

**Compute four indicators, each scaled 0 (not flood-prone) to 1 (very flood-prone):**
1. **Drainage** (SoilGrids): average clay over 15–100 cm. 0 at ≤ 25%, 1 at ≥ 45%. If topsoil sand ≥ 50%, subtract 0.3 (minimum 0).
2. **Wetness** (NASA): July–September `GWETTOP`. Use the share of days above 0.85 if daily data exist, otherwise the mean.
3. **Monsoon surplus** (Open-Meteo): June–October sum of (rain − et0), divided by 2500 mm, capped at 1.
4. **Elevation** (Open-Meteo): (20 − elevation in m) / 20, kept between 0 and 1. If it is easy, use NASA SRTM elevation instead because it is finer.

**Combine:** index = 0.35 elevation + 0.30 drainage + 0.20 wetness + 0.15 surplus. If a source is missing, leave it out and rescale the weights.
**Class:** index < 0.30 → HL, < 0.50 → MHL, < 0.70 → MLL, otherwise LL.
**Confidence:** high only if at least 3 indicators are available and the index is at least 0.08 away from a class boundary. Otherwise low.

All of these numbers are starting values. Keep them in one config place and tune them in section 5.

**Policy:**
- Farmer value given: use it for Stage 3. Compare it with the estimate: same class = `match`, one class apart = `adjacent` (note only), two or more apart = `conflict`. On a high-confidence conflict, return a warning asking the farmer to confirm. Do not change the value.
- Farmer value not given: use the estimate if confidence is high. If low, use MHL and flag it as an unconfirmed default.
- A source that fails or returns null must never crash the run. It only lowers confidence.

**Add to the output:** `land_type_check` with the farmer value, estimated class, confidence, agreement, the four indicator values, and a one-line plain-language message.

## 4. Rules
- Follow this repo's conventions and dependency choices. No network calls in tests: use recorded sample responses.
- Deterministic: the same input gives the same output.
- Do not invent data. State every assumption.

## 5. Tests and calibration
**Stage 3:** Raninagar (24.78, 89.04, MHL) includes Potato and Sunflower in Rabi. HL removes Boro. LL removes Potato, Solanaceae and cole crops. Dowarabazar (25.05, 91.56, LL) gives K=1 with Boro. Mongla (22.1532, 89.6591, MHL) gives K=1 with only T. Aman in Kharif-2. HL in Rajshahi keeps Chickpea in Rabi. ML is treated as MLL. No season list is ever empty. No selected crop has family "Unknown".
**Validation:** missing sources lower confidence without crashing. Match, adjacent and conflict each produce the right output. Farmer value missing is handled as described above.
**Calibration:** run the validation on places with a known land type: Raninagar (MHL), Dowarabazar (LL), Charghat (24.28, 88.75, HL), Mongla (MHL), plus any benchmark locations in the teammate's repo that carry a land type. Adjust the starting numbers, and report honestly how often the estimate matches.

## 6. Report back
What you built; test results; the calibration table (location, known class, estimated class, confidence); the final numbers you chose; assumptions; and anything in the teammate's spec or code that was unclear.







***stage-5***

Variables : 
Soil nitrogen (N)
Soil organic carbon (SOC)
Soil pH
Soil salinity (EC)
Soil moisture


Nitrogen & Moisture :  (For Now)

Next soil nitrogen state:

Variable
Meaning
Nt
Initial soil nitrogen stock
Ft
Fertilizer nitrogen added
Bt
Biological nitrogen fixation
Ot
Nitrogen returned through organic amendments and residues
Ut
Nitrogen removed through crop uptake and harvest
Lt
Nitrogen lost through leaching, volatilization and other losses









Next Crop’s Yield:



Yt=Y,cNtNt+KN,cfWfC

Y,c = Potential yield of crop c.
KN,c = Crop-specific nitrogen response parameter.
fW = Water-stress factor.
fC = Other climate and management factors.

Profit Calculation:






Soil Optimization Function:


First term rewards improvement in nitrogen stock.
Second term rewards improvement in organic carbon.
Third term penalizes nitrogen falling below a critical threshold.
,, control the relative importance.

(Intitally =0, until we find real organic carbon data)


( The units Needed to be used as needed )


Possible Modifications:

Primary nitrogen value needed
Engine rule: no sequence can add 2 exhaustive crops sequentially






## Behaviour

-You are not allowed to run any llm calls by your own.
- You should not build everything in one go what has been asked for. Break it down into pieces first. Build little, test it,come to me. I observe and then you proceed.
-You should never assume anything.If you are confused. Do ask.
-Is somethig has been asked for if you dont find a way to do this you should not assume rather represent in structured way 1)what is missing 2) what this mean for us 3) your propese solutions 4)trade-offs
-when you are in plan mode-You dont dump every plan in one response. Bring it chunk by chunk.You dont decide everything of your own, show me options.explain trade offs and i will decide.
-talk precisely and in short unless asked to elaborate.
5)Use simple easy to understand wordings, be precise unless told otherwise.
6) don overcomplicate things. keep thing simple. do what it asked only unless you thing there is something important to add. then bring it on and explain easily.
7) in each file at the top write sequentially on what this file does.


## codebase summary

*** Do not waste token by reading all the files. Strictly follow this snippet ***
Agent Context: cropseq codebase
0. What this project is
cropseq is a backend-only Python system that recommends a crop rotation for a farm. It is a pipeline of 9 stages (s0..s8): s0 is the chat intake, s1..s8 the pipeline. S1, S2, S3, S4, S5, S6, S7 and S8 are real; S6 uses clearly flagged mock crop economics. There is a separate frontend repo. CORS, an optional API key and deployment docs exist (see FRONTEND_SPEC.md).
Working directory: D:\Josh\Nasa app. Package manager: uv. Python >=3.14. Layout: src/cropseq.
Commands (run from project root, PowerShell):
uv sync                        # install deps + lock
uv run pytest -q --ignore=tests/live   # offline tests (use this for checks)
uv run pytest tests/live -s -q # live API tests, prints shapes
uv run ruff check .            # lint
uv run ruff format .           # format
uv run python tests/stage_range.py s3 s6   # run a stage range
uv run uvicorn cropseq.api.main:app        # start API
1. Hard rules (from AGENTS.md)
1. Each stage exposes exactly one public function: run(input) -> output in stages/sN_name/service.py.
2. A stage may import only from cropseq.contracts and its own folder. Never from another stage. tests/stages/test_rule2_imports.py enforces this.
3. Only pipeline.py wires stages together.
4. contracts/ holds all shared Pydantic v2 models.
5. API layer is thin: routes call pipeline.run only.
6. Every stage has a fixture JSON in data/data_shape/.
7. At the top of every file, write a sequential explanation of what that file does (numbered steps).
8. Keep code simple and small. Answers short and precise.
9. Never run LLM calls yourself.
2. Folder layout (actual, not planned)
AGENTS.md                     # project instructions, edit this when decisions change
resources.md                  # what each external source gives us (Open-Meteo documented)
pyproject.toml                # deps, ruff config
.env.example                  # env var names
data/
  cache.sqlite                # S2 response cache
  data_shape/                 # ALL fixtures: s1_input.json, s1_output.json, s2_output.json ... s8_output.json
src/cropseq/
  __init__.py
  config.py                   # pydantic-settings Config, global `config` instance
  errors.py                   # CropseqError hierarchy with http_status
  http.py                     # shared HttpClient used by stage adapters
  pipeline.py                 # run(profile) -> FinalResponse
  contracts/                  # common, farmer, environment, crops, sequences, evaluation, explanation
  stages/
    s1_intake/service.py
    s2_environment/{__init__,ports,service,adapters/{http,soilgrids,open_meteo},cache/{sqlite}}
    s3_normalization/{service, ports, adapters/fao}.py
    s4_filtering/{service,fixture.py,ports.py,adapters/fake.py}
    s5_sequences/service.py
    s6_optimization/service.py
    s7_explanation/{service,fixture.py,ports.py,adapters/fake.py}
    s8_audit/service.py
  api/{main.py, routes.py}
tests/
  conftest.py
  test_config.py
  contracts/test_fixtures.py
  stages/{test_rule2_imports, test_s2_adapters, test_s2_cache, test_s2_service}
  e2e/test_pipeline.py
  live/test_external_apis.py   # calls real APIs, prints shapes
  stage_range.py               # run_range(start, end) + CLI
No cli.py exists yet. There is no deps.py. No data/crops/crops.json — S4 loads crops from its own fixture.
3. Contracts (shared Pydantic models)
Import style: from cropseq.contracts import FarmerProfile, Environment, ...
contracts/common.py:
- Season(name: str, start_month: int 1-12, end_month: int 1-12) — data, never hardcode months.
- StageOutput(BaseModel) — base for all stage outputs: warnings: list[str] = [], source: str = "".
- EvidenceReference(source_id: str, title: str, url: str|None, claim: str = "").
contracts/farmer.py:
- Location(latitude: float -90..90, longitude: float -180..180).
- FarmerProfile(farm_id: str, location: Location, area_ha: float >0, budget_usd: float >=0, irrigation_quota_m3: float >=0, priorities: dict[str,float] = {}, soil_overrides: dict[str,float] = {}, attributes: dict[str,float|str] = {}).
- priorities keys must match config.objectives.
contracts/environment.py:
- RawEnvironment(StageOutput): soil_raw: dict, weather_raw: dict[str, dict] keyed by provider ("open_meteo", "nasa_power"), fetched_at: str — untouched API payloads.
- SoilProfile(ph: float, organic_carbon_g_kg: float|None, texture: str|None, is_field_tested: bool, attributes: dict).
- SeasonClimate(season: str, mean_temp_c: float, precipitation_mm: float, et0_mm: float, attributes: dict).
- Environment(StageOutput): soil: SoilProfile, seasons: list[SeasonClimate].
contracts/crops.py:
- Crop(crop_id: str, name: str, family: str, attributes: dict[str, float|str|list[int]]) — only those 3 fields fixed; everything else lives in attributes.
- FeasibleCrops(StageOutput): by_season: dict[str, list[Crop]] keyed by Season.name.
contracts/sequences.py:
- CandidateSequence(sequence_id: str, crop_ids: list[str]) — one crop per season, length = config.horizon.
- SequencePool(StageOutput): sequences: list[CandidateSequence].
contracts/evaluation.py:
- EvaluatedSequence(sequence_id: str, crop_ids: list[str], metrics: dict[str,float], is_pareto_optimal: bool, notes: dict[str,str]).
- metrics keys must equal config.objectives (pipeline checks this; Pydantic can't).
- EvaluatedSequences(StageOutput): sequences: list[EvaluatedSequence].
contracts/explanation.py:
- Explanation(StageOutput): summary: str, sections: dict[str,str], evidence: list[EvidenceReference], generated_by: str ("template" or "llm").
- FinalResponse(StageOutput): farmer: FarmerProfile, environment: Environment, evaluated: EvaluatedSequences, explanation: Explanation — the API's response body.
4. config.py
Config(BaseSettings) with env-file support. Global instance config.
Fields:
- horizon: int = 3
- seasons: list[Season] (3 default seasons: 1–4, 5–8, 9–12)
- objectives: list[str] = ["gross_margin", "water_m3", "soil_score"]
- adapter_soil = "soilgrids" (alias ADAPTER_SOIL)
- adapter_weather = "openmeteo,nasa_power" (alias ADAPTER_WEATHER, comma-separated; both fetched by default)
- adapter_crops = "fake", adapter_explainer = "fake"
- adapters: dict[str, str] — filled by _sync_adapters as {"soil": ..., "weather": ..., "crops": ..., "explainer": ...}
- llm_enabled: bool = False, llm_model: str = "gpt-4o-mini"
- cache_db: str = "data/cache.sqlite"
There is no ENV_PROVIDER and no fake adapter for soil/weather anymore.
5. errors.py
CropseqError(Exception)      http_status = 500, .message
├─ InvalidInput              422
├─ UpstreamUnavailable       504
└─ NoFeasibleSequences       400
6. The 8 stages
Each has run(); when an input is None it loads its default fixture, so stages run standalone. When the pipeline calls them, real inputs are passed.
stage	signature	behavior today
s1_intake	run(profile: FarmerProfile | None) -> FarmerProfile	validates request. Default input s1_input.json; returns s1_output.json (ignores passed profile — stub).
s2_environment	run(location: Location | None) -> RawEnvironment	real. Calls SoilGrids + Open-Meteo with cache. Default location from s1_output.json.
s3_normalization	run(profile: FarmerProfile | None, raw: RawEnvironment | None) -> Environment	default inputs s1_output.json + s2_output.json; returns s3_output.json. TODO: convert SoilGrids pH×10 etc. using profile.soil_overrides.
s4_filtering	run(environment: Environment | None) -> FeasibleCrops	default input s3_output.json. Uses FakeCropCatalog (from its own fixture), filters by attributes["suitable_seasons"], attaches warnings/source from fixture.
s5_sequences	run(feasible: FeasibleCrops | None) -> SequencePool	default input s4_output.json; returns s5_output.json.
s6_optimization	run(pool: SequencePool | None, environment: Environment | None, profile: FarmerProfile | None) -> EvaluatedSequences	defaults s5_output + s3_output + s1_output; returns s6_output.json.
s7_explanation	run(evaluated: EvaluatedSequences | None) -> Explanation	default input s6_output.json; delegates to the configured explainer (fake → returns s7_output.json).
s8_audit	run(explanation: Explanation | None, evaluated: EvaluatedSequences | None) -> FinalResponse	defaults s7_output + s6_output; returns s8_output.json.
s2 in detail (the only real one)
service.py:
- run(location) → builds service → _run_coroutine(service.fetch(...)) → RawEnvironment.
- build_environment_service(soil_name=None, weather_name=None, cache_path=None) -> EnvironmentService — reads config.adapters, instantiates adapters + SQLiteCache. `weather_name` may be a comma-separated list.
- _build_soil_provider(name) — only "soilgrids"; anything else raises NotImplementedError.
- _build_weather_providers(names) — accepts "openmeteo"/"open_meteo" and "nasa_power". Weather failure raises UpstreamUnavailable("Sorry, try again...").

NASA POWER adapter: adapters/nasa_power.py — NasaPowerAdapter, name = "nasa_power", BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point", community AG, 18 parameters, dates as YYYYMMDD, returns raw JSON.
- _get_planning_date_range(reference_year=2025) -> tuple[date, date] — derives 2025-01-01 .. 2025-12-31 from config.seasons, handles year-wrapping seasons.
- _run_coroutine[T](coro) — runs async from sync code (thread fallback if a loop is running).
- EnvironmentService(soil_provider, weather_providers, cache):
- async fetch(latitude, longitude, start_date, end_date) -> RawEnvironment
- Steps: build cache keys → cache lookup → parallel fetch of missing ones (asyncio.gather(return_exceptions=True)) → raise on exception (no fallback) → cache.set new payloads → return RawEnvironment with source="soil:... (api|cache), weather:...".
ports.py (Protocols): SoilDataPort(name property, async fetch(lat, lon) -> dict), WeatherDataPort(name, async fetch(lat, lon, start_date, end_date) -> dict), CachePort(get, set). Aliases SoilProvider/WeatherProvider exist.
adapters/http.py — HttpClient(timeout=15.0, max_attempts=3), async get_json(url, params, headers) -> dict. Retries only timeouts/network errors/429/5xx with exponential backoff.
adapters/soilgrids.py — SoilGridsAdapter(http_client=None), name = "soilgrids", BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query", PROPERTIES = (phh2o, clay, sand, silt, soc, nitrogen), DEPTHS = 6 ranges. fetch returns raw GeoJSON with properties.layers[i].depths[j].values.mean and unit_measure.d_factor (pH comes back ×10). No unit conversion here.
adapters/open_meteo.py — OpenMeteoAdapter, name = "open_meteo", BASE_URL = "https://archive-api.open-meteo.com/v1/archive", daily variables = temperature_2m_mean, precipitation_sum, et0_fao_evapotranspiration. Params include timezone=auto, temperature_unit=celsius, precipitation_unit=mm.
cache/sqlite.py — make_cache_key(provider, request) -> sha256 hex; SQLiteCache(database_path) with get(key) -> dict|None, set(key, provider, request, response), close(); table environment_cache.
7. pipeline.py
- run(profile: FarmerProfile) -> FinalResponse — calls s1→s8 in order, passing each output forward (s2.run(farmer.location), s6.run(pool, environment, profile)...).
- _check_metric_keys(evaluated) — asserts each sequence's metrics keys equal set(config.objectives), else raises CropseqError.
8. API layer
api/main.py:
- create_app() -> FastAPI — title "cropseq", includes router, registers a CropseqError handler returning JSONResponse(status_code=exc.http_status, content={"detail": exc.message}).
- module-level app = create_app(). Run: uv run uvicorn cropseq.api.main:app.
api/routes.py:
- router = APIRouter()
- GET /health → {"status": "ok"}
- POST /api/v1/recommendations/optimize — body FarmerProfile, response_model=FinalResponse, calls pipeline.run(profile). FastAPI validates the body automatically (422 on bad body).
No debug stage endpoint. /docs works by default.
9. Fixtures (data/data_shape/)
README.md documents the chain: sN_output.json is produced by stage N and is the input of the next stage. Files: s1_input.json, s1_output.json (FarmerProfile, farm-001, lat 23.8103 lon 90.4125, 12.5 ha, $8000 budget, 45000 m³ water, priorities {gross_margin 0.5, water_m3 0.3, soil_score 0.2}, soil_overrides {ph 6.4}), s2_output.json (RawEnvironment with full SoilGrids GeoJSON + Open-Meteo daily), s3..s8_output.json.
Fixtures are hand-maintained, never written by code. They are validated by tests/contracts/test_fixtures.py against the output contract. If you add a required field to a contract, that fixture must be edited by hand.
10. Tests
- conftest.py — autouse fixture points config.cache_db to a temp file. (No fake adapters are set anymore.)
- test_config.py — defaults + env override.
- contracts/test_fixtures.py — every sN_output.json validates against its model.
- stages/test_rule2_imports.py — AST check that no stage imports another stage.
- stages/test_s2_adapters.py — SoilGrids/Open-Meteo adapter query structure with AsyncMock(spec=HttpClient); HttpClient retry test with httpx mocked.
- stages/test_s2_service.py — cache hit/miss with AsyncMock providers; _get_planning_date_range (both standard and wrapping seasons); test_s2_run_entrypoint runs the real S2 entrypoint (needs network).
- e2e/test_pipeline.py — full pipeline.run end-to-end (needs network).
- live/test_external_apis.py — test_soilgrids_raw() and test_open_meteo_raw(); print payload shape; no skip gate, so they always run with pytest. Currently SoilGrids returns 503 (ISRIC outage) → this test fails.
- stage_range.py — run_range(start: str, end: str) -> dict[str, Any] runs stages in order from start to end, carrying outputs in a dict, missing inputs fall back to fixtures, prints name -> Type. CLI: uv run python tests/stage_range.py s3 s6. pipeline.py is not touched by this.
Use --ignore=tests/live when you want a fully offline test run.
11. External sources (resources.md)
resources.md exists in the root. It documents sources in numbered form: 1) request we send, 2) response we get, 3) what it gives us. Open-Meteo is documented. SoilGrids is not yet (API was down).
Open-Meteo gives exactly 3 daily series: temperature_2m_mean (°C), precipitation_sum (mm), et0_fao_evapotranspiration (mm, FAO-56 reference ET). The API supports more (humidity, wind, radiation, soil moisture/temperature) if we add variables to DAILY_VARIABLES.
SoilGrids returns raw GeoJSON; pH comes back ×10 (d_factor: 10), SOC ×10, nitrogen ×100. Conversion belongs to S3.
12. Known gaps / current state
- S0 chat intake exists (`/api/v1/intake/message`); rules adapter by default, LLM opt-in.
- S1 echoes the real profile; S5 generates sequences from S4 pools; S8 assembles the real response. No fixture returns remain in those stages.
- S6 uses mock crop economics from `data/crops/crop_params.json` (flagged in every response). Replace before real advice.
- S7 defaults to the LLM explainer and falls back to the template on any failure.
- S4 uses the real BARC database. S7 no longer has a fake adapter.
- S3 has a FAO Crop Calendar adapter but `run()` does not call it yet.
- `cropseq/http.py` is shared by S2 and S3.
- Upstream httpx failures now return 504 through `api/main.py`.
- API has CORS (`CORS_ORIGINS`) and an optional `API_KEY` (`X-API-Key`).
- Deployment: `Dockerfile` + `.dockerignore`; see FRONTEND_SPEC.md section 9.
- cli.py and data/crops/crops.json still do not exist.
13. How to work here
1. Read the target file and the contracts it uses.
2. Keep run() as the only public function of a stage.
3. Respect rule 2 (no cross-stage imports).
4. Write a numbered "what this file does" docstring at the top of every file you touch.
5. Keep it simple; prefer small diffs.
6. Verify: uv run ruff check . + uv run ruff format . + uv run pytest -q --ignore=tests/live.
7. Ask instead of assuming when something is ambiguous.




