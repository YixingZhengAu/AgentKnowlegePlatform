# DEPLOY.md —— 临时公网部署(AWS EC2 单机,脚本化)

**目的**:让面试官在这段时间里能用浏览器打开这套系统。定位是**临时演示环境**,不是生产:
单机、单进程、无高可用、无备份、结束即销毁。所有部署资产在 `deploy/`。

**全流程四条命令**(在本机跑,不用手动进 AWS 控制台,也不用手动 ssh):

```bash
cd deploy
cp deploy.env.example deploy.env && vi deploy.env   # 只有四项要填,见 §1
./aws_up.sh                                        # 开机器:key pair / 安全组 / 实例 / Elastic IP
./remote_deploy.sh all                             # 传代码 → 装机 → bootstrap → seed → 发布
./aws_down.sh                                      # 演示结束,全部拆掉
```

**形态**:一台 EC2 跑全部东西 —— Caddy(HTTPS + 可选密码门 + 同源反代)在最前面,
后面是 systemd 常驻的 uvicorn,再后面是 compose 起的三个容器(系统库 PG / 演示业务库 MySQL / MinerU)。

```
浏览器 ──HTTPS──> Caddy :443 ──┬── /            → /srv/knowledge-agent/web(Vite 构建产物,SPA 兜底)
                               └── /api /healthz → 127.0.0.1:8000  uvicorn(systemd)
                                                     ├── agent_system   PG16+pgvector :5432(容器)
                                                     ├── demo_biz       MySQL 8.4 :3307(容器,只读账号)
                                                     └── MinerU         :18001(容器,解析 PDF 时才用)
```

**为什么是同源反代**:前端一律用相对路径(`web/src/api/client.ts` 的 `API_BASE` 默认空串),
所以线上没有 CORS、没有预检、SSE 不受跨域影响 —— 与本地 Vite dev proxy 的行为一致。

---

## 1. `deploy/deploy.env` 要填什么

| 项 | 说明 |
| --- | --- |
| `AWS_PROFILE` | 用 `~/.aws` 里哪个 profile(脚本只用它读 EC2,不需要新建 IAM) |
| `AWS_REGION` | `ap-southeast-2`(悉尼;面试官在澳洲) |
| `SITE_DOMAIN` | **可留空**。留空 = `demo-<随机6位>.<公网IP>.nip.io`;填了域名的话 A 记录要你自己去 DNS 服务商加 |
| `BASIC_AUTH_PASSWORD` | **可留空**。填了 = 全站密码门;留空 = 不装门,见 §4 |
| `OPENAI_API_KEY` | **可留空** = 复用本机 `.env` 里那把 |
| `INSTANCE_TYPE` / `WITH_MINERU` | 默认 `t4g.large` + 起 MinerU;不需要线上解析新 PDF 就改 `t4g.medium` + `false` |

机型为什么是 **arm64**:`docker/mineru/Dockerfile` 本来就是为 Apple Silicon 写的 arm64 CPU 镜像,
放 Graviton 是同一条已验证路径;换 x86 得重新验那棵 4.9GB 依赖树。

## 2. `aws_up.sh` 做了什么(幂等,重复跑安全)

只碰四种资源,全部打 `Name=<STACK_NAME>` 标签,方便一把拆干净:

1. **key pair** —— 私钥落 `~/.ssh/<STACK_NAME>.pem`(chmod 400)。
2. **security group** —— 入站只三条:22 只放**你当前的公网 IP**、80/443 对全网。
   数据库(5432/3307)和后端(8000)一律不开,它们只绑 `127.0.0.1`。
   *你换网络后 ssh 会不通 —— 重跑 `aws_up.sh` 会补一条新的 22 规则。*
3. **实例** —— Ubuntu 24.04 arm64(AMI 走 SSM 公共参数,不写死 `ami-xxx`)、gp3 30GiB、IMDSv2 强制。
4. **Elastic IP** —— 必须有:stop/start 之后公网 IP 会变,发给面试官的链接就废了。

产出 `deploy/stack.env`(实例 id / EIP / 公网 IP / 站点地址 / 私钥路径),后面两个脚本读它。

## 3. `remote_deploy.sh` 的五个阶段(可单独重跑)

| 阶段 | 干什么 |
| --- | --- |
| `code` | `git archive HEAD` 打包上传(**部署的是提交过的代码**)+ `deploy/` 目录单独同步 + 生成服务器的 `.env`(`APP_ENV=prod`,`SECRET_KEY` 服务器独立生成)+ 生成服务器的 `deploy.env` |
| `provision` | `provision.sh`:Docker + compose、Node 22、uv、Caddy、2G swap |
| `bootstrap` | `./bootstrap.sh -y --with-mineru`:依赖、两个库、迁移、seed、真调 LLM 的冒烟。**最慢的一步**(MinerU 要 build 镜像 + 下 1GB 权重) |
| `seed` | `make seed-s3`:问数的演示知识与向量(索引面 75 条) |
| `release` | `release.sh`:前端生产构建 → `/srv/knowledge-agent/web` → 渲染装 systemd 单元与 Caddyfile → 起服务 → 自检 |

`code` 阶段有一个例外:`bootstrap.sh` 用**本地版**覆盖 HEAD 版。装机路径上的修复必须立刻生效,
不能等提交(实测踩过:`mktemp -t bootstrap-warn` 是 BSD 语法,GNU mktemp 要模板带 `XXXXXX`,
于是这个"从零到能跑"的脚本在 Linux 上第一步就挂 —— 已修)。其余文件一律以 HEAD 为准。

改完代码要重发:`./remote_deploy.sh code && ./remote_deploy.sh release`。

## 4. 没有密码门时,靠什么挡陌生人

系统 S0–S5 硬编码 `default_user`,**没有登录态、没有权限**(见 `CLAUDE.md` 关键约定)。
公网裸奔意味着任何人都能用你的 OpenAI key 提问、删知识库、删已发布的问答。

`BASIC_AUTH_PASSWORD` 留空(为了让面试官零摩擦点进来)时,挡在前面的是**主机名收窄**:
Caddyfile 的站点块按主机名匹配,`SITE_ADDRESS` 是 `demo-<随机6位>.<IP>.nip.io`,
于是**直接扫公网 IP 的请求匹配不到任何站点**,既拿不到页面也拿不到证书。
链接只在你和面试官手里,不可枚举。

这不是认证,是遮挡。配套必须做的两条:

- OpenAI 后台给这把 key 设 **usage limit**(月度硬上限),演示结束 rotate 掉。
- 链接别贴进简历、GitHub、公开页面 —— 一旦被索引,遮挡就没了。

要密码门就在 `deploy.env` 填 `BASIC_AUTH_PASSWORD` 再跑一次 `./remote_deploy.sh code release`;
`release.sh` 会自己 `caddy hash-password`,明文不落任何提交。

## 5. 运维手册(就这几条)

本地(在 `deploy/` 下,`stack.env` 提供 IP 与私钥):

| 要干什么 | 命令 |
| --- | --- |
| ssh 进去 | `ssh -i ~/.ssh/knowledge-agent-demo.pem ubuntu@$(grep PUBLIC_IP stack.env \| cut -d= -f2)` |
| 发新版本 | `./remote_deploy.sh code && ./remote_deploy.sh release` |
| 换网络后 ssh 不通 | 重跑 `./aws_up.sh`(补一条你新 IP 的 22 规则) |
| 加/去掉密码门 | 改 `deploy.env` 的 `BASIC_AUTH_PASSWORD` → `./remote_deploy.sh code release` |
| **结束演示** | `./aws_down.sh`(terminate 实例 + 释放 EIP + 删安全组与 key pair)+ **rotate OpenAI key** |

服务器上:

| 要干什么 | 命令 |
| --- | --- |
| 看后端日志 | `journalctl -u knowledge-agent-api -f` |
| 重启后端 | `sudo systemctl restart knowledge-agent-api` |
| 看 Caddy 日志(含访问日志) | `journalctl -u caddy -f` |
| 容器状态 | `docker ps` / `make db` / `make mineru` |

容器都带 `restart: unless-stopped`,后端是 `Restart=always` 的 systemd 单元,Caddy 是 enable 的,
所以实例重启后整套会自己回来 —— 不需要手动拉起任何东西。

**省钱**:晚上不用可以在控制台 Stop 实例(EBS 仍计费,30GiB 约 USD 2.4/月;Elastic IP 保住不变的 IP,
但未关联到运行实例时按小时计费)。t4g.large 按需约 USD 0.0672/hr ≈ 1.6/天。

## 6. 想更省:不在线上跑 MinerU

MinerU 只在"上传新 PDF 走 S1 解析"时用得到。`WITH_MINERU=false` + `INSTANCE_TYPE=t4g.medium` 即可。
已有的演示文档与已发布问答可以从本地搬:

```bash
docker exec agent_system_pg pg_dump -U postgres -Fc agent_system > /tmp/agent_system.dump
scp -i ~/.ssh/knowledge-agent-demo.pem /tmp/agent_system.dump ubuntu@<IP>:/tmp/
rsync -av -e "ssh -i ~/.ssh/knowledge-agent-demo.pem" ./storage/ ubuntu@<IP>:~/agent-system/storage/
# 服务器上:注意 dsn_enc 是用本地 SECRET_KEY 加密的,搬库就得连 SECRET_KEY 一起搬
docker cp /tmp/agent_system.dump agent_system_pg:/tmp/
docker exec agent_system_pg pg_restore -U postgres -d agent_system --clean --if-exists /tmp/agent_system.dump
```

代价是线上"上传 PDF"这条路会失败(解析 job 连不上 MinerU)。

## 6.5 这台机器上现在有什么演示数据(2026-08-24 部署实测)

- **智能问数(S3)**:`make seed-s3` 灌的 7 条已发布意图 / 75 条索引面。服务器上跑
  `uv run python -m scripts.smoke_s3_e2e --check` = **20/20**,越界拒答硬闸门 7/7。
- **精准问答(S1)**:`data/company-travel-policy.pdf` 走完整条真流水线
  (上传 → MinerU 解析 5 页 40 块 → 确认 → LLM 抽出 25 条候选 → 采纳 10 条),
  采纳即发布,对话里立刻命中并标 Verified。**seed 不含这些** —— 新开的机器要自己走一遍,
  否则 `/ingest/exact-qa` 是空页面、对话也命中不了精准问答。
- **文档 RAG(S2)**:该域还没开发,`/ingest/document` 是空白壳。面试时说明是阶段计划里的下一片。

线上实测过的三条链路(都经公网地址):精准问答命中(`verified=true`,trace 只有
`retrieve_exact_qa`、无生成阶段)、问数执行(`rewrite_sql` + `execute_sql`,返回真实数字与最终 SQL)、
问数的模板外拒答(不落生成模型)。

## 6.6 部署时踩到的四个坑(已修在仓库里,别再踩)

| 坑 | 现象 | 修在哪 |
| --- | --- | --- |
| `mktemp -t bootstrap-warn` | GNU mktemp 要模板带 `XXXXXX`,`bootstrap.sh` 在 Linux 上第一步就挂 | `bootstrap.sh` |
| arm64 torch 带 CUDA | PyPI 的 linux-aarch64 torch wheel 会拖进一套 nvidia cu13 库,MinerU 镜像撑爆 30GiB 磁盘 | `docker/mineru/Dockerfile`(先从 `download.pytorch.org/whl/cpu` 钉住 torch/torchvision 再装 mineru;torch 从数 GB 降到 147MB,build 从 138s 降到 17s) |
| Caddy 写不了 `/var/log/caddy` | 官方 `caddy.service` 有文件系统沙箱,启动直接 permission denied | `deploy/Caddyfile.tmpl`(访问日志改走 journal) |
| `SECRET_KEY` 每次重发都换 | `datasources.dsn_enc` 用它加密,换 key 后问数报 `datasource_dsn_undecryptable` | `deploy/remote_deploy.sh`(服务器上已有的 key 沿用,只有首次生成) |

另两处环境差异,脚本里已处理:非交互 ssh 不读 `~/.bashrc`,所以 `rsh()` 显式补
`PATH=$HOME/.local/bin`(否则 `make` 报 `uv: command not found`);EC2 实例访问自己的
Elastic IP 不回环,所以 `release.sh` 自检里"首页返回 000"是假警报,要从本地验。

## 7. 已知的"这是演示环境"

诚实列一下,面试时被问到不用回避:

- 单 worker uvicorn。异步任务用的是进程内 `BackgroundTasks`(刻意不引 Celery/Redis,见 `CLAUDE.md`),
  多 worker 会让任务派发与启动时的"僵尸任务收尸"失去单一归属,所以固定 1 个。并发演示够用。
- 无备份、无监控告警。数据在实例的 EBS 上,`aws_down.sh` 一跑即没。演示数据可由 seed 重建。
- 2 vCPU 上 MinerU 解析一份 4 页 PDF 是分钟级(本机是同一路径,只是核多)。
- 没有登录与多租户;不设密码门时靠主机名收窄遮挡(§4)。
- 只有一台机器,没有 CDN;前端是静态产物,Caddy 已开 zstd/gzip 压缩。
