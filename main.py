"""FastAPI capture service: analyze text with LLM and append to GitHub repo."""

import re
from typing import Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from github import Github
from openai import AsyncOpenAI

from config import get_settings

settings = get_settings()

app = FastAPI(
    title="Capture API",
    description="Capture and categorize notes to GitHub",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class CaptureRequest(BaseModel):
    text: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)


class CaptureResponse(BaseModel):
    status: str
    category: str
    summary: str


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not settings.API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured")
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return x_api_key


def get_openai_client() -> AsyncOpenAI:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL or None,
    )


def _normalize_category(raw: str) -> str:
    raw_upper = raw.strip().upper().replace(" ", "_")
    for c in settings.CATEGORIES:
        if c.upper() == raw_upper:
            return c
    return "Unsorted"


async def analyze_with_llm(text: str) -> Tuple[str, str, str]:
    """Returns (category, summary, processed_text)."""
    client = get_openai_client()
    categories_str = ", ".join(settings.CATEGORIES)
    prompt = f"""Analyze this note and respond in exactly this format (no extra text):
CATEGORY: one of [{categories_str}]
SUMMARY: exactly 10 words, no more no less
TASK_LINE: if this describes a task or todo, output a single line starting with "- [ ] " and the task text; otherwise output the original text as a single line (can be multi-line content), preserving meaning.

Note:
---
{text}
---"""
    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = (response.choices[0].message.content or "").strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}")

    category = "Unsorted"
    summary = ""
    processed = text

    for line in content.split("\n"):
        line = line.strip()
        if line.upper().startswith("CATEGORY:"):
            category = _normalize_category(line[9:].strip())
        elif line.upper().startswith("SUMMARY:"):
            summary = line[8:].strip()
        elif line.upper().startswith("TASK_LINE:"):
            processed = line[10:].strip()
        elif line and not summary and ":" not in line[:15]:
            summary = line[:200]

    if not summary:
        summary = text[:50] + ("..." if len(text) > 50 else "")
    return (category, summary, processed)


async def append_to_github(category: str, timestamp: str, summary: str, processed_text: str) -> None:
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN or GITHUB_REPO not configured")

    import asyncio

    def _sync_append() -> None:
        g = Github(settings.GITHUB_TOKEN)
        repo = g.get_repo(settings.GITHUB_REPO)
        path = f"Projects/{category}.md"
        one_line = processed_text.replace("\n", " ")
        one_line = re.sub(r"\s+", " ", one_line).strip()
        new_content = f"\n- [{timestamp}] {summary}\n  - {one_line}"
        try:
            file = repo.get_contents(path)
            current = file.decoded_content.decode("utf-8")
            updated = (current.rstrip() + new_content + "\n").encode("utf-8")
            repo.update_file(path, f"Capture: {timestamp}", updated, file.sha)
        except Exception:
            body = new_content.strip() + "\n"
            repo.create_file(path, f"Capture: {timestamp}", body.encode("utf-8"))

    await asyncio.to_thread(_sync_append)


@app.get("/")
async def root():
    return {"service": "capture", "version": "1.0.0"}


@app.post("/capture", response_model=CaptureResponse)
async def capture(
    body: CaptureRequest,
    _: str = Depends(verify_api_key),
):
    try:
        category, summary, processed_text = await analyze_with_llm(body.text)
        await append_to_github(category, body.timestamp, summary, processed_text)
        return CaptureResponse(
            status="success",
            category=category,
            summary=summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
