"""意图检索(B7 原样迁入):用户问题 → 命中哪个已发布意图(问数链路的运行时入口)。

链路:已发布意图 → 索引面(摘要 + N 条相似问法,一面一行向量,存 `intent_vectors`)
     → 用户问题 embed → 每意图取其所有面的 **max** 相似度 → **双门槛**判定。

★ 为什么每意图取 max 而不是均值:命中哪一种问法都算命中这个意图(与 S1 一问一行同构)。
  取均值会被"问法多样性"反向惩罚 —— 问法写得越全面,平均分越低。

★ 为什么要两道门槛(绝对阈值 + top1/top2 边距),缺一不可:
  * 只有阈值:两个意图分数咬得很近时(如"按仓库的出库量" vs "按产品的出库量"),
    top1 高于阈值就被当成确信命中,选错的是哪个纯看运气;
  * 只有边距:一个跟谁都不像的问题,可能恰好"矮子里拔将军"拉开边距,被当成问数。
  低于阈值 → 判非问数(交回 S4 路由);过阈但边距不足 → 返回 top-k 候选,confident=False,
  由 S4 决定是否加一步 LLM 复核(接口形状留好,这里不实现)。

★ 空路由(null route):除了真意图,索引里还有一组**非问数负例面**(`non_data_faces` 表:
  产品规格/质保/操作手册/故障码/流程政策/闲聊)。top1 落在这组面上 → 直接判非问数。
  它不是锦上添花,是 B8 实测逼出来的:"What's the warranty period on the HC-300 battery
  cabinet?" 与一条含产品全名的库存流水问法相似度 0.5183、边距 0.2575 —— **确信地判错**。
  纯绝对阈值救不了这一类:0.5183 高于任何能保住真正例的阈值(应命中类最低 0.4981)。
  根因是索引面里刻意带真实产品名(相似问法的取值纪律),于是"问这个产品的属性"和
  "查这个产品的数据"在词面上高度重叠;区分它们靠的不是分数高低,而是**有没有一个更像的负例**。
  这是语义路由的标准做法(给"以上都不是"也配一组示例),零 LLM 成本,复用同一套面机制。

★ 职责边界(与改写层划清):"问数域但模板外"的问题(问没有的仓库、问毛利)**应该命中最近的
  意图**,拒答是 planner 的事(feasible=false)。检索层只回答"是不是问数、最像哪个模板",
  不回答"能不能答" —— 让检索层去猜模板能力,等于把改写层的能力边界复制一份到这里,必然漂移。

★ 归一化(迁移时最容易静默出错的一处,S1 M4 的教训):写入 `intent_vectors` 前与
  查询向量都做 L2 归一化,于是**本地点积 == pgvector 的余弦**。这不是为了改分数
  (余弦对模长本来不敏感),而是为了让 `smoke_s3_index.py` 能把两条算路对上号 ——
  选错距离算子的症状是分数静默偏移、阈值全部作废,只有对数能抓住它。
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntentVector, NonDataFace, SqlIntent
from app.providers import get_embedder

#: 命中阈值:top1 低于它 → 判非问数。**由实测分离带取中点**(见 documents/S3-PLAN.md 的 B7 证据块):
#: 空路由拦不到的那批非问数负例最高 0.4071 ↔ 应命中类最低 0.4981,中点 0.4526 → 取 0.45。
#: 注意:加了空路由之后,把全部负例算进来的话这条带是**重叠**的(0.5183 > 0.4981,warranty 题)。
#: 那一类靠阈值救不了 —— 抬阈值先误杀真正例 —— 只能靠空路由。所以这个 0.45 只对
#: "没被空路由拦下的问题"负责,别再拿它当唯一防线。
HIT_THRESHOLD = 0.45
#: 边距阈值:top1 − top2 低于它 → 命中但**不确信**,返回候选让上层(S4)决定是否加 LLM 复核。
#: 0.03 是谨慎带:评测集里没有任何一题 top-1 判错,所以它现在一条错也没拦下,
#: 代价是 32 题里 2 题多走一步确认。留着的理由是审计证明 i07↔i09、i16↔i18 两对意图天生咬得近
#: (留一法里 one-liner 互相检错),等意图数变多,这两对最先出问题。
MARGIN_THRESHOLD = 0.03
#: 返回几个候选。分档只看 top1/top2,其余是给 trace 面板看"差多少"的
TOP_K = 3

#: 面的来源(评审报告要看"哪一类面在真正干活")
FACE_SUMMARY = "summary"
FACE_QUESTION = "question"
FACE_NON_DATA = "non_data"
#: 空路由的伪意图 id。用 __ 前缀是为了永远不可能与真实 intent_id 撞车。
NON_DATA_INTENT = "__non_data__"
#: 简述(brief)**不入索引** —— B7 消融实测的结论,不是省事:
#: 加不加简述面,11 道真人题的命中、均分(0.752)、均边距(0.184)、负例最高分(0.407)完全一样,
#: 简述面在真人题里一次都没当过命中面;而它贡献了 3 条自洽性冲突(i07↔i09、i18 的简述互相检错)。
#: 说明书体的长段落对"问句 vs 问句"的匹配没有增益,只会在相近意图之间制造噪声。
FACE_BRIEF = "brief"  # 只在文档里提到:B7 的消融实验用它做过对照,正式索引不建它




def normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


def cosine(a: list[float], b: list[float]) -> float:
    """两个**已归一化**向量的余弦相似度 = 点积。"""
    return sum(x * y for x, y in zip(a, b, strict=True))


async def embed_query(question: str) -> list[float]:
    return normalize((await get_embedder().embed([question]))[0])


async def load_index(session: AsyncSession, kb_id: uuid.UUID) -> list[dict]:
    """从 `intent_vectors` 装出与实验床同形的索引:[{intent_id, kind, text, vec}]。

    `intent_id` 用意图的**人可读 code**(i01…)而不是 uuid:trace 面板、评审报告和
    评测集都按 code 指称意图,换成 uuid 会让所有人审材料失去可读性。uuid 另存一列备用。
    空路由的面 code 固定是 `__non_data__`(伪意图,`__` 前缀保证永远不与真 code 撞车)。
    """
    rows = (await session.execute(
        select(IntentVector, SqlIntent.code)
        .outerjoin(SqlIntent, IntentVector.intent_id == SqlIntent.id)
        .where(IntentVector.kb_id == kb_id)
    )).all()
    index: list[dict] = []
    for vec, code in rows:
        index.append({
            "intent_id": code or NON_DATA_INTENT,
            "intent_uuid": vec.intent_id,
            "kind": vec.face_kind,
            "text": vec.face_text,
            "vec": list(vec.embedding),
        })
    return index


async def load_non_data_faces(session: AsyncSession, kb_id: uuid.UUID) -> list[str]:
    """启用中的空路由负例面(人可编辑的资产)。"""
    return list((await session.scalars(
        select(NonDataFace.face_text)
        .where(NonDataFace.kb_id == kb_id, NonDataFace.enabled.is_(True))
        .order_by(NonDataFace.face_text)
    )).all())


def build_faces(intent_faces: dict[str, dict], non_data: list[str] | None = None) -> list[dict]:
    """展开索引面:一面一条 {intent_id, kind, text}。

    `intent_faces = {code: {"one_liner": str, "questions": [str]}}`。
    摘要剥掉 "Query: "/"Stats: " 前缀 —— 那是内部治理标签,用户问句里绝不会出现,
    留着只会给每条意图加一段共同的无关文本,冲淡意图之间的区分度。
    意图简述(brief)**不入索引**:B7 消融实测它零增益却制造 3 条自洽性冲突。
    """
    from app.services.text2sql.questions import _strip_prefix

    faces: list[dict] = []
    for code, spec in intent_faces.items():
        faces.append({"intent_id": code, "kind": FACE_SUMMARY,
                      "text": _strip_prefix(spec["one_liner"])})
        for q in spec.get("questions", []):
            faces.append({"intent_id": code, "kind": FACE_QUESTION, "text": q})
    for t in non_data or []:
        faces.append({"intent_id": NON_DATA_INTENT, "kind": FACE_NON_DATA, "text": t})
    return faces


def _score_intents(qvec: list[float], index: list[dict], skip: int | None = None) -> list[dict]:
    """每意图 = 其所有面的 max 相似度;返回按分降序的列表(带命中的那一面)。"""
    best: dict[str, dict] = {}
    for i, face in enumerate(index):
        if i == skip:
            continue
        s = cosine(qvec, face["vec"])
        cur = best.get(face["intent_id"])
        if cur is None or s > cur["score"]:
            best[face["intent_id"]] = {"intent_id": face["intent_id"], "score": s,
                                       "matched_face": face["text"], "face_kind": face["kind"]}
    return sorted(best.values(), key=lambda x: -x["score"])


def _decide(ranked: list[dict], *, hit: float, margin: float) -> dict:
    """双门槛判定(纯函数,可离线测)。改错了不报错,只会静默把问题路由错。"""
    top1 = ranked[0]["score"] if ranked else 0.0
    top2 = ranked[1]["score"] if len(ranked) > 1 else 0.0
    gap = top1 - top2
    # 空路由优先于阈值:落在负例面上的问题,分数可以很高(它就是很像一个非问数问题),
    # 用阈值去拦它必然要把阈值抬到伤害真正例的位置。
    if ranked and ranked[0]["intent_id"] == NON_DATA_INTENT:
        return {"is_data_question": False, "confident": False, "reason": "null_route",
                "top1": top1, "margin": gap}
    if top1 < hit:
        return {"is_data_question": False, "confident": False, "reason": "below_hit_threshold",
                "top1": top1, "margin": gap}
    if gap < margin:
        return {"is_data_question": True, "confident": False, "reason": "ambiguous_margin",
                "top1": top1, "margin": gap}
    return {"is_data_question": True, "confident": True, "reason": "confident_hit",
            "top1": top1, "margin": gap}


async def retrieve(question: str, index: list[dict], *, hit: float = HIT_THRESHOLD,
                   margin: float = MARGIN_THRESHOLD, top_k: int = TOP_K) -> dict:
    """运行时入口。输出形状对齐 S4 路由要件。"""
    ranked = _score_intents(await embed_query(question), index)
    d = _decide(ranked, hit=hit, margin=margin)
    return {
        "question": question,
        "is_data_question": d["is_data_question"],
        "confident": d["confident"],
        "reason": d["reason"],
        "top1_score": round(d["top1"], 4),
        "margin": round(d["margin"], 4),
        "candidates": [{"intent_id": c["intent_id"], "score": round(c["score"], 4),
                        "matched_face": c["matched_face"], "face_kind": c["face_kind"]}
                       for c in ranked[:top_k]],
    }


def arbitrate(result: dict) -> str:
    """联调期最简三路裁决**桩**:接口形状留给 S4,B7 只实现"够分就走问数"。

    真正的三路裁决(精准问答 / 文档 RAG / 问数)是 S4 的事:那里要拿三条链路的分数横向比,
    这里只回答问数这一路的自评。
    """
    return "text2sql" if result["is_data_question"] else "fallback"


# --------------------------------------------------- 索引自洽性审计(向量层冲突)


def audit_index(index: list[dict]) -> list[dict]:
    """留一法审计:每条索引面**把自己排除**后再检索,必须检回自己所属的意图。

    这是 questions.py 文本层冲突检测的向量层对偶,两道关正交:文本不像但向量像的问法
    (换了一套词说同一件事)只有这里能抓到。检回别的意图的面 = 会把用户主动拉去错的模板,
    是索引里最有害的一类数据,应当删除或改写。
    """
    per_intent = {}
    for f in index:
        per_intent[f["intent_id"]] = per_intent.get(f["intent_id"], 0) + 1
    findings = []
    for i, face in enumerate(index):
        if face["kind"] == FACE_NON_DATA:
            continue  # 空路由负例面不审自己(它们本来就该互相像),但**留在索引里当竞争者**:
            #          某条相似问法若更像一句非问数问题,那是真冲突,必须被报出来
        if per_intent[face["intent_id"]] < 2:
            continue  # 把自己排除后这个意图就没有面了,判它"检错"没有意义
        ranked = _score_intents(face["vec"], index, skip=i)
        if not ranked:
            continue
        top = ranked[0]
        own = next((r for r in ranked if r["intent_id"] == face["intent_id"]), None)
        findings.append({
            "intent_id": face["intent_id"], "kind": face["kind"], "text": face["text"],
            "top1_intent": top["intent_id"], "top1_score": round(top["score"], 4),
            "own_score": round(own["score"], 4) if own else None,
            "ok": top["intent_id"] == face["intent_id"],
        })
    return findings
