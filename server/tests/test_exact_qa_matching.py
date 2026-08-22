"""S1 精准问答:文本比对纯函数的离线单测。

**为什么 S1 只给这几个函数写单测**(S1-plan §7.1):它们输入输出确定,而且
**改错了不报错、只是静默给错答案** —— 沙箱阶段在这里踩过两次真实的坑,
两次都是"跑评测才发现",肉眼读代码看不出来。用例直接取自那两个坑与
S1 Step 5 人写评测集里的困难负例,不是编的。
"""

from app.services.exact_qa.matching import (
    CONFLICT_JACCARD,
    DUP_JACCARD,
    conflicting_face,
    is_near_duplicate,
    jaccard,
    normalize,
    salient_mismatch,
    salient_tokens,
    same_question_face,
    tokens,
)

# ---------------------------------------------------------------- 区分性 token


def test_salient_tokens_are_the_ones_carrying_digits():
    """型号、分辨率、数值 —— "答错了最要命"的那些词都含数字。"""
    assert salient_tokens(tokens("Top-1 accuracy of ResNet-101")) == {"1", "101"}
    assert salient_tokens(tokens("What backbone does YOLOv3 use?")) == {"yolov3"}
    assert salient_tokens(tokens("Which loss is used for class predictions")) == set()


# ------------------------------------------------- 坑 ①:判重静默丢知识(M2)


def test_resnet_101_and_152_are_not_duplicates():
    """★ 沙箱实测踩过的坑:两句 Jaccard 0.867,只看词集会判成重复,
    于是「ResNet-152 的指标」被静默丢掉 —— 不报错,只是那条知识以后永远问不出来。"""
    q101 = "What is the ImageNet Top-1 and Top-5 accuracy of ResNet-101?"
    q152 = "What is the ImageNet Top-1 and Top-5 accuracy of ResNet-152?"
    assert jaccard(tokens(q101), tokens(q152)) >= DUP_JACCARD, "前提:词集确实高度相似"
    assert not is_near_duplicate(q152, [q101]), "区分性 token 不同 → 不是重复"


def test_real_rephrasing_is_still_caught_as_duplicate():
    """保险不能把判重整个废掉:同一事实的换词问法仍要被拦(归 M3 管,不进候选列表)。"""
    a = "What loss function does YOLOv3 use for bounding box coordinates?"
    b = "What loss function does YOLOv3 use for bounding box coordinate regression?"
    assert is_near_duplicate(b, [a])


def test_dedup_threshold_stays_at_the_measured_value():
    """0.70 是"有区分性 token 兜底"才敢放低到的值;两者必须一起改。"""
    assert DUP_JACCARD == 0.70
    assert CONFLICT_JACCARD == 0.75


# ------------------------------------------- 坑 ②:一句问法映射两个答案(M3)


def test_conflicting_face_finds_the_other_item():
    """跨条冲突:某条的改写撞上别条的标准问 = 检索必然选错一个,必须丢。"""
    faces = [
        (0, "What training techniques are used for YOLOv3?"),
        (1, "How does YOLOv3 perform on small objects?"),
    ]
    got = conflicting_face("Which training techniques are used for YOLOv3?", 3, faces)
    assert got == 0


def test_conflicting_face_ignores_the_item_itself():
    """自己的标准问不算冲突(否则每条的改写都会被自己拦掉)。"""
    faces = [(0, "What training techniques are used for YOLOv3?")]
    assert conflicting_face("Which training techniques are used for YOLOv3?", 0, faces) is None


def test_conflict_keeps_different_models_apart():
    """同样句式问不同型号,不算撞车 —— 它们本该各自命中。"""
    faces = [(0, "What are the Top-1 and Top-5 accuracies of ResNet-101?")]
    assert conflicting_face("Top-1 and Top-5 accuracies of ResNet-152?", 1, faces) is None


# ------------------------------------------- 坑 ③:高分错命中(M4 护栏)


def test_guard_blocks_416_hitting_the_320_entry():
    """★ 实测最危险的一条:「416×416 的 mAP」以 **0.827** 命中「320×320」那条。
    分数落在正例区间(0.61–0.91)正中,任何阈值都拦不住,只有护栏能拦。"""
    query = "What is the mAP of YOLOv3 at 416 x 416?"
    face = "What throughput and mAP does YOLOv3 achieve at 320×320 resolution?"
    assert salient_mismatch(query, face) == {"416"}


def test_guard_blocks_darknet19_hitting_darknet53():
    """同领域困难负例:Darknet-19 与 Darknet-53 语义几乎一致,差的就是那个数字。"""
    query = "How many convolutional layers does Darknet-19 have?"
    face = "What feature extractor does YOLOv3 use and how many convolutional layers does it have?"
    assert salient_mismatch(query, face) == {"19"}


def test_guard_does_not_fire_on_a_genuine_paraphrase():
    """零误伤是护栏能上生产的前提:正例的数字必须在命中面里出现过。"""
    query = "yolov3 inference speed at 320 input size"
    face = "What throughput and mAP does YOLOv3 achieve at 320×320 resolution?"
    assert salient_mismatch(query, face) == set()


def test_guard_is_blind_to_this_hard_negative():
    """★ 护栏的能力边界,写成测试免得以后误以为它够用:
    「训练要多久」命中「用了哪些训练技巧」(实测 0.72),两句的区分性 token 都只有
    yolov3,差集是空的 —— 护栏放它过去。这类只有第三段(light 模型复核)挡得住。"""
    query = "How long does it take to train YOLOv3 on COCO?"
    face = "What training techniques are used for YOLOv3?"
    assert salient_mismatch(query, face) == set()


# ---------------------------------------------------------------- 归一化


def test_normalize_folds_typographic_quotes_and_whitespace():
    """解析产物里是弯引号;不折平的话 quote 逐字定位会大面积失败。"""
    assert normalize("YOLOv3’s   detection\nperformance") == "yolov3's detection performance"


def test_same_question_face_needs_both_conditions():
    """两个条件是"与"关系:词集像 + 区分性 token 一致,少一个都不算同一问题面。"""
    assert same_question_face("Darknet-53 layer count", "Darknet-53 layer count?", 0.9)
    assert not same_question_face("Darknet-53 layer count", "Darknet-19 layer count", 0.9)
    assert not same_question_face(
        "Darknet-53 layer count", "How fast is Darknet-53 on a Titan X?", 0.9
    )
