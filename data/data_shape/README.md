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
