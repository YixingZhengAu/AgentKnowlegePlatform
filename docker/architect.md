# docker/architect.md

## 两个数据库,两台实例

| 库 | 实例 | 用途 | 账号 |
| --- | --- | --- | --- |
| `agent_system` | `agent_system_pg`(PG 16 + pgvector,5432) | 本系统全部业务表 | `postgres` |
| `clenergy_biz` | `agent_system_bizdb`(MySQL 8.4,**3307**) | 演示业务库,智能问数的查询目标 | `biz_reader`(只读) |

**U6 决策在 S3 开工时被修正**:原本是"一个 PG 实例两个 database",现在业务库独立成 MySQL 容器。
三个理由,按重要性排:

1. 演示的主张是"接入客户已有的库",而客户库以 MySQL 为多。同构复用自家 PG 会把最值得展示的
   那部分(方言差异、`information_schema` introspection)藏起来。
2. MySQL 逼着 introspection 走 `information_schema` + `SELECT DISTINCT` 采样这条真实路径,
   而不是 PG 的便捷目录视图 —— 枚举识别、列注释缺失、无外键的逻辑关联都在这条路上暴露出来。
3. **隔离从 GRANT 变成物理隔离**:问数用的账号根本连不到系统库,不靠权限拧对。

## biz_reader 的权限边界

`mysql/init/01-users.sql` 只做一件事:`GRANT SELECT ON clenergy_biz.*`。没有 INSERT/UPDATE/
DELETE/CREATE,也没有别的库的任何权限。运行时还有第二道闸(单条 SELECT、表列白名单、
强制 LIMIT、读超时),在 `server/app/services/text2sql/executor.py`;
数据库权限是最后一道,不是唯一一道。

自检(`make bizdb-verify` 里的最后一项就是它):
```bash
docker exec agent_system_bizdb mysql -ubiz_reader -pbiz_reader clenergy_biz \
  -e "INSERT INTO products (sku,name,series,category,unit_price,launch_date) VALUES ('x','x','x','x',1,'2024-01-01');"
# 应报 ERROR 1142 (INSERT command denied)
```

## 演示数据是生成的,不是手写的

`mysql/gen_seed.py` → `mysql/init/03-seed.sql`(纯 stdlib、`seed=42`、锚点日期写死
`2026-08-23`,任何机器重跑产出逐字节一致)。数据刻意有形状:24 个月每月有单、澳洲光伏旺季
加权、州分布 NSW>VIC>QLD>SA>WA、约 6.4% cancelled、`orders.total_amount` 严格等于订单行聚合、
`inventory.on_hand_qty` 严格等于流水净额且滚动余额任意时点不为负。
**改了生成器要重跑它,再 `make bizdb-reset`** —— init 脚本只在数据卷首次创建时执行。

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
