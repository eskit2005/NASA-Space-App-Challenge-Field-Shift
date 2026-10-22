# Fixtures — `data/data_shape/`

One output JSON per stage (s1..s8) plus the single pipeline input.
Every file is validated against its contract in `src/cropseq/contracts/` by
`tests/contracts/test_fixtures.py`.

| File | Validates as (contract) | Stage | Stage input comes from |
| --- | --- | --- | --- |
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

- Shared keys are pinned to `src/cropseq/config.py`:
  - `priorities` (s1) and `metrics` (s6) use exactly `config.objectives`.
  - Season names (`season_1..season_3`) in s3/s4 use exactly `config.seasons`.
- There is **no** `data/crops/crops.json`; the 3 placeholder crops
  (wheat, rice, mung bean) live inside `s4_output.json`. The crops adapter is
  `"web" | "fake"` (default `"web"`).
- `s2_output.json` keeps payloads raw on purpose (SoilGrids pH still x10);
  conversion is S3's job.
- `s8_output.json` embeds the farmer / environment / evaluated / explanation
  copied verbatim from `s1_output.json`, `s3_output.json`, `s6_output.json`,
  `s7_output.json`.
