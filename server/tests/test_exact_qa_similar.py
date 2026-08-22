"""S1 相似问过滤 `filter_similar()` 的离线单测(不联网)。

这一层丢掉的每一句都有明确理由,统计数字会进 Job 的 step 日志 ——
数字不对(比如冲突检测失效)在界面上看不出来,只有检索时才表现为"答错",所以在这里守。
"""

from app.schemas.exact_qa import OriginRef, QaCandidate
from app.services.exact_qa.similar_gen import filter_similar


def _cand(q: str, a: str = "Some verified answer.") -> QaCandidate:
    return QaCandidate(
        standard_question=q,
        answer=a,
        origin_ref=OriginRef(document_id="doc", page_idx=0, quote="q"),
    )


def test_rephrasing_identical_to_the_standard_question_is_dropped():
    """★ 实测每轮稳定 16 条:留着白占一行向量,而且检索面里出现两句一样的没有意义。"""
    c = _cand("How many layers does Darknet-53 have?")
    raw = ["How many layers does Darknet-53 have?", "Darknet-53 layer count?"]
    stats = filter_similar([c], [raw])
    assert c.similar_questions == ["Darknet-53 layer count?"]
    assert stats["drop_same_as_standard"] == 1 and stats["kept"] == 1


def test_same_as_standard_ignores_case_and_whitespace():
    c = _cand("Darknet-53 layer count?")
    stats = filter_similar([c], [["  darknet-53   layer  count? "]])
    assert c.similar_questions == [] and stats["items_empty"] == 1


def test_rephrasing_colliding_with_another_item_is_dropped():
    """★ 最致命的脏数据:同一句问法映射两个答案,检索必然选错一个。"""
    a = _cand("What training techniques are used for YOLOv3?", "Multi-scale training and so on.")
    b = _cand("How does YOLOv3 perform on small objects?", "It does well on small objects.")
    stats = filter_similar([a, b], [[], ["Which training techniques are used for YOLOv3?"]])
    assert b.similar_questions == []
    assert stats["drop_conflict"] == 1


def test_an_accepted_rephrasing_also_blocks_later_items():
    """已接受的改写要进问题面,否则后一条的改写会撞上它而无人察觉。"""
    a = _cand("What is the top-1 accuracy of Darknet-53?")
    b = _cand("How fast is Darknet-53 on a Titan X?")
    stats = filter_similar(
        [a, b],
        [["Darknet-53 top-1 accuracy on ImageNet?"], ["Darknet-53 top-1 accuracy on ImageNet"]],
    )
    assert a.similar_questions == ["Darknet-53 top-1 accuracy on ImageNet?"]
    assert b.similar_questions == [] and stats["drop_conflict"] == 1


def test_different_models_are_not_a_conflict():
    """同句式问不同型号不算撞车 —— 它们本该各自命中(区分性 token 那道保险)。"""
    a = _cand("Top-1 accuracy of ResNet-101?")
    b = _cand("Top-1 accuracy of ResNet-152?")
    stats = filter_similar([a, b], [[], ["What is the top-1 accuracy of ResNet-152?"]])
    assert len(b.similar_questions) == 1 and stats["drop_conflict"] == 0


def test_within_one_item_duplicates_collapse():
    c = _cand("Darknet-53 layer count?")
    stats = filter_similar([c], [["How many layers?", "how many layers?", "  "]])
    assert c.similar_questions == ["How many layers?"]
    assert stats["raw"] == 3 and stats["kept"] == 1
