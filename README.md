# Skincare Advisor (SkinScan)

A full-stack React + FastAPI application that analyzes a face photo using vision AI to provide personalized, cosmetic skincare suggestions (skin type tendency, visible concerns, morning & evening routines, cautions, and professional care guidance).

> **Disclaimer:** This is not a diagnostic or medical tool. Results are cosmetic recommendations and not a substitute for a consultation with a certified dermatologist.

---

## Deploy to Vercel

This repository is preconfigured for full-stack deployment on **Vercel** with a Vite frontend and FastAPI serverless functions:

1. Push this repository to GitHub (or use [gaurisingh29/skinscan](https://github.com/gaurisingh29/skinscan)).
2. Log in to [Vercel](https://vercel.com) and click **"Add New Project"** -> **"Import"** this repository.
3. In the project configuration:
   - Leave **Framework Preset** as default or Vite.
   - Leave **Root Directory** as `./`.
4. Under **Environment Variables**, add:
   - `OPENAI_API_KEY`: Your OpenAI API key (`sk-...`).
   - *(Optional)* `OPENAI_MODEL`: Defaults to `gpt-4o`. Can also be `gpt-4o-mini`.
5. Click **Deploy**. Vercel will build the frontend into `frontend/dist` and deploy `api/index.py` as a serverless function responding to `/api/*`.

---

## Run Locally

### 1. Backend Setup (FastAPI)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*Create a `backend/.env` file with `OPENAI_API_KEY=sk-...`.*

### 2. Frontend Setup (React + Vite)
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Vite will automatically proxy `/api` calls to `http://localhost:8000`.

---

## Testing
Run backend unit tests (uses mocks, no live API key required):
```powershell
cd backend
python -m unittest
```
