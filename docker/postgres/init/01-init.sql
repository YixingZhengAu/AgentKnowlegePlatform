-- Postgres 初始化脚本(仅在数据卷首次创建时执行)
-- 目标:
--   1. 系统库 agent_system 装 vector / pgcrypto 扩展
--   2. 建演示业务库 clenergy_biz(U6:同实例、单独 database)
--   3. 建只读账号 biz_reader,智能问数(S3)用它连业务库

-- ===== 系统库(POSTGRES_DB=agent_system,当前连接就是它)=====
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ===== 只读账号 =====
CREATE ROLE biz_reader LOGIN PASSWORD 'biz_reader';

-- ===== 演示业务库 =====
CREATE DATABASE clenergy_biz OWNER postgres;

\connect clenergy_biz

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- biz_reader 只给读:能连、能看 schema、能 SELECT 现有和未来的表
GRANT CONNECT ON DATABASE clenergy_biz TO biz_reader;
GRANT USAGE ON SCHEMA public TO biz_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO biz_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO biz_reader;
-- 显式收回建表权限(PG15 起 public schema 默认已无 CREATE,这里再兜一层)
REVOKE CREATE ON SCHEMA public FROM biz_reader;
REVOKE ALL ON DATABASE clenergy_biz FROM PUBLIC;
GRANT CONNECT ON DATABASE clenergy_biz TO biz_reader;

-- biz_reader 不允许连系统库
\connect agent_system
REVOKE ALL ON DATABASE agent_system FROM PUBLIC;
