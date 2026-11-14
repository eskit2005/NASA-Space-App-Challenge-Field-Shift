# 🌾 FieldShift — Frontend

Farmer-facing decision support UI for the **FieldShift Crop Rotation Advisor**. Built for the **NASA Space Apps Challenge 2026**.

---

## ⚡ Quick Usage (Testing Before Cloud Backend Deployment)

> **The backend is not hosted on the cloud yet.**  
> The web application is engineered with **two operational modes** so that evaluators and farmers can explore the entire recommendation flow immediately.

### Mode 1: Instant Cloud / Vercel Demo (Mock Mode)
The deployed frontend runs with built-in realistic mock data grounded in real NASA & BARC agronomic output (`s8_output.json`).
* **Zero Backend Required:** Works 100% offline and in the browser.
* **Full Experience:** Explore the conversational AI intake, Upazila geo-location selection, budget & water quota inputs, seasonal planting journeys, visual profit/water/soil gauges, and weather summaries.
* **Header Status:** In the top bar, you can see `🧪 Mock Mode` with an instant toggle switch.

### Mode 2: Connect to a Local Live Backend (Full Live Pipeline)
If you want to run the live Python pipeline (fetching real-time SoilGrids soil data and Open-Meteo weather):

1. **Start the Backend API (FastAPI):**
   ```bash
   # From the repository root
   PYTHONPATH=src uvicorn cropseq.api.main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Run the Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   # Opens at http://localhost:3000
   ```

3. **Toggle Live Backend:**
   * In the top-right header, click **`(Switch)`** next to the backend badge to toggle between **Live Backend** and **Mock Mode** in real time!
   * Or set `VITE_MOCK_API=false` in `frontend/.env.local`.

---

## 🚀 Future Cloud Backend Deployment (Connecting Vercel to Live Backend)

When you deploy the FastAPI backend to a cloud host (Render, Railway, Fly.io, etc.):

1. **Backend Environment Variable:**
   ```bash
   CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
   ```

2. **Vercel Frontend Environment Variables:**
   * `VITE_API_BASE_URL`: `https://your-deployed-backend.onrender.com`
   * `VITE_MOCK_API`: `false`

---

## 📱 Screens & Features

| Screen | Description |
|--------|-------------|
| **Conversational Intake** | Adaptive conversational AI collecting location (Upazila/GPS), farm size, land type (HL to VLL), seasonal budget, water quota, and answering farmer questions in real time. |
| **Review Farm Details** | Pre-calculation overview with inline editing of all parcel constraints and priorities before running optimization. |
| **Calculation Engine** | Animated feedback reflecting stages (satellite soil query, weather normalization, candidate sequences, Pareto optimization). |
| **Farmer-Friendly Results** | Visual seasonal planting journey cards, interactive profit/water/soil gauges, regional weather forecast, alternative rotation cards, and simplified agronomic reasoning without technical jargon. |

---

## 🛠️ Tech Stack
* **Framework:** React 18 + Vite + TypeScript
* **Styling:** Custom responsive CSS (earthy, high-contrast, farmer-first palette)
* **Testing:** Headless Chrome Puppeteer verification across mobile (375px/414px), tablet (768px), and desktop (1200px)

---

## 📁 Project Structure

```
src/
  components/
    ConversationalChat.tsx  # Adaptive AI intake with contextual single-chip prompts
    ReviewScreen.tsx        # Inline editable farm details and constraints
    LoadingScreen.tsx       # Live pipeline step visualization
    ResultScreen.tsx        # Redesigned farmer-friendly seasonal journeys & visual gauges
    Header.tsx              # Navigation & Live / Mock backend switcher
    UpazilaPicker.tsx       # Bangladesh upazila search with precomputed coordinates
  types/
    api.ts                  # FarmerProfile, FinalResponse, EvaluatedSequence types
  utils/
    api.ts                  # API fetchers, health checking, and automatic mock fallback
    helpers.ts              # Currency, water volume, and score formatters
    cropNames.ts            # Crop ID to human-readable agronomic names
  mock/
    mockData.ts             # NASA / BARC sample output fixture
  config.ts                 # Environment variable configurations
  App.tsx                   # Central stage router
  index.css                 # Responsive stylesheet
```
