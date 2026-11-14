# FieldShift Frontend

Farmer-facing UI for the cropseq crop rotation advisor. Built for the NASA Space Apps Challenge.

## Quick Start

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Configuration

Copy `.env.example` to `.env.local`:

```
VITE_MOCK_API=true           # true = use mock data (default, works offline)
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Switch to the real backend by setting `VITE_MOCK_API=false` once CORS is enabled on the backend.

## Screens

| Screen | Description |
|--------|-------------|
| Chat Intake | 7-step guided questionnaire → builds FarmerProfile |
| Review | Shows exactly what will be POSTed, with Edit button |
| Loading | Animated pipeline steps, real feedback |
| Result | Best rotation, all options, explanation, sources, warnings |
| Q&A | Disabled until `POST /api/v1/recommendations/ask` ships |

## Project Structure

```
src/
  components/
    ChatIntake.tsx    # 7-step wizard
    ReviewScreen.tsx  # Pre-submit review card
    LoadingScreen.tsx # Pipeline animation
    ResultScreen.tsx  # Full results display
    Header.tsx        # Nav + backend status badge
  types/
    api.ts            # FarmerProfile + FinalResponse TypeScript types
  utils/
    api.ts            # fetchRecommendations(), checkHealth(), ApiError
    helpers.ts        # deriveBestSequence(), collectWarnings(), formatters
    cropNames.ts      # crop_id → display name map
  mock/
    mockData.ts       # s8_output.json as TypeScript
  config.ts           # MOCK_API, API_BASE_URL from env
  App.tsx             # Screen router
  index.css           # Global styles (earthy, farmer-first palette)
```

## Error Handling

| Status | UI |
|--------|----|
| 422 (FastAPI validation) | Shows field-level messages |
| 422 (our validation) | Shows detail string |
| 400 (no feasible rotation) | Shows backend message |
| 504 (upstream outage) | "Service temporarily unavailable, retry in a minute" + Retry button |
| 500 / unknown | Generic error + Retry + Start Over |

## Checklist ✅

- [x] Full intake chat works offline (mock mode)
- [x] Summary card shows exactly what will be POSTed
- [x] Mock mode renders s8_output.json correctly
- [x] 400 / 422 / 504 / 500 all render friendly messages
- [x] Winner derived by weighted score (not hardcoded), Pareto shortlist separated
- [x] All warnings rendered in a yellow banner
- [x] Q&A box present but disabled with tooltip
- [x] Zero TypeScript errors
- [x] Unknown response fields preserved, never crashed on
