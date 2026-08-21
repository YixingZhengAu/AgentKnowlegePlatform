"""审核台后端的离线测试(不碰 DB):payload 合并语义、状态推导、计数。

DB 相关的部分(PATCH / 批量 / 发布的状态机)在 Step 8 的接口实测里验
—— 那里有真的 20 条假数据可审,比 mock 出来的 session 更有说服力。
"""

from app.core.staging import (
    PUBLISHABLE_STATUSES,
    count_by_status,
    derive_review_status,
    known_publishers,
    merge_payload,
)


def test_payload_patch_is_shallow_merge():
    """只改 answer 时不必回传整个 payload;其它键原样保留。"""
    old = {"standard_question": "Q?", "answer": "old", "keywords": ["a", "b"]}
    got = merge_payload(old, {"answer": "new"})
    assert got == {"standard_question": "Q?", "answer": "new", "keywords": ["a", "b"]}


def test_payload_lists_are_replaced_not_merged():
    """list 是"整份重写"语义 —— 否则"删掉一个相似问"没法表达。"""
    got = merge_payload({"keywords": ["a", "b", "c"]}, {"keywords": ["a"]})
    assert got["keywords"] == ["a"]


def test_editing_content_implies_modified():
    assert (
        derive_review_status(requested=None, has_payload_edit=True, current="pending") == "modified"
    )


def test_explicit_status_wins_over_modified():
    """点"通过"就是 approved,即使这一次同时改了内容。"""
    assert (
        derive_review_status(requested="approved", has_payload_edit=True, current="pending")
        == "approved"
    )


def test_no_change_keeps_current_status():
    assert (
        derive_review_status(requested=None, has_payload_edit=False, current="approved")
        == "approved"
    )


def test_count_by_status_covers_every_status():
    counts = count_by_status(["pending", "approved", "approved", "modified"])
    assert counts == {"pending": 1, "approved": 2, "rejected": 0, "modified": 1}


def test_modified_is_publishable():
    """ "人工改过再通过"必须跟着一起发布,否则改完的条目永远发不出去。"""
    assert set(PUBLISHABLE_STATUSES) == {"approved", "modified"}


def test_s0_has_no_type_publisher_registered():
    """S0 刻意不写正式表:发布只做通用骨架,各类型的 publisher 由 S1–S3 注册。"""
    assert known_publishers() == []
