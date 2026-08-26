"""M3 切分:块序列 → 切片。★ 整个 S2 的质量地基。

四条规则(出处 V2 §3-chunk):
    1. 按标题层级切:每个章节自成一片,超长再按 token 二次切
    2. 二次切**只在句子边界下刀** —— 切出半句话是最难查的质量问题
    3. **图表块整块不切**,并与前后各一段正文合成一个切片(孤立描述语义太薄)
    4. 每片带 heading_path / seq / 起始页 / bbox

图表在正文里先放占位符 `{{FIGURE:<img>}}`,describe 步骤再把它换成
`[image description] …` + 图片链接两行。这样做的好处:切分与描述解耦 ——
描述换了词,切分结果一个字都不变。
"""

import re

import tiktoken

from app.config import settings
from app.schemas.document import Block, Chunk, Figure, ParseOutput

#: 图表占位符 —— describe 步骤按这个找替换点
FIGURE_PLACEHOLDER = "{{FIGURE:%s}}"

#: 句子边界:句末标点(允许后面跟一个引号/括号)+ 空白。
#: 🩸 `(?<=[.!?;:][”"')\]])` 这一支是实测补的:原文里 `… 2020.”` 这种收尾会让
#: 纯 `(?<=[.!?;:])` 匹配不上,于是两段被粘成"一句"。
#: 🩸 末尾那支**只放全角标点**:它的 `\s*` 是零宽的 —— 写成 ASCII 的话
#: 任何 ASCII 冒号后面都会下刀,`http://127.0.0.1:8766/x.html` 会被切成三段。
#: ASCII 标点由前面那支负责,它要求后面必须有空白,不会误伤。
_SENTENCE_END = re.compile(
    r"(?:(?<=[.!?;:])|(?<=[.!?;:][”\"')\]]))\s+(?=[A-Z(\[\d“\"])|(?<=[。！？；：])\s*"
)

#: 段落边界 —— 结构上的句子边界,永远优先于标点判断
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n+")

#: 全角句读 —— 在它后面断句时,拼回去**不能加空格**(中文没有词间空格)
_CJK_ENDINGS = "。！？；："

_ENCODER = tiktoken.get_encoding("cl100k_base")


# ─── token 与句子 ─────────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    """按 embedding 模型的分词器数 token(cl100k_base)。"""
    return len(_ENCODER.encode(text))


def split_units(text: str) -> list[tuple[str, bool]]:
    """把文本切成 `(句子, 是否段首)` 单元 —— 装片时靠这个标记还原段落结构。

    先切段落是结构性保证:段落边界一定是句子边界,不依赖标点识别是否成功。
    """
    units: list[tuple[str, bool]] = []
    for raw in _PARAGRAPH_BREAK.split(text):
        para = raw.strip()
        if not para:
            continue
        parts = [s.strip() for s in _SENTENCE_END.split(para) if s and s.strip()]
        units.extend((sent, i == 0) for i, sent in enumerate(parts or [para]))
    return units


def _join_units(units: list[tuple[str, bool]]) -> str:
    """把单元拼回文本:段首前加空行,段内用空格;全角句读后直接相接。

    🩸 一律用空格拼会在中文句子里插进空格(实测 `接口编排执行失败:` 被切开后
    拼成 `失败: 接口…`),文本就和原文对不上了。
    """
    out = ""
    for sent, starts_para in units:
        if not out:
            out = sent
        elif starts_para:
            out += "\n\n" + sent
        else:
            out += ("" if out[-1] in _CJK_ENDINGS else " ") + sent
    return out


def pack_units(
    units: list[tuple[str, bool]], max_tokens: int, overlap_tokens: int
) -> list[str]:
    """把句子单元装进不超上限的片,相邻片带重叠,**段落结构保留**。

    Args:
        units: `split_units()` 的输出。
        max_tokens: 每片上限。
        overlap_tokens: 相邻片之间回退多少 token 作为重叠。

    Returns:
        片文本列表;**每片都以完整句子结尾**,段落之间仍是空行分隔。
    """
    packed: list[str] = []
    buf: list[tuple[str, bool]] = []
    buf_tokens = 0

    for unit in units:
        sent_tokens = count_tokens(unit[0])
        if buf and buf_tokens + sent_tokens > max_tokens:
            packed.append(_join_units(buf))
            # 回退若干整句作为重叠,不按 token 硬切(否则重叠部分是半句)
            tail: list[tuple[str, bool]] = []
            tail_tokens = 0
            for prev in reversed(buf):
                prev_tokens = count_tokens(prev[0])
                if tail_tokens + prev_tokens > overlap_tokens:
                    break
                tail.insert(0, prev)
                tail_tokens += prev_tokens
            buf, buf_tokens = tail, tail_tokens
        buf.append(unit)
        buf_tokens += sent_tokens

    if buf:
        packed.append(_join_units(buf))
    return packed


# ─── 分节 ─────────────────────────────────────────────────────────────────────

def split_sections(blocks: list[Block]) -> list[tuple[list[str], list[Block]]]:
    """按标题把块序列分节。

    🩸 **标题块本身留在该节正文的第一位**,不只写进 `heading_path`:
    `chunks.tsv` 是 `to_tsvector('simple', content)` 生成列(已定不改),
    只索引 `content` —— 标题文本不进 content,标题里的词就永远搜不到。

    Returns:
        `[(heading_path_含自身, 该节的块序列_首位是标题块), ...]`。
    """
    sections: list[tuple[list[str], list[Block]]] = []
    current_path: list[str] = []
    current_body: list[Block] = []

    for b in blocks:
        if b.is_heading:
            if current_body or current_path:
                sections.append((current_path, current_body))
            current_path = [*b.heading_path, b.text]
            current_body = [b]
        else:
            current_body.append(b)

    if current_body or current_path:
        sections.append((current_path, current_body))
    return _absorb_headline_only(sections)


def _absorb_headline_only(
    sections: list[tuple[list[str], list[Block]]],
) -> list[tuple[list[str], list[Block]]]:
    """只有标题、没有正文的章节不单独出片,标题文本顺延给下一节。

    🩸 两个都要满足,少一个就是 bug:
    ① **不出片** —— 多层目录式文档会产生一批 5–9 token 的"纯标题片",
       搜不到任何东西,还在向量空间里挤成一团(实测某份 20 页文档有 17 片这种);
    ② **文本不能丢** —— `chunks.tsv` 只索引 `content`,标题只留在下级的
       `heading_path` 里是不够的,那个短语会从关键词索引里彻底消失。
    """
    kept: list[tuple[list[str], list[Block]]] = []
    carry: list[str] = []

    for path, body in sections:
        if not any(not b.is_heading for b in body):
            carry.extend(b.text for b in body if b.text)
            continue
        if carry and body:
            head = body[0]
            body = [
                head.model_copy(update={"text": "\n\n".join([*carry, head.text])}),
                *body[1:],
            ]
            carry = []
        kept.append((path, body))

    return kept


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

def _figure_of(block: Block) -> Figure:
    """把图表块转成切片里的 figure 记录。"""
    return Figure(
        kind=block.figure_kind or "image",
        img=block.img_path or "",
        source_caption=block.captions,
        source_footnote=block.footnotes,
        table_body=block.table_body,
        page_idx=block.page_idx,
        bbox=block.bbox,
    )


def _figure_content(block: Block, before: str, after: str) -> str:
    """图表切片的正文:前一段 + 占位符 + 后一段。"""
    placeholder = FIGURE_PLACEHOLDER % (block.img_path or "")
    return "\n\n".join(part for part in (before, placeholder, after) if part)


def _emit(
    chunks: list[Chunk],
    *,
    content: str,
    heading_path: list[str],
    page_idx: int,
    bbox: list[int] | None = None,
    figures: list[Figure] | None = None,
) -> None:
    """追加一片,顺手算 token 与 seq。"""
    if not content.strip():
        return
    chunks.append(
        Chunk(
            seq=len(chunks),
            content=content.strip(),
            heading_path=heading_path,
            token_count=count_tokens(content),
            page_idx=page_idx,
            bbox=bbox,
            figures=figures or [],
        )
    )


# ─── 公共函数 ─────────────────────────────────────────────────────────────────

def chunk_section(
    heading_path: list[str],
    body: list[Block],
    chunks: list[Chunk],
    *,
    max_tokens: int,
    overlap: int,
) -> None:
    """把一个章节切成若干片,追加到 `chunks`。

    图表块的处理:取它前面**最后一段**正文与后面**第一段**正文,三者合成一片;
    被借走的正文不再单独出片(避免同一段话在两片里各出现一次)。
    """
    pending: list[Block] = []  # 还没出片的正文块

    def flush(keep_last: bool) -> None:
        """把累积的正文出片;`keep_last` 表示留最后一段给紧随其后的图表。"""
        blocks = pending[:-1] if keep_last and len(pending) > 1 else pending
        if keep_last and len(pending) == 1:
            blocks = []
        # 🩸 剩下的只有标题时不能单独出片:章节形如 [标题, 正文, 图] 时,留一段给图会
        # 把标题孤零零刷成一片(实测 4 token,搜不到东西)。让它跟着图走。
        if keep_last and blocks and all(b.is_heading for b in blocks):
            blocks = []
        if not blocks:
            return
        text = "\n\n".join(b.text for b in blocks if b.text)
        if text:
            for part in pack_units(split_units(text), max_tokens, overlap):
                _emit(chunks, content=part, heading_path=heading_path,
                      page_idx=blocks[0].page_idx, bbox=blocks[0].bbox)
        del pending[: len(blocks)]

    i = 0
    while i < len(body):
        block = body[i]

        # 🩸 代码块**逐字保留**:JSON 报文、API 响应、文件路径靠换行才读得懂,
        # 走句子切分会把换行拼成空格。自成一片,并粘上前面那段做上下文。
        if block.type == "code":
            flush(keep_last=True)
            before = "\n\n".join(b.text for b in pending if b.text)
            pending.clear()
            _emit(chunks, content="\n\n".join(p for p in (before, block.text) if p),
                  heading_path=heading_path, page_idx=block.page_idx, bbox=block.bbox)
            i += 1
            continue

        if not block.is_figure:
            pending.append(block)
            i += 1
            continue

        # 图表:先把前面的正文出片,只留最后一段跟图走
        flush(keep_last=True)
        # 没被刷走的都归这张图 —— 通常就是紧邻的那一段,标题被留下时也一并带上
        before = "\n\n".join(b.text for b in pending if b.text)
        pending.clear()

        after = ""
        if i + 1 < len(body) and not body[i + 1].is_figure:
            after = body[i + 1].text
            i += 1  # 后一段被借走,不再单独出片

        _emit(chunks, content=_figure_content(block, before, after),
              heading_path=heading_path, page_idx=block.page_idx,
              bbox=block.bbox, figures=[_figure_of(block)])
        i += 1

    flush(keep_last=False)


def build_chunks(
    cleaned: ParseOutput,
    *,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """把清洗后的块序列切成切片序列(seq 从 0 连续)。

    Args:
        cleaned: clean 步骤的产物。
        max_tokens: 每片 token 上限,默认取 `DOC_RAG_CHUNK_MAX_TOKENS`。
        overlap: 相邻片重叠 token,默认取 `DOC_RAG_CHUNK_OVERLAP`。

    Returns:
        切片列表。
    """
    limit = max_tokens if max_tokens is not None else settings.doc_rag_chunk_max_tokens
    lap = overlap if overlap is not None else settings.doc_rag_chunk_overlap
    chunks: list[Chunk] = []
    for heading_path, body in split_sections(cleaned.blocks):
        chunk_section(heading_path, body, chunks, max_tokens=limit, overlap=lap)
    return chunks
