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
    rerank_provider: Literal["passthrough", "cross_encoder"] = "cross_encoder"

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

    # ===== 精准问答(S1)=====
    # MinerU 常驻解析服务(docker/mineru 的容器,`make mineru` 起;那 4.9GB 依赖树永不进 server 镜像)
    mineru_api_url: str = "http://127.0.0.1:18001"
    mineru_timeout_sec: float = 600.0
    # 命中分档阈值(Step 5 用 27 条人写评测集实测定稿,见 S1-plan §5 M4):
    # 正例 0.613–0.912 / 越界负例 0.129–0.384 / 困难负例 0.613–0.827
    # —— 阈值只切得开"越界",切不开"同领域没答案",所以另有两道正交的关(护栏 + 复核)。
    exact_qa_hit_threshold: float = 0.55
    exact_qa_borderline_threshold: float = 0.40
    # 命中前用 light 模型复核一次(挡纯语义邻近的困难负例;实测 23/27 → 26/27,命中时 +2.9s)
    exact_qa_hit_gate: bool = True

    # ===== 文档 RAG(S2)=====
    # 重排:本地 cross-encoder(契约变更 C7)。以下五个值全部由 Step 5 评测集实测定稿,
    # 依据逐条见 documents/S2-PLAN.md 附录二(参数定稿总表)。
    doc_rag_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # 每条候选喂给重排前截到多少 token(512 是 BERT 家族位置数硬上限,余量留给 query)
    doc_rag_rerank_max_tokens: int = 400
    # 重排后保留几条喂给生成:hit@k 曲线显示 5→8 收益为 0,5→10 只多 1 题却让上下文翻倍
    doc_rag_rerank_topn: int = 5
    # rerank=纯用重排分;guard=整题最高分低于阈值时判定模型失灵,退回召回名次(实测 90%→95%)
    doc_rag_rerank_strategy: Literal["rerank", "guard"] = "guard"
    # guard 阈值:扫描全区间得最优平台 −4.86 ~ +0.02,取中点。
    # 人话含义 sigmoid(−2.5)≈7.6% —— "连最好的候选模型都认为相关概率不到 8%"时才推翻它。
    # 🩸 两个边界各只有 1 个样本,评测集变大后必须重扫。
    doc_rag_rerank_guard: float = -2.5
    # 🩸 强制走本地权重缓存。sentence-transformers 每次加载都会去 HuggingFace 核对版本,
    # 哪怕权重早已缓存 —— 实测这一趟网络往返 8.6s,把 3s 的加载拖成 13s。
    # 代价:权重必须先下好(bootstrap.sh 的"预下载重排模型"那一步)。
    doc_rag_rerank_offline: bool = True

    # 切分:沙箱 Step 5 评测集逐题查过 3 道失败题,没有一道是切分造成的 → 定稿不改
    doc_rag_chunk_max_tokens: int = 512
    doc_rag_chunk_overlap: int = 80
    # 图表描述(整条摄取链唯一调 LLM 的地方,走 light tier)
    doc_rag_describe_figures: bool = True
    doc_rag_describe_concurrency: int = 4
    # 表格逐行覆盖的行数上限。🩸 15 曾把 Darknet-53(18 行)刚好卡进截断,
    # 丢掉的恰是表尾的分类头 —— 表格是纯文本,token 便宜,阈值给足。
    doc_rag_table_exhaustive_rows: int = 40
    # 检索:两条腿各召回多少条进 RRF,以及 RRF 的平滑常数
    doc_rag_vector_topk: int = 30
    doc_rag_fts_topk: int = 30
    doc_rag_rrf_k: int = 60
    # 命中片前后各带几片上下文(只记 ref,拼不拼由生成阶段决定)
    doc_rag_context_expand: int = 1
    # 生成之后再跑一次"每个结论有没有材料支撑"的校验(多一次 light 调用)。
    # 默认关:它挡的是"有材料但概括过头"这种低频问题,演示时可以打开当亮点。
    # 结果只进 trace 的 verify_doc_rag 跨度,不改答案正文,也不动引用面板。
    doc_rag_verify: bool = False

    # ===== 数据库 =====
    database_url: str
    # 演示业务库(智能问数的查询目标)的只读连接串。它**不是**本系统的 engine:
    # 业务库是独立的 MySQL 实例,由 datasources 表按行管理(密文存 dsn_enc)。
    # 这里的值只作"演示数据源"的出厂配置 —— seed 时加密写进那张表。
    biz_database_url: str | None = None
    # 问数执行闸:单次查询的读超时与返回行上限(B6 实测定稿,改前先跑 S3 评测集)
    text2sql_query_timeout_sec: int = 15
    text2sql_max_rows: int = 500

    @field_validator("database_url")
    @classmethod
    def _must_be_async_driver(cls, v: str) -> str:
        """全链路 async,driver 写错会在第一次查询才炸,这里提前拦住。"""
        if "+asyncpg" not in v:
            raise ValueError("DATABASE_URL 必须使用 asyncpg 驱动,如 postgresql+asyncpg://...")
        return v

    @field_validator("biz_database_url")
    @classmethod
    def _biz_must_be_mysql(cls, v: str | None) -> str | None:
        """演示业务库是 MySQL(理由见 docker/architect.md)。执行走同步 pymysql +
        线程池:问数查询是"一条 SELECT、强制 LIMIT、15s 超时",为它拉一个异步 MySQL
        驱动进来,换到的是一条与 Phase B 实测路径不同的执行链 —— 不值当。"""
        if v and not v.startswith("mysql+pymysql://"):
            raise ValueError("BIZ_DATABASE_URL 必须是 mysql+pymysql://...(演示业务库是 MySQL 8.4)")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.file_storage_dir)
        return p if p.is_absolute() else (REPO_ROOT / p).resolve()

    @field_validator("exact_qa_hit_threshold")
    @classmethod
    def _hit_threshold_range(cls, v: float) -> float:
        """0.90 是计划早期的臆测值,实测只剩 2/14 正例 —— 写错方向的值在这里就拦住。"""
        if not 0.0 < v <= 1.0:
            raise ValueError("EXACT_QA_HIT_THRESHOLD 必须在 (0, 1] 区间内")
        return v

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
