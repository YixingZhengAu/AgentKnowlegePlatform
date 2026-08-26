# CLAUDE.md

面试演示项目:企业知识 Agent 系统(Enterprise Knowledge Agent)(精准问答对 / 文档 RAG / 智能问数 + Agent 路由问答)。
需求见 `documents/PRD.md`,阶段计划见 `documents/S0-PLAN.md`、`documents/S1-PLAN.md`(S1 已完成)、`documents/S3-PLAN.md`(S3 已完成)、`documents/S2-PLAN.md`(S2 已完成),表结构唯一出处 `documents/DB-DESIGN.md`,前端风格唯一出处 `documents/UI-STYLE.md`,临时公网部署唯一出处 `documents/DEPLOY.md`,**开发某类 knowledge ingestion 前必读 `documents/DOMAIN-DEV-GUIDE.md`**(代码落点与并行开发纪律,防止冲突)。语言纪律见下节。

## 语言纪律:对外英文,对内中文

判断标准只有一条 —— **仓库外的人(GitHub 访客、面试官、平台用户)能看到的地方,一律英文**;只有团队内部读的开发资料才用中文。

**必须英文:**

- `README.md`(以及任何未来新增的 README、LICENSE、CONTRIBUTING 等仓库门面文件)
- **git commit message**(标题与正文全英文,常规 imperative 风格,如 `Add bootstrap.sh: one command to a runnable machine`);PR 标题与描述、issue、tag/release notes 同理
- 前端界面文案、Agent 问答交互、演示知识内容(QA 对 / 文档 / 业务数据)—— 平台面向澳洲用户,无 i18n,英文单语
- 面向用户的 API 报错文案、日志中会被外部看到的字符串

**保持中文:**

- `documents/` 下的设计文档(PRD、阶段计划、DB-DESIGN、UI-STYLE、DOMAIN-DEV-GUIDE)
- 各目录的 `claude.md` / `architect.md`,以及本文件
- 代码注释与 docstring

## 技术栈

- 后端:Python 3.13 + FastAPI + Pydantic + SQLAlchemy + Alembic
- 前端:React + TypeScript + Vite + Tailwind + shadcn/ui
- 数据库:PostgreSQL 16 + pgvector(docker-compose 镜像 `pgvector/pgvector:pg16`)
- LLM 与 Embedding:OpenAI(main=gpt-5 / light=gpt-5-mini / embedding=text-embedding-3-small, dim=1536)
- 异步任务:FastAPI BackgroundTasks(刻意不用 Celery/Redis)
- 编排:自研轻量编排,不引入 LangChain 等重框架(面试可解释性优先)

## 环境安装:根目录 `bootstrap.sh`

- 新机器接手项目:`./bootstrap.sh`(= `make bootstrap`)。幂等,细节 `./bootstrap.sh --help`
- **凡是新增了外部依赖或初始化步骤(新容器、新服务、新环境变量、新一次性命令),当场同步进 `bootstrap.sh`** —— 它是"从零到能跑"的唯一出处,不能靠口头交接

## Python 环境:统一用 uv

- 依赖管理只用 uv,**加任何包一律 `uv add <pkg>`**,禁止 pip install / 手改 pyproject 依赖段
- 运行:`uv run python -m ...`、`uv run uvicorn ...`
- 开发依赖:`uv add --dev <pkg>`

## 目录约定(monorepo)

- `server/` 后端(`app/{main,config,db,models,schemas,api,providers,core,services}`)
- `web/` 前端(`src/{api,components,layouts,pages,lib}` + `scripts/` 前端冒烟)
- `server/scripts/` 冒烟/工具脚本(在 server 下跑:`uv run python -m scripts.seed_minimal`)
- `docker/` 容器初始化脚本(Postgres init:建业务库与只读账号)
- `deploy/` 临时公网部署资产(EC2 装机 / 发布脚本 / Caddy + systemd 模板;步骤见 `documents/DEPLOY.md`)

## 代码索引机制:每个文件夹的 claude.md + architect.md

项目会变大,靠这两个文件做代码索引和定位:

- **每个代码文件夹下都要有 `claude.md` 和 `architect.md` 两个文件**,新建文件夹时同步创建
- `claude.md`:必须精干(每次都会被加载)。只放三样:该目录职责一句话、关键文件一行一个的索引、指向本目录 `architect.md`
- `architect.md`:被 claude.md 索引,放详细内容:内部结构、数据流、关键函数/类的位置,用于快速定位要改的代码在哪个文件哪一块
- 根目录:`CLAUDE.md` 就是根的 claude.md,配套的全局导航在根 `architect.md`(目录地图 + "我要改 X 去哪")
- 改代码前先看根 `architect.md` 定位到目录,再看该目录的这两个文件;找不到再全局搜索

## 文档同步纪律

- **每次改完代码,随手同步修改所有相关 md 中对应的部分**(本目录 claude.md / architect.md,以及 PRD、阶段计划里被影响的描述),保证文档与代码实时一一对应
- 每轮改动结束前自查一遍:这次改动有没有让任何 md 过时;有就当场改,不留到以后
- 新增/移动/删除文件、改 API、改表结构,属于必须同步文档的改动

## 关键约定

- 契约先行:后端改 API 后跑 `make types`(openapi.json → `web/src/api/types.gen.ts`),前端不许手写 API 类型
- 向量维度由配置 `EMBEDDING_DIM` 决定,不硬编码
- 密钥只放本地 `.env`(不入库);模板维护在 `.env.example`
- 用户系统:S0–S5 一律硬编码 `default_user`
- 开发顺序按 PRD §9 垂直切片,当前处于 S0
