"""S1 命中分档 `decide_tier()` 的离线单测(不联网、不连库)。

分数区间取自 Step 5 的真实实测(documents/S1-PLAN.md §5 M4):
正例 0.613–0.912 / 越界负例 0.129–0.384 / 困难负例 0.613–0.827。
边界写死在测试里,是为了让"以后有人顺手把阈值往上抬"这件事立刻变红 ——
抬阈值买不到精度(0.75 时正例从 14 掉到 8),这个结论必须有守卫。
"""

from app.config import settings
from app.schemas.exact_qa import HitTier
from app.services.exact_qa.retriever import decide_tier

HIT = 0.55
BORDER = 0.40


def tier(score, missing=None):
    return decide_tier(
        score, guard_missing=missing, hit_threshold=HIT, borderline_threshold=BORDER
    )


# ---------------------------------------------------------------- 阈值边界


def test_thresholds_in_config_match_the_measured_values():
    """定稿值(Step 5 实测)。改这三个值之前先读 M3-M4 实测记录。"""
    assert settings.exact_qa_hit_threshold == 0.55
    assert settings.exact_qa_borderline_threshold == 0.40


def test_exactly_at_hit_threshold_is_a_hit():
    """闭区间:>= hit 就是命中(sweep 时按 >= 统计的,实现必须一致)。"""
    assert tier(HIT) is HitTier.HIT


def test_just_below_hit_is_borderline_not_miss():
    """0.40–0.55 之间是 BORDERLINE:S1 按未命中处理,但要留 trace 观察阈值定得对不对。"""
    assert tier(HIT - 0.001) is HitTier.BORDERLINE
    assert tier(0.50) is HitTier.BORDERLINE


def test_exactly_at_borderline_is_borderline():
    assert tier(BORDER) is HitTier.BORDERLINE


def test_below_borderline_is_miss():
    """越界负例(0.129–0.384)全落在这里 —— 阈值唯一真正切得干净的一类。"""
    assert tier(BORDER - 0.001) is HitTier.MISS
    assert tier(0.384) is HitTier.MISS
    assert tier(0.129) is HitTier.MISS


def test_lowest_measured_positive_still_hits():
    """实测最低的正例是 0.613。它必须还在命中区里,否则等于砍召回。"""
    assert tier(0.613) is HitTier.HIT


def test_empty_index_is_a_miss_not_a_crash():
    """库里没有任何已采纳 QA 时(演示第一步就是这个状态)不许炸。"""
    assert tier(None) is HitTier.MISS


# ---------------------------------------------------------------- 护栏交互


def test_guard_downgrades_a_high_score_to_borderline():
    """★ 实测最危险的一条:0.827 的「416×416」命中「320×320」。
    分数远超阈值,只有护栏拦得住 —— 拦下后是 BORDERLINE(落回生成),不是 HIT。"""
    assert tier(0.827, {"416"}) is HitTier.BORDERLINE


def test_guard_cannot_rescue_a_miss():
    """护栏只降级不升级:分数太低的依然是 MISS(不要被"降级"字面误导)。"""
    assert tier(0.20, {"416"}) is HitTier.MISS


def test_empty_guard_set_does_not_downgrade():
    """空差集 = 护栏没意见。用 falsy 判断,别写成 `is not None`。"""
    assert tier(0.90, set()) is HitTier.HIT


def test_defaults_come_from_config():
    """不传阈值时必须走 settings,不能在函数里写死数字。"""
    assert decide_tier(settings.exact_qa_hit_threshold) is HitTier.HIT
    assert decide_tier(settings.exact_qa_borderline_threshold - 0.01) is HitTier.MISS
