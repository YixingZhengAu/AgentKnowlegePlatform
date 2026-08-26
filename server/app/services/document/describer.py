"""M4 图表描述 —— 整条摄取链**唯一调 LLM** 的步骤。

做的事:把切片正文里每个 `{{FIGURE:...}}` 占位符,换成模型看图写出的描述 + 图片链接。

    [table description] <模型撰写的描述,含行列维度与关键行数值>
    ![](images/<sha256>.jpg)

**只有方括号里的关键词是固定的**,描述正文 100% 由模型撰写;
原文 caption/footnote 与表格 HTML 只是喂给模型的输入,不要求原样出现在正文里
(它们结构化留档在 `Figure.source_caption` / `source_footnote`,供渲染与引用面板用)。

★ 描述写法是**三段式**(沙箱 Step 4 定稿):LEAD 定主题 → COVERAGE 列实体 → VALUES 铺数值。
理由:一条描述同时服务四个消费者,它们的胃口互相冲突 ——
向量检索要短而切题、`tsv` 要穷尽字面量、cross-encoder 只看得到前 ~400 token、
生成要准确数值。四者不是取舍关系,是**排序**关系,所以按重要性从前往后铺。
"""

import asyncio

from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import get_logger
from app.providers import ImagePart, TextPart, image_part
from app.schemas.document import Chunk, Figure
from app.services.document import storage
from app.services.document.chunker import FIGURE_PLACEHOLDER
from app.services.document.llm import parse_structured

log = get_logger(__name__)

#: 关键词固定,描述正文全由模型写
KEYWORD = {
    "table": "[table description]",
    "image": "[image description]",
    "chart": "[image description]",
}

MAX_TOKENS = 4000


class FigureDescription(BaseModel):
    """模型对一张图/表的输出。"""

    description: str = Field(description="Three-part description: lead, coverage, values.")
    truncated: bool = Field(description="True only when a large table was not covered in full.")


def _system_prompt() -> str:
    """三段式描述规则。行数阈值由配置注入,所以做成函数而不是常量。"""
    rows = settings.doc_rag_table_exhaustive_rows
    return f"""\
You describe one figure or table from a technical document. The description is indexed \
for retrieval and is read back to a user who cannot see the image, so it must make the \
figure FINDABLE, not merely transcribed.

Users never ask "what tables are there". They ask a question. Write the description so \
that it reads like the answer to the questions this figure can answer.

Write the description in exactly three parts, in this order, as continuous plain prose \
(no headings, no bullet lists, no preamble such as "This image shows"). \
The part names below are instructions to you, not text for the reader: the words \
LEAD, COVERAGE and VALUES must never appear in the description you write, and the \
three parts must run together as ordinary sentences with no separators between them:

1. LEAD — one or two sentences naming the subject of the figure and what kind of \
information it gives about that subject. Think of the question a reader would ask to \
arrive at this figure, then write the LEAD as the opening of the ANSWER to it. \
This is the most important sentence in the description: a reranker may see nothing but \
the opening, so the topic must be decided here. Make it specific enough that a sibling \
figure in the same document could not have the same opening.
   Write it as a plain declarative statement. Never phrase it as a question, and never \
use a framing formula such as "This table answers", "Which ... ?" or "What are ... ?". \
Never open with the shape of the table ("has N rows and M columns"), and never simply \
repeat the section heading.

2. COVERAGE — a short clause naming the ENTITIES the figure covers: every model number, \
product name, standard number, region, method name or certificate reference that \
appears in it. Exact identifiers are what keyword search matches on, so they must \
appear early, not only deep in the value list. List the entities themselves — not the \
column headers, which belong in part 3.

3. VALUES — the full detail. For a table: every data row, with its values. For an image \
or chart: the relationships and trends that are VISIBLE in the plot, plus every printed \
label, axis name, legend entry and value. End with the shape of the table if it is a \
table ("N data rows, M columns").

Vocabulary — how to make it findable without inventing anything:
- The wording of the LEAD may draw only on the section heading, the caption, the \
footnote, the surrounding text, and the table's own column headers. Never use outside \
knowledge about the subject.
- You may name the KIND of quantity a printed unit represents: AUD is a price or cost, \
years is a duration, kWh is a capacity, ms is a time. That is reading the unit, not \
adding a fact.
- You may state a relationship that is visibly true in the plot ("the YOLOv3 points sit \
at lower inference time at comparable AP"). You may NOT state what it means, why it \
matters, or which option is better.
- Never invent numbers, labels, units, rows or conclusions. Keep every identifier, \
model name, part number and unit exactly as printed.

Rules for the VALUES part of a table:
- If the table has {rows} data rows or fewer, cover EVERY row — none may be skipped.
- If it has more rows than that, cover the most significant ones and state in the \
description: "This table has N rows; this description covers the M most significant \
rows." Set truncated to true in that case only. Significant does NOT mean "the first \
M rows": always include the first rows, the LAST rows, and any row carrying a distinct \
value, name or output shape. A trailing summary, total or output row is never dropped.
- An OCR-derived HTML rendering of the table may be supplied. It is a hint only and is \
known to drop or misalign rows. The image is authoritative: when they disagree, or when \
the HTML has fewer rows than the image, follow the image.
"""


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

def _surrounding_text(chunk: Chunk) -> str:
    """切片正文去掉占位符 —— 就是图表前后各一段正文,给模型当上下文。"""
    text = chunk.content
    for fig in chunk.figures:
        text = text.replace(FIGURE_PLACEHOLDER % fig.img, " ")
    return text.strip()


def _user_content(chunk: Chunk, fig: Figure, document_id: str) -> list[TextPart | ImagePart]:
    """拼图文混排的 user message:原文线索 + 上下文正文(+ 表格 HTML)+ 截图。"""
    lines = [f"Figure kind: {fig.kind}"]
    if chunk.heading_path:
        lines.append(f"Section: {chunk.heading_text}")
    if fig.source_caption:
        lines.append("Caption in the document: " + " ".join(fig.source_caption))
    if fig.source_footnote:
        lines.append("Footnote in the document: " + " ".join(fig.source_footnote))
    if fig.table_body:
        lines.append(
            "OCR-derived table HTML (hint only, may drop or misalign rows — "
            f"the image wins):\n{fig.table_body}"
        )
    if text := _surrounding_text(chunk):
        lines.append(f"Surrounding text:\n{text}")

    text_part: TextPart = {"type": "text", "text": "\n\n".join(lines)}
    return [text_part, image_part(storage.read_image(document_id, fig.img))]


async def _describe_one(
    chunk: Chunk, fig: Figure, document_id: str, sem: asyncio.Semaphore
) -> int:
    """描述一张图表,结果就地写回 `fig`。返回本次消耗的 token 总数。"""
    async with sem:
        parsed, result = await parse_structured(
            FigureDescription,
            instructions=_system_prompt(),
            user_content=_user_content(chunk, fig, document_id),
            tier="light",
            max_tokens=MAX_TOKENS,
        )
    fig.description = parsed.description.strip()
    fig.truncated = parsed.truncated
    return result.usage.total_tokens


def _apply(chunk: Chunk) -> None:
    """把正文里的占位符换成"关键词 + 描述 / 图片链接"两行。"""
    for fig in chunk.figures:
        if not fig.description:
            continue
        chunk.content = chunk.content.replace(
            FIGURE_PLACEHOLDER % fig.img,
            f"{KEYWORD[fig.kind]} {fig.description}\n![]({fig.img})",
        )


# ─── 公共函数 ─────────────────────────────────────────────────────────────────

async def describe(chunks: list[Chunk], document_id: str) -> tuple[int, int]:
    """给所有缺描述的图表补上描述,并替换正文占位符(就地修改 `chunks`)。

    **逐块幂等**:已有描述的图表跳过 —— Job 重跑不重新花钱。
    `DOC_RAG_DESCRIBE_FIGURES=false` 时只做占位符清理,一次模型都不调。

    Args:
        chunks: 切片列表,就地修改。
        document_id: 图片相对路径基于它。

    Returns:
        `(描述的图表数, 消耗的 token 数)`。
    """
    todo = [(c, f) for c in chunks for f in c.figures if not f.description]
    if not settings.doc_rag_describe_figures:
        log.info("document_describe_skipped", figures=len(todo))
        todo = []

    tokens = 0
    if todo:
        sem = asyncio.Semaphore(settings.doc_rag_describe_concurrency)
        for used in await asyncio.gather(
            *(_describe_one(c, f, document_id, sem) for c, f in todo)
        ):
            tokens += used
        log.info("document_described", figures=len(todo), tokens=tokens)

    for chunk in chunks:
        _apply(chunk)
    return len(todo), tokens
