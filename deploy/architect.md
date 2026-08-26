# deploy/architect.md

## 1. 形态与请求路径

```
浏览器 ──HTTPS──> Caddy :443 ──┬── /            → /srv/knowledge-agent/web(Vite 产物,SPA 兜底)
                  Basic Auth   └── /api /healthz /docs → 127.0.0.1:8000 uvicorn(systemd)
                                                          ├── agent_system  PG16+pgvector :5432(容器)
                                                          ├── demo_biz      MySQL 8.4 :3307(容器)
                                                          └── MinerU        :18001(容器)
```

公网只有 80/443 开着;后端绑 `127.0.0.1`,两个数据库和 MinerU 只在容器网络与本机。

## 2. 四个设计取舍(改之前先看这里)

**同源反代,不做跨域**。前端 `web/src/api/client.ts` 的 `API_BASE` 默认空串,一律相对路径。
于是线上与本地 Vite dev proxy 是同一种拓扑:没有 CORS、没有预检、SSE 不受跨域影响。
`release.sh` 仍会把仓库根 `.env` 的 `CORS_ORIGINS` 对齐站点地址,那是兜底,不是链路依赖。

**单 worker**。异步任务是进程内 `BackgroundTasks`(刻意不引 Celery/Redis,见 `CLAUDE.md`),
`app/main.py` 启动时还会给上一条命残留的 running 任务"收尸"。多 worker 会让派发与收尸失去单一归属,
所以单元里写死 `--workers 1`。

**访问控制在 Caddy,不在应用里**。系统 S0–S5 硬编码 `default_user`、无登录态,
公网暴露的风险(别人花你的 OpenAI key、删知识库)必须在应用之外挡掉。挡在反代层的好处是
应用代码零改动 —— 演示环境的约束不污染仓库。两档:
`deploy.env` 填了 `BASIC_AUTH_PASSWORD` 就拼进 `Caddyfile.auth.snippet`(全站密码门);
留空则只靠**主机名收窄** —— 站点块按主机名匹配,扫 IP 的请求匹配不到任何站点。强度取决于名字好不好猜:现在用的是可读名字 `company-knowledge-agent.<IP>.nip.io`,比随机 6 位弱一档,取舍写在 `documents/DEPLOY.md` §4。
后者是遮挡不是认证,代价与配套见 `documents/DEPLOY.md` §4。

**arm64**。`docker/mineru/Dockerfile` 是为 Apple Silicon 写的 arm64 CPU 镜像,
放 Graviton 是同一条已验证路径;换 x86 要重验那棵 4.9GB 依赖树。

## 2.5 谁在哪台机器上跑

| 脚本 | 跑在 | 读什么 | 写什么 |
| --- | --- | --- | --- |
| `aws_up.sh` | 本地 | `deploy.env` | AWS 资源 + `stack.env` |
| `remote_deploy.sh` | 本地(经 ssh 驱动服务器) | `deploy.env` + `stack.env` | 服务器上的代码、`.env`、`deploy/deploy.env` |
| `provision.sh` | 服务器 | — | 系统包 / swap |
| `release.sh` | 服务器 | 服务器上的 `deploy/deploy.env` | `/srv/knowledge-agent/web`、`/etc/systemd/system/`、`/etc/caddy/Caddyfile` |
| `aws_down.sh` | 本地 | `deploy.env` + `stack.env` | 拆掉 AWS 资源 |

**代码怎么上去**:`git archive HEAD` 打包(部署的是提交过的代码),`deploy/` 目录因为还没进 git
所以单独 tar over ssh 送(不用 `rsync -e`:仓库路径里有空格,拼 `-e` 字符串会被拆词)。
唯一的例外是 `bootstrap.sh` —— 用本地版覆盖 HEAD 版,因为装机路径上的修复必须立刻生效。

## 3. 模板渲染

两个 `.tmpl` 里的 `__占位符__` 由 `release.sh::render()` 做**字面替换**,用 python 而不是 sed ——
bcrypt hash 里有 `$` `.` `/` 这些元字符,字面替换省心。

占位符:`__SITE_ADDRESS__` `__API_PORT__` `__WEB_ROOT__`(固定 `/srv/knowledge-agent/web`)
`__REPO_ROOT__` `__RUN_USER__`,以及 `__AUTH_BLOCK__` —— 它的值是渲染好的
`Caddyfile.auth.snippet`(填了密码时)或空串(没填时)。

## 4. 我要改 X

| 我要改… | 去哪 |
| --- | --- |
| 站点地址 / 访问密码 | 本地 `deploy.env` → `./remote_deploy.sh code release` |
| 机型 / 磁盘 / 区域 / 起不起 MinerU | 本地 `deploy.env` 的 A 段 → `./aws_up.sh` |
| AWS 资源的创建或拆除逻辑 | `aws_up.sh` / `aws_down.sh`(资源都打 `Name=<STACK_NAME>` 标签,便于一把拆) |
| 代码怎么送上服务器 | `remote_deploy.sh::stage_code`(见 §2.5) |
| 反代的路径分流、超时、压缩、日志 | `Caddyfile.tmpl`(`@api` 匹配器那段) |
| 后端的启动参数(worker 数、端口、代理头) | `knowledge-agent-api.service.tmpl` |
| 装机要多装一个系统依赖 | `provision.sh`(同时想一想:该不该进 `bootstrap.sh`?应用级依赖归它) |
| 发布流程加一步(如新的 seed 命令) | `release.sh` 的对应小节 + `documents/DEPLOY.md` §4 |
| 发新版本时要先动库 | 已经有了:`stage_release()` 会先跑 `stage_migrate()`(`make migrate`),再 `release.sh` 重启后端 —— 顺序不能反 |
| AWS 侧操作、运维手册、成本与收尾 | `documents/DEPLOY.md` |

**边界**:应用级的依赖与初始化(容器、迁移、seed、环境变量)一律进 `bootstrap.sh`,
本目录只管"这台机器怎么变成一个对外可访问的站点"。两者不重叠。
