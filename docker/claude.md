# docker/

**职责**:本地依赖服务的容器化配置(仅 Postgres 一个服务)。

| 路径 | 说明 |
| --- | --- |
| `postgres/init/01-init.sql` | 数据卷首次创建时执行:装扩展、建 `clenergy_biz`、建只读账号 `biz_reader` |

对应 `docker-compose.yml`(仓库根)。详见 `architect.md`。
