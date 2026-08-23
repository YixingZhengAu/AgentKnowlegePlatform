"""C5 冒烟(连库 + 联网):问数链路接进 `/api/chat` 后的三问 —— 命中 / 模板外 / 非问数。

断言的是 S3 最终要演示的那件事:

* **命中**:`executed` → 内容是**代码算出来的**结论(没过生成模型)、`verified=true`、
  带一条 `citation_type=sql` 的引用(最终 SQL + 结果表格 + 行数)、trace 里
  **五要素齐全**(意图分数 / 模板 id / 改写计划 / 最终 SQL / 行数+耗时);
* **模板外**:`refused_out_of_template` → 返回拒答话术,**不落到生成模型**
  (交给它只会换来一个听起来合理的编数,而这是问数链路最不能出的错);
* **非问数**:`refused_non_data` → 检索层就判掉了,**这一段零 LLM**(trace 里没有
  token 记账),然后照常落回生成。

第四步在真 HTTP 上看一眼 SSE 事件协议:命中时必须有 `verified` 事件、且不该起 generate。

跑法(需要 make api + make seed-s3):
    cd server && uv run python -m scripts.smoke_s3_chat
"""

import asyncio
import json
import sys

import httpx
from sqlalchemy import select

from app.core.chat import STAGE_EXACT_QA, STAGE_TEXT2SQL, run_chat
from app.db import SessionLocal
from app.models import Agent, MessageCitation, SqlIntent, Trace

API_BASE = "http://localhost:8000"

#: 三个代表问题,逐字取自 B8 冻结的评测集(`fixtures/s3/eval_cases.json`)——
#: 不另写一套,好让这里的结论与 `smoke_s3_e2e.py` 的结论可以互相对照
Q_HIT = "Monthly revenue trend since January 2026"                    # E04 executed
Q_OUT = "Monthly revenue broken down by product category"             # E14 refused_out_of_template
#: E18 refused_non_data —— 这题是**空路由**拦下的(它以 0.5183 确信命中过库存意图)
Q_NON = "What's the warranty period on the HC-300 battery cabinet?"


async def _traces(session, message_id) -> dict[str, Trace]:
    rows = (
        await session.execute(select(Trace).where(Trace.message_id == message_id))
    ).scalars().all()
    return {t.stage: t for t in rows}


async def _citations(session, message_id) -> list[MessageCitation]:
    return list(
        (
            await session.execute(
                select(MessageCitation).where(MessageCitation.message_id == message_id)
            )
        ).scalars().all()
    )


async def _sse_events(agent_id, question: str) -> list[tuple[str, str]] | None:
    """打一次真 SSE,返回 [(event, data), ...];后端没起来返回 None(不让它变成假失败)。"""
    events: list[tuple[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=180) as client:
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
        published = (
            await session.execute(
                select(SqlIntent.code).where(SqlIntent.status == "published")
            )
        ).scalars().all()
        if not published:
            raise SystemExit("库里没有已发布意图 —— 先跑 make seed-s3")
    print(f"[chat] agent={agent.name} 已发布意图 {len(published)} 个")

    # ---------------------------------------------------------- ① 命中并执行
    print(f"\n① 命中(应 executed,Verified):{Q_HIT!r}")
    r = await run_chat(agent_id=agent.id, question=Q_HIT)
    stages = [s["stage"] for s in r.trace]
    print(f"   verified={r.verified} stages={stages} 耗时 {r.latency_ms}ms 花费 ${r.cost_usd}")
    print(f"   content: {r.content[:140]}")
    assert r.verified, "问数命中却没标 verified(检查 seed-s3 与阈值)"
    assert "generate" not in stages, (
        "★ 命中却调了生成模型 —— 结论那句话必须是代码从结果集算出来的,不然 Verified 不成立"
    )
    assert stages[-3:] == [STAGE_TEXT2SQL, "rewrite_sql", "execute_sql"], f"stage 不全:{stages}"
    assert r.citations and r.citations[0]["citation_type"] == "sql", "命中必须带 sql 引用"
    extra = r.citations[0]["extra"]
    print(f"   引用: intent={extra['intent_code']} score={extra['score']} "
          f"rows={extra['rowcount']} cols={extra['cols']}")
    print(f"   SQL: {r.citations[0]['snippet'][:120]}…")
    assert extra["rowcount"] > 0 and extra["rows"], "引用里没带结果表格(前端要画表)"
    assert extra["cols"], "引用里没带列名"

    async with SessionLocal() as session:
        rows = await _citations(session, r.message_id)
        assert len(rows) == 1 and rows[0].citation_type == "sql", "message_citations 没落库"
        intent = await session.get(SqlIntent, rows[0].ref_id)
        assert intent is not None, "★ 引用的 ref_id 指不到意图行(前端点不回去)"
        spans = await _traces(session, r.message_id)
        # ★ trace 五要素:意图分数 / 模板 id / 改写计划 / 最终 SQL / 行数 + 耗时
        rt, rw, ex = spans[STAGE_TEXT2SQL], spans["rewrite_sql"], spans["execute_sql"]
        assert rt.output["top1_score"] is not None and rt.output["candidates"], "缺意图分数"
        assert rw.output["template_id"] == extra["intent_code"], "缺模板 id"
        assert rw.output["plan"], "缺改写计划"
        assert rw.output["final_sql"], "缺最终 SQL"
        assert ex.output["rowcount"] > 0 and ex.latency_ms is not None, "缺行数或取数耗时"
        assert rw.latency_ms is not None, "缺改写耗时"
        print(f"   trace 五要素齐:score={rt.output['top1_score']} "
              f"template={rw.output['template_id']} plan={list(rw.output['plan'])} "
              f"rows={ex.output['rowcount']} 改写 {rw.latency_ms}ms + 取数 {ex.latency_ms}ms")
        # ★ 账记在 rewrite_sql 上(唯一一次模型调用是改写计划),不记在检索那一段
        assert (rw.prompt_tokens or 0) > 0, (
            "★ 改写模型的账没记进 trace —— 这条链路在成本面板上是个黑洞"
        )
        assert not rt.prompt_tokens, "检索段不该有 token 账(它只算一次 embedding)"
        # 三段耗时相加不该超过整体:检索段的耗时被改成"只有检索那一段"就是为了这个
        assert (rt.latency_ms + rw.latency_ms + ex.latency_ms) <= r.latency_ms + 5, (
            "★ 三个 stage 的耗时之和大于总耗时 —— 有一段被重复计了"
        )
        print(f"   记账:{rw.prompt_tokens}+{rw.completion_tokens} tokens / ${rw.cost_usd} "
              f"(model={rw.model});检索 {rt.latency_ms}ms 零 LLM")

    # ---------------------------------------------------------- ② 模板外
    print(f"\n② 模板外(应 refused_out_of_template,不落生成):{Q_OUT!r}")
    r2 = await run_chat(agent_id=agent.id, question=Q_OUT)
    stages2 = [s["stage"] for s in r2.trace]
    print(f"   verified={r2.verified} stages={stages2}")
    print(f"   content: {r2.content[:160]}")
    assert not r2.verified, "模板外拒答被标成了 Verified"
    assert not r2.citations, "拒答不该有引用"
    assert "generate" not in stages2, (
        "★ 模板外的问题落到了生成模型 —— 那会换来一个听起来合理的编数"
    )
    assert "execute_sql" not in stages2, "拒答却执行了 SQL"
    async with SessionLocal() as session:
        spans = await _traces(session, r2.message_id)
        rw = spans["rewrite_sql"]
        assert rw.output["final_sql"] is None, "拒答不该有最终 SQL"
        print(f"   trace: 命中最近的模板 {rw.output['template_id']},"
              f"feasible={rw.output['plan'].get('feasible')} "
              f"violations={rw.output['violations']}")
        # ★ 拒答文案必须是 planner 专门写给用户的那一句(`infeasible_reason`)。
        #   D5 实测过的坑:早先取的是 `notes[0]`,而那条常是"日期解析成了几号"这种记账 ——
        #   于是"问了利润率"换来一句讲日期的回答。断言把这个坑钉死。
        reason = (rw.output["plan"].get("infeasible_reason") or "").strip()
        assert reason, "★ planner 说不可行却没写 infeasible_reason —— 用户会拿到一句兜底文案"
        assert r2.content.strip() == reason, (
            f"★ 给用户的拒答文案不是 infeasible_reason:{r2.content[:80]!r}"
        )
        print(f"          拒答理由(直接给用户看的那句):{r2.content[:100]}")

    # ---------------------------------------------------------- ③ 非问数
    print(f"\n③ 非问数(应 refused_non_data,零 LLM,然后落回生成):{Q_NON!r}")
    r3 = await run_chat(agent_id=agent.id, question=Q_NON)
    stages3 = [s["stage"] for s in r3.trace]
    print(f"   verified={r3.verified} stages={stages3}")
    assert not r3.verified, "非问数问题被标成了 Verified"
    assert "rewrite_sql" not in stages3, "★ 非问数问题居然进了改写(空路由没拦住)"
    assert "generate" in stages3, "非问数应落回生成(它可能是别的链路答的)"
    async with SessionLocal() as session:
        spans = await _traces(session, r3.message_id)
        rt = spans[STAGE_TEXT2SQL]
        assert rt.output["is_data_question"] is False, "检索层没判成非问数"
        assert not rt.prompt_tokens and rt.cost_usd is None, (
            "★ 非问数拒答花了 LLM token —— 「检索层拒答零成本」这句话就不成立了"
        )
        print(f"   trace: is_data_question=false top1={rt.output['top1_score']} "
              f"top1 面 = {rt.output['candidates'][0]['intent_id']}(零 LLM 记账)")

    # ---------------------------------------------------------- ④ SSE 事件协议
    print("\n④ SSE 路径(HTTP,验事件协议)")
    events = await _sse_events(agent.id, Q_HIT)
    if events is None:
        print("   ⚠ 后端没在 8000 上,跳过(先 make api 再跑可覆盖这一步)")
    else:
        names = [e for e, _ in events]
        print(f"   事件序列: {' → '.join(dict.fromkeys(names))}")
        assert "verified" in names, "命中却没有 verified 事件,前端打不出 Verified 标注"
        verified_ev = json.loads(next(d for e, d in events if e == "verified"))
        assert verified_ev["source"] == "text2sql", f"verified.source 不对:{verified_ev}"
        starts = [json.loads(d)["stage"] for e, d in events if e == "stage_start"]
        assert "generate" not in starts, f"命中时不该起 generate:{starts}"
        assert starts == [STAGE_EXACT_QA, STAGE_TEXT2SQL, "rewrite_sql", "execute_sql"], (
            f"stage_start 序列不对:{starts}"
        )
        done = json.loads(next(d for e, d in events if e == "done"))
        assert done["verified"] is True and done["citations"], "done 里缺 verified/citations"
        c = done["citations"][0]
        assert c["citation_type"] == "sql" and c["extra"]["cols"], "done 的引用里缺结果表格"
        print(f"   done: verified={done['verified']} 引用 1 条(sql,"
              f"{c['extra']['rowcount']} 行 / {len(c['extra']['cols'])} 列)")

    print("\n[chat] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
