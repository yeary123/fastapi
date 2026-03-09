# Capture API (FastAPI)

Capture notes via POST, classify and summarize with an LLM, and append to a private GitHub repo. Designed to work with an iOS Shortcut.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # edit .env with your keys
uvicorn main:app --reload
```

POST to `http://localhost:8000/capture` with header `X-API-Key: <your API_KEY>` and JSON body `{"text": "...", "timestamp": "..."}`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | Secret for `X-API-Key` header (e.g. from iOS Shortcut). |
| `OPENAI_API_KEY` | Yes | OpenAI API key, or OpenRouter API key if using OpenRouter. |
| `OPENAI_BASE_URL` | No | If set (e.g. `https://openrouter.ai/api/v1`), uses OpenRouter. |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4o-mini`). |
| `GITHUB_TOKEN` | Yes | GitHub Personal Access Token. |
| `GITHUB_REPO` | Yes | Repo in form `owner/repo` (e.g. `myuser/notes`). |

## GitHub Personal Access Token (PAT)

1. **Create a token**
   - GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**.
   - **Generate new token (classic)**.
   - Name it (e.g. `capture-api`), choose an expiry, and enable:
     - **repo** (full control of private repositories).

2. **Copy and store**
   - Copy the token once (it starts with `ghp_`). It won’t be shown again.
   - Put it in `.env` as `GITHUB_TOKEN=ghp_...`. Never commit `.env` or the token.

3. **Repo layout**
   - The app appends to files under `Projects/` in the repo, e.g. `Projects/SEO_Work.md`, `Projects/Personal_Life.md`. Create the `Projects` folder and an initial file if you like, or the app will create them on first write.

## Deploy on Vercel

- Connect the repo to Vercel; Vercel will detect FastAPI (entrypoint: `app.py`).
- In the Vercel project, set the same env vars (e.g. `API_KEY`, `OPENAI_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO`, and optionally `OPENAI_BASE_URL`, `OPENAI_MODEL`).
- Deploy; your iOS Shortcut should call `https://<your-project>.vercel.app/capture`.

## API

- **POST /capture**  
  - Headers: `X-API-Key: <API_KEY>`, `Content-Type: application/json`.  
  - Body: `{"text": "string", "timestamp": "string"}`.  
  - Response: `{"status": "success", "category": "...", "summary": "..."}` for use in your Shortcut/notification.
