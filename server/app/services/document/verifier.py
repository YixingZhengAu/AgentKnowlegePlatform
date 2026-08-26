"""一致性后校验:答案里的每个结论,材料里是否真的有支撑(分册 3 §5-4)。

**默认关**(`DOC_RAG_VERIFY=false`)。开了就在生成之后多跑一次 light 模型,
把"有材料但概括过头"的句子挑出来。默认关的理由:每次问答多一次 LLM 调用,
而它挡的是低频问题;演示时可以当亮点打开。

🩸 **判据必须写清"什么不构成否决"** —— 照搬 S1 那道 hit gate 的教训:
校验器天然倾向于"严格",不告诉它哪些情况合法,它会否掉措辞朴素的正确答案。
"""

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.document.llm import parse_structured

log = get_logger(__name__)

_INSTRUCTIONS = """You check whether an answer stays within its source excerpts.

Report ONLY claims that the excerpts do not support. For each one, quote the claim \
verbatim and say in one short sentence what the excerpts actually say instead.

None of the following is a reason to report a claim:
- the answer is short, blunt or plainly worded;
- the answer omits detail the user did not ask for;
- the answer paraphrases or summarises instead of quoting;
- the answer merges facts from several excerpts;
- the answer restates the question, or adds an ordinary connective phrase;
- a number or name is formatted differently but means the same thing.

Report a claim only when the excerpts contradict it, or contain nothing about it \
at all. If every claim is supported, return an empty list."""


class UnsupportedClaim(BaseModel):
    """一条没被材料支撑的结论。"""

    claim: str = Field(description="The unsupported sentence, quoted from the answer")
    reason: str = Field(description="What the excerpts actually say, in one sentence")


class VerifyReport(BaseModel):
    """校验结果 —— 只装被否决的部分,全部通过时是空列表。"""

    unsupported: list[UnsupportedClaim] = []


async def verify(answer: str, evidence: str) -> VerifyReport:
    """检查 `answer` 的每个结论在 `evidence` 里是否站得住。

    Args:
        answer: 生成模型的完整回答。
        evidence: 拼进 prompt 的那段证据原文(与模型看到的逐字相同)。

    Returns:
        校验报告;**校验自身出错时返回空报告** —— 它是诊断工具,
        不能因为它挂了就把一个已经答完的问答弄失败。
    """
    try:
        report, result = await parse_structured(
            VerifyReport,
            instructions=_INSTRUCTIONS,
            user_content=f"EXCERPTS\n{evidence}\n\nANSWER\n{answer}",
            tier="light",
        )
        log.info(
            "doc_rag_verify_done",
            unsupported=len(report.unsupported),
            cost_usd=str(result.cost_usd),
        )
        return report
    except Exception as exc:
        # 🩸 整个函数体都要在 try 里:校验是诊断工具,连它自己的日志行炸了
        # 都不该把一次已经答完的问答变成失败(实测踩过一次:写错了 result 的字段名)
        log.warning("doc_rag_verify_failed", error=str(exc))
        return VerifyReport()
