"""FastAPI capture service: accept notes and append directly to GitHub."""

import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from github import Github

from config import get_settings

settings = get_settings()

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


async def append_to_github(category: str, date_str: str, timestamp_display: str, processed_text: str) -> None:
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN or GITHUB_REPO not configured")

    import asyncio

    def _sync_append() -> None:
        g = Github(settings.GITHUB_TOKEN)
        repo = g.get_repo(settings.GITHUB_REPO)
        base = (settings.GITHUB_CAPTURE_BASE_PATH or "").strip().rstrip("/")
        path = f"{base}/闪念/{date_str}.md" if base else f"闪念/{date_str}.md"
        one_line = processed_text.replace("\n", " ")
        one_line = re.sub(r"\s+", " ", one_line).strip()
        new_content = f"\n- [{timestamp_display}] {one_line}"
        try:
            file = repo.get_contents(path)
            current = file.decoded_content.decode("utf-8")
            updated = (current.rstrip() + new_content + "\n").encode("utf-8")
            repo.update_file(path, f"Capture: {timestamp_display}", updated, file.sha)
        except Exception:
            body = new_content.strip() + "\n"
            repo.create_file(path, f"Capture: {timestamp_display}", body.encode("utf-8"))

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
        # 使用接口请求时间（北京时间）作为日期和显示时间
        request_time = datetime.now(ZoneInfo("Asia/Shanghai"))
        date_str = request_time.strftime("%Y-%m-%d")
        timestamp_display = f"{request_time.year}年{request_time.month}月{request_time.day}日 {request_time.hour:02d}:{request_time.minute:02d}"
        category = "Unsorted"
        summary = body.text[:50] + ("..." if len(body.text) > 50 else "")
        await append_to_github(category, date_str, timestamp_display, body.text)
        return CaptureResponse(
            status="success",
            category=category,
            summary=summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
