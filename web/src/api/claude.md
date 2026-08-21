# web/src/api/

**职责**:与后端交互的全部代码。**API 类型只来自生成物,禁止手写**。

| 文件 | 说明 |
| --- | --- |
| `types.gen.ts` | `make types` 生成(openapi → TS),**不手改** |
| `schema.ts` | 生成类型的可读别名 + 三类知识的标签/识别色映射,页面只 import 这里 |
| `client.ts` | `apiFetch` / `apiPost` / `apiDelete` + `ApiError`:把后端错误体翻成异常 |
| `hooks.ts` | `useApi(path, {refetchInterval})`:GET 的 `{data,error,loading,reload}`,间隔可按数据算 |
| `sse.ts` | chat 流式接口的客户端(`streamChat` / `parseSseFrame`) |
| `useChat.ts` | 对话状态机:消息流、流式拼接、trace 累积、中断、开/切会话 |

详见 `architect.md`。
