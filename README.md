# Skincare Advisor

A small React + FastAPI app that sends a face photo to OpenAI GPT-4o for cautious, cosmetic skincare suggestions. The app does not retain photos after processing; they are sent to OpenAI for analysis. Do not upload a photo unless you are comfortable with that.

This is not a medical tool. Results are not a diagnosis or a substitute for a dermatologist.
Before submitting a photo, users must consent to sending it to OpenAI. The backend does not save uploaded image files, but images are sent to OpenAI for processing.

## Run locally

1. Paste your OpenAI API key into `backend/.env` as `OPENAI_API_KEY=...`. Keep this file private.
2. Start the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

3. In another terminal, start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open the local URL printed by Vite.

To run backend checks without making provider requests:

```powershell
cd backend
python -m unittest
```

The backend reads `backend/.env` or the `OPENAI_API_KEY` environment variable. The Vite dev server proxies `/api` requests to `http://localhost:8000`.

## Structure

```text
skincare-advisor/
  backend/
    .env                 # Local API key; ignored by git
    main.py              # FastAPI health and image-analysis endpoints
    requirements.txt
  frontend/
    index.html
    package.json
    vite.config.js
    src/
      App.jsx            # Photo selection, upload, and results
      main.jsx
      styles.css
```

## API

- `GET /api/health` — confirms the backend is running.
- `POST /api/analyze` — accepts one multipart `image` (JPEG, PNG, or WebP; maximum 10 MB) and returns a cautious visual assessment, possible concerns, routine suggestions, and cautions. The request is sent to OpenAI GPT-4o; the image is not retained by this server after processing.

Provider failures return actionable guidance for common authentication, permissions, model availability, quota, and service errors. The backend logs the HTTP status and OpenAI request ID without logging the key or image.

## Before publishing

This local prototype is not production-hardened. Deploy behind HTTPS; add authentication, rate limiting, abuse monitoring, and a strict production CORS allowlist; document provider data handling and retention; and review applicable privacy and health-product requirements. Never put the OpenAI key in frontend code.
