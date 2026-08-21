# web/src/domains/exact-qa/

**职责**:精准 QA(exact_qa)域前端 —— 本域 ingestion 流程的一切代码都落在这里。

| 文件 | 说明 |
| --- | --- |
| `module.ts` | 域描述符(路由 `/ingest/exact-qa`、识别色黄、qa_pair 渲染器注册) |
| `IngestPage.tsx` | 空白壳页,真实流程待需求确认后重写 |

详见 `architect.md`;跨域约定见 `../claude.md`。
