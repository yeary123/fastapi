"""
Centralized configuration for the Capture API.

All values ultimately来自环境变量（本地通过 .env，线上通过 Vercel 环境变量）。
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    # API key 用于校验请求 Header: X-API-Key
    API_KEY: str

    # LLM / OpenAI / OpenRouter / SiliconFlow
    OPENAI_API_KEY: str
    # 例如 SiliconFlow 提供的 OpenAI 兼容地址，如：
    # https://api.siliconflow.cn/v1  （以官方文档为准）
    OPENAI_BASE_URL: Optional[str] = None
    # 例如 deepseek v3.2 在 SiliconFlow 上对应的模型 ID
    # （以 SiliconFlow 控制台/文档里的实际模型名为准）
    OPENAI_MODEL: str = "deepseek-v3.2"

    # GitHub
    GITHUB_TOKEN: str
    GITHUB_REPO: str  # e.g. "username/repo-name"
    # 闪念文件所在目录的前缀，例如 obsidian/obsidian 表示写入 仓库/obsidian/obsidian/闪念/日期.md
    GITHUB_CAPTURE_BASE_PATH: str = "obsidian/obsidian"

    # 分类列表，可以按需在环境变量里覆盖（逗号分隔）
    CATEGORIES: List[str] = [
        "SEO_Work",
        "Tetris_Dev",
        "Bookkeeping_App",
        "Personal_Life",
        "Unsorted",
    ]


@lru_cache()
def get_settings() -> Settings:
    """
    统一获取配置，FastAPI 生命周期中只解析一次环境变量。
    """
    return Settings()

