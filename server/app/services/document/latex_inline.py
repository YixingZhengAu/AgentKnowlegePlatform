"""行内 LaTeX 归一化:把 MinerU 判成"公式"的普通文字还原成人话。

**为什么需要**(2026-08-24 实测):MinerU 的公式检测会把 `−20 °C to +50 °C`
这类写法认成行内公式,交给公式识别模型输出 LaTeX:

    $- 2 0 ~ ^ { \\circ } \\mathsf { C }$

它对排版是忠实的(`°` 本来就是 `^\\circ`,数学模式下空格不算数),
但我们把它当**纯文本**存进库:`tsv` 会把 `2` 和 `0` 切成两个词,搜 "-20" 匹配不到;
生成时模型还可能把这串东西原样抄进答案。

**范围卡死两条**:
    1. 只处理**文本块里的行内 `$…$`**;
    2. **独立 `equation` 块一律不动** —— 那些是真公式,转成纯文本反而更糟。

拿不准的一律**原样保留** —— 归一化失败只是没改进,乱改会毁掉原文。
"""

import re

#: 行内公式:`$...$`,不跨行,长度设上限避免把整段吞掉
INLINE_MATH = re.compile(r"\$([^$\n]{1,200}?)\$")

#: 命令 → 明文。只收窄到产品文档里真会出现的那些
_COMMAND_MAP = {
    r"\circ": "°",
    r"\times": "×",
    r"\pm": "±",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\approx": "≈",
    r"\cdot": "·",
    r"\%": "%",
    r"\ ": " ",
    "~": " ",
}

#: 只是字体包装,去掉命令保留内容
_FONT_WRAPPERS = re.compile(r"\\(?:mathsf|mathrm|mathbf|mathit|text|textrm|mbox)\s*")

#: 归一化后仍然含这些,说明是真公式 —— 整段回退成原样
_REAL_MATH_MARKERS = re.compile(r"\\(?:frac|sqrt|sum|int|hat|bar|vec|begin|left|right)|[_^]")

#: 数字之间的多余空格(公式识别模型按位吐 token 造成的)
_DIGIT_GAP = re.compile(r"(?<=\d) (?=\d)")


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

def _strip_superscript_degree(body: str) -> str:
    """`^ { \\circ }` / `^\\circ` → `°`(上标只在度数这一种情况下能安全去掉)。"""
    body = re.sub(r"\^\s*\{\s*\\circ\s*\}", r"\\circ", body)
    return re.sub(r"\^\s*\\circ", r"\\circ", body)


def _strip_braces(body: str) -> str:
    """去掉单纯用于分组的花括号。"""
    return body.replace("{", " ").replace("}", " ")


def _apply_commands(body: str) -> str:
    """把已知命令替换成明文字符。"""
    for command, plain in _COMMAND_MAP.items():
        body = body.replace(command, plain)
    return body


def _tidy_spaces(text: str) -> str:
    """合并数字间空格、把符号贴回数字、按 SI 习惯摆放度数符号。"""
    while _DIGIT_GAP.search(text):  # "2 0 0" 要连着收
        text = _DIGIT_GAP.sub("", text)
    text = re.sub(r"\s+", " ", text)
    # 正负号贴住数字:"- 20" → "-20"
    text = re.sub(r"(?<=[-+−±])\s+(?=\d)", "", text)
    # SI 习惯:数值与 °C 之间留一个空格,° 与单位字母之间不留
    text = re.sub(r"\s*°\s*([CF])", r" °\1", text)
    text = re.sub(r"\s+([,.;:%])", r"\1", text)
    return text.strip()


# ─── 公共函数 ─────────────────────────────────────────────────────────────────

def normalize_inline_math(text: str) -> str:
    """把一段文本里的行内 `$…$` 归一化成普通文字。

    Args:
        text: 文本块正文(**不要传 equation 块**)。

    Returns:
        归一化后的文本;识别不了的公式原样保留(含 `$`)。
    """

    replaced = False

    def replace(match: re.Match[str]) -> str:
        nonlocal replaced
        body = _strip_superscript_degree(match.group(1))
        # 先判真公式:上标下标、分式、根号等一律不碰
        if _REAL_MATH_MARKERS.search(_FONT_WRAPPERS.sub("", body)):
            return match.group(0)
        body = _FONT_WRAPPERS.sub("", body)
        body = _apply_commands(_strip_braces(body))
        if "\\" in body:  # 还有没认识的命令 → 放弃,保留原样
            return match.group(0)
        plain = _tidy_spaces(body)
        if not plain:
            return match.group(0)
        replaced = True
        return plain

    out = INLINE_MATH.sub(replace, text)
    return _tidy_seams(out) if replaced else text


def _tidy_seams(text: str) -> str:
    """收拾"公式被换成文字"之后接缝处的标点。

    实测原案:原文写成 `$2 5 6 \\times 2 5 6 ,$ ,` —— 公式里外各有一个逗号,
    替换后变成 `256 × 256, ,`。只在**紧挨归一化结果**的位置动手,不碰其它正文。
    """
    text = re.sub(r"([,.;:])\s*\1+", r"\1", text)  # ", ," → ","
    text = re.sub(r"(?<=[\d°×±%])\s+([,.;:])", r"\1", text)  # "256 ." → "256."
    return re.sub(r"[ \t]{2,}", " ", text)
