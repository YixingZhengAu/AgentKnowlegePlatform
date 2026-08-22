"""M5 冒烟(连库 + 联网):/api/chat 三问 —— 正例 / 越界 / 困难负例。

断言的是 S1 最终要演示的那件事:
- **正例**:命中 → 内容与库里的标准答案**逐字相同**、`verified=true`、
  带一条 `message_citations`(citation_type=exact_qa,能点回原文)、**没有 generate stage**
  (命中不调生成模型,这是"零改写"的机器可证明形式);
- **越界问题**:不命中 → 落回生成,不带引用不带标注;
- **困难负例**(同领域但原文没答案):不命中,且 trace 里能查到
  分数 + 命中面 + 是哪道关否决的(护栏差集 / 复核理由)—— §5 M5 要求的埋点,
  不埋后面就没法调阈值。

跑法(需要先 make api,库里得有已采纳的 QA:先跑 smoke_s1_api.sh 或 smoke_exact_qa_store.py):
    cd server && uv run python -m scripts.smoke_s1_chat
"""

import asyncio
import json
import sys

import httpx
from sqlalchemy import select

from app.core.chat import STAGE_EXACT_QA, run_chat
from app.core.errors import AppError
from app.db import SessionLocal
from app.models import Agent, ExactQaItem, ExactQaVector, MessageCitation, Trace

#: 本机后端(SSE 那一步用;没起来就跳过那一步)
API_BASE = "http://localhost:8000"

#: 越界问题:与库里内容完全不相干(实测这类分数 0.13–0.38,阈值一刀切干净)
OUT_OF_SCOPE = "How do I reset my password for the portal?"
#: 困难负例:同领域、语义邻近,但原文没有这个答案(实测 0.61–0.83,阈值切不开)
HARD_NEGATIVE = "How many convolutional layers does Darknet-19 have?"


async def _pick_positive(session) -> tuple[ExactQaItem, str]:
    """从库里挑一条已采纳的 QA,用它**某条相似问**去问 —— 这才验到了"扩召回面"。"""
    rows = (
        await session.execute(
            select(ExactQaItem)
            .where(ExactQaItem.status == "enabled")
            .order_by(ExactQaItem.created_at.desc())
        )
    ).scalars().all()
    if not rows:
        raise SystemExit(
            "库里没有已启用的正式 QA —— 先跑 ./scripts/smoke_s1_api.sh 采纳一条"
        )
    for item in rows:
        faces = (
            await session.execute(
                select(ExactQaVector.question_text).where(ExactQaVector.item_id == item.id)
            )
        ).scalars().all()
        alt = [f for f in faces if f != item.standard_question]
        if alt:
            return item, alt[0]
    return rows[0], rows[0].standard_question


async def _trace_of(session, message_id, stage: str) -> Trace | None:
    return (
        await session.execute(
            select(Trace).where(Trace.message_id == message_id, Trace.stage == stage)
        )
    ).scalar_one_or_none()


async def _citations(session, message_id) -> list[MessageCitation]:
    return list(
        (
            await session.execute(
                select(MessageCitation).where(MessageCitation.message_id == message_id)
            )
        )
        .scalars()
        .all()
    )


async def _sse_events(agent_id, question: str) -> list[tuple[str, str]] | None:
    """打一次真 SSE,返回 [(event, data), ...];后端没起来返回 None(不让这一步变成假失败)。"""
    events: list[tuple[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{API_BASE}/api/agents/{agent_id}/chat",
                json={"question": question, "stream": True},
            ) as resp:
                resp.raise_for_status()
                name = ""
                async for line in resp.aiter_lines():
                    if line.startswith("event: "):
                        name = line[7:].strip()
                    elif line.startswith("data: "):
                        events.append((name, line[6:]))
    except httpx.HTTPError:
        return None
    return events


async def main() -> int:
    async with SessionLocal() as session:
        agent = (
            await session.execute(
                select(Agent).where(Agent.status == "active").order_by(Agent.created_at).limit(1)
            )
        ).scalar_one_or_none()
        if agent is None:
            raise SystemExit("没有 active 的 agent,请先 make seed")
        item, paraphrase = await _pick_positive(session)

    print(f"[chat] agent={agent.name}")
    # 稍微扰动一下(小写、去问号、口语开头):否则问的是索引里逐字存在的那句,
    # 分数必然 1.0,只能证明"通路是通的",证明不了"不是字符串精确匹配"。
    # 真正的改写召回质量由 Step 5 的 27 条评测集与 6c 的 store 冒烟负责。
    query = "so " + paraphrase.rstrip("?").lower()
    print(f"[chat] 正例:拿一条**相似问**扰动后来问(验扩召回面):{query!r}")
    print(f"       索引里的那句改写:{paraphrase!r}")
    print(f"       它对应的标准问:{item.standard_question!r}")

    # ---------------------------------------------------------- ① 正例
    print("\n① 正例(应命中,Verified Answer)")
    r = await run_chat(agent_id=agent.id, question=query)
    print(f"   verified={r.verified} status={r.status} 耗时 {r.latency_ms}ms 花费 ${r.cost_usd}")
    print(f"   stages={[s['stage'] for s in r.trace]}")
    print(f"   content: {r.content[:110]}…")
    assert r.verified, "正例没有命中(检查库里那条 QA 是否 enabled、阈值是否被改过)"
    assert r.content.strip() == item.answer.strip(), "命中必须**原样**返回标准答案(零改写)"
    assert "generate" not in [s["stage"] for s in r.trace], (
        "命中却调了生成模型 —— 那 Verified Answer 这个标注就不成立了"
    )
    assert r.citations and r.citations[0]["citation_type"] == "exact_qa", "命中必须带引用"
    extra = r.citations[0]["extra"]
    print(
        f"   引用: score={extra['score']} p{extra['page_idx']} "
        f"matched={extra['matched_question'][:60]!r} standard={extra['is_standard_question']}"
    )
    async with SessionLocal() as session:
        rows = await _citations(session, r.message_id)
        assert len(rows) == 1 and str(rows[0].ref_id) == str(item.id), "message_citations 没落库"
        span = await _trace_of(session, r.message_id, STAGE_EXACT_QA)
        assert span is not None and span.output["tier"] == "hit", "命中的 trace 不对"
        score = span.output["best_score"]
        print(f"   trace[{STAGE_EXACT_QA}]: tier=hit best_score={score}")
        assert score < 1.0, "分数正好 1.0 = 问的就是索引里逐字那句,这一轮没验到改写召回"

    # ---------------------------------------------------------- ② 越界
    print("\n② 越界问题(应不命中,落回生成)")
    r2 = await run_chat(agent_id=agent.id, question=OUT_OF_SCOPE)
    print(f"   verified={r2.verified} stages={[s['stage'] for s in r2.trace]}")
    print(f"   content: {r2.content[:110]}…")
    assert not r2.verified, "越界问题被标成了 Verified Answer"
    assert not r2.citations, "未命中不该有引用"
    assert "generate" in [s["stage"] for s in r2.trace], "未命中必须落回生成"
    async with SessionLocal() as session:
        span = await _trace_of(session, r2.message_id, STAGE_EXACT_QA)
        assert span is not None
        print(
            f"   trace: tier={span.output['tier']} best_score={span.output['best_score']} "
            f"(阈值 borderline 以下 → MISS)"
        )
        assert span.output["tier"] == "miss", "越界问题应该 MISS(分数远低于下限)"

    # ---------------------------------------------------------- ③ 困难负例
    print("\n③ 困难负例(同领域但原文没答案:不许命中,且 trace 要留下否决依据)")
    r3 = await run_chat(agent_id=agent.id, question=HARD_NEGATIVE)
    print(f"   verified={r3.verified} stages={[s['stage'] for s in r3.trace]}")
    assert not r3.verified, "★ 困难负例被标成了 Verified Answer —— 三段式里有一道关失效了"
    async with SessionLocal() as session:
        span = await _trace_of(session, r3.message_id, STAGE_EXACT_QA)
        assert span is not None
        out = span.output
        print(
            f"   trace: tier={out['tier']} best_score={out['best_score']}\n"
            f"          命中面: {(out['best_face'] or '')[:70]}\n"
            f"          护栏缺: {out.get('guard_missing')}  复核否决: {out.get('gate_reason')}"
        )
        assert out["tier"] in ("miss", "borderline")
        # ★ §5 M5 的埋点要求:分数 + 命中面 + 是哪道关挡的,三样都要能查到
        assert out["best_score"] is not None and out["best_face"], "trace 缺分数或命中面"
        if out["tier"] == "borderline":
            assert out.get("guard_missing") or out.get("gate_reason"), (
                "BORDERLINE 却没记是哪道关挡的 —— 以后没法调阈值"
            )

    # ---------------------------------------------------------- ④ SSE 路径
    # 前面三问走的是 run_chat()(非流式入口)。D4 说两条路径是同一份编排,
    # 但**事件协议**是前端真正消费的东西,得在 HTTP 上亲眼看一次:
    # 新增的 `verified` 事件必须出现,且命中时**不该有** generate 的 stage_start。
    print("\n④ SSE 路径(HTTP,验事件协议)")
    events = await _sse_events(agent.id, query)
    if events is None:
        print("   ⚠ 后端没在 8000 上,跳过(先 make api 再跑可覆盖这一步)")
    else:
        names = [e for e, _ in events]
        print(f"   事件序列: {' → '.join(dict.fromkeys(names))}")
        assert "verified" in names, "命中却没有 verified 事件,前端打不出 Verified Answer 标注"
        stage_starts = [json.loads(d)["stage"] for e, d in events if e == "stage_start"]
        assert stage_starts == [STAGE_EXACT_QA], f"命中时不该起 generate:{stage_starts}"
        done = json.loads(next(d for e, d in events if e == "done"))
        assert done["verified"] is True and done["citations"], "done 里缺 verified/citations"
        print(f"   done: verified={done['verified']} citations={len(done['citations'])} 条")

    # ---------------------------------------------------------- ⑤ 历史消息读回来
    # Step 7 留下的缺口:标注只存在于流式那一次的事件里,刷新页面就没了。
    # 现在 GET /messages 自己带 citations 与 verified,前端不必猜。
    print("\n⑤ 历史消息(GET /api/conversations/{id}/messages:刷新后标注还在吗)")
    async def _messages(conversation_id) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{API_BASE}/api/conversations/{conversation_id}/messages")
            resp.raise_for_status()
            return list(resp.json()["items"])

    try:
        # ①②③ 各自开了一轮会话(没传 conversation_id),所以要按会话分别读
        msgs = await _messages(r.conversation_id)
        miss_msgs = await _messages(r2.conversation_id)
    except httpx.HTTPError:
        print("   ⚠ 后端没在 8000 上,跳过")
    else:
        hit = next((m for m in msgs if m["id"] == str(r.message_id)), None)
        assert hit is not None, "刚才那条助手消息不在历史里"
        assert hit["verified"] is True, "★ 历史里的命中消息丢了 Verified 标注"
        assert len(hit["citations"]) == 1, "历史消息应带 1 条引用"
        c = hit["citations"][0]
        assert c["citation_type"] == "exact_qa" and c["extra"]["score"], "引用字段不全"
        # 越界那条不该被标注(判定规则在后端一处,前端不参与)
        miss = next((m for m in miss_msgs if m["id"] == str(r2.message_id)), None)
        assert miss is not None and miss["verified"] is False and not miss["citations"], (
            "未命中的历史消息不该带标注或引用"
        )
        print(
            f"   {len(msgs)} 条消息:命中那条 verified=True + 1 条引用"
            f"(score={c['extra']['score']} p{c['extra']['page_idx']}),越界那条无标注"
        )

    print("\n[chat] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except AppError as exc:
        print(f"[chat] 失败({exc.code}): {exc.message}")
        sys.exit(1)
