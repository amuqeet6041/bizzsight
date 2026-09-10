# SME eCommerce Insights — Full Application (Next.js + Python)

This is your complete application: a Next.js frontend+backend, and a Python
FastAPI microservice that does the actual data cleaning and metrics
calculation (the same tested logic from your prototype).

```
full-app/
├── frontend/            ← Next.js app (UI + API routes) — run this with npm
│   ├── app/
│   │   ├── page.js               (main page — orchestrates the 3 stages)
│   │   ├── layout.js
│   │   ├── components/
│   │   │   ├── FileUpload.jsx    (Phase 4)
│   │   │   ├── MappingReview.jsx (Phase 5)
│   │   │   └── Dashboard.jsx     (Phase 6)
│   │   └── api/
│   │       ├── suggest-mapping/route.js   (Phase 3 — calls Python)
│   │       └── process/route.js           (Phase 3 — calls Python)
│   └── .env.local        ← tells Next.js where the Python service is
│
├── python-service/       ← FastAPI microservice — run this with uvicorn
│   ├── main.py
│   ├── pipeline/
│   │   ├── mapping.py    (unchanged from your prototype)
│   │   ├── cleaning.py   (unchanged from your prototype)
│   │   └── metrics.py    (unchanged from your prototype)
│   └── requirements.txt
│
└── sample_messy_orders.csv   ← test file
```

## How to run it (you need TWO terminals open at once)

**Terminal 1 — start the Python service:**
```bash
cd python-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Leave this running. You should see `Uvicorn running on http://0.0.0.0:8000`.

**Terminal 2 — start the Next.js app:**
```bash
cd frontend
npm install
npm run dev
```
Leave this running too. Open `http://localhost:3000` in your browser.

## Try it

1. Upload `sample_messy_orders.csv` in the browser.
2. Review the auto-detected column mapping (it should get almost everything
   right — correct anything wrong).
3. Click "Generate Insights."
4. You'll see the metric cards, charts, and insights — this is your live
   dashboard, built entirely in React.
5. Click "Download for Power BI" to get the same two-sheet Excel file as
   before, if you still want to show the Power BI dashboard too.

## How the pieces talk to each other

```
Browser (React state: upload → mapping → dashboard)
   ↓ fetch("/api/suggest-mapping") / fetch("/api/process")
Next.js API routes (app/api/.../route.js) — run on the server
   ↓ fetch("http://localhost:8000/...")
Python FastAPI service (main.py) — runs your pandas pipeline
   ↓ returns JSON
back up the chain to the browser
```

The browser never talks to Python directly — only through your Next.js API
routes. This means later, if you deploy, the Python service's URL can be
private/internal and only your Next.js server needs to reach it.

## Customizing

- **More column aliases**: `python-service/pipeline/mapping.py` — same as
  the prototype, add variations to the `ALIASES` dict.
- **More metrics**: `python-service/pipeline/metrics.py` — add a new key to
  the `metrics` dict in `compute_metrics()`, then add a matching card in
  `frontend/app/components/Dashboard.jsx`'s `CARD_METRICS` list.
- **More insight rules**: `generate_insights()` in the same file — plain
  if/else logic.
- **Styling**: everything uses Tailwind classes directly in the `.jsx`
  files — change classes like `bg-blue-600` or `rounded-xl` directly.

## If something doesn't connect

- Make sure BOTH terminals are running at the same time.
- Check `frontend/.env.local` has `PYTHON_SERVICE_URL=http://localhost:8000`
  matching whatever port you started uvicorn on.
- If you see a CORS error in the browser console, double check the Python
  service is actually running — that error usually means the Next.js
  server couldn't reach it, not an actual CORS misconfiguration.
