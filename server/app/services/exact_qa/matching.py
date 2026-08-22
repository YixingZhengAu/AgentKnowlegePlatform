"""问题文本比对的纯函数 —— **本域三处都用同一道保险,所以单独一层**。

三个调用点(沙箱阶段各自踩过坑,结论都收在这里):

| 用在哪 | 干什么 | 阈值 |
| --- | --- | --- |
| M2 抽取(`extractor.py`) | 候选列表内判重(同一事实的多种问法归 M3) | `DUP_JACCARD` 0.70 |
| M3 相似问(`similar_gen.py`) | 跨条冲突检测(一句问法映射两个答案) | `CONFLICT_JACCARD` 0.75 |
| M4 检索(`retriever.py`) | 命中护栏(分数够但型号/尺寸对不上 → 不算命中) | 无阈值,看差集 |

★ 三处共用的那道保险叫 **区分性 token**(`salient_tokens`:含数字的词)。
它不是锦上添花,是被两个真 bug 逼出来的:

1. M2 判重只看词集 Jaccard 时,「ResNet-152 的指标」被当成「ResNet-101 的指标」的重复
   (Jaccard 0.867)**静默丢掉一条知识** —— 不报错,只是那条知识以后永远问不出来。
2. M4 里「416×416 的 mAP」以 **0.827** 命中索引里「320×320」那条,
   任何阈值都拦不住(正例分数区间 0.61–0.91 与它完全重叠),会把错答案标成 Verified Answer。

两处的共同特征都是"型号/分辨率/数值不一样",所以判定统一成一句话:
**区分性 token 对不上,就不是同一个问题。**

这几个函数改错了不会报错、只会静默给错答案,所以 `tests/test_exact_qa_matching.py` 是
S1 唯一必须有的离线单测(S1-plan §7.1)。
"""

import re

#: 判重阈值(M2)。有区分性 token 这道保险兜着,阈值可以放低到 0.70 去抓"只差一两个词"的改写
#: (如 "bounding box coordinates" vs "bounding box coordinate regression",Jaccard 0.79)。
DUP_JACCARD = 0.70

#: 跨条冲突阈值(M3)。比判重严一点 —— 宁可少一条改写,也不能让两个答案抢同一句问法。
CONFLICT_JACCARD = 0.75


def tokens(s: str) -> set[str]:
    """词集:只留字母数字串,大小写无关。"""
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def salient_tokens(ts: set[str]) -> set[str]:
    """区分性 token:含数字的词(型号 resnet-101 → {resnet,101};数值 77.2;尺寸 320)。"""
    return {t for t in ts if any(c.isdigit() for c in t)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def same_question_face(a: str, b: str, threshold: float) -> bool:
    """a 与 b 是否算"同一个问题面":词集 Jaccard 达阈值 **且** 区分性 token 完全一致。"""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    if salient_tokens(ta) != salient_tokens(tb):
        return False  # 型号/数值不同 → 不是同一个问题,哪怕句式一模一样
    return jaccard(ta, tb) >= threshold


def is_near_duplicate(
    question: str, seen: list[str], threshold: float = DUP_JACCARD
) -> bool:
    """M2:问题在已保留的候选里是否已经出现过。"""
    return any(same_question_face(question, s, threshold) for s in seen)


def conflicting_face(
    question: str,
    self_index: int,
    faces: list[tuple[int, str]],
    threshold: float = CONFLICT_JACCARD,
) -> int | None:
    """M3:一句改写是否与**别的候选**的问题面撞车;撞了返回那条候选的下标。

    `faces` = [(候选下标, 问题面原文)],含各条标准问与已接受的改写。
    """
    for idx, face in faces:
        if idx == self_index:
            continue
        if same_question_face(question, face, threshold):
            return idx
    return None


def salient_mismatch(query: str, face: str) -> set[str]:
    """M4 护栏:查询里出现、而被命中的问题面里没有的区分性 token。

    非空 = 用户问的型号/尺寸/数值不在这条知识里 → 降级为 BORDERLINE,落回生成模型,
    宁可少答一句也不把错答案标成 Verified Answer。
    """
    return salient_tokens(tokens(query)) - salient_tokens(tokens(face))


def normalize(s: str) -> str:
    """定位/去重用的归一化:压空白、统一排版引号(解析产物里是弯引号)、小写。"""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()
