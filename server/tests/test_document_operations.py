"""S2-4 运营层里那些**错了不报错**的纯函数(分册 4)。

两处都不会抛异常,只会安静地做错事:
① 退休行判反 → 一条不可逆的退休行被当成"可以重新启用",或反过来;
② embedding 输入的拼法在"发布"与"重新启用"两条路径上不一致 →
   同一条切片被启用一次就换了一个向量,召回行为悄悄变了。
"""

from app.schemas.document import chunk_is_retired, embed_input

# ─── 退休行的判据 ─────────────────────────────────────────────────────────────


def test_retired_reads_the_meta_flag():
    """判据是 `meta.retired`,不是 `status` —— `disabled` 有两个来源:
    人手点的"禁用"(可逆)和重新发布时的退休(不可逆),前端要能分开显示。"""
    assert chunk_is_retired({"retired": True})
    assert not chunk_is_retired({"page_idx": 2})


def test_retired_tolerates_missing_meta():
    """`meta` 是 jsonb,缺键、空、None 都可能 —— 一律当"不是退休行"。"""
    assert not chunk_is_retired(None)
    assert not chunk_is_retired({})


def test_retired_is_not_inferred_from_negative_seq():
    """🩸 曾经用 `seq < 0` 编码退休行,那套编码**跨代不唯一**(同一个 seq 退休两次
    会撞同一个负号槽,2026-08-25 实测炸在唯一约束上)。现在 seq 原样保留,
    唯一性交给"只管 active 行"的部分索引 —— 所以 seq 的正负与退休无关。"""
    assert not chunk_is_retired({"page_idx": 0})


# ─── embedding 输入 ──────────────────────────────────────────────────────────


def test_embed_input_matches_publish_shape():
    """标题路径 + 空行 + 正文。发布与重新启用共用这一个拼法。"""
    assert embed_input("Doc > 4. Warranty", "Body text.") == "Doc > 4. Warranty\n\nBody text."


def test_embed_input_without_heading_has_no_leading_blank():
    """没有标题路径时不能留下开头的空行 —— 那会让同一段正文产生两个不同的向量。"""
    assert embed_input(None, "Body text.") == "Body text."
    assert embed_input("", "Body text.") == "Body text."
