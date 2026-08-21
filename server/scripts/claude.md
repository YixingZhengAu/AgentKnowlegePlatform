# server/scripts/

**职责**:CLI 脚本。六步法的第 ② 步(先在命令行把逻辑跑通,再接 HTTP)都写在这里。

| 文件 | 用途 |
| --- | --- |
| `seed_minimal.py` | 灌最小数据:default_user + 3 个空 KB + 默认 Agent + 绑定(幂等) |
| `dump_openapi.py` | 导出 openapi.json(`make types` 的第一步) |

详见 `architect.md`。
