# server/app/services/document/

**职责**:文档 RAG(Document RAG) 知识域的全部后端逻辑(S2 填充,当前为空壳)。

| 文件 | 说明 |
| --- | --- |
| `__init__.py` | 空(域内模块就绪后由 `services/__init__.py` 统一注册) |

**纪律**:不 import 兄弟域;只向上依赖 `app/core` / `app/models` / `app/schemas`。

详见 `architect.md`。
