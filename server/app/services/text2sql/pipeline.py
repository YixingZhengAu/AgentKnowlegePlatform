"""端到端链路(B8 原样迁入):用户问题 → 检索 → 改写计划+应用 → 执行闸 → 结果包。

这个文件是 **`core/chat.py` 的 `retrieve_text2sql` stage 的核心**,所以它刻意不碰任何 I/O:
索引、发布包、语义层、业务库连接都从外面传进来,自己只负责编排与埋点。这样它既能被
chat 链路调用,也能被离线评测脚本调用,**两条路走的是同一段代码** —— 评测集才守得住回归。

链路四段(与 C5 要埋的 trace 五要素一一对应):
  ① retrieve   → 意图分数 + 命中模板 id   (trace: intent_scores, template_id)
  ② plan       → LLM 改写计划             (trace: plan)
  ③ apply      → 确定性应用器重建 SQL     (trace: final_sql)
  ④ execute    → 执行闸 + 取数            (trace: rowcount, latency_ms)

★ 三个终态,缺一不可(它们是三种完全不同的失败,混在一起就没法定位问题):
  * refused_non_data     检索层判"这不是问数" → 交回 S4 走其他链路,**一次 LLM 都不花**;
  * refused_out_of_template  是问数、命中了最近的模板,但 planner/应用器判定模板答不了;
  * executed             跑通取到数(可能 0 行,带 empty_result 标记)。
  另有 execution_failed:SQL 生成了但执行闸或数据库拒绝 —— 这一类**永远算失败**,
  因为它意味着应用器放过了一条自己都跑不通的 SQL,是 bug 而不是业务边界。

★ 为什么不确信(margin 不足)时仍然照跑:B7 的 confident=False 是"要不要加一步 LLM 复核"
  的信号,归 S4 决定。B8 离线链路不能替 S4 做这个决定,所以照跑 top1,但把
  needs_confirmation 挂在结果上,报告里单列 —— 让人看见"这题是踩线过的"。

★ 结果摘要(summary)是**代码算出来的**,不是 LLM 写的。S3 的交付物是表格 + 轨迹,
  自然语言叙述归 S4 的 generate stage;在这里插一次 LLM 会凭空多一个不受评测约束的环节。
"""

from __future__ import annotations

import time

from app.services.text2sql import retrieve as rt
from app.services.text2sql import rewrite as rw
from app.services.text2sql.bizdb import BizConn

#: 非问数拒答文案(面向用户,英文 —— 平台面向澳洲用户)。
#: 只说"这不是能从业务库查数回答的问题",不猜它属于哪条链路 —— 那是 S4 的裁决。
NON_DATA_REPLY = (
    "This does not look like a question I can answer from the business database. "
    "I can help with orders, customers, revenue and stock movement figures."
)

#: 模板外拒答的兜底文案(planner 通常会在 notes 里写清具体原因,这句是它没写时用的)
OUT_OF_TEMPLATE_REPLY = "This question is outside what the approved template can answer."

OUTCOMES = ("executed", "refused_out_of_template", "refused_non_data", "execution_failed")


def _summarise(intent: dict, exe: dict) -> str:
    """确定性英文结果摘要:行数 + 列名 + 首行(报告与 SSE 都用这一句)。"""
    if exe["rowcount"] == 0:
        return "Query ran successfully but matched no rows in the current data."
    cols = ", ".join(exe["cols"])
    first = ", ".join(f"{c}={v}" for c, v in zip(exe["cols"], exe["sample"][0], strict=True))
    return f"{exe['rowcount']} row(s) returned [{cols}]. Top row: {first}."


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def answer(question: str, index: list[dict], packages: dict[str, dict], layer: dict,
                 conn: BizConn) -> dict:
    """一问一答的完整链路。返回既能喂报告、也能喂 SSE trace 的结果包。"""
    timings: dict[str, int] = {}
    t_all = time.perf_counter()

    t0 = time.perf_counter()
    retrieved = await rt.retrieve(question, index)
    timings["retrieve"] = _ms(t0)

    out: dict = {
        "question": question,
        "route": rt.arbitrate(retrieved),
        "needs_confirmation": bool(retrieved["is_data_question"]) and not retrieved["confident"],
        "retrieval": retrieved,
        "intent_id": None, "intent_summary": None,
        "plan": None, "violations": [], "adjustments": [],
        "final_sql": None, "execution": None,
        "summary": None, "reply": None, "timings_ms": timings,
    }

    if not retrieved["is_data_question"]:
        out["outcome"] = "refused_non_data"
        out["reply"] = NON_DATA_REPLY
        out["summary"] = "Not a data question — handed back to the router."
        timings["total"] = _ms(t_all)
        return out

    intent_id = retrieved["candidates"][0]["intent_id"]
    package = packages[intent_id]
    out["intent_id"] = intent_id
    out["intent_summary"] = package["intent"]["one_liner"]

    # B6 的 rewrite() 已经把 计划 → 应用 → 执行 串好并逐步记录,这里不复制它的逻辑
    t0 = time.perf_counter()
    rec = await rw.rewrite(question, package, layer, conn)
    timings["rewrite_and_execute"] = _ms(t0)

    out["plan"] = rec.get("plan")
    out["violations"] = rec.get("violations", [])
    out["adjustments"] = rec.get("adjustments", [])
    out["final_sql"] = rec.get("final_sql")

    if rec["status"] in ("refused_by_planner", "rejected_by_applier"):
        out["outcome"] = "refused_out_of_template"
        out["refused_by"] = rec["status"]
        # 拒答文案只认 planner 的 `infeasible_reason`(它是专门写给用户的那一句)。
        # ★ 不再从 `notes` 里取第一条:notes 是记账(解析到的日期、没照办的次要细节),
        #   第一条经常与"为什么拒"无关 —— 那会让用户拿到一句答非所问的回答(D5 实测)。
        #   应用器拒绝的那条路没有面向用户的理由(violations 是内部术语),走固定文案。
        reason = ((rec.get("plan") or {}).get("infeasible_reason") or "").strip()
        out["reply"] = reason if reason else OUT_OF_TEMPLATE_REPLY
        out["summary"] = f"Refused ({rec['status']}): {out['reply']}"
    elif rec["status"] == "executed":
        out["outcome"] = "executed"
        out["execution"] = rec["execution"]
        out["summary"] = _summarise(package["intent"], rec["execution"])
        out["reply"] = out["summary"]
    else:
        out["outcome"] = "execution_failed"
        out["execution_error"] = rec.get("execution_error")
        out["summary"] = f"Execution failed: {rec.get('execution_error')}"

    timings["total"] = _ms(t_all)
    return out


def trace_events(result: dict) -> list[dict]:
    """把结果包摊成 C5 要埋的 trace 事件(五要素:意图分数/模板 id/计划/最终 SQL/行数+耗时)。

    在这里先把形状定下来,Phase C 接 `@traced` 时照抄即可,不用临时设计埋点字段。

    ★ 耗时的拆分(C5 补上的一处):改写与执行是在 `rw.rewrite()` 里连着跑的,`timings_ms`
      只有一个合计值。执行闸会回带自己的 `elapsed_ms`,所以这里把它减出去 ——
      两个 stage 的耗时相加仍然等于那个合计值,面板上不会凭空多出时间。
    """
    r = result["retrieval"]
    events = [{"stage": "retrieve_text2sql", "latency_ms": result["timings_ms"].get("retrieve"),
               "output": {"is_data_question": r["is_data_question"], "confident": r["confident"],
                          "top1_score": r["top1_score"], "margin": r["margin"],
                          "candidates": [{"intent_id": c["intent_id"], "score": c["score"]}
                                         for c in r["candidates"]]}}]
    joint = result["timings_ms"].get("rewrite_and_execute")
    exec_ms = (result.get("execution") or {}).get("elapsed_ms")
    plan_ms = joint - exec_ms if (joint is not None and exec_ms is not None) else joint
    if result["intent_id"]:
        events.append({"stage": "rewrite_sql",
                       "latency_ms": plan_ms,
                       "output": {"template_id": result["intent_id"], "plan": result["plan"],
                                  "final_sql": result["final_sql"],
                                  "violations": result["violations"],
                                  "adjustments": result["adjustments"]}})
    if result.get("execution"):
        e = result["execution"]
        events.append({"stage": "execute_sql", "latency_ms": exec_ms,
                       "output": {"sql_executed": e["sql_executed"], "rowcount": e["rowcount"],
                                  "cols": e["cols"], "flags": e["flags"]}})
    return events
