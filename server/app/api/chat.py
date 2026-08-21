"""问答接口:SSE 流式 + 非流式,都走 `app.core.chat`。

事件协议(S1–S4 只增加事件类型,不改协议):

```
event: meta         data: {"message_id": "...", "conversation_id": "..."}
event: stage_start  data: {"stage": "generate"}
event: token        data: {"text": "..."}
event: stage_end    data: {"stage": "generate", "latency_ms": 812, "usage": {...}}
event: done         data: {"message_id": "...", "citations": [], "trace": [...]}
event: error        data: {"stage": "generate", "message": "..."}   # 只在失败时出现
```

`meta` 是对计划里四个事件的补充:新开会话时前端要在第一个 token 之前就拿到
conversation_id / message_id(否则无法在 done 之前把这条消息挂到正确的会话上)。
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.chat import ChatEvent, chat_events, run_chat
from app.core.errors import AppError
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/agents", tags=["chat"])
log = get_logger(__name__)

# 编排没能开始时的 done 事件骨架:字段齐全、值为空,前端不用做特判
_ABORTED = {
    "message_id": None,
    "conversation_id": None,
    "status": "failed",
    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    "cost_usd": "0",
    "latency_ms": 0,
    "citations": [],
    "trace": [],
}


def _sse(ev: ChatEvent) -> str:
    return f"event: {ev.event}\ndata: {json.dumps(ev.data, ensure_ascii=False)}\n\n"


async def _sse_stream(
    *, agent_id: uuid.UUID, req: ChatRequest, user_id: uuid.UUID
) -> AsyncIterator[str]:
    """把事件流转成 SSE 文本。

    关键点:**流一旦开始,HTTP 状态码就定死是 200 了** —— 之后再抛异常,全局异常
    handler 也改不了状态码,客户端只会看到连接莫名断掉。所以这里把"编排还没开始就失败"
    (agent 不存在、DB 连不上)的异常也翻译成协议内的 error + done 事件:
    前端永远只需要处理一种终止信号(done),不需要额外识别"连接断了"。
    """
    try:
        async for ev in chat_events(
            agent_id=agent_id,
            question=req.question,
            conversation_id=req.conversation_id,
            user_id=user_id,
        ):
            yield _sse(ev)
    except AppError as exc:
        yield _sse(ChatEvent("error", {"code": exc.code, "message": exc.message}))
        yield _sse(ChatEvent("done", {**_ABORTED, "error": f"{exc.code}: {exc.message}"}))
    except Exception as exc:
        log.exception("sse_stream_failed", error=str(exc))
        yield _sse(ChatEvent("error", {"code": "internal_error", "message": str(exc)}))
        yield _sse(ChatEvent("done", {**_ABORTED, "error": f"{type(exc).__name__}: {exc}"}))


@router.post("/{agent_id}/chat", response_model=ChatResponse)
async def chat(agent_id: uuid.UUID, req: ChatRequest, user: CurrentUser):
    """问答。`stream=true`(默认)返回 SSE 流,`stream=false` 返回完整 JSON。"""
    if req.stream:
        return StreamingResponse(
            _sse_stream(agent_id=agent_id, req=req, user_id=user.id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                # 反代(nginx)默认会缓冲,不关掉就看不到"流"
                "X-Accel-Buffering": "no",
            },
        )
    result = await run_chat(
        agent_id=agent_id,
        question=req.question,
        conversation_id=req.conversation_id,
        user_id=user.id,
    )
    # ChatResult 是 slots dataclass(没有 __dict__),用 asdict 而不是 vars
    return ChatResponse(**asdict(result))
