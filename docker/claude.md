# docker/

**职责**:本地依赖服务的容器化配置(Postgres + 演示业务 MySQL + MinerU 三个服务)。

| 路径 | 说明 |
| --- | --- |
| `postgres/init/01-init.sql` | 数据卷首次创建时执行:给系统库装 vector / pgcrypto 扩展 |
| `mysql/init/01-users.sql` | 演示业务库的只读账号 `biz_reader`(问数运行时唯一允许的账号) |
| `mysql/init/02-schema.sql` | `clenergy_biz` 七表 DDL(注释故意只覆盖一部分 —— 治理要有活干) |
| `mysql/init/03-seed.sql` | 灌数(24 个月、1289 单;**生成物**,别手改) |
| `mysql/gen_seed.py` | 03-seed.sql 的生成器,纯 stdlib、`seed=42`,重跑逐字节一致 |
| `mineru/Dockerfile` | MinerU 3.4.5(pipeline 后端,CPU/arm64)自建镜像;`make mineru` 起常驻服务 |

对应 `docker-compose.yml`(仓库根)。业务库自检:`make bizdb-verify`。详见 `architect.md`。
