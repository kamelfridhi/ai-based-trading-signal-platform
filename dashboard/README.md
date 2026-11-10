# Trading Signal Dashboard

React + Vite front-end for the FastAPI backend.

## Prerequisites

- API running: `python -m src.api.run_server` (port 8000)
- Node.js 18+

## Development

```powershell
cd dashboard
npm install
npm run dev
```

Open **http://localhost:5173**. API calls use the Vite proxy (`/api` → `localhost:8000`).

## Production build

```powershell
npm run build
npm run preview
```

Set `VITE_API_URL=http://localhost:8000` in `dashboard/.env` if not using the dev proxy.
