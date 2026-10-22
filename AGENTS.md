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
│   │   ├── s2_environment/  # ports.py (SoilProvider, WeatherProvider), adapters/{fake.py, soilgrids.py, openmeteo.py}, service.py
│   │   ├── s3_normalization/
│   │   ├── s4_filtering/
│   │   ├── s5_sequences/
│   │   ├── s6_optimization/
│   │   ├── s7_explanation/  # ports.py (Explainer), adapters/{template.py, llm.py}, service.py
│   │   └── s8_audit/
│   ├── pipeline.py   # run(profile) -> RecommendationResponse; wires s1..s8
│   ├── config.py     # pydantic-settings; selects adapters (e.g. ENV_PROVIDER=fake|real, EXPLAINER=template|llm)
│   ├── api/{main.py, routes.py, deps.py}
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
s5: FeasibleCrops -> SequencePool (3-season sequences)
s6: (SequencePool, EnvironmentalObservation, FarmerProfile) -> EvaluationResult (evaluated sequences + Pareto flags)
s7: EvaluationResult -> Explanation
s8: (Explanation, EvaluationResult) -> RecommendationResponse
Base the models on typical fields: FarmerProfile (farm_id, lat, lon, area_hectares, budget_usd, irrigation_quota_m3, priorities, optional soil_overrides), SoilProfile (ph, clay/sand/silt fractions, organic_carbon_g_kg, total_nitrogen_g_kg, is_field_tested), Crop (crop_id, common_name, botanical_family, suitable_seasons, ph tolerance range, growth_days, kc coefficients, baseline yield/price/cost, nitrogen_balance, root_depth_class), EvaluatedSequence (sequence_id, crops, gross_margin_usd, irrigation_demand_m3, soil_health_score, is_pareto_optimal). Use sensible validation (ge/le bounds). Keep models small; they will evolve.

## Stubs
Each stage's `run` returns data loaded from its fixture, validated by the output contract. Real adapters (soilgrids.py, openmeteo.py, llm.py) may be minimal classes implementing the port with `raise NotImplementedError` plus a TODO comment. fake.py and template.py adapters must work and be the defaults.

## API
FastAPI app with:
- GET /health
- POST /api/v1/recommendations/optimize (FarmerProfile -> RecommendationResponse)
- POST /api/v1/stages/{stage_name}/run (debug: raw JSON in, stage output out)
Routes call pipeline/stage functions only.

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
data shape


## Behaviour

-You are not allowed to run any llm calls by your own.
- You should not build everything in one go what has been asked for. Break it down into pieces first. Build little, test it,come to me. I observe and then you proceed.
-You should never assume anything.If you are confused. Do ask.
-Is somethig has been asked for if you dont find a way to do this you should not assume rather represent in structured way 1)what is missing 2) what this mean for us 3) your propese solutions 4)trade-offs
-when you are in plan mode-You dont dump every plan in one response. Bring it chunk by chunk.You dont decide everything of your own, show me options.explain trade offs and i will decide.
-talk precisely and in short unless asked to elaborate.



