# 🌾 FieldShift — Frontend

Farmer-facing decision support UI for the **FieldShift Crop Rotation Advisor**. Built for the **NASA Space Apps Challenge 2026**.

---

## ⚡ Quick Usage: Running with the Local Backend

Follow these steps to run the live Python pipeline backend locally and connect it to the frontend UI.

### Step 1: Start the Local Backend (FastAPI)

From the repository root directory:

```bash
# 1. Install dependencies (if not already installed)
pip install -r requirement.txt

# 2. Launch the backend server with hot-reload
PYTHONPATH=src uvicorn cropseq.api.main:app --host 127.0.0.1 --port 8000 --reload
```

* **Health Check:** Open `http://127.0.0.1:8000/api/v1/health` → returns `{"status":"ok"}`
* **Interactive API Docs:** Open `http://127.0.0.1:8000/docs`

---

### Step 2: Start the Frontend UI

In a new terminal window:

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Launch the development server
npm run dev
```

* **Frontend URL:** Open `http://localhost:3000` in your browser.

---

### Step 3: Verify the Connection

* When the frontend loads, look at the top-right header:
  * **🟢 Backend Online:** The frontend is connected live to your local FastAPI backend at `http://127.0.0.1:8000`. All farmer conversations, SoilGrids satellite queries, and multi-objective sequence optimizations are running in real time through the local Python pipeline.
  * **🧪 Mock Mode (Fallback):** If the local backend is stopped, the frontend automatically falls back to built-in NASA & BARC mock data (`data_shape/s8_output.json`) so the UI never crashes and remains 100% testable.
  * **Switch Toggle:** Click **`(Switch)`** in the top header anytime to manually toggle between **Live Backend** and **Mock Mode**.

> [!NOTE]
> If testing the frontend hosted on Vercel (`https://...`): Modern browsers block HTTPS web pages from making insecure requests to `http://localhost` (Mixed Content policy). For local backend development and testing, always use `npm run dev` locally at `http://localhost:3000`.

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
