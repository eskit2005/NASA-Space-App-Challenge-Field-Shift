# cropseq — Frontend ↔ Backend Spec

What this file does:

1. Explains how the farmer actually uses the system (the flow).
2. Lists the API contract that already exists today.
3. Says exactly what the **frontend** must build (your friend's job).
4. Says exactly what the **backend** must add (my job).
5. Lists the future modules and how they plug in.
6. Defines the handshake rules so we never break each other.

Read section 1 and 2 first. Then each side reads only its own section.

---

## 1. The big picture

The farmer never types JSON. He talks. The frontend is a guided chat + result screen.

```
Farmer
  │  answers predefined questions (chat UI)
  ▼
FRONTEND
  │  builds a FarmerProfile JSON
  ▼
BACKEND  POST /api/v1/recommendations/optimize
  │  runs pipeline s1..s8 (~seconds)
  ▼
FRONTEND
  │  renders: best rotation, scores, explanation, evidence, warnings
  ▼
Farmer asks a follow-up question
  │
  ▼
BACKEND  Q&A endpoint  →  answer grounded in that recommendation
```

The same flow repeats every season.

### Flows we are building

| # | Flow | Status |
|---|------|--------|
| 1 | Guided intake chat + Q&A → `FarmerProfile` | **endpoint exists** (`/api/v1/intake/message`); now answers questions grounded in pipeline context |
| 2 | Submit profile → recommendations | **API exists** (`/api/v1/recommendations/optimize`) |
| 3 | Show result + explanation | frontend only, API exists |
| 4 | Follow-up Q&A about the result | **supported via Stage 0** (`/api/v1/intake/message` reads `data/pipeline_context.json`) |
| 5 | "Is this sequence good? Why?" (future module) | backend endpoint *not built yet* |

Flows 1–4 are fully functional on the backend. Flow 5 is a future module.

---

## 2. API that exists today

Base URL, local dev: `http://127.0.0.1:8000`

### 2.1 Health

```
GET /health  →  200 {"status": "ok"}
```

Use it for a "backend online" badge. Nothing else.

### 2.2 Intake chat (optional; replaces the scripted questions)

```
POST /api/v1/intake/message
Content-Type: application/json
Body: { "messages": [{ "role": "farmer"|"assistant", "content": "..." }],
        "draft": { ...partial profile... }, "farm_id": "farm-001" }
→ 200 { "reply": "...", "draft": {...}, "missing_fields": [...],
        "is_complete": false, "profile": null, "warnings": [] }
```

The server asks the next question and returns the updated draft. The frontend
resends the whole conversation and draft every turn (stateless).

When `is_complete` is `true`, `profile` holds the finished `FarmerProfile`.
Post that exact object to `/api/v1/recommendations/optimize`.

### 2.3 Create recommendations

```
POST /api/v1/recommendations/optimize
Content-Type: application/json
Body: FarmerProfile
→ 200 FinalResponse
```

If the backend sets `API_KEY`, both POST routes require `X-API-Key: <value>`.
Ask the backend owner whether the deployed API has a key. Never put the key in
client-side source that ships to the public unless the owner accepts that.

Interactive docs (auto-generated, always correct):
`http://127.0.0.1:8000/docs`
Raw schema: `http://127.0.0.1:8000/openapi.json`

If the JSON shape is ever unclear, `/openapi.json` is the source of truth. This file is a human summary of it.

### 2.4 Request body — `FarmerProfile`

| Field | Type | Required | Rules |
|---|---|---|---|
| `farm_id` | string | yes | Any id the frontend generates, e.g. `farm-001` |
| `location.latitude` | number | yes | −90 … 90 |
| `location.longitude` | number | yes | −180 … 180 |
| `area_ha` | number | yes | > 0 (hectares) |
| `budget_usd` | number | yes | ≥ 0 |
| `irrigation_quota_m3` | number | yes | ≥ 0 (cubic metres per season) |
| `priorities` | object string→number | no | Keys must be `gross_margin`, `water_m3`, `soil_score`. Use the numbers as weights |
| `soil_overrides` | object string→number | no | Only if he had a lab test, e.g. `{"ph": 6.4}` |
| `attributes` | object string→(number or string) | no | Free extras, e.g. `{"district": "dhaka"}` |

Rules the frontend must enforce before sending (so the farmer gets a friendly message, not a 422):

- All numbers are numbers, not strings. `12.5` not `"12.5"`.
- No empty required field.
- `priorities` should be normalised to sum to 1.0. If you send `{0.5, 0.3, 0.2}` it works as-is; if the farmer only cares about two things, scale those two up.
- Send `soil_overrides` only when the farmer confirms he has a lab result.

Example request:

```json
{
  "farm_id": "farm-001",
  "location": { "latitude": 23.8103, "longitude": 90.4125 },
  "area_ha": 12.5,
  "budget_usd": 8000,
  "irrigation_quota_m3": 45000,
  "priorities": { "gross_margin": 0.5, "water_m3": 0.3, "soil_score": 0.2 },
  "soil_overrides": { "ph": 6.4 },
  "attributes": { "district": "dhaka", "irrigation_method": "tube_well" }
}
```

### 2.5 Response — `FinalResponse`

Full realistic example (this exact file is in the repo, use it as mock data):
`data/data_shape/s8_output.json`

Top-level shape:

| Field | What it is | Frontend use |
|---|---|---|
| `farmer` | the profile you sent, echoed and validated | header / summary card |
| `environment.soil` | `ph`, `organic_carbon_g_kg`, `texture`, `is_field_tested`, `attributes` | soil chip / detail panel |
| `environment.seasons[]` | per-season `mean_temp_c`, `precipitation_mm`, `et0_mm` | climate strip |
| `recommended_sequence_id` | the backend's pick (may be `null`) | headline / default card |
| `evaluated.sequences[]` | the candidates | main result list |
| `explanation.summary` | 1 paragraph | top of result |
| `explanation.sections` | named paragraphs, e.g. `water`, `soil`, `rotation_risk` | accordion |
| `explanation.evidence[]` | `source_id`, `title`, `url`, `claim` | "why?" links |
| `explanation.generated_by` | `"template"` or `"llm"` | show a small label |
| `warnings` (on every block) | list of strings | yellow banner, never a crash |
| `source` (on every block) | provenance string | tooltip |

`evaluated.sequences[]` item:

| Field | Type | Notes |
|---|---|---|
| `sequence_id` | string | e.g. `seq-001` |
| `crop_ids` | string[] | one crop per season, in season order (currently 3) |
| `metrics` | object string→number | keys are exactly `gross_margin`, `water_m3`, `soil_score` |
| `is_pareto_optimal` | bool | **the shortlist flag** — see warning below |
| `notes` | object string→string | e.g. `{"label": "low water"}` |

> **Winner:** use `recommended_sequence_id` when it is present. Fall back to
> `is_pareto_optimal` / `notes.score` when it is `null`. Do **not** hardcode
> `seq-001`.

### 2.6 Errors

Two different shapes exist. Handle both.

| Case | Status | Body |
|---|---|---|
| Missing or wrong `X-API-Key` (only when configured) | 401 | `{"detail": "Invalid or missing API key."}` |
| Bad input caught by FastAPI | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| Our own input error | 422 | `{"detail": "message string"}` |
| No feasible rotation | 400 | `{"detail": "message string"}` |
| Upstream API failed (SoilGrids / weather / LLM) | 504 | `{"detail": "message string"}` |
| Anything unexpected | 500 | `{"detail": "..."}` (sometimes not JSON — have a fallback) |

Rules for the UI:

- `detail` is a string **or** an array. Check the type.
- 401 → "This app is not authorised. Check the API key." Do not retry.
- 504 → "Weather/soil data service is unavailable, please retry in a minute." Not the farmer's fault.
- 400 → show the message; usually a constraint is impossible.
- Never show a raw stack trace. Log it to console only.
- Retry button on 504/500. No auto-retry loop.

### 2.7 CORS — **done**

The backend now sends CORS headers for every origin listed in `CORS_ORIGINS`
(comma-separated). Dev defaults are `http://localhost:3000` and
`http://127.0.0.1:3000`. The production frontend URL must be added on the
backend before you point the deployed site at the deployed API.

---

## 3. FRONTEND — what he must build

### 3.1 Stack

Any framework. Static HTML + fetch is enough. No server-side rendering needed. Default assumption: React or plain Vite, running on `http://localhost:3000`.

### 3.2 Screens

1. **Chat intake** — the guided questions. One question per step.
2. **Review** — show the collected answers as a readable card, with "Edit" on each line.
3. **Loading** — a real loading state; the pipeline takes seconds, not milliseconds. Show progress words ("fetching soil…", "scoring rotations…") but do not fake percentages.
4. **Result** — recommendation, scores, explanation, evidence, warnings.
5. **Follow-up Q&A** — chat box attached to the result (feature-flagged until the endpoint exists).

### 3.3 Intake Modes (Guided Form Wizard + S0 Conversational AI Chat)

The frontend provides two intake modes:
1. **Guided Form Wizard** (7 steps): Location, Farm Size & Land Type, Budget, Water Quota, Priorities, Lab Soil Test, Additional Details (Irrigation Method).
2. **Conversational AI Chat** (Stage 0): Natural conversational intake powered by `/api/v1/intake/message`.
   - **Core required fields**: Location, Farm Size, Budget, Water Quota, Land Type.
   - **Contextual Suggestion Chips**: Exactly one row of relevant suggestions is presented matching the active question (Location chips, Size chips, Budget chips, Water chips, Land type chips).
   - **Soil pH Handling**: Soil pH is specialized lab data and is **never proactively asked** in conversational chat. Farmers who have a lab test can view and edit their lab test pH on the Review Screen or if they mention it, the backend extracts it into `soil_overrides.ph`.
   - **Optional Irrigation Prompt**: After the 5 core fields are collected, the AI assistant invites the farmer's irrigation method (Tube well, Canal, Pond, Rainfed) as an optional question with quick pills, and permits immediate one-click proceeding with standard defaults.
   - **Review Screen Inline Editing**: Every field (Farm Size, Land Type, Budget, Water Quota, Soil pH, Irrigation Method) can be edited directly inline on the Review Screen without restarting intake.
   - **Responsive Design**: Mobile-first layouts (375px+ viewports), 16px input font prevention for iOS zoom, wrap-safe flex rows, and full-width touch-friendly button stacks.

### 3.4 Result screen — what to show, in what order

1. One-line headline: the best sequence, crops in season order.
2. `explanation.summary`.
3. The shortlist: cards for every `is_pareto_optimal: true` sequence, with `notes.label` as the card title.
4. Metrics per card — label them in farmer language:
   - `gross_margin` → "Expected margin (USD)"
   - `water_m3` → "Water needed (m³)"
   - `soil_score` → "Soil health (0–1)"
5. Collapsed "All options" list including the dominated ones, marked as such.
6. `explanation.sections` as an accordion.
7. `explanation.evidence` as a sources list. `url: null` → plain text, no link.
8. `warnings` (top-level plus nested) as one yellow banner.
9. "Ask a question" box — disabled with a tooltip until flow 4 ships.

Do not display `crop_ids` as raw ids. Display names. Because the crop catalog is not exposed as an endpoint yet, ship a small local map `crop_id → name` (see 6.5) and fall back to the raw id.

### 3.5 Metric display rules

- Never invent units the field name does not have. `soil_score` is 0–1, not a percent.
- `gross_margin` is USD for the whole farm, not per hectare.
- Compare only within one response. There are no historical baselines yet.
- If a `metrics` key is missing, show "—" and do not crash. Keys are configured server-side in `config.objectives` and can change.

### 3.6 State and typing

- One typed model for `FarmerProfile` and one for `FinalResponse`, mirroring section 2 exactly.
- Unknown fields must be preserved and ignored, not dropped. The backend adds fields over time.
- Treat every response field as possibly empty. `{}` and `[]` are legal.

### 3.7 Mock mode (useful while the backend is offline or upstream data is down)

- Ship a `MOCK_API=true` switch.
- Mock returns a copy of `data/data_shape/s8_output.json` after ~2s.
- Everything else — validation, loading, error rendering — must behave identically.
- Switching to the real API should be a base-URL change, nothing else.

### 3.8 Follow-up Q&A (build the UI now, wire it later)

- Attached to the result, not a separate page.
- Suggested chips: "Why this rotation?", "What if I have less water?", "Why not rice every season?".
- Request will send the question **plus the whole result object** (stateless server). Do not send only a conversation id — there is no server session store.
- Render answers as plain text. Citations, if returned, render like `evidence`.

### 3.9 What the frontend must never do

- Call SoilGrids, Open-Meteo, or any LLM directly.
- Store secrets. There are none.
- Compute agronomy (feasibility, water balance, rotation rules). The backend decides; the frontend displays.
- Hardcode the season count, objective names, or crop ids as permanent truths.

---

## 4. Contract changes — how we stay in sync

1. Backend never renames or removes a field in the same API version. New fields are added as optional with defaults.
2. Frontend never breaks on unknown/missing fields.
3. If a change is needed, I bump the version in the path (`/api/v1` → `/api/v2`) or add a field, and tell him. No silent changes.
4. `/openapi.json` is the referee. When in doubt, regenerate types from it.
5. Fixtures in `data/data_shape/` are hand-maintained. `s8_output.json` is the canonical example response.

---

## 5. Known contract gaps (agreed, not yet fixed)

| Gap | Why it matters | Status |
|---|---|---|
| `recommended_sequence_id` | Frontend had to guess the winner | **Done** — optional field, may be `null` |
| Crop ids without names | Result showed `mung_bean` | **Done** — `GET /api/v1/crops` |
| No season labels/months | "season_1" is not farmer language | **Done** — `GET /api/v1/seasons` |
| No objective labels/units | Frontend hardcoded USD / m³ | **Done** — `GET /api/v1/objectives` |
| No request id / no persistence | Cannot reopen an old recommendation | Out of scope for v1; Q&A is stateless |
| Pipeline can 500 on upstream outage | Demo can break mid-presentation | **Fixed** — upstream errors return 504 |
| S6 crop economics are mock values | Scores are not agronomic advice | **Open** — flagged in every response `warnings` |

---

## 6. BACKEND — what I must do

Ordered. Nothing here is done yet unless marked.

### 6.1 CORS — **done**

`CORSMiddleware` is in `src/cropseq/api/main.py`. Origins come from the
`CORS_ORIGINS` env var (comma-separated), methods `GET, POST, OPTIONS`, headers
`Content-Type, X-API-Key`. No credentials are used.

**Acceptance:** `OPTIONS` from an allowed origin returns 200 with
`access-control-allow-origin`; an unknown origin gets no header (tested).

### 6.2 Keep the existing contract stable

`POST /api/v1/recommendations/optimize` stays exactly as it is. No field renames. Additions only, always optional.

### 6.3 Intake endpoint — **done**

```
POST /api/v1/intake/message
Body:  { "messages": [...], "draft": {...}, "farm_id": "farm-001" }
→      { "reply": "...", "draft": {...}, "missing_fields": [...],
         "is_complete": false, "profile": null, "warnings": [] }
```

- Server-side questions, rules extraction by default; LLM extraction is opt-in.
- Stateless: the frontend resends the whole conversation and draft.
- When complete, `reply` is the hold-on message and `profile` is final.
- The scripted version in 3.3 still works; choose one per screen.

### 6.4 Follow-up Q&A capability (flow 4) — **Live via Stage 0**

Follow-up questions are supported directly through `POST /api/v1/intake/message`:

```
POST /api/v1/intake/message
Body:  { "messages": [{"role": "farmer", "content": "Why this rotation?"}], "draft": <FarmerDraft> }
→      IntakeReply with "reply": grounded agronomic and mathematical answer
```

- **Single Pipeline Context Store:** Whatever got produced in every stage across the entire pipeline (`s1_farmer`, `s2_raw_environment`, `s3_environment`, `s4_feasible_crops`, `s5_sequence_pool`, `s6_mathematical_solution`, `s7_explanation`, `s8_final_result`) is automatically saved into one single file: `data/pipeline_context.json`.
- When a farmer asks any question (e.g., *"Why this rotation?"*, *"What if I have less water?"*, *"Why not rice every season?"*, *"Which crop is riskiest?"*, *"What crops can grow here?"*), Stage 0 loads `data/pipeline_context.json` and returns a grounded answer.
- If required fields are still missing from `draft`, it answers the question and appends the next intake question. If the draft is complete, it returns the answer directly with `is_complete: true`.

### 6.5 Reference data endpoints — **done**

```
GET /api/v1/crops            → [{ "crop_id": "1", "name": "Wheat", "family": "Poaceae" }]
GET /api/v1/objectives       → [{ "key": "gross_margin", "label": "Expected margin", "unit": "USD" }]
GET /api/v1/seasons          → [{ "name": "Rabi", "start_month": 11, "end_month": 2 }]
```

- Read-only, public, no API key.
- Crop ids are the BARC database ids as strings; Fallow is `"999"`.
- Lets the frontend stop hardcoding labels, units, and crop names.

### 6.6 Future module: explain a given sequence (flow 5)

```
POST /api/v1/sequences/explain
Body:  { "crop_ids": ["wheat","rice","mung_bean"], "farmer": <FarmerProfile> }
→      { "score": {...}, "verdict": "good"|"mixed"|"poor", "explanation": <Explanation> }
```

- Evaluates a sequence the farmer typed, instead of only the ones we generated.
- Reuses s4/s6 scoring + s7 explainer. New orchestration only.
- Not built. Frontend should not build the screen until this exists.

### 6.7 Operational checklist before handing over

- CORS on, dev origin allowed.
- `API_KEY` set in production; both POST routes return 401 without it.
- Server runs with `uv run uvicorn cropseq.api.main:app --reload --port 8000`.
- `/health` and `/docs` reachable.
- A real successful call captured and saved for the mock.
- Known failure paths confirmed: 400, 401, 422, 504.
- One page of env vars in `.env.example`; no secrets anywhere.
- `recommended_sequence_id` and the three lookup endpoints are live.

---

## 7. Who owns what

| Area | Owner |
|---|---|
| Screen flow, chat script, validation messages | Frontend |
| JSON types, mock data, error copy for HTTP codes | Frontend |
| CORS, endpoint shapes, pipeline behaviour, error codes | Backend |
| Field names and semantics in `FinalResponse` | Backend (shared contract) |
| Adding a field → telling the other side | Backend |
| Building against `/openapi.json` | Frontend |

---

## 8. Checklist before the first joint demo

Frontend:

- [ ] Full intake chat works offline
- [ ] Summary card shows exactly what will be POSTed
- [ ] Mock mode renders `s8_output.json` correctly
- [ ] 400 / 422 / 504 / 500 all render friendly messages
- [ ] Winner derived, not hardcoded; dominated options visibly separated
- [ ] `warnings` rendered somewhere visible
- [ ] Q&A box present but disabled, with a reason

Backend:

- [x] CORS allows the dev origin
- [x] `recommendations/optimize` returns 200 on the canonical fixture profile
- [x] `FinalResponse` validated against the contract in a test
- [x] `recommended_sequence_id` added
- [x] Crop / objective / season lookup endpoints live
- [x] Upstream failure returns 504, not 500
- [ ] Follow-up Q&A endpoint stubbed with a documented shape
- [ ] S6 crop economics replaced with real data (currently mock, flagged in warnings)

---

## 9. Deployment (two separate apps)

The backend and frontend deploy independently. They share only the API URL and
the contract in `/openapi.json`.

```
Browser
  │  fetch  https://api.example.com/api/v1/...
  ▼
FRONTEND (static host)                     BACKEND (Docker + uvicorn)
  VITE_API_BASE_URL=https://api.example.com  CORS_ORIGINS=https://app.example.com
                                             API_KEY=<long random>
                                             OPENAI_API_KEY=<secret>
```

### Backend

Fastest path (Render): push the repo, then create a Blueprint from
`render.yaml`. It builds the Dockerfile, checks `/health`, and mounts a 1 GB
disk for the cache. Fill `CORS_ORIGINS` and `OPENAI_API_KEY` in the dashboard;
`API_KEY` is generated for you. Copy that key into the frontend config.

Manual path:

1. Build the image: `docker build -t cropseq .`
2. Run it with the env vars above. The container listens on `$PORT` (default 8000).
3. Required production env:
   - `CORS_ORIGINS` — the exact frontend origin, no trailing slash.
   - `API_KEY` — required for a public deployment; the LLM costs money.
   - `LLM_MODEL` and the provider key (e.g. `OPENAI_API_KEY`).
   - `LLM_ENABLED=false` to force the template explainer.
4. Optional: mount a disk for `CACHE_DB`; without it the cache is lost on restart.
5. Health check path: `/health`.
6. The data files (`data/bangladesh/*`, `data/crops/*`, fixtures) are inside the image.

### Frontend

1. Set `VITE_API_BASE_URL` (or the framework equivalent) to the backend URL.
2. Send `X-API-Key` on both POST routes if the backend has `API_KEY` set.
3. Use a long request timeout: the pipeline can take 10–40 s (weather APIs + LLM).
4. Never call SoilGrids, Open-Meteo or an LLM directly.

### Keeping the two repos in sync

- `/api/v1` path. Add fields, never rename or remove them.
- `/openapi.json` is the referee; generate types from it.
- Backend CI must pass before deploy; the contract tests are the guard.
- Change `CORS_ORIGINS` before the first deployed frontend call, not after.
