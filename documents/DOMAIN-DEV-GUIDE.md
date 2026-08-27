# 知识域开发指引(DOMAIN-DEV-GUIDE)

**读者**:负责开发某一类 knowledge ingestion(精准 QA / 文档 RAG / 智能问数)的开发者。
**目的**:三个域由不同人**并行开发**,这份文档告诉你代码该写在哪、哪些地方不能碰,
保证三个人同时开发、合并时不打架。

**开工前置**:你负责的域的真实 ingestion 流程必须**先写进 `PRD.md` 对应小节**
(§3.2–§3.4 目前标记"待需求方确认后重写"),流程没进 PRD 之前不写页面、不加接口。

---

## 1. 一张表:你的域对应哪里

| 域 | 前端文件夹 | 后端包 | 路由 | 识别色 token | staging item_type |
| --- | --- | --- | --- | --- | --- |
| 精准 QA(S1) | `web/src/domains/exact-qa/` | `server/app/services/exact_qa/` | `/ingest/exact-qa` | `bg-kb-exact-qa`(黄) | `qa_pair` |
| 文档 RAG(S2) | `web/src/domains/document/` | `server/app/services/document/` | `/ingest/document` | `bg-kb-document`(蓝) | `chunk` |
| 智能问数(S3) | `web/src/domains/text2sql/` | `server/app/services/text2sql/` | `/ingest/text2sql` | `bg-kb-text2sql`(紫) | `sql_intent` |
| 编排(未排期) | `web/src/domains/workflow/` | —(没有后端) | `/ingest/workflow` | `bg-kb-workflow`(navy) | —(没有候选) |

**第四行是占位**:编排(第四种知识,2026-08-27 加)现在只有一页静态画布预览,
**没有后端、没有表、没有 Job、没有审核台**,`knowledge_bases.type` 里也还没有这个取值。
它的设计说明在说明页 `/how-it-works/workflow` 与 `PRD.md §3.6`;真开发的落点见
`web/src/domains/workflow/architect.md` 末节。别把它当成一个在开发中的域。

**核心规则一句话**:你的所有代码只落在上面两个属于你的文件夹里;
需要在共享文件落笔的地方全部收敛成"加一行",见 §4 冲突地图。

## 2. 前端:写在 `web/src/domains/<你的域>/`

你的域文件夹里现在有一个空白壳 `IngestPage.tsx` 和一个描述符 `module.ts`,开发就是充实它们
(**已经做完的 `domains/exact-qa/` 就是一份可抄的样板**:域内路由壳 + 三个页面 + 渲染器 + 动作层):

1. **摄取页面**:替换 `IngestPage.tsx` 的空状态,上传/表单/进度条(`<JobProgress jobId>` 现成)
   都写在你的文件夹里。页面多了就拆子组件,仍然全部放在域文件夹内。
   **域内二级页**(比如 S1 的校对页)自己在 `IngestPage.tsx` 里摆一层 `<Routes>` ——
   共享路由表给了每个域一个 `/ingest/<域>/*` 空间,加页面不用碰 `App.tsx`。
2. **审核渲染器**:写 `ItemCard`(列表项怎么画)+ `ItemEditor`(右侧编辑表单),
   在你的 `module.ts` 的 `renderers` 字段登记(key = 你的 item_type)。
   登记前审核台走 JSON 兜底渲染 —— 所以后端先行完全可行,不必等前端。
3. **审核动作层(可选)**:如果你的域"通过"不是 S0 的默认语义(标 approved、最后批量发布),
   在域内写一个 `ReviewActions` 并登记进 `renderers.<item_type>.actions`。
   S1 就是这么把"采纳即发布 + 驳回必须填理由"接上去的,审核台本体一行没改。
   批量也在这一层:给 `bulkApprove(items)` 就用你的实现(S1 的采纳要建向量,只能逐条打接口),
   `bulkReject: false` 可以只关掉批量驳回而保留批量勾选。
4. **路由 / 侧栏导航 / 顶栏标题**:不用写。它们由 `domains/index.ts` 的 `DOMAINS`
   数组自动生成,你的 `module.ts` 改了 label/icon 会自动生效。

⚠ **一个真踩过的坑**:域页面要用右侧面板就 import `@/layouts/rightPanel`,
**不要 import `AppLayout`** —— AppLayout 要遍历 DOMAINS,反向 import 会成 ESM 环,
运行时炸 `Cannot access 'DOMAINS' before initialization`(S1 Step 7b 抓到过)。

**不能碰的(shared 层,只读)**:`src/{api,components,layouts,lib}`、`App.tsx`、
`AppLayout.tsx`、`components/staging/registry.ts`。要改公共契约(比如审核台组件加能力、
SSE 协议加事件),**单独提出来与集成者讨论**,不要顺手改。

**两条硬纪律**:

- 界面文案一律**英文**(面向澳洲用户,无 i18n;对外可见内容与 commit message 同样英文,见根 `CLAUDE.md` §语言纪律);hex 色值只允许出现在
  `src/index.css`(你的域识别色 token 已存在,直接用 `bg-kb-*` 工具类)
- `src/api/types.gen.ts` 是 `make types` 的生成物:**禁止手改,合并冲突永远重跑
  `make types` 解决,禁止手工合并**

## 3. 后端:写在 `server/app/services/<你的域>/`

约定的文件形态(三域对称,详见你的域文件夹里的 `architect.md`):

```
<你的域>/
  ingest.py     Job 子类:steps 声明 + 每步实现(产出 staging_items)
  publisher.py  审核通过后写正式表 + 建索引(@register_publisher("<item_type>"))
  retrieve.py   问答链路里的检索 stage
```

1. **Job 子类**:继承 `core/jobs.py` 的 `JobRunner`,加 `@register_job`;
   进度条、分步日志、失败重跑、僵尸回收框架全包,参照 `core/jobs_demo.py` 的 `DemoSleepJob`。
   **注册行加在 `app/services/__init__.py`**(全局唯一注册点,一行),别处不 import。
2. **publisher**:`@register_publisher("<item_type>")`,发布骨架(`core/staging.py`)会调它。
3. **接口**:你的域需要新 API 时,在 `app/api/` 建自己的文件,在 `api/__init__.py`
   include 一行;改完跑 `make types` 让前端类型同步。
4. **检索 stage 接入 `core/chat.py`**:chat 编排是共享文件,插 stage 属于公共契约变更,
   **与集成者协调后再动**,不要自行修改。

**硬纪律**:不 import 兄弟域;只向上依赖 `app/core` / `app/models` / `app/schemas`;
加依赖包一律 `uv add <pkg>`,禁止 pip / 手改 pyproject。

## 4. 数据库:只动自己的,migration 不自己生成

- 你只改两处:`app/models/` 里**自己域的文件** + `documents/DB-DESIGN.md` **自己域的节**
  (文档先于代码,两者不一致以文档为准)
- **不自己跑 `alembic revision`** —— 合并时由集成者统一生成,避免 multiple heads
- **共享表红线**:`ingest_jobs` / `staging_items` / `publish_records` / `knowledge_bases`
  四张表的 DDL 任何域不得动、不得加"只有自己需要"的列;
  域差异进 `staging_items.payload`(jsonb)或你自己域的表

## 5. 冲突地图:所有会碰到共享文件的落笔点

并行开发唯一可能冲突的地方就是下面几行 —— 都设计成"相邻一行",git 能自动合并:

| 共享文件 | 你要做的 | 大小 |
| --- | --- | --- |
| `web/src/domains/index.ts` | 域已在 `DOMAINS` 数组里,通常不用动 | 0–1 行 |
| `server/app/services/__init__.py` | 你的 Job 子类就绪后,取消对应注释加 import | 1 行 |
| `server/app/api/__init__.py` | 你的域有新 router 时 include | 1 行 |
| `server/app/core/chat.py` | 插检索 stage —— **与集成者协调,不自行改** | — |

除此之外还要在任何共享文件落笔的,先停下来:大概率是设计走偏了,或者属于公共契约变更。

## 6. 联调工具(S0 已交付,直接用)

- `make dev` 前后端一起起;`make smoke` / `make smoke-sse` 冒烟;`make types` 契约同步
- 域冒烟的参照实现:`make smoke-s1`(精准 QA 的四个脚本 —— LLM 调用点 / 存储与 pgvector
  对数 / HTTP 全链路 / chat 三问)。**自己的域照这个套路各写一份**,回归时零成本重跑
- Job 框架联调:`demo_sleep` 假任务可调慢、可注入失败、可产出待审条目 ——
  `curl -X POST localhost:8000/api/jobs -H 'Content-Type: application/json' \
  -d '{"job_type":"demo_sleep","kb_id":"<kb_id>","params":{"step_seconds":0}}'`
- 审核台直链:`http://localhost:5173/jobs/{job_id}/review`(筛选/编辑/批量/键盘流/发布全流程可用)
- 全链路参照:提交 → 轮询 `GET /api/jobs/{id}` 到 `review` → 审核台 → `POST /api/jobs/{id}/publish`

## 7. 提交前自查清单

- [ ] 我的改动是否只落在自己的两个域文件夹 + §5 冲突地图允许的那几行?
- [ ] 后端改了 API 的话,跑过 `make types`?前端没有手写 API 类型?
- [ ] `cd server && uv run pytest` 与 `cd web && npx tsc -b && npm run lint` 全绿?
- [ ] 界面文案全英文?组件里没有裸 hex 色值?
- [ ] 动过表结构的话:改的是自己域的 model 文件 + DB-DESIGN 自己的节,**没有**自己生成 migration?
- [ ] 本目录的 `claude.md` / `architect.md` 已随手同步(新增文件要进索引)?

---

背景与决策记录见 `S0-PLAN.md` §5(S0 后的结构调整);全局导航见根 `architect.md`。
