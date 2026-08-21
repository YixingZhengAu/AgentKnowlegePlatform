# server/migrations/

**职责**:Alembic 迁移。表结构的唯一文档出处是 `documents/DB-DESIGN.md`,migration 照它写。

| 路径 | 说明 |
| --- | --- |
| `env.py` | 连接串与 target_metadata 都来自 `app.config` / `app.models`,ini 里不写密钥 |
| `versions/` | 迁移脚本(文件名带时间戳) |
| `script.py.mako` | 生成模板 |

详见 `architect.md`。
