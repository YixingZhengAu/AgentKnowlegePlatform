"""精准问答(S1)的数据契约 —— 字段名在 S1 沙箱阶段定型后不再改动。

沙箱阶段这份契约是"模块间以 json 文件交接"的唯一出处(M1→M2→M3→M4);
集成后它同时承担三个角色:
1. 服务层内部的数据形状(parser / extractor / similar_gen / retriever 之间);
2. 落库形状(`staging_items.payload` = QaCandidate 去掉 origin_ref/confidence,
   `staging_items.origin_ref` = OriginRef);
3. API 出入参(经 `make types` 生成前端类型,前端禁止手写)。

沙箱版里的**路径常量**(OUT_DIR / parse_dir)不在这里 —— 落盘位置是服务层的事,
见 `app/services/exact_qa/storage.py`;这里只留"文件名与 URL 方案"这类跨层契约。
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

# ==========================================================================
# 0. 常量:产物文件命名 / 图片 URL 方案(契约的一部分,不许各层自己拍)
# ==========================================================================

#: 解析产物在 FILE_STORAGE_DIR 下的父目录:storage/parses/{document_id}/
PARSE_SUBDIR = "parses"
#: 带页标记的 markdown(M1 产出,人工校对的对象,M2 的输入)
PAGED_MD_NAME = "paged.md"
#: 人工校对后的 markdown(校对页保存的落点;M2 优先读它,没有则退回 paged.md)
REVIEWED_MD_NAME = "reviewed.md"
#: M1 的机器可读产物(页尺寸、块序列、统计)
PARSE_RESULT_NAME = "parse_result.json"
#: 图片子目录名(md 里的相对路径前缀)
IMAGES_SUBDIR = "images"

#: 页标记注释格式:markdown 里每页开头插一行,page_idx 从 0 起(与 MinerU 一致)
PAGE_MARKER_FMT = "<!-- page: {page_idx} -->"

#: 会被拼进 markdown 的**内容**块类型(build_paged_md 里每一种都有对应分支)
CONTENT_BLOCK_TYPES = frozenset({"text", "table", "image", "chart", "equation"})

#: content_list 里已知要过滤掉的页边噪声类型(MinerU 自己的 md 已丢弃,我们自己拼要对齐)
#: header/footer 是页眉页脚(实测:公司名、文档编号 | Internal use only),与页码同类
NOISE_BLOCK_TYPES = frozenset(
    {"aside_text", "page_number", "header", "footer", "discarded"}
)

#: 已知类型 = 内容 + 噪声。不在这里面的类型**不报错**,按噪声丢掉并计入 stats.dropped_by_type
#: —— MinerU 升级随时可能冒出新类型,不能让一个陌生块把整篇文档的解析打死(见 §踩坑)
KNOWN_BLOCK_TYPES = CONTENT_BLOCK_TYPES | NOISE_BLOCK_TYPES

#: 图片出口(契约点 M1.5):**改写在后端出口做,入库一律存相对路径**
FILE_SERVICE_URL_FMT = "/api/files/parses/{document_id}/images/{name}"


def image_url(document_id: str, name: str) -> str:
    """把 md 里的 `images/<sha256>.jpg` 改写成文件服务 URL(改写发生在后端)。"""
    return FILE_SERVICE_URL_FMT.format(document_id=document_id, name=name)


# ==========================================================================
# 1. MinerU 侧:content_list.json 的块结构(M1 的输入,实测字段)
# ==========================================================================

BBox1000 = Annotated[list[int], Field(min_length=4, max_length=4)]
"""bbox = [x0, y0, x1, y1],**每轴各自归一化到 0–1000** 的整数,原点左上。

还原成 PDF point:x_pt = x / 1000 * page_width_pt(页尺寸取 ParseResult.pages)。
"""

#: 实测见过的类型(3.4.5 / backend=pipeline):
#:   text        正文/标题,标题带 text_level(1=一级)
#:   table       table_body 是 HTML,另有 caption/footnote
#:   image       切图 + image_caption
#:   chart       图表切图;pipeline 模式下 content 恒为空字符串
#:   equation    行间公式,text 是 LaTeX
#:   aside_text  页边噪声(如 arXiv 竖排水印)
#:   page_number 页码噪声
#:   header      页眉噪声
#:   footer      页脚噪声
#:
#: **故意不写成 Literal**:这份 content_list 是 MinerU 的输出,不是我们的入参,
#: 枚举收窄只会让没见过的类型把整篇解析打成 parse failed(实测 header 就是这么炸的)。
#: 类型的语义判断集中在 CONTENT_BLOCK_TYPES / NOISE_BLOCK_TYPES 两个集合。
BlockType = str


class ContentBlock(BaseModel):
    """content_list.json 里的一个块(只声明我们会用到的字段,其余忽略)。"""

    model_config = {"extra": "ignore"}

    type: BlockType
    page_idx: int = Field(ge=0, description="页序号,0 起")
    bbox: BBox1000 | None = None

    # text / equation / chart
    text: str | None = None
    text_level: int | None = Field(default=None, description="1=一级标题;正文为 None")
    text_format: str | None = Field(default=None, description="equation 为 'latex'")
    content: str | None = Field(default=None, description="chart 的文本内容,pipeline 下恒空")

    # image / chart / table / equation 的切图相对路径:images/<sha256>.jpg
    img_path: str | None = None

    image_caption: list[str] = []
    chart_caption: list[str] = []
    table_caption: list[str] = []
    table_footnote: list[str] = []
    table_body: str | None = Field(default=None, description="表格 HTML")

    @property
    def is_noise(self) -> bool:
        """非内容块一律算噪声 —— 已知的页眉页脚页码,以及任何没见过的新类型。"""
        return self.type not in CONTENT_BLOCK_TYPES

    @property
    def is_unknown_type(self) -> bool:
        """MinerU 冒出的新类型:不报错,但要能在日志与 stats 里看见。"""
        return self.type not in KNOWN_BLOCK_TYPES


class PageInfo(BaseModel):
    """一页的物理尺寸(PDF point),前端把归一化 bbox 换算回 PDF 坐标做高亮时要用。"""

    page_idx: int = Field(ge=0)
    width_pt: float = Field(gt=0)
    height_pt: float = Field(gt=0)


# ==========================================================================
# 2. M1 解析产物
# ==========================================================================

class ParseStats(BaseModel):
    """解析统计,给校对页/日志看,也是质量回归的抓手。"""

    page_count: int = 0
    block_count: int = 0
    noise_dropped: int = Field(default=0, description="过滤掉的非内容块总数")
    dropped_by_type: dict[str, int] = Field(
        default={}, description="过滤掉的块按类型计数,如 {'header': 13, 'page_number': 5}"
    )
    table_count: int = 0
    image_count: int = Field(default=0, description="image + chart")
    equation_count: int = 0
    elapsed_ms: int = 0


class ParseResult(BaseModel):
    """M1 输出(落盘 parse_result.json)。M2 只需要 paged.md 与 blocks。"""

    document_id: str
    source_pdf: str = Field(description="原 PDF 的相对路径(FILE_STORAGE_DIR 下)")
    parse_dir: str = Field(description="产物目录的相对路径:parses/{document_id}/")
    pages: list[PageInfo]
    blocks: list[ContentBlock] = Field(description="已过滤噪声的块序列,按阅读顺序")
    images: list[str] = Field(default=[], description="images/ 下的文件名列表")
    stats: ParseStats = ParseStats()


# ==========================================================================
# 3. 候选 QA:M2 产出 / M3 补全 / 人工采纳的对象
# ==========================================================================

class OriginRef(BaseModel):
    """原文出处,整体存 `staging_items.origin_ref`(jsonb)。

    quote 用于审核台文本对照(必须能在源文本里定位到,否则该候选在 M2 就被丢弃);
    page_idx + bbox 用于在原 PDF 上定位/高亮。bbox 可空(quote 跨块时给不出唯一框)。
    """

    document_id: str
    page_idx: int = Field(ge=0)
    quote: str = Field(min_length=1, description="原文片段,逐字摘录,不许改写")
    bbox: BBox1000 | None = None


class QaCandidate(BaseModel):
    """一条候选 QA。字段集 = DB-DESIGN §8 的 qa_pair payload + origin_ref + confidence。"""

    standard_question: str = Field(min_length=1)
    answer: str = Field(min_length=1, description="硬约束:非空,空的在 M2 就丢弃")
    keywords: list[str] = []
    similar_questions: list[str] = Field(default=[], description="M3 填充,3–5 条")
    origin_ref: OriginRef = Field(description="硬约束:必须有出处")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @field_validator("standard_question", "answer")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    def as_payload(self) -> dict:
        """落 `staging_items.payload` 的形状(origin_ref / confidence 各有专属列)。"""
        return {
            "standard_question": self.standard_question,
            "answer": self.answer,
            "keywords": list(self.keywords),
            "similar_questions": list(self.similar_questions),
        }


class DropReason(StrEnum):
    """M2 过滤掉候选的原因,计数进 ExtractStats,用来判断 prompt 好不好。"""

    EMPTY_ANSWER = "empty_answer"
    NO_ORIGIN_REF = "no_origin_ref"
    QUOTE_NOT_FOUND = "quote_not_found"   # quote 在校对文本里定位不到
    DUPLICATE_QUESTION = "duplicate_question"
    SCHEMA_INVALID = "schema_invalid"     # LLM 输出不合 schema


class ExtractStats(BaseModel):
    model: str = ""
    chunk_count: int = Field(default=0, description="长文分段抽取的段数")
    raw_count: int = Field(default=0, description="LLM 原始产出条数")
    kept_count: int = 0
    dropped: dict[str, int] = {}
    elapsed_ms: int = 0


class QaCandidateSet(BaseModel):
    """M2/M3 的中间产物(集成后只在 Job 的 scratch 里传,不再落 json 文件)。"""

    document_id: str
    source_md: str = Field(description="抽取所用文本的文件名(reviewed.md 或 paged.md)")
    candidates: list[QaCandidate]
    stats: ExtractStats = ExtractStats()


# ==========================================================================
# 4. M3 相似问生成
# ==========================================================================

class SimilarQuestions(BaseModel):
    """light 模型对单条 QA 的结构化输出。"""

    questions: list[str] = Field(min_length=1, max_length=8)

    @field_validator("questions")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for q in (x.strip() for x in v):
            if q:
                seen.setdefault(q, None)
        return list(seen)


# ==========================================================================
# 5. M4 检索
# ==========================================================================

class HitTier(StrEnum):
    """检索分档。阈值取值见 config 的 exact_qa_* 三项(Step 5 实测定稿)。"""

    HIT = "hit"                # >= EXACT_QA_HIT_THRESHOLD 且过了两道关,原样返回答案
    BORDERLINE = "borderline"  # 分数够但被护栏/复核降级,或介于两阈值之间;S1 当未命中
    MISS = "miss"              # 未命中,落回生成


class RetrievalCandidate(BaseModel):
    """一个被检索到的问题面(标准问或某条相似问)。"""

    item_id: str = Field(description="exact_qa_items.id")
    question_text: str = Field(description="被向量化的那句问题原文")
    is_standard: bool
    score: float = Field(description="余弦相似度")


class RetrievalResult(BaseModel):
    query: str
    tier: HitTier
    top: list[RetrievalCandidate] = Field(default=[], description="按分数降序,top-k")
    answer: str | None = Field(default=None, description="命中时的标准答案,零改写")
    origin_ref: OriginRef | None = None
    #: 被区分性 token 护栏拦下时,缺了哪些 token(排序后的列表,给 trace 看)
    guard_missing: list[str] = []
    #: 被 light 模型复核否决时的理由(给 trace 看,是后续调阈值的依据)
    gate_reason: str | None = None


# ==========================================================================
# 6. API 出入参(S1 的 REST 契约;前端类型由 `make types` 生成,禁止手写)
# ==========================================================================


class DocumentFunnel(BaseModel):
    """漏斗计数:一眼看到"抽了多少、采纳了多少",即知识转化率(S1-plan §4 决策 4)。"""

    candidates: int = Field(default=0, description="抽取出的候选条数")
    pending: int = Field(default=0, description="还没裁决的候选")
    accepted: int = Field(default=0, description="已采纳(= 已发布,在库有索引)")
    rejected: int = 0


class DocumentOut(ORMModel):
    """文档列表/详情的一行。

    `stage` 是给界面用的**推导态**:文档表只存解析态(4 态),
    "待校对 / 抽取中 / 待采纳 / 已完成"由关联 Job 的状态推出来(S1-plan §8.4)。
    """

    id: uuid.UUID
    kb_id: uuid.UUID
    name: str
    file_type: str | None
    size_bytes: int | None
    parse_status: str
    parse_error: str | None
    stage: str = Field(description="uploaded/parsing/review_text/extracting/review_qa/done/failed")
    parse_job_id: uuid.UUID | None = None
    extract_job_id: uuid.UUID | None = None
    parse_stats: ParseStats | None = None
    funnel: DocumentFunnel = DocumentFunnel()
    created_at: datetime
    updated_at: datetime


class UploadResult(BaseModel):
    """上传即建 Job:前端拿到 job_id 就能直接轮询进度条,不用再问一次。"""

    document_id: uuid.UUID
    source_id: uuid.UUID
    job_id: uuid.UUID


class ReviewTextOut(BaseModel):
    """校对页要的一切:文本 + 页尺寸(bbox 换算)+ 是否已经校对过。"""

    document_id: uuid.UUID
    source: str = Field(description="paged.md(原始解析) 或 reviewed.md(已校对过)")
    text: str = Field(description="图片路径**已改写**成文件服务 URL,可直接渲染")
    pages: list[PageInfo]
    images: list[str] = []
    reviewed: bool = Field(description="是否存在 reviewed.md")


class ReviewTextUpdate(BaseModel):
    """保存校对结果。永不覆盖 paged.md —— 原始解析件留着可对比。"""

    text: str = Field(min_length=1)


class ConfirmExtractResult(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID


class RejectRequest(BaseModel):
    """不采纳必须填理由:它是下一轮调 prompt 的原始素材。"""

    note: str = Field(min_length=1, max_length=1000)


class ExactQaItemOut(ORMModel):
    """正式 QA 列表的一行(**不带长答案正文**,S1-plan §4 决策 5:列表轻详情重)。"""

    id: uuid.UUID
    kb_id: uuid.UUID
    standard_question: str
    keywords: list[str]
    similar_count: int = 0
    status: str
    index_faces: int = Field(default=0, description="索引面行数(标准问 + 相似问)")
    source_staging_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ExactQaItemDetail(ExactQaItemOut):
    answer: str
    similar_questions: list[str]
    origin_ref: OriginRef | None = None
