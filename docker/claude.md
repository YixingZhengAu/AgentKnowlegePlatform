# docker/

**职责**:本地依赖服务的容器化配置(Postgres + MinerU 两个服务)。

| 路径 | 说明 |
| --- | --- |
| `postgres/init/01-init.sql` | 数据卷首次创建时执行:装扩展、建 `clenergy_biz`、建只读账号 `biz_reader` |
| `mineru/Dockerfile` | MinerU 3.4.5(pipeline 后端,CPU/arm64)自建镜像;`make mineru` 起常驻服务 |

对应 `docker-compose.yml`(仓库根)。详见 `architect.md`。
