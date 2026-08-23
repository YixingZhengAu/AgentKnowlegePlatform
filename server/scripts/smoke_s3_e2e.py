"""S3 冒烟:把 B8 冻结的 20 题评测集在**正式代码路径**上重跑一遍。

用法:
  `uv run python -m scripts.smoke_s3_e2e --check`   零 LLM 的确定性复验(默认,`make smoke-s3` 走它)
  `uv run python -m scripts.smoke_s3_e2e --all`     全链路真调 LLM(会花钱,约 20 次 gpt-5)
  `uv run python -m scripts.smoke_s3_e2e --question "..."`  只问一句,打印全链路中间产物

★ **这个脚本存在的理由**:Phase C 的承诺是"只换基础设施,不改核心逻辑"。这种承诺没法靠
  读代码确认 —— 只能靠同一套评测集在新路径上跑出同样的分数。所以它不是"有空跑跑的测试",
  它是那句承诺的**唯一证据**。B 阶段的成绩:20/20,越界与拒答硬闸门 7/7,execution_failed 0。

★ 两种模式分工(沿用 B8 的划分):
  * `--all` 每题真调一次 gpt-5 产改写计划 —— 测的是「今天这条链路还跑得通吗」;
  * `--check` 重放**已存的计划**(`fixtures/s3/eval_plans.json`,B8 闸门那次跑出来的),
    只把应用器 + 执行闸 + 全部断言再走一遍 —— 完全确定性、零 LLM 成本,
    适合每次改动后无脑重跑。检索仍然真跑(现算 embedding),所以改了相似问法、
    阈值或空路由,它会照实报"检索结论变了,旧计划不可复用",不会假装通过。
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import KnowledgeBase, SqlIntent
from app.services.text2sql import bizdb, executor, indexer, semantic
from app.services.text2sql import pipeline as pl
from app.services.text2sql import retrieve as rt
from app.services.text2sql import rewrite as rw

FIXTURES = Path(__file__).parent / "fixtures" / "s3"
#: 这两类是硬闸门:答错一题就是"该拒的没拒"或"该答的拒了",没有商量余地
STRICT_KINDS = ("out_of_template", "non_data")
PASS_RATE = 0.90


# ------------------------------------------------------------------ 装载


async def load_context(session) -> tuple[dict, list[dict], dict, dict]:
    """从正式表装出链路要的四样东西:kb / 索引 / 发布包 / 语义层。

    发布包(package)的形状与 Phase B 的 `out/published/*.json` 逐字一致 ——
    改写层吃的就是这个形状,换个形状就等于改了它的输入。
    """
    kb = (await session.scalars(
        select(KnowledgeBase).where(KnowledgeBase.type == "text2sql")
        .order_by(KnowledgeBase.created_at))).first()
    if kb is None:
        raise SystemExit("没有 text2sql 知识库。先跑:uv run python -m scripts.seed_minimal")

    index = await rt.load_index(session, kb.id)
    intents = (await session.scalars(
        select(SqlIntent).where(SqlIntent.kb_id == kb.id,
                                SqlIntent.status == "published"))).all()
    if not intents or not index:
        raise SystemExit("库里没有已发布意图或索引面。先跑:uv run python -m scripts.seed_s3_demo")

    packages: dict[str, dict] = {}
    for it in intents:
        packages[it.code] = {
            "intent": {"intent_id": it.code, "type": it.intent_type, "bucket": it.bucket,
                       "one_liner": it.one_liner, "brief": it.brief, "tables": list(it.tables)},
            "sql": it.sql,
            "params": it.params,
        }
    layer = await semantic.load_layer(session, intents[0].datasource_id)
    return kb, index, packages, layer


# ------------------------------------------------------------------ 断言


def verify(case: dict, res: dict) -> list[dict]:
    """把 expect 逐条翻成可打勾的检查项(与 B8 的 `verify()` 同一份逻辑)。"""
    e = case["expect"]
    checks: list[dict] = []

    def add(desc: str, ok: bool, got: str = "") -> None:
        checks.append({"desc": desc, "ok": bool(ok), "got": got})

    add("链路未以 SQL 执行错误收尾(执行失败永远算 bug,不算业务边界)",
        res["outcome"] != "execution_failed", res.get("execution_error", "") or "-")
    add(f"路由 = {e['route']}", res["route"] == e["route"], res["route"])
    add(f"终态 = {e['outcome']}", res["outcome"] == e["outcome"], res["outcome"])

    if "intent" in e:
        add(f"命中意图 = {e['intent']}", res["intent_id"] == e["intent"], res["intent_id"] or "-")
    elif "intent_in" in e:
        add(f"命中意图 ∈ {e['intent_in']}", res["intent_id"] in e["intent_in"],
            res["intent_id"] or "-")

    sql = res.get("final_sql") or ""
    for s in e.get("sql_contains", []):
        add(f"最终 SQL 含 `{s}`", s.lower() in sql.lower())
    for s in e.get("sql_not_contains", []):
        add(f"最终 SQL 不含 `{s}`", s.lower() not in sql.lower())
    if e.get("no_sql"):
        add("未生成任何 SQL(拒答必须发生在生成之前)", not sql, sql[:60] or "-")
    if e.get("no_llm"):
        add("未花任何 LLM 调用(非问数应在检索层被拦下)", res.get("plan") is None)

    cols = (res.get("execution") or {}).get("cols", [])
    for c in e.get("cols_include", []):
        add(f"结果列含 `{c}`", c in cols, ", ".join(cols) or "-")
    for c in e.get("cols_exclude", []):
        add(f"结果列不含 `{c}`", c not in cols, ", ".join(cols) or "-")
    if e.get("nonempty"):
        rc = (res.get("execution") or {}).get("rowcount", 0)
        add("结果非空(断言才测得到东西)", rc > 0, str(rc))
    return checks


def _wrap(case: dict, res: dict) -> dict:
    checks = verify(case, res)
    return {**res, "case_id": case["case_id"], "kind": case["kind"],
            "expect": case["expect"], "checks": checks,
            "ok": all(c["ok"] for c in checks)}


# ------------------------------------------------------------------ 跑批


async def run_case(case: dict, index, packages, layer, conn) -> dict:
    res = await pl.answer(case["question"], index, packages, layer, conn)
    return _wrap(case, res)


async def replay_case(case: dict, saved: dict, index, packages, layer, conn) -> dict:
    """--check:不调 LLM。检索真跑,改写计划取已存的,重放应用器 + 执行闸 + 全部断言。"""
    retrieved = await rt.retrieve(case["question"], index)
    res: dict = {
        "question": case["question"], "route": rt.arbitrate(retrieved),
        "needs_confirmation": retrieved["is_data_question"] and not retrieved["confident"],
        "retrieval": retrieved, "intent_id": None, "intent_summary": None,
        "plan": None, "violations": [], "adjustments": [], "final_sql": None,
        "execution": None, "summary": None, "reply": None, "timings_ms": {}, "replayed": True,
    }

    if not retrieved["is_data_question"]:
        res.update(outcome="refused_non_data", reply=pl.NON_DATA_REPLY,
                   summary="Not a data question — handed back to the router.")
        return _wrap(case, res)

    intent_id = retrieved["candidates"][0]["intent_id"]
    plan = saved.get("plan")
    if intent_id != saved.get("intent_id") or plan is None:
        # 检索结论变了(改过相似问法/阈值/空路由)→ 旧计划不可复用。如实标记,不假装通过
        res.update(outcome="replay_stale", intent_id=intent_id,
                   summary=f"检索命中 {intent_id},与已存记录 {saved.get('intent_id')} 不一致,"
                           f"需重跑 --all")
        return {**res, "case_id": case["case_id"], "kind": case["kind"],
                "expect": case["expect"], "ok": False,
                "checks": [{"desc": "已存计划可复用(检索结论未变)", "ok": False,
                            "got": f"{saved.get('intent_id')} → {intent_id}"}]}

    package = packages[intent_id]
    res.update(intent_id=intent_id, intent_summary=package["intent"]["one_liner"], plan=plan)
    if not plan.get("feasible", False):
        # 与 `pipeline.answer` 同一条规则:拒答文案取 planner 的 `infeasible_reason`。
        # 已存的计划(B8 冻结的 `eval_plans.json`)早于这个字段,所以重放时会落到固定文案 ——
        # 断言不看文案,这不影响成绩;要看真实理由请跑 `--all`。
        reason = (plan.get("infeasible_reason") or "").strip()
        res.update(outcome="refused_out_of_template", refused_by="refused_by_planner",
                   reply=reason or pl.OUT_OF_TEMPLATE_REPLY)
        res["summary"] = f"Refused (refused_by_planner): {res['reply']}"
    else:
        applied = rw.apply_plan(package, plan, layer)
        res["violations"], res["adjustments"] = applied["violations"], applied["adjustments"]
        if not applied["ok"]:
            res.update(outcome="refused_out_of_template", refused_by="rejected_by_applier",
                       reply="Rejected by the applier.", summary="Refused (rejected_by_applier).")
        else:
            res["final_sql"] = applied["sql"]
            try:
                exe = await executor.agate_and_execute(conn, applied["sql"], layer)
                res.update(outcome="executed", execution=exe,
                           summary=pl._summarise(package["intent"], exe))
                res["reply"] = res["summary"]
            except Exception as ex:  # noqa: BLE001 —— 执行失败要如实记录,不吞
                res.update(outcome="execution_failed", execution_error=str(ex),
                           summary=f"Execution failed: {ex}")
    return _wrap(case, res)


# ------------------------------------------------------------------ 输出


def print_case_detail(res: dict) -> None:
    r = res["retrieval"]
    print(f"\n问题:{res['question']}")
    print(f"  ① 检索  is_data={r['is_data_question']} confident={r['confident']} "
          f"reason={r['reason']} top1={r['top1_score']} margin={r['margin']}")
    for c in r["candidates"]:
        print(f"        {c['intent_id']:<14} {c['score']:.4f}  [{c['face_kind']}] "
              f"{c['matched_face'][:70]}")
    if res.get("plan"):
        p = res["plan"]
        print(f"  ② 计划  feasible={p.get('feasible')} outputs={p.get('outputs_selected')}")
        print(f"        groupbys={p.get('groupbys_selected')}")
        for f in p.get("filters", []):
            print(f"        filter {f['param_id']:<22} enabled={f['enabled']} value={f['value']!r}")
        for n in p.get("notes", []):
            print(f"        note: {n}")
    if res.get("adjustments"):
        for a in res["adjustments"]:
            print(f"  ③ 应用器调整  {a}")
    if res.get("violations"):
        for v in res["violations"]:
            print(f"  ③ 应用器拒绝  {v}")
    if res.get("final_sql"):
        print(f"  ④ 最终 SQL  {res['final_sql']}")
    if res.get("execution"):
        e = res["execution"]
        print(f"  ⑤ 执行  {e['rowcount']} 行 {e['cols']} flags={e['flags']}")
        for row in e["sample"][:3]:
            print(f"        {row}")
    print(f"  终态:{res['outcome']}  |  {res.get('summary')}")


def summarise(results: list[dict]) -> dict:
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    strict = [r for r in results if r["kind"] in STRICT_KINDS]
    strict_ok = sum(1 for r in strict if r["ok"])
    failed_exec = sum(1 for r in results if r["outcome"] == "execution_failed")
    return {"total": total, "ok": ok, "rate": ok / total if total else 0.0,
            "strict": len(strict), "strict_ok": strict_ok, "failed_exec": failed_exec}


# ------------------------------------------------------------------ 入口


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="全链路真调 LLM(会花钱)")
    ap.add_argument("--check", action="store_true", help="零 LLM 确定性复验(默认)")
    ap.add_argument("--question", help="只问一句,打印全链路中间产物")
    ap.add_argument("--verbose", action="store_true", help="逐题打印中间产物")
    args = ap.parse_args()

    conn = bizdb.demo_conn()
    async with SessionLocal() as session:
        kb, index, packages, layer = await load_context(session)
        size = await indexer.index_size(session, kb.id)

    print(f"知识库 {kb.name} · 已发布意图 {size['intents']} 个 · 索引面 {size['faces']} 条"
          f"(摘要 {size['summary']} + 问法 {size['question']} + 空路由 {size['non_data']})")
    print(f"业务库 {conn.masked()} · 语义层 {len(layer['tables'])} 表")

    if args.question:
        res = await pl.answer(args.question, index, packages, layer, conn)
        print_case_detail(res)
        print("\ntrace 事件(C5 要埋的五要素):")
        for ev in pl.trace_events(res):
            # execute_sql 的耗时目前是 None:改写与执行是在 rewrite() 里连着跑的,
            # 只计了一个合计值。C5 接 @traced 时按 stage 各计一次,这里不替它改 pipeline
            ms = f"{ev['latency_ms']}ms" if ev["latency_ms"] is not None else "—"
            print(f"  [{ev['stage']}] {ms} "
                  f"{json.dumps(ev['output'], ensure_ascii=False)[:160]}")
        return 0

    cases = json.loads((FIXTURES / "eval_cases.json").read_text())
    mode = "all" if args.all else "check"
    saved = {} if mode == "all" else json.loads(
        (FIXTURES / "eval_plans.json").read_text())["plans"]
    print(f"评测集 {len(cases)} 题 · 模式 {mode}"
          f"{'(真调 LLM)' if mode == 'all' else '(零 LLM:重放已存计划)'}\n")

    results = []
    for case in cases:
        if mode == "all":
            res = await run_case(case, index, packages, layer, conn)
        else:
            res = await replay_case(case, saved.get(case["case_id"], {}),
                                    index, packages, layer, conn)
        results.append(res)
        mark = "✅" if res["ok"] else "❌"
        print(f"  {mark} {res['case_id']} [{res['outcome']}] {res['intent_id'] or '—'} · "
              f"{res['question'][:60]}")
        if not res["ok"]:
            for c in res["checks"]:
                if not c["ok"]:
                    print(f"        ✗ {c['desc']}  (实际:{c['got']})")
        if args.verbose:
            print_case_detail(res)

    st = summarise(results)
    print(f"\n总体:{st['ok']}/{st['total']} = {st['rate']:.1%}(线 ≥{PASS_RATE:.0%})")
    print(f"越界/拒答硬闸门:{st['strict_ok']}/{st['strict']}(线 100%)")
    outcomes: dict[str, int] = {}
    for r in results:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    print(f"终态分布:{outcomes}")
    thin = [r["case_id"] for r in results if r.get("needs_confirmation")]
    if thin:
        print(f"踩线过(检索边距不足,照跑 top1):{thin}")

    passed = (st["rate"] >= PASS_RATE and st["strict_ok"] == st["strict"]
              and st["failed_exec"] == 0)
    print("✅ S3 冒烟通过" if passed else "❌ S3 冒烟未通过")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
