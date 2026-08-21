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

## 注意

**init 脚本只在数据卷首次创建时执行**。改了它必须 `make db-reset`(`docker compose down -v`)才生效。
