# web/src/domains/text2sql/

**职责**:智能问数(text2sql)域前端 —— 本域 ingestion 流程的一切代码都落在这里。

| 文件 | 说明 |
| --- | --- |
| `module.ts` | 域描述符(路由 `/ingest/text2sql`、识别色紫、暂无渲染器) |
| `IngestPage.tsx` | 空白壳页,真实流程待需求确认后重写 |

详见 `architect.md`;跨域约定见 `../claude.md`。
