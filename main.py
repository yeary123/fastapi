"""FastAPI capture service: accept notes and append directly to GitHub."""

import re
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from github import Github

from config import get_settings

settings = get_settings()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_from_timestamp(timestamp: str) -> str:
    ts = (timestamp or "").strip()
    if not ts:
        return "unknown-date"

    # Common case: ISO-8601-ish "YYYY-MM-DD..." -> take first 10 chars
    if len(ts) >= 10 and _DATE_RE.match(ts[:10]):
        return ts[:10]

    # Sometimes passed as just "YYYY-MM-DD"
    if _DATE_RE.match(ts):
        return ts

    return "unknown-date"


app = FastAPI(
    title="Capture API",
    description="Capture notes and append directly to GitHub",
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


async def append_to_github(category: str, timestamp: str, summary: str, processed_text: str) -> None:
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN or GITHUB_REPO not configured")

    import asyncio

    def _sync_append() -> None:
        g = Github(settings.GITHUB_TOKEN)
        repo = g.get_repo(settings.GITHUB_REPO)
        date_str = _date_from_timestamp(timestamp)
        path = f"闪念/{date_str}.md"
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
        # 暂时不做 AI 分析，统一按 Unsorted 分类，summary 为前 50 个字符
        category = "Unsorted"
        summary = body.text[:50] + ("..." if len(body.text) > 50 else "")
        processed_text = body.text
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
