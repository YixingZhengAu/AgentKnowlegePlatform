-- Postgres 初始化脚本(仅在数据卷首次创建时执行)
-- 目标:系统库 agent_system 装 vector / pgcrypto 扩展。
--
-- 这里**不再建演示业务库**:S3 开工时把 clenergy_biz 换成了独立的 MySQL 8.4 容器
-- (docker/mysql/,端口 3307)。理由见 docker/architect.md「两个数据库」一节 ——
-- 演示的主张是"接入客户已有的库",而客户库以 MySQL 为多;同时物理隔离比 GRANT 更硬:
-- 问数用的账号根本连不到这台 PG。

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 系统库不对 PUBLIC 开放
REVOKE ALL ON DATABASE agent_system FROM PUBLIC;
