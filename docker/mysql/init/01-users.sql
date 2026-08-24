-- 只读账号:问数运行时唯一允许使用的账号(与系统 PG 侧 biz_reader 命名对齐)
CREATE USER 'biz_reader'@'%' IDENTIFIED BY 'biz_reader';
GRANT SELECT ON demo_biz.* TO 'biz_reader'@'%';
FLUSH PRIVILEGES;
