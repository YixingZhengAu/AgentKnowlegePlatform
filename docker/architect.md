# docker/architect.md

## 一个实例两个库(U6 决策)

| 库 | 用途 | 账号 |
| --- | --- | --- |
| `agent_system` | 本系统全部业务表 | `postgres` |
| `clenergy_biz` | 演示业务库,智能问数的查询目标 | `biz_reader`(只读) |

## biz_reader 的权限边界

init 脚本里做了三件事,S3 问数的"安全可控"就靠它:

1. `GRANT SELECT ON ALL TABLES` + `ALTER DEFAULT PRIVILEGES ... GRANT SELECT`(未来建的表也只读)
2. `REVOKE CREATE ON SCHEMA public`(不能建表)
3. `REVOKE ALL ON DATABASE agent_system FROM PUBLIC`(**连不上系统库**)

自检:
```bash
docker exec -e PGPASSWORD=biz_reader agent_system_pg psql -U biz_reader -d clenergy_biz -c "create table t(id int);"   # 应报权限不足
docker exec -e PGPASSWORD=biz_reader agent_system_pg psql -U biz_reader -d agent_system -c "select 1;"                  # 应报 CONNECT 权限不足
```

## MinerU 解析容器(S1)

官方镜像基于 CUDA + sglang(amd64),Apple Silicon 上跑不起来,所以自建一个只装 pipeline 后端的最小镜像:

- `mineru/Dockerfile`:`uv pip install "mineru[pipeline]==3.4.5" six`
  （**`six` 必须手动补**:3.4.5 的 pipeline OCR 代码 import 了它但没写进依赖,实测踩坑）
- 形态是**常驻 HTTP 服务**(`mineru-api`,容器 `agent_system_mineru`,宿主 18001 → 容器 8001):
  模型加载一次约 13s,一次性 CLI 每次都要重加载,所以常驻。
- 模型权重 1.0GB 落 named volume `mineru_models`（compose 里写死卷名,换项目名也不丢权重）。
- 后端按 `.env` 的 `MINERU_API_URL` 调它;那 4.9GB 依赖树**永不进 server 镜像**。
- 起停:`make mineru`(或装机时 `./bootstrap.sh --with-mineru`) / `make mineru-stop`。健康检查打容器内 `/health`。

## 注意

**init 脚本只在数据卷首次创建时执行**。改了它必须 `make db-reset`(`docker compose down -v`)才生效。
