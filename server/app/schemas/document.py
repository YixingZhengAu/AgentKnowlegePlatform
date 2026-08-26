"""S2 文档 RAG 的数据契约:MinerU 块 → 结构化块 → 切片 → 接口出入参。

本域**不复用** `app/schemas/exact_qa.py`:S1 只声明了它自己要用的字段,
漏了 `image_footnote` / `chart_footnote`(实测 MinerU 会给,S1 静默丢掉)。
S2 的图表描述要把所有原文线索喂给模型,所以这里**字段全收**。

四层数据:
    MineruBlock   MinerU content_list 里的一个块(外部输入,字段宽松)
    Block         我们加工后的块(补了 heading_path,噪声已判定)
    Chunk         切片(进 embedding / tsv / staging 的最终形态)
    *Out          接口出参
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

# ─── 落盘位置(与 S1 逐字相同,不是巧合)──────────────────────────────────────

#: 🩸 这三个常量必须与 `app/schemas/exact_qa.py` 的同名常量保持一致:
#: `app/api/files.py` 的图片出口是**按 document_id 寻址、不分域**的,
#: 它读的是 S1 的 `storage.images_dir()`。S2 沿用同一套目录,就能白拿那个出口;
#: 改成别的目录就得再开一个接口(共享文件,要协调)—— 不值得。
PARSE_SUBDIR = "parses"
IMAGES_SUBDIR = "images"
SOURCES_SUBDIR = "sources"

#: 解析产物文件名(本域自己的,S1 没有对应物)
PARSED_NAME = "parsed.json"
CHUNKS_NAME = "chunks.json"

FILE_SERVICE_URL_FMT = "/api/files/parses/{document_id}/images/{name}"


def image_url(document_id: str, name: str) -> str:
    """切图的对外 URL。库里只存相对路径,URL 只在接口出口拼。"""
    return FILE_SERVICE_URL_FMT.format(document_id=document_id, name=name)


# ─── 块类型集合(判断收敛到这几个常量,别处不写字面量)────────────────────────

#: 内容块:进正文的
#: 🩸 `code` 是 2026-08-25 沙箱实测补的:一份技术文档里有 7 个 code 块(JSON 报文、
#: API 响应、文件路径),原先落在"未知类型"分支被整体丢掉 —— 而这些恰恰是用户
#: 会拿去搜的字符串。当初"未知类型只计数不抛异常"的设计就是为了让这种缺口浮出来。
CONTENT_BLOCK_TYPES = frozenset({"text", "table", "image", "chart", "equation", "code"})

#: 已知噪声块:页眉页脚页码等,丢弃但要留痕
NOISE_BLOCK_TYPES = frozenset({"aside_text", "page_number", "header", "footer", "discarded"})

#: 已知类型全集 —— 集合外的类型按噪声丢,**不抛异常**(S1 血泪:收窄成 Literal
#: 会让 MinerU 冒出的新类型把整篇解析打成 failed)
KNOWN_BLOCK_TYPES = CONTENT_BLOCK_TYPES | NOISE_BLOCK_TYPES

#: 图表块:整块不切,且要走 describe 的
FIGURE_BLOCK_TYPES = frozenset({"image", "chart", "table"})

BBox1000 = Annotated[list[int], Field(min_length=4, max_length=4)]
"""bbox = [x0, y0, x1, y1],每轴各自归一化到 0–1000 的整数,原点左上。"""

FigureKind = Literal["image", "chart", "table"]

#: staging_items.item_type 取值(见 app/models/ingest.py 的 ITEM_TYPES)
ITEM_TYPE = "chunk"


# ─── 第一层:MinerU 原始块 ───────────────────────────────────────────────────

class MineruBlock(BaseModel):
    """content_list.json 里的一个块。

    `extra="allow"`:MinerU 给了但我们没声明的字段一律留着,
    避免"新字段静默消失"这类只能靠肉眼发现的问题。
    """

    model_config = {"extra": "allow"}

    type: str  # 故意不用 Literal,理由见 KNOWN_BLOCK_TYPES
    page_idx: int = Field(ge=0, description="页序号,0 起")
    bbox: BBox1000 | None = None

    # text / equation / chart
    text: str | None = None
    text_level: int | None = Field(default=None, description="1=一级标题;正文为 None")
    text_format: str | None = Field(default=None, description="equation 为 'latex'")
    content: str | None = Field(default=None, description="chart 文本;pipeline 下恒空")

    # 切图相对路径:images/<sha256>.jpg
    img_path: str | None = None

    # 三组 caption + 三组 footnote(S1 漏了 image/chart 的 footnote,这里补全)
    image_caption: list[str] = []
    image_footnote: list[str] = []
    chart_caption: list[str] = []
    chart_footnote: list[str] = []
    table_caption: list[str] = []
    table_footnote: list[str] = []

    table_body: str | None = Field(default=None, description="表格 HTML,不进 content")

    # code(sub_type: code / algorithm)
    code_body: str | None = Field(default=None, description="代码块正文,当作 text 收")
    code_caption: list[str] = []
    code_footnote: list[str] = []
    sub_type: str | None = None

    @property
    def is_content(self) -> bool:
        """是否进正文。"""
        return self.type in CONTENT_BLOCK_TYPES

    @property
    def is_unknown_type(self) -> bool:
        """MinerU 冒出的新类型:不报错,但要在日志与统计里看得见。"""
        return self.type not in KNOWN_BLOCK_TYPES

    @property
    def is_heading(self) -> bool:
        """标题块 = text 且带 text_level。"""
        return self.type == "text" and self.text_level is not None

    @property
    def captions(self) -> list[str]:
        """四组 caption 合一(一个块只会有一组非空)。"""
        return [*self.image_caption, *self.chart_caption,
                *self.table_caption, *self.code_caption]

    @property
    def footnotes(self) -> list[str]:
        """四组 footnote 合一。"""
        return [*self.image_footnote, *self.chart_footnote,
                *self.table_footnote, *self.code_footnote]

    @property
    def is_empty_figure(self) -> bool:
        """退化图表块:既没有切图也没有表格 HTML,什么都描述不出来。

        实测 MinerU 会吐出这种块(`type=table`,`img_path=''`,无 `table_body`)。
        留着它 describe 会拿不到图、正文里还会留一个死占位符。
        """
        return self.type in FIGURE_BLOCK_TYPES and not (self.img_path or self.table_body)


# ─── 第二层:加工后的块 ─────────────────────────────────────────────────────

class Block(BaseModel):
    """清洗后的内容块,已补上标题路径。

    `heading_path` **不是 MinerU 给的** —— MinerU 只给 `text_level`,
    路径由 `parser.py` 遍历块序列时用一个栈推导出来。
    """

    type: str
    page_idx: int
    bbox: BBox1000 | None = None
    heading_path: list[str] = Field(default_factory=list, description="不含自身标题")
    text_level: int | None = Field(default=None, description="标题层级;正文为 None")

    text: str = ""
    img_path: str | None = None
    captions: list[str] = []
    footnotes: list[str] = []
    table_body: str | None = None

    @property
    def is_heading(self) -> bool:
        """标题块 —— 切分的边界靠它。"""
        return self.text_level is not None

    @property
    def is_figure(self) -> bool:
        """图表块:整块不切,且要走 describe。"""
        return self.type in FIGURE_BLOCK_TYPES

    @property
    def figure_kind(self) -> FigureKind | None:
        """图表种类;非图表块返回 None。"""
        return self.type if self.is_figure else None  # type: ignore[return-value]


# ─── 第三层:切片 ───────────────────────────────────────────────────────────

class Figure(BaseModel):
    """切片里的一张图/表,对应 `chunks.meta.figures[]` 的一项。

    `description` 在 describe 步骤才填;`source_caption` / `source_footnote`
    是原文线索 —— **只作为喂给模型的输入留档,不要求原样出现在 `content` 里**。
    """

    kind: FigureKind
    img: str = Field(description="相对路径 images/<sha256>.jpg")
    description: str | None = None
    truncated: bool = False
    source_caption: list[str] = []
    source_footnote: list[str] = []
    table_body: str | None = Field(default=None, description="给模型当提示,不进 content")
    page_idx: int
    bbox: BBox1000 | None = None


def chunk_is_retired(meta: dict | None) -> bool:
    """这条切片是不是**退休行** —— 已被文档的新一版取代,只为历史引用而留。

    判据放在 `chunks.meta.retired` 而不是 `status` 上:`status='disabled'` 有两个来源,
    人手点的"禁用"(可逆)和重新发布时的退休(不可逆),前端要能分开显示。

    Args:
        meta: `chunks.meta`。

    Returns:
        是退休行则为 True。
    """
    return bool((meta or {}).get("retired"))


def embed_input(heading_path: str | None, content: str) -> str:
    """embedding 的输入文本 —— **唯一出处**。

    🩸 发布时(`indexer`)与重新启用时(`api/document.py::enable_chunk`)必须用**同一个拼法**:
    差一个换行就是差一个向量,而这种漂移不报错,只是让那条切片的召回行为悄悄变了。

    Args:
        heading_path: 标题路径,如 `Handbook > 4. Warranty Policy`;没有就传 None。
        content: 切片正文。

    Returns:
        拼好的 embedding 输入。
    """
    return f"{heading_path or ''}\n\n{content}".strip()


def short_heading(heading_path: list[str], keep: int = 2) -> str:
    """标题路径的短展示形态:**按层级砍,不按字符砍**。

    🩸 早先各页面用 `heading_text[-50:]` 截断,会从单词中间切开
    (`Battery Storage` → `ery Storage`),看起来像解析出了问题。
    最有信息量的是末几级,所以保留末 `keep` 级,前面用省略号顶掉。
    """
    if len(heading_path) <= keep:
        return " > ".join(heading_path)
    return "… > " + " > ".join(heading_path[-keep:])


class Chunk(BaseModel):
    """一条切片 —— 发布后就是 `chunks` 表的一行。"""

    seq: int = Field(ge=0, description="文档内顺序;合并后不重排,允许留空洞")
    content: str
    heading_path: list[str] = []
    token_count: int = 0
    page_idx: int = Field(ge=0, description="起始页")
    bbox: BBox1000 | None = None
    figures: list[Figure] = []

    @property
    def has_figure(self) -> bool:
        """含图表 → 需要 describe。"""
        return bool(self.figures)

    @property
    def heading_text(self) -> str:
        """标题路径的展示形态,也是 embedding 输入的前缀。"""
        return " > ".join(self.heading_path)

    @property
    def embed_text(self) -> str:
        """embedding 的输入 = 标题路径 + 正文(V2 §4 已定,本期无 summary)。"""
        return embed_input(self.heading_text, self.content)

    def as_payload(self) -> dict:
        """落 `staging_items.payload` 的形状。

        🩸 **必须自成一体**:发布与"合并相邻"都是拿 `payload` 反过来
        `Chunk.model_validate()` 的,少一个必填字段(比如 `page_idx`)当场就炸。
        `origin_ref` 那份页码是给审核台跳原文用的,不是这里的替代品。
        """
        return {
            "seq": self.seq,
            "content": self.content,
            "heading_path": self.heading_path,
            "token_count": self.token_count,
            "page_idx": self.page_idx,
            "bbox": self.bbox,
            "figures": [f.model_dump() for f in self.figures],
        }


# ─── 统计与产物 ─────────────────────────────────────────────────────────────

class DropStats(BaseModel):
    """丢弃留痕 —— 按类型计数,进日志与 `documents.meta`。

    🩸 丢东西不留痕是最难查的一类问题:用户只会说"手册里明明有这句话"。
    """

    dropped_by_type: dict[str, int] = Field(default_factory=dict)
    unknown_types: dict[str, int] = Field(default_factory=dict)
    empty_text_blocks: int = 0

    def drop(self, block_type: str, *, unknown: bool = False) -> None:
        """记一次丢弃。"""
        self.dropped_by_type[block_type] = self.dropped_by_type.get(block_type, 0) + 1
        if unknown:
            self.unknown_types[block_type] = self.unknown_types.get(block_type, 0) + 1

    @property
    def total(self) -> int:
        """丢弃总数。"""
        return sum(self.dropped_by_type.values())


class ParseOutput(BaseModel):
    """parse 步骤的产物(也是 clean 的输入与输出)。"""

    doc_name: str
    page_count: int = 0
    blocks: list[Block] = []
    stats: DropStats = Field(default_factory=DropStats)
    extra_fields_seen: dict[str, int] = Field(
        default_factory=dict, description="MinerU 给了但契约未声明的字段名 → 出现次数"
    )

    @model_validator(mode="after")
    def _page_count_from_blocks(self) -> "ParseOutput":
        """页数没显式给时,从块的最大 page_idx 推导。"""
        if not self.page_count and self.blocks:
            self.page_count = max(b.page_idx for b in self.blocks) + 1
        return self


def declared_field_names() -> set[str]:
    """`MineruBlock` 显式声明的字段名集合。"""
    return set(MineruBlock.model_fields)


def unknown_extra_fields(raw_blocks: list[dict[str, Any]]) -> dict[str, int]:
    """统计原始块里出现过、但契约未声明的字段名。

    Args:
        raw_blocks: content_list 的原始 dict 列表。

    Returns:
        字段名 → 出现次数。空 dict 表示契约已覆盖全部字段。
    """
    declared = declared_field_names()
    seen: dict[str, int] = {}
    for raw in raw_blocks:
        for key in raw:
            if key not in declared:
                seen[key] = seen.get(key, 0) + 1
    return seen


# ─── 接口出入参 ─────────────────────────────────────────────────────────────
#
# 🩸 **类名不许与别的域撞车**:FastAPI 用类名当 OpenAPI 的 component key,
# 一撞就退化成全限定名(`app__schemas__exact_qa__UploadResult`),
# 于是**别人的**前端 `components['schemas']['UploadResult']` 当场失效。
# 实测踩过一次:S2 起初也叫 `DocumentOut` / `UploadResult`,把 S1 前端打断了。

#: 文档在界面上的阶段 —— 由 `documents.parse_status` 与关联 Job 的状态推导,
#: **不新增列**(与 S1 同一条纪律:少一处会不同步的状态)
DocumentStage = Literal["pending", "ingesting", "review", "published", "failed"]


class DocumentSummary(ORMModel):
    """文档列表的一行。"""

    id: uuid.UUID
    name: str
    size_bytes: int | None = None
    parse_status: str
    parse_error: str | None = None
    created_at: datetime

    stage: DocumentStage = "pending"
    ingest_job_id: uuid.UUID | None = None
    chunk_count: int = 0
    page_count: int | None = None


class IngestSubmitted(BaseModel):
    """上传接口的回执 —— 三个 id 前端都要用(轮询 job、跳审核台)。"""

    document_id: uuid.UUID
    source_id: uuid.UUID
    job_id: uuid.UUID


class ChunkMergeResult(BaseModel):
    """合并相邻切片的结果。"""

    item_id: uuid.UUID
    merged_item_id: uuid.UUID
    token_count: int


class ChunkDetail(BaseModel):
    """点开引用 `[n]` 时回显的**全量原文 + 元数据**(分册 3 §6)。

    🩸 **不在 `message_citations` 里存全文副本**,点开时按 `ref_id` 实时读库。
    这样做安全的前提是被引用过的切片**不物理删**(下线是软标志,归 S2-4),
    所以 `ref_id` 永远解析得到。
    """

    id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    seq: int
    content: str
    heading_path: str | None = None
    page_idx: int | None = None
    token_count: int | None = None
    figures: list[Figure] = []
    #: 这条切片已被文档的新一版取代,只为历史引用还读得到而留着。
    #: 它不会再出现在任何检索结果里
    retired: bool = False


# 名字刻意不叫 `ChunkRow`:那是 `app.models.Chunk` 在各文件里的惯用别名,撞了会很难读
class PublishedChunk(BaseModel):
    """切片管理页的一行 —— 已发布的正式行(不是待审候选)。"""

    id: uuid.UUID
    seq: int
    content: str
    heading_path: str | None = None
    page_idx: int | None = None
    token_count: int | None = None
    status: Literal["active", "disabled"]
    #: 有没有向量。禁用会清空 embedding,所以它同时是"能不能被召回"的直观证据
    embedded: bool
    figure_count: int = 0
    #: 已被文档的新一版取代,只为历史引用而留。**判据用这个,不要用 `seq < 0`** ——
    #: `seq` 给出去的时候已经还原成它当初的编号了(负号区是内部实现)
    retired: bool = False


class ChunkStatusResult(BaseModel):
    """启用/禁用的回执。启用要重算 embedding,所以它不是瞬时操作。"""

    id: uuid.UUID
    status: Literal["active", "disabled"]
    embedded: bool


class ReingestSubmitted(BaseModel):
    """单文档重跑的回执。"""

    document_id: uuid.UUID
    job_id: uuid.UUID
    #: 重跑期间仍然对外可召回的旧切片数(新的一批发布前不下线,见 S2-4 分册 §4)
    live_chunks: int


class SearchRecall(BaseModel):
    """两条腿各召回多少、融合后剩多少 —— 调试台最上面那一行。"""

    vector: int
    fts: int
    fused: int


class SearchHit(BaseModel):
    """调试台的一条结果。`rank_*` 为空 = **这条腿没召回它**,那正是要看的东西。"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    doc_name: str
    seq: int
    page_idx: int
    heading_path: str | None = None
    #: 重排分(cross-encoder logit,可能是负数);guard 策略失灵时是召回序
    score: float
    #: 在向量腿里的名次(1 起),没被这条腿召回则为 None
    rank_vector: int | None = None
    #: 在全文腿里的名次(1 起),没被这条腿召回则为 None
    rank_fts: int | None = None
    figures: int = 0
    content: str


class SearchResult(BaseModel):
    """`GET /search` 的响应 —— 检索调试台的全部数据来源。"""

    query: str
    recall: SearchRecall
    hits: list[SearchHit]
    #: 重排跑过没有(召回为空时不跑)
    reranked: bool = False
    #: 🩸 **重排整题失灵,已退回召回名次**(`guard` 策略,阈值 `DOC_RAG_RERANK_GUARD`)。
    #: 调试台上这是最该看见的一件事:此时列表的顺序**不是**重排给的,而是 RRF 名次
    guard_fallback: bool = False
    #: 命中为空。用来把"两条腿都没召回"与"召回了但都被重排压下去"分开显示
    empty: bool = False
