"""S2 检索层的离线单测:停用词处理 + RRF 融合。

这两处都是纯函数,但错了不报错 —— 只是安静地把正确答案排到十名开外。

🩸 停用词那条是**生产级缺陷**,不是沙箱的权宜之计:`plainto_tsquery` 是 AND 语义,
而 `simple` 分词器不去停用词,一个自然语言问题会命中 0 条;改成 OR 又会命中几乎全库,
而 `ts_rank` 没有 IDF,`the` 和 `warranty` 权重一样大。两个坑必须同时躲开。
"""

import uuid

from app.services.document.retriever import keyword_terms, rrf


def test_stopwords_are_removed():
    """自然语言问题里的功能词一个都不该进 tsquery。"""
    terms = keyword_terms("How much does it cost to extend the warranty on an HC-430?")
    assert "how" not in terms and "the" not in terms and "does" not in terms
    assert "warranty" in terms and "cost" in terms


def test_identifiers_survive_tokenisation():
    """型号/编号是全文腿的主要职责,连字符与点号不能被切开。"""
    terms = keyword_terms("Is the HC-430 certified to AS/NZS 4777.2:2020?")
    assert "hc-430" in terms
    assert "4777.2" in terms


def test_all_stopwords_yields_nothing():
    """全是停用词时返回空 —— 调用方据此整条跳过全文腿,而不是去查一个空 tsquery。"""
    assert keyword_terms("what is it about") == []


def test_rrf_fuses_on_rank_not_score():
    """两条腿都排前列的候选,融合分要高于只有一条腿排第一的。

    这正是 RRF 存在的理由:余弦 0–1 与 `ts_rank` 0.0x 量纲不同,不能直接相加。
    """
    a, b, c = (uuid.uuid4() for _ in range(3))
    fused = dict(rrf([[a, b], [b, c]], k=60))
    assert fused[b] > fused[a] > fused[c]


def test_rrf_is_sorted_descending():
    """输出必须已按融合分降序 —— 下游把它当名次直接用。"""
    ids = [uuid.uuid4() for _ in range(4)]
    scores = [s for _, s in rrf([ids, list(reversed(ids))], k=60)]
    assert scores == sorted(scores, reverse=True)


def test_rrf_of_nothing_is_nothing():
    """双路都没召回 → 空。上层据此走兜底话术,而不是拿空列表继续跑。"""
    assert rrf([[], []], k=60) == []
