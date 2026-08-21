# 结构调整计划(RESTRUCTURE-PLAN)

**背景**:三类知识(精准 QA / 文档 RAG / 智能问数)的 ingestion 流程将由不同开发者并行开发,
且真实流程与 S0 演示假设完全不同。本次调整只做**结构**:把并行开发的隔离边界立起来、
把会误导人的演示页面删掉,不预设任何一类的具体流程。

**四条决策(已与需求方确认)**:

1. Knowledge Bases 页删除(接口与表保留,它是归属根)
2. 侧栏改为 "Knowledge Ingestion" 二级导航,三个知识域各一个子项、各一条路由
3. 三个域页面是**空白壳**:只有域识别色 + 空状态一句话,不放任何表单按钮,留给各域开发者自行发挥
4. **具体页面代码删除,框架保留**:旧 JobsPage(demo 表单)、KbListPage、QA 渲染器一并删;
   泛型审核台、Job 框架、进度条组件、注册表接缝全部保留 —— 以后加代码有明确的落点文件夹,互不打架

**删/留清单(逐文件,避免歧义)**:

| 处置 | 东西 | 理由 |
| --- | --- | --- |
| 删 | `web/src/pages/KbListPage.tsx` + 路由/导航/标题 | 决策 1 |
| 删 | `web/src/pages/JobsPage.tsx`(demo 提交表单 + 任务列表页) | 联调夹具,不是产品形态,留着误导 |
| 删 | `web/src/components/staging/QaRenderers.tsx` + 注册表里 `qa_pair` 一行 | 属于 exact-qa 域的"具体页面代码",由 S1 开发者在自己域文件夹里重写 |
| 留 | `GET /api/kbs`、`knowledge_bases` 表、全部后端接口 | 外键归属根;删页面不删实体 |
| 留 | `<StagingReview>`(泛型审核台)、`ReviewPage`、JSON 兜底渲染器 | 框架件,三域共用 |
| 留 | Job 框架(`core/jobs.py`)、`demo_sleep` 假任务、`<JobProgress>` | 框架联调对象;入口改走 curl/脚本 |
| 留 | 静态预览(`web/demo/`) | 同步瘦身:删掉的页面对应的 fixture 路由一起删 |

**两个已知代价(接受)**:

- 删掉 JobsPage 后,跑 demo 任务和进入审核台**暂时没有界面入口**:demo 任务用 curl/脚本提交,
  审核台用直链 `/jobs/{id}/review` 打开。正式入口由各域开发者在自己的域页面里做。
- 删掉 QA 渲染器后,审核台里 `qa_pair` 条目走 JSON 兜底渲染 —— 这正是兜底渲染器存在的意义
  (渲染器没写好之前,任何类型都能审)。

---

## Stage 1 · 前端 domains/ 骨架 + manifest(纯加法,先立框架再拆旧墙)

**做什么**:

1. 新建 `web/src/domains/`,一域一文件夹:

   ```
   web/src/domains/
     index.ts            # 唯一共享落笔点:DomainModule 类型 + DOMAINS 数组(三行)
     exact-qa/
       module.ts         # 描述符:key/itemType/label/icon/tone/path/页面/渲染器
       IngestPage.tsx    # 空白壳:域识别色 EmptyState + "To be built in S1"
       claude.md / architect.md
     document/           # 同上,S2
     text2sql/           # 同上,S3
   ```

2. `DomainModule` 描述符把「路由 / 导航子项 / 顶栏标题 / 识别色 / 审核渲染器 / 预览假数据」
   收进一个对象;`App.tsx` 路由、`AppLayout` 导航与 `TITLES`、`staging/registry.ts`
   全部改为**遍历 `DOMAINS` 生成**,不再手写。加一个域 = `index.ts` 加一行。
3. 侧栏 "Ingestion" 改为 "Knowledge Ingestion" 可展开分组,子项三个,识别色按 UI-STYLE §2
   (QA=accent 黄 / 文档=info 蓝 / 问数=紫),色值不出现在组件里。
4. 现有 `src/{api,components,layouts,lib}` **约定为 shared 层**(不搬家、不改 import 路径,
   靠文档纪律圈定"域开发者只读"),避免大迁移引入无谓风险。

**自测(全绿才进 Stage 2)**:

- [ ] `cd web && npx tsc -b && npm run lint && npm run build` 零错误
- [ ] dev 环境点击走查:三个子项都能点开,各自空状态 + 识别色正确,顶栏标题正确,
      直接刷新 `/ingest/document` 不 404
- [ ] 回归:`/chat` 流式对话 + 轨迹面板正常;`/jobs/{id}/review` 审核台正常(此时 qa_pair
      仍走 QA 渲染器,Stage 2 才删)
- [ ] grep 断言:`App.tsx` / `AppLayout.tsx` / `registry.ts` 中不再出现任何单个域的硬编码
      (只 import `domains/index`)

## Stage 2 · 删旧页面(KbListPage / JobsPage / QA 渲染器)

**做什么**:

1. 删除上表"删"列的三个文件及其路由、导航项、`TITLES` 行、页面间链接
   (`JobProgress` 里指向 review 的链接保留 —— 它是框架件)
2. `staging/registry.ts` 删除 `qa_pair` 行(注册表和兜底机制原样保留)
3. `web/demo/` 同步:删 kbs/jobs 页面 fixture 路由;**保留** staging 审核台的可写假数据流
   (预览里审核台改用直链进入,`qa_pair` 走 JSON 兜底渲染)
4. `make demo` 重建预览

**自测**:

- [ ] `npx tsc -b && npm run lint && npm run build` 零错误(死 import 全清干净的证明)
- [ ] curl 全链路回归(替代被删的界面入口):
      `POST /api/jobs`(demo_sleep)→ 轮询 `GET /api/jobs/{id}` 到 review →
      浏览器直链 `/jobs/{id}/review` → JSON 兜底渲染 20 条 → 改一条/批量通过 → 发布成功
- [ ] 检查 `/kbs`、`/jobs` 直接访问被重定向,侧栏无死链
- [ ] `grep -rn "KbListPage\|JobsPage\|QaRenderers" web/src web/demo` 零命中
- [ ] 静态预览:审核台直链可用、可改状态、可发布;chat 流式正常

## Stage 3 · 后端三域文件夹 + 注册解耦

**做什么**:

1. 建 `server/app/services/{exact_qa,document,text2sql}/`,各含 `__init__.py` +
   `claude.md` / `architect.md`(写明:本域的 Job 子类、publisher、检索 stage、prompt 都落这里,
   **不 import 兄弟域**,只向上依赖 core/models)
2. 注册解耦:`app/services/__init__.py` 成为唯一的"注册 import 点"
   (现在先 import `core.jobs_demo`,S1–S3 各加自己一行);`api/jobs.py` 删掉对
   `jobs_demo` 的直接 import,改 import `app.services`
3. **不建任何新接口、不写任何域逻辑** —— 各域 router 等流程确定后由各域自己加

**自测**:

- [ ] `cd server && uv run pytest` 全绿
- [ ] uvicorn 冷启动无报错;`GET /api/jobs/types` 仍返回 `["demo_sleep"]`
      (证明注册链 `services/__init__ → core.jobs_demo` 是通的)
- [ ] curl 全链路回归同 Stage 2(提交→进度→审核→发布)
- [ ] 两个冒烟脚本:`make smoke`(后端)+ `make smoke-sse`(前端 SSE)全绿

## Stage 4 · 文档同步 + 并行开发纪律入册

**做什么**(按 CLAUDE.md 文档同步纪律,这不是可选项):

1. 根 `architect.md`:目录地图、"我要改 X 去哪"表、数据流图更新(域文件夹、manifest、入口变化)
2. `web/claude.md` / `web/src/*` 各级索引更新;新增纪律:
   - `types.gen.ts` 是生成物,**冲突永远重跑 `make types`,禁止手工合并**
   - `src/{api,components,layouts,lib}` 是 shared 层,域开发者只读;要改公共契约单独提
3. `server/claude.md` 新增纪律:
   - **migration 串行生成**:域开发者只改 `models/` 自己域的文件 + DB-DESIGN 自己域的节,
     不自己 `alembic revision`;合并时由集成者统一生成,避免 multiple heads
   - 共享表(`ingest_jobs`/`staging_items`/`publish_records`/`knowledge_bases`)红线:
     任何域不得加"只有自己需要"的列,差异进 jsonb 或自己域的表
4. `documents/S0-PLAN.md` 标注:Step 6 的契约验证证据(`KbListPage.tsx:52`)与 Step 8 的
   QA 渲染器已被本计划删除/接替,历史记录不改,注明接替物
5. `documents/PRD.md`:受影响的导航/页面描述同步;三类 ingestion 流程标记为"待需求方确认后重写"

**自测**:

- [ ] 逐份文档走查:本次删/增的每个文件在对应 claude.md/architect.md 里有/无索引与实际一致
- [ ] 终检回归(全套):`make types` 后 git diff 干净(接口没变的证明)、pytest、双冒烟、
      `tsc -b`、curl 全链路、`make demo` 预览重建
- [ ] git 提交(每 Stage 一个 commit,提交前 `git diff --cached | grep -c 'sk-proj'` = 0)

---

## 不在本计划内(明确不做)

- 三类 ingestion 的任何真实流程/表单/接口 —— 等需求方讲完流程,写进 PRD 后由各域开发
- 审核台渲染器契约的 `actions` 插槽(S3 预判需求)—— 等真需要时作为公共契约变更单独提
- Alembic merge 策略工具化 —— 纪律先行,出现真实冲突再说
