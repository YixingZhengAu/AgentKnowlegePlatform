"""相似问法生成(B7 原样迁入):每个意图 → N 条模拟用户问法(索引面素材)。

概念与 S1 精准问答的"相似问题"完全一致(`server/app/services/exact_qa/similar_gen.py`),
这里是把它复用到**意图**上:索引里比的是"问句 vs 问句",而不是"问句 vs 说明文"。
相似问法是意图的**可配置资产**(AI 生成、人可编辑),落 `intent_questions` 表,
保存即重建该意图的索引面(`indexer.rebuild_intent_faces`)。

★ 从 S1 直接继承的两条教训(不是锦上添花,是被真 bug 逼出来的):
  ① **不许把问题问宽**:一条把限定词丢掉的问法会去劫持别的意图的用户问题;
  ② **跨条冲突检测**:同一句问法同时像两个意图,检索必然选错一个 —— 是索引里最脏的数据。
     本文件做的是**文本层**冲突(Jaccard 词集),向量层的自洽性审计在 retrieve.py
     (每条索引面必须检回自己所属的意图),两道关正交。

生成时把**兄弟意图的 one-liner 一并喂给模型**,要求"这条问法必须只能由本意图回答、
不能同时像列出的兄弟意图" —— 在源头上防冲突,比事后过滤便宜。
"""

from __future__ import annotations

import json
import re

from app.services.text2sql import bizdb
from app.services.text2sql.bizdb import BizConn
from app.services.text2sql.llm import complete

#: 每个意图生成几条相似问法
DEFAULT_N = 8
#: 跨意图文本冲突阈值(沿用 S1 CONFLICT_JACCARD:宁可少一条问法,也不要一句话像两个意图)
CONFLICT_JACCARD = 0.75

QUESTIONS_SCHEMA = {
    "name": "similar_questions",
    "schema": {
        "type": "object",
        "required": ["questions"],
        "properties": {
            "questions": {"type": "array", "items": {"type": "string"}},
        },
    },
}

SYSTEM_PROMPT = """\
You expand the retrieval surface of a data-question router.

A business intelligence assistant holds a fixed set of verified SQL templates. Each template
answers one INTENT. At runtime a user question is matched against indexed phrasings of every
intent, and the closest intent's template is used. Your job: write {n} alternative ways a real
employee at an Australian solar-equipment company would ask for exactly what THIS intent answers.

Rules:
1. Same information need, different wording. Every phrasing must be fully answered by this
   intent's template — no broader, no narrower, no extra dimension the template does not have.
2. Never widen a question by dropping what it is about. If the intent is "monthly outbound units
   by warehouse", then "How is our inventory doing?" is WRONG: it invites answers this template
   cannot give and will hijack unrelated questions. Keep every qualifier that makes the intent
   what it is (the entity, the measure, the grouping).
3. Must NOT fit any sibling intent listed below. A phrasing that could equally well be answered
   by a sibling is poison for the router — it makes the two intents indistinguishable. When two
   intents are close, keep the word that separates them (e.g. "by warehouse" vs "by product").
4. Vary the surface form, not the meaning: synonyms, word order, question vs. imperative.
   Include at least one short keyword-style phrasing ("Sydney outbound volume by month") and at
   least one full natural sentence ("Can you show me how many units we shipped out of each
   warehouse each month?"). Use everyday business words (shipped out, sales, best customers),
   not the database's column names.
5. Runtime parameters are free to vary — the rewriter fills them in. So DO include phrasings
   that name a concrete customer, warehouse, product, order or period (e.g. "last quarter",
   "for Sydney", "since March"). Two hard limits:
   a. Use ONLY the real values listed under real_values below. Never invent a customer name,
      product, SKU, warehouse city or order number — this company has exactly the customers,
      products and warehouses listed, and a made-up one makes the phrasing nonsense. Refer to a
      product the way a person would — by its SKU *or* by its name, never both glued together.
   b. Do NOT invent a filter the template does not have (e.g. a state, a sales rep, a cost or
      margin) — that would teach the router a question it cannot answer.
6. English only. One question per item, no numbering, no surrounding quotes.
"""

#: 真实取值(从演示业务库现取)。防模型编造 Perth 仓库 / 不存在的客户名 —— 相似问法是
#: 会被人审、会进演示的资产,编造值既误导审阅者,也教会路由器一堆库里没有的说法。
_VALUE_SQL = {
    "customers": "SELECT name FROM customers ORDER BY id LIMIT 6",
    "order_numbers": "SELECT order_no FROM orders ORDER BY order_date DESC LIMIT 3",
    "product_skus": "SELECT sku FROM products ORDER BY id LIMIT 6",
    "product_names": "SELECT name FROM products ORDER BY id LIMIT 6",
    "warehouses": "SELECT DISTINCT warehouse FROM stock_movements ORDER BY warehouse",
    "product_categories": "SELECT DISTINCT category FROM products ORDER BY category",
    "order_statuses": "SELECT DISTINCT status FROM orders ORDER BY status",
    "movement_types": "SELECT DISTINCT movement_type FROM stock_movements ORDER BY movement_type",
}


def value_book(conn: BizConn) -> dict:
    """从业务库现取真实取值。**这一步不能省**:B7 首轮没喂它时,模型编出了 Perth /
    Adelaide 仓库和不存在的客户与产品 —— 相似问法是会进演示、会被人审的资产,
    编造值既误导审阅者,也教会路由器一堆库里没有的说法。"""
    book = {k: [r[0] for r in bizdb.query(conn, sql)[1]] for k, sql in _VALUE_SQL.items()}
    book["data_window"] = "2024-09-01 to 2026-08-23 (today is 2026-08-23)"
    return book


def build_messages(intent: dict, siblings: list[dict], n: int, values: dict | None = None) -> list[dict[str, str]]:
    """intent = 本意图(published 里的 intent 段);siblings = 其余意图;values = 真实取值表。"""
    payload = {
        "real_values": values or {},
        "this_intent": {
            "kind": intent["type"],  # query = list rows / stats = aggregate
            "summary": _strip_prefix(intent["one_liner"]),
            "detail": intent["brief"],
            "tables": intent["tables"],
        },
        "sibling_intents": [
            {"id": s["intent_id"], "summary": _strip_prefix(s["one_liner"])} for s in siblings
        ],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(n=n)},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


async def gen_one(intent: dict, siblings: list[dict], n: int = DEFAULT_N,
                  values: dict | None = None) -> list[str]:
    out = await complete(
        build_messages(intent, siblings, n, values),
        tier="main",
        max_tokens=1200,
        json_schema=QUESTIONS_SCHEMA,
        tag=f"questions-{intent['intent_id']}",
    )
    return [q.strip() for q in out.get("questions", []) if q and q.strip()]


# ------------------------------------------------- 文本层过滤(纯函数,可离线测)


def _strip_prefix(one_liner: str) -> str:
    """剥掉治理前缀 "Query: " / "Stats: "。

    这两个词是给内部治理看的分型标签,用户问句里绝不会出现;留在索引面里
    只会给每条意图加一段共同的无关文本,把意图之间的区分度冲淡。
    """
    return re.sub(r"^\s*(query|stats)\s*:\s*", "", one_liner, flags=re.I).strip()


def normalize(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def conflicting_face(question: str, self_id: str, faces: list[tuple[str, str]],
                     threshold: float = CONFLICT_JACCARD) -> tuple[str, str] | None:
    """这句问法是否与**别的意图**的某个问题面撞车;撞了返回 (意图 id, 那句面)。"""
    tq = tokens(question)
    for iid, face in faces:
        if iid == self_id:
            continue
        if jaccard(tq, tokens(face)) >= threshold:
            return iid, face
    return None


def filter_questions(raw: dict[str, list[str]], summaries: dict[str, str]) -> tuple[dict[str, list[str]], list[dict]]:
    """把各意图的原始问法过滤成可入索引的问法集,返回 (保留结果, 丢弃记录)。

    过滤必须串行:要看全局问题面(某意图的问法不能撞上别意图的摘要或已接受的问法)。
    """
    faces: list[tuple[str, str]] = [(iid, s) for iid, s in summaries.items()]  # 摘要本身也是索引面
    kept_all: dict[str, list[str]] = {}
    dropped: list[dict] = []

    for iid, questions in raw.items():
        seen = {normalize(summaries[iid])}
        kept: list[str] = []
        for q in questions:
            if normalize(q) in seen:
                dropped.append({"intent_id": iid, "question": q, "reason": "duplicate of the intent summary or an earlier question"})
                continue
            clash = conflicting_face(q, iid, faces)
            if clash:
                dropped.append({"intent_id": iid, "question": q,
                                "reason": f"text conflict with {clash[0]}: \"{clash[1]}\""})
                continue
            seen.add(normalize(q))
            kept.append(q)
            faces.append((iid, q))  # 已接受的问法也进问题面,防后面的意图撞它
        kept_all[iid] = kept
    return kept_all, dropped
