"""全局配置:所有配置项从仓库根的 .env 读入,启动时校验缺失项。

设计要点:
- `EMBEDDING_DIM` 是唯一维度出处(migration、向量列、Provider 都读它),不硬编码。
- LLM 只暴露 tier(main/light),业务代码不写型号名,tier→型号映射只在这里。
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# server/app/config.py -> server/ -> 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 仓库根的 .env 是唯一密钥来源;server/.env 仅作本地覆盖用(通常不存在)
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "server" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 应用 =====
    app_env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    file_storage_dir: str = "./storage"
    secret_key: str = Field(min_length=8)

    # ===== Provider 选择 =====
    llm_provider: Literal["openai"] = "openai"
    embedding_provider: Literal["openai"] = "openai"
    rerank_provider: Literal["passthrough"] = "passthrough"

    # ===== OpenAI =====
    openai_api_key: str = Field(min_length=8)
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model_main: str = "gpt-5"
    llm_model_light: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # ===== Provider 行为(超时/重试/批量) =====
    # 推理型模型(gpt-5 系)的思考档位:low 让演示的响应延迟可接受
    llm_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "low"
    # 推理 token 也算在 max_completion_tokens 里,给它留出的额外预算
    # (不留的话思考吃满预算,content 会是空字符串)
    llm_reasoning_headroom: int = 2048
    llm_timeout_sec: float = 60.0
    embedding_timeout_sec: float = 30.0
    # 瞬时故障(限流/超时/5xx)的总尝试次数,含首次
    provider_max_attempts: int = 3
    # 一次 embedding 请求最多塞多少条文本(供应商有上限,超了要自己切批)
    embedding_batch_size: int = 64

    # ===== 数据库 =====
    database_url: str
    biz_database_url: str | None = None

    @field_validator("database_url", "biz_database_url")
    @classmethod
    def _must_be_async_driver(cls, v: str | None) -> str | None:
        """全链路 async,driver 写错会在第一次查询才炸,这里提前拦住。"""
        if v and "+asyncpg" not in v:
            raise ValueError("DATABASE_URL 必须使用 asyncpg 驱动,如 postgresql+asyncpg://...")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.file_storage_dir)
        return p if p.is_absolute() else (REPO_ROOT / p).resolve()

    def model_for_tier(self, tier: Literal["main", "light"]) -> str:
        """业务代码只说要强模型还是快模型,型号在这里映射。"""
        return self.llm_model_main if tier == "main" else self.llm_model_light


class MissingConfigError(RuntimeError):
    """配置缺失:把 pydantic 的字段名翻译成 .env 里的变量名,直接告诉你缺哪一行。"""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        lines = []
        for err in exc.errors():
            var = str(err["loc"][0]).upper()
            lines.append(f"  - {var}: {err['msg']}")
        raise MissingConfigError(
            "读取配置失败。请检查仓库根目录的 .env(可从 .env.example 复制):\n" + "\n".join(lines)
        ) from exc


settings = get_settings()
