"""M2 清洗:去掉 MinerU 没标出来的残留噪声。

分工要说清:**页眉页脚页码优先靠 MinerU 的噪声块标注**(那一步在 parse 里做完了),
本步只处理它漏掉的残留:
    1. 跨页重复的短文本(生成式 PDF 里没有,扫描件/带页眉的文档里会有)
    2. 纯页码样式的文本块(如 "3"、"- 3 -"、"Page 3 of 12")
    3. 正文内部的连续空行、行尾空白
    4. **行内 LaTeX 归一化**(见 `latex_inline.py`):MinerU 会把 `−20 °C` 这类
       普通文字判成公式并输出 LaTeX,不还原的话检索搜不到、答案会带乱码

🩸 丢弃一律计入 `DropStats`。
"""

import re
from collections import defaultdict

from app.schemas.document import Block, ParseOutput
from app.services.document.latex_inline import normalize_inline_math

#: 跨这么多页出现同一段短文本,判为页眉/页脚
REPEAT_PAGE_THRESHOLD = 3

#: 只有短文本才可能是页眉页脚 —— 长段落跨页重复通常是真内容(如免责声明)
REPEAT_MAX_CHARS = 80

#: 纯页码样式
PAGE_NUMBER_RE = re.compile(
    r"^(?:[-–—\s]*\d+[-–—\s]*|page\s+\d+(?:\s+of\s+\d+)?)$", re.IGNORECASE
)


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """压掉连续空行与行尾空白(不动正文语义)。"""
    out: list[str] = []
    for line in (raw.rstrip() for raw in text.splitlines()):
        if not line and out and not out[-1]:
            continue  # 连续空行只留一个
        out.append(line)
    return "\n".join(out).strip()


def _running_headers(blocks: list[Block]) -> set[str]:
    """找出跨页重复的短文本 —— 页眉页脚的特征。"""
    pages_by_text: dict[str, set[int]] = defaultdict(set)
    for b in blocks:
        text = b.text.strip()
        if b.type == "text" and not b.is_heading and 0 < len(text) <= REPEAT_MAX_CHARS:
            pages_by_text[text].add(b.page_idx)
    return {t for t, pages in pages_by_text.items() if len(pages) >= REPEAT_PAGE_THRESHOLD}


# ─── 公共函数 ─────────────────────────────────────────────────────────────────

def clean(parsed: ParseOutput) -> ParseOutput:
    """清洗块序列,返回新的 `ParseOutput`(丢弃计入同一份 stats)。

    Args:
        parsed: parse 步骤的产物。

    Returns:
        清洗后的 `ParseOutput`;`stats.dropped_by_type` 里会多出
        `running_header` / `page_number_text` 两类计数。
    """
    stats = parsed.stats.model_copy(deep=True)
    headers = _running_headers(parsed.blocks)
    kept: list[Block] = []

    for b in parsed.blocks:
        if b.is_figure:
            kept.append(b)
            continue

        text = _normalize_text(b.text)
        # equation 块是真公式,一个字符都不动;只归一化 text 块里的行内 $…$
        if b.type == "text":
            text = normalize_inline_math(text)
            if not b.is_heading:
                if text in headers:
                    stats.drop("running_header")
                    continue
                if PAGE_NUMBER_RE.match(text):
                    stats.drop("page_number_text")
                    continue
            if not text:
                stats.empty_text_blocks += 1
                continue

        kept.append(b.model_copy(update={"text": text}))

    return ParseOutput(
        doc_name=parsed.doc_name,
        page_count=parsed.page_count,
        blocks=kept,
        stats=stats,
        extra_fields_seen=parsed.extra_fields_seen,
    )
