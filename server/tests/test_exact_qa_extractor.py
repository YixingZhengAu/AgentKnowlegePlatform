"""S1 抽取层过滤逻辑的离线单测:quote 逐字定位与修复、硬约束丢弃、页码/bbox 回填。

这一层的失败模式全是"静默"的:quote 修复写错就少一条知识,页码回填写错就
审核台跳错页 —— 都不抛异常。所以拿沙箱实测里真实出现过的形态做 fixture。
"""

from app.schemas.exact_qa import ContentBlock, DropReason
from app.services.exact_qa.extractor import (
    LlmQaItem,
    filter_candidates,
    locate,
    repair_quote,
    split_by_pages,
)
from app.services.exact_qa.matching import normalize

MD = """<!-- page: 0 -->

# YOLOv3: An Incremental Improvement

We use a new network for performing feature extraction. It has 53 convolutional layers.

<!-- page: 1 -->

Table 1. Darknet-53.

<table><tr><td>Residual</td><td>1024</td></tr></table>

During training we use binary cross-entropy loss for the class predictions.
"""

BLOCKS = [
    ContentBlock(
        type="text",
        page_idx=0,
        bbox=[100, 200, 900, 260],
        text="We use a new network for performing feature extraction. "
        "It has 53 convolutional layers.",
    ),
    ContentBlock(
        type="table",
        page_idx=1,
        bbox=[110, 300, 880, 500],
        table_body="<table><tr><td>Residual</td><td>1024</td></tr></table>",
    ),
    ContentBlock(
        type="text",
        page_idx=1,
        bbox=[120, 600, 870, 640],
        text="During training we use binary cross-entropy loss for the class predictions.",
    ),
]


def _item(**kw) -> LlmQaItem:
    base = dict(
        standard_question="Q?",
        answer="A.",
        keywords=["k"],
        quote="It has 53 convolutional layers.",
        page_idx=0,
        confidence=0.9,
    )
    return LlmQaItem(**{**base, **kw})


# ---------------------------------------------------------------- 切段


def test_split_keeps_a_page_marker_in_every_chunk():
    """每段都必须带页标记,否则模型填不出 page_idx(origin_ref 就没了页码)。"""
    chunks = split_by_pages(MD, max_chars=80)
    assert len(chunks) == 2
    assert all("<!-- page:" in c for c in chunks)


def test_split_merges_pages_until_the_char_budget():
    """短文档不该被切碎:一次调用抽一整篇,上下文完整质量才好。"""
    assert len(split_by_pages(MD, max_chars=10_000)) == 1


def test_text_without_markers_is_one_chunk():
    """没有页标记的文本(人工校对时把标记删了)不许炸,退化成整篇一段。"""
    assert split_by_pages("plain text with no markers") == ["plain text with no markers"]


# ---------------------------------------------------------------- quote 定位


def test_locate_returns_page_and_bbox_of_the_containing_block():
    """bbox 由我们用 content_list 回填,模型只填 page_idx 作兜底。"""
    quote, page_idx, bbox = locate("It has 53 convolutional layers.", MD, BLOCKS)
    assert quote == "It has 53 convolutional layers."
    assert page_idx == 0
    assert bbox == [100, 200, 900, 260]


def test_locate_finds_quotes_inside_table_html():
    """表格来源的候选,quote 就是一段 <tr><td>…,要能在 table_body 里定位到。"""
    quote, page_idx, bbox = locate("<tr><td>Residual</td><td>1024</td></tr>", MD, BLOCKS)
    assert quote and page_idx == 1 and bbox == [110, 300, 880, 500]


def test_locate_is_whitespace_and_quote_insensitive():
    """模型抄 quote 时常把换行压成空格 —— 归一化后仍要能对上。"""
    quote, page_idx, _ = locate(
        "We use a new network for performing feature   extraction.", MD, BLOCKS
    )
    assert quote and page_idx == 0


#: 修复用例:前 55 字符能逐字对上,后半截是模型自己接上去的
GOOD_PREFIX = "We use a new network for performing feature extraction."
FABRICATED_TAIL = " AND SOMETHING THE MODEL MADE UP"


def test_repair_quote_takes_the_longest_matching_prefix():
    """★ 实测:模型爱在句尾把两处文字接起来。二分取最长可对上的前缀,
    实测让 quote_not_found 从 6 降到 1 —— 不修复就是白丢好候选。"""
    assert repair_quote(GOOD_PREFIX + FABRICATED_TAIL, normalize(MD)) == GOOD_PREFIX


def test_repair_refuses_prefixes_that_are_too_short():
    """短于 40 字符(MIN_QUOTE_CHARS)的片段在审核台上没有对照价值,宁可丢掉这条候选。
    「It has 53 convolutional layers.」只有 31 字符 —— 对得上也不要。"""
    assert repair_quote("It has 53 convolutional layers." + "X" * 50, normalize(MD)) is None


def test_locate_gives_up_on_a_fabricated_quote():
    """逐字 quote 校验是"抓事实性错抄"的那道关(实测拦下过把 σ(t_x) 抄成 c(t_x) 的一条)。"""
    assert locate("YOLOv3 has 99 convolutional layers.", MD, BLOCKS) == (None, None, None)


# ---------------------------------------------------------------- 硬约束过滤


def test_empty_answer_is_dropped():
    """答案为空的候选没有任何价值,在抽取层就丢(不进候选列表)。"""
    kept, dropped, _ = filter_candidates("doc", [_item(answer="   ")], MD, BLOCKS)
    assert kept == [] and dropped[DropReason.EMPTY_ANSWER] == 1


def test_missing_quote_is_dropped_as_no_origin_ref():
    """"必须带原文出处"是硬约束:没引用的一律不进候选。"""
    kept, dropped, _ = filter_candidates("doc", [_item(quote="")], MD, BLOCKS)
    assert kept == [] and dropped[DropReason.NO_ORIGIN_REF] == 1


def test_unlocatable_quote_is_dropped():
    item = _item(quote="not in the document at all")
    kept, dropped, _ = filter_candidates("doc", [item], MD, BLOCKS)
    assert kept == [] and dropped[DropReason.QUOTE_NOT_FOUND] == 1


def test_repaired_quote_is_counted_and_kept():
    bad = GOOD_PREFIX + FABRICATED_TAIL
    kept, dropped, repaired = filter_candidates("doc", [_item(quote=bad)], MD, BLOCKS)
    assert len(kept) == 1 and repaired == 1 and not dropped
    assert kept[0].origin_ref.quote == GOOD_PREFIX


def test_duplicate_questions_collapse_but_different_models_do_not():
    """判重与"区分性 token"保险在过滤主体里的联合行为(单独的用例见 test_exact_qa_matching)。"""
    items = [
        _item(standard_question="What is the Top-1 accuracy of ResNet-101?"),
        _item(standard_question="What is the Top-1 accuracy of ResNet-152?"),
        _item(standard_question="What's the Top-1 accuracy of ResNet-101?"),
    ]
    kept, dropped, _ = filter_candidates("doc", items, MD, BLOCKS)
    assert len(kept) == 2, "101 与 152 各留一条"
    assert dropped[DropReason.DUPLICATE_QUESTION] == 1, "重复问 101 的那条被丢"


def test_page_idx_from_the_block_wins_over_the_model():
    """模型填的页码只作兜底:它经常照抄段首的页标记,块页码才是准的。"""
    kept, _, _ = filter_candidates(
        "doc",
        [_item(quote="During training we use binary cross-entropy loss", page_idx=0)],
        MD,
        BLOCKS,
    )
    assert kept[0].origin_ref.page_idx == 1


def test_candidates_are_sorted_worst_confidence_last():
    """审核台默认"最不靠谱的先看",列表顺序在这里就定好(置信度降序 + 页序)。"""
    items = [
        _item(standard_question="Qa?", confidence=0.5),
        _item(standard_question="Qb?", confidence=0.95),
    ]
    kept, _, _ = filter_candidates("doc", items, MD, BLOCKS)
    assert [c.confidence for c in kept] == [0.95, 0.5]


def test_origin_ref_carries_the_document_id():
    """origin_ref 里的 document_id 是"引用能跳回原文"的起点,不能漏。"""
    kept, _, _ = filter_candidates("DOC-42", [_item()], MD, BLOCKS)
    assert kept[0].origin_ref.document_id == "DOC-42"
