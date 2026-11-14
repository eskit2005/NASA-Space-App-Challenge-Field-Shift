# Fixtures — `data/data_shape/`

One output JSON per stage (s1..s8) plus the single pipeline input.
Every file is validated against its contract in `src/cropseq/contracts/` by
`tests/contracts/test_fixtures.py`.

| File | Validates as (contract) | Stage | Stage input comes from |
| --- | --- | --- | --- |
| `s0_input.json` | `IntakeTurn` | — (chat request) | Frontend chat messages + draft |
| `s0_output.json` | `IntakeReply` | `s0_intake` | `s0_input.json` |
| `s1_input.json` | `FarmerProfile` | — (pipeline input) | API / CLI request |
| `s1_output.json` | `FarmerProfile` | `s1_intake` | `s1_input.json` |
| `s2_output.json` | `RawEnvironment` | `s2_environment` | `s1_output.json` |
| `s3_output.json` | `Environment` | `s3_normalization` | `s1_output.json` + `s2_output.json` |
| `s4_output.json` | `FeasibleCrops` | `s4_filtering` | `s3_output.json` (crop catalog via adapter) |
| `s5_output.json` | `SequencePool` | `s5_sequences` | `s4_output.json` |
| `s6_output.json` | `EvaluatedSequences` | `s6_optimization` | `s5_output.json` + `s3_output.json` + `s1_output.json` |
| `s7_output.json` | `Explanation` | `s7_explanation` | `s6_output.json` |
| `s8_output.json` | `FinalResponse` | `s8_audit` | `s7_output.json` + `s6_output.json` |

## Notes

- S0 is the chat layer before S1. `s0_output.json` has `is_complete: true`
  and a `profile` object; that `profile` is the exact body for
  `POST /api/v1/recommendations/optimize`. S0 is not part of
  `pipeline.run(profile)`.
- Shared keys are pinned to `src/cropseq/config.py`:
  - `priorities` (s1) and `metrics` (s6) use exactly `config.objectives`.
  - Season names (`Rabi`, `Kharif-1`, `Kharif-2`) in s3/s4 use exactly `config.seasons`.
- There is **no** `data/crops/crops.json`; the 3 placeholder crops
  (wheat, rice, mung bean) live inside `s4_output.json`. The crops adapter is
  `"fake"` by default.
- `s2_output.json` keeps payloads raw on purpose (SoilGrids pH still x10);
  conversion is S3's job.
- `s3_output.json` also carries `location` and `land_type_check`. S3 never
  replaces the farmer's `land_type`; it only compares it with the estimate.
- `s8_output.json` embeds the farmer / environment / evaluated / explanation
  copied verbatim from `s1_output.json`, `s3_output.json`, `s6_output.json`,
  `s7_output.json`.

## Unified Pipeline Context — `data/pipeline_context.json`

Whatever gets produced in every stage across the entire pipeline is automatically consolidated and persisted into one single file: `data/pipeline_context.json` (configured via `PIPELINE_CONTEXT_FILE` in `config.py`).

### File Structure:
- `updated_at`: ISO 8601 timestamp of the run.
- `stages`: Raw payloads from every stage:
  - `s1_farmer`: `FarmerProfile`
  - `s2_raw_environment`: `RawEnvironment`
  - `s3_environment`: `Environment` (SoilGrids, Open-Meteo, land type check)
  - `s4_feasible_crops`: `FeasibleCrops` (crop list per season)
  - `s5_sequence_pool`: `SequencePool` (candidate sequences)
  - `s6_mathematical_solution`: `EvaluatedSequences` (Pareto frontier, scores, metrics)
  - `s7_explanation`: `Explanation` (agronomic rationale, sections, evidence)
  - `s8_final_result`: `FinalResponse` (audited recommendation)
- `summary`: Structured convenience view for Stage 0 agent grounding:
  - `mathematical_solution`: evaluated sequences count, Pareto-optimal count & list
  - `crop_list`: feasible crops by season with botanical family
  - `sequence_pool`: candidate sequence pool
  - `best_rotation`: recommended sequence with gross margin, water m³, and soil score
  - `soil_and_climate`: topsoil pH, texture, organic carbon, seasonal weather
  - `explanation`: summary text, section deep-dives, citations

This file is loaded by Stage 0 (`s0_intake`) to answer farmer questions in real time.
