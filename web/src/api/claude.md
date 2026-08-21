# web/src/api/

**职责**:与后端交互的全部代码。**API 类型只来自生成物,禁止手写**。

| 文件 | 说明 |
| --- | --- |
| `types.gen.ts` | `make types` 生成(openapi → TS),**不手改** |
| `schema.ts` | 生成类型的可读别名 + 三类知识的标签/识别色映射,页面只 import 这里 |
| `client.ts` | `apiFetch` + `ApiError`:把后端错误体 `{error:{code,message,detail}}` 翻成异常 |
| `hooks.ts` | `useApi(path)`:只读 GET 的 `{data, error, loading, reload}` |
| `sse.ts` | chat 流式接口的客户端(`streamChat` / `parseSseFrame`) |

详见 `architect.md`。
