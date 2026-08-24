# deploy/ · 临时公网部署资产

**职责**:一条命令把这套系统开到 AWS 上给面试官看 —— 开机器、装机、传代码、常驻、HTTPS、拆干净。定位是临时演示环境,不是生产。

| 文件 | 是什么 |
| --- | --- |
| `aws_up.sh` | **本地跑**。开机器:key pair / security group / EC2 实例 / Elastic IP,产出 `stack.env`。幂等 |
| `remote_deploy.sh` | **本地跑**。五阶段:`code`(git HEAD + deploy/ + .env)/ `provision` / `bootstrap` / `seed` / `release`,可单独重跑 |
| `aws_down.sh` | **本地跑**。演示结束拆干净:terminate 实例 + 释放 EIP + 删安全组与 key pair |
| `provision.sh` | 服务器上跑。装机:Docker + compose / Node 22 / uv / Caddy / 2G swap。幂等 |
| `release.sh` | 服务器上跑。发布:前端构建 → 静态产物落盘 → 渲染装 systemd 与 Caddy 配置 → 起服务 → 自检。幂等 |
| `Caddyfile.tmpl` | Caddy 站点模板:自动 HTTPS + 同源反代(静态 + `/api` 转 8000);站点块按主机名匹配 |
| `Caddyfile.auth.snippet` | 可选的全站密码门片段(`deploy.env` 填了密码才会被拼进去) |
| `knowledge-agent-api.service.tmpl` | 后端 systemd 单元模板(uvicorn 单 worker) |
| `deploy.env.example` | 配置模板;`deploy.env` / `stack.env` / `known_hosts` 都不入库 |

**完整步骤、运维手册、"不设密码门靠什么挡人"在 `documents/DEPLOY.md`**;设计取舍见本目录 `architect.md`。
