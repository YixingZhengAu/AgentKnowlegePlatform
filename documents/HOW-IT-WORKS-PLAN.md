# How It Works 说明页 · 计划(HOW-IT-WORKS-PLAN)

**版本**:v1
**日期**:2026-08-24
**性质**:一个前端功能的实施计划(不是阶段计划,不占 S 编号;与 S2 的开发互不阻塞)
**一句话**:在系统里长一副**面试用的幻灯片**,把这套系统的设计思想讲清楚。

---

## 1. 目标与非目标

### 1.1 目标

| # | 目标 | 判据 |
| --- | --- | --- |
| G1 | 屏幕共享时能靠它把设计思想讲完 | 从总页滚到底 + 进三个子页,一次讲解 8–10 分钟,不需要再切别的窗口 |
| G2 | 讲的是**为什么这么设计**,不是怎么用 | 全篇不出现表名、字段名、函数名、接口路径、阈值数字 |
| G3 | 讲清与通用 RAG 的差别 | 痛点 → 根因 → 我们的回答,三段式,读者能复述出"分层 + 前置 + 人审 + RAG 兜底" |
| G4 | 大字可读 | 1440×900 投屏下正文不小于 16px,标题层级一眼分明 |

### 1.2 非目标(明确不做)

- **不做深链**:不往 `/ingest/*`、`/chat`、审核台跳。这页是讲稿,不是导览。
  (讲完之后要演示,是我手动切到那些页面,不靠页内按钮。)
- **不做使用手册**:不写"点哪个按钮、填哪个框"。
- **不动后端**:零接口、零 openapi 变更、不跑 `make types`。
- **不做 i18n**、不做打印/PDF 导出、不做动画演示、不做暗色模式。
- 不引任何新前端依赖(图表/幻灯片/Markdown 渲染库一概不引)。

---

## 2. 内容:主张与三条推论(整页的地基)

**主张(总页开场那句)**

> **Enterprise agents shouldn't improvise.**
> We move the thinking forward — from answer time to curation time.

**三条推论**(总页的骨架,三个子页各是它在一层里的展开)

| # | 推论 | 讲法 |
| --- | --- | --- |
| R1 | **前置而非临场** | 精准问答对与问数意图都是事先定好、事先验收的。回答时 Agent 只做匹配与受限填空,不做自由发挥 —— 企业要的是可控、可复现、可追责,不是聪明。 |
| R2 | **业务团队是知识的所有者** | AI 只提候选,**只有业务人员审核通过的才成为知识**。没人签字的东西不进检索面。 |
| R3 | **RAG 是兜底,不是主力** | 只有不要求百分百准确的问题才交给 RAG。所以检索有顺序:**精准问答 → 问数意图 → RAG → 说不知道**。 |

R3 就是全站最好讲的一张图:一个**倒漏斗**,自上而下四层(Exact / Text-to-SQL / RAG / Fallback),
右侧标三根轴:required accuracy ↓、human effort ↓、model freedom ↑。

---

## 3. 总页 `/how-it-works` 的结构

**结构演进(2026-08-24,需求方定,替代最初的八屏长滚)**:观看者没时间从上滚到底,
所以总页改为「**两个常驻块 + 六个折叠区**」——
主张块(屏 1)与三层卡片(原屏 8,**提前到第二位**)常驻;
其余六个论点收进折叠区,默认收起,折叠态一行 = 标题 + 关键词摘要,当目录用,讲哪点开哪。
体裁同步收紧:**全篇关键词/短语,不写文章**,完整句只留每层主角句与每屏强调句。

下表是内容清单(原八屏的论点全部保留,只是呈现方式变了):

| # | 屏 | 内容要点 | 图 |
| --- | --- | --- | --- |
| 1 | **The claim** | 主张两句 + 三条推论各一行 | 倒漏斗(四层 + 三根轴) |
| 2 | **Why generic RAG isn't enough** | 七条痛点,每条三段式:症状 → 根因 → 我们的回答(见 §3.1) | 无(三列文字网格) |
| 3 | **Three layers, one gate** | 三层知识各一句定位;共同的治理骨架 **raw material → AI proposes → business approves → published**;重点句:human-in-the-loop 是设计的一部分,不是补丁 | 骨架四步条 |
| 4 | **What happens when someone asks** | 一条从提问到答案的链路,标出三件事:哪里短路直接给标准答案、哪里只允许受限改写、哪里允许概括但必须给出处;末端是"没有依据就说没有" | 竖向链路图(带三个分岔终点) |
| 5 | **Who uses it, and how** | 两条路径:Business / Knowledge Ops(上传 → 审核 → 发布)与 End user(提问 → 答案 + 出处 + 可展开的过程) | 两条并列泳道 |
| 6 | **The three layers side by side** | 五行对比:required accuracy / who defines the knowledge / what the model may do at answer time / main risk / how we contain it | 表(唯一一张表) |
| 7 | **What we deliberately don't do** | 取舍与代价:覆盖率靠人工投入、冷启动慢、长尾要运营闭环、不做带副作用的 Action、不追高并发 | 无 |
| 8 | **Three layers in detail** | 三张卡片进子页(识别色圆点 + 一句主角句) | 无 |

### 3.1 屏 2 的七条痛点(症状 → 根因 → 我们的回答)

| 症状 | 根因 | 我们的回答 |
| --- | --- | --- |
| 什么都能答一点,什么都不敢信 | 所有知识丢进同一个库,高价值答案被普通文档稀释 | 按要求的准确度分三层治理,各层各自的策略 |
| 同一个问题两次答不一样 | 判断全留给回答时的模型 | 把决策前移到治理期:决定一次,不是每次 |
| 错的知识和对的知识享受同等待遇 | AI 抽完直接生效,没人签字 | 业务人员审核是发布的必经闸门 |
| 同一个指标有两个答案 | 口径散落在文档、SQL、口头里 | 口径只留一份,焊在已验收的模板里 |
| 数据类问题永远答不对 | 答案根本不在文档里 | 数据问题走治理过的语义层,不靠文档 |
| 答错了不知道该修哪 | 全链路是黑盒 | 每次回答都留可看的过程与出处 |
| 检索为空就开始编 | 流程缺兜底 | 无依据即明说,不允许自由发挥 |

---

## 4. 三个子页(同一模板)

路由:`/how-it-works/exact-qa` · `/how-it-works/document` · `/how-it-works/text2sql`

**六段模板**

1. **What this layer is for** —— 定位 + 对准确度的要求 + 两个真实业务问题示例
2. **Why it can't be improvised** —— 答错的后果
3. **What we settle up front** —— 前期定好了什么(业务语言)
4. **Where the business team steps in** —— 他们批的到底是什么(**每页重点段**)
5. **What happens at answer time** —— 几步,以及模型**被允许 / 不被允许**做什么
6. **What this layer deliberately doesn't do** —— 取舍与代价

**三页的主角句(每页第 1 段的那一句)**

| 页 | 主角句 |
| --- | --- |
| Exact Q&A | On a confident match we return the human-approved answer **verbatim** — the model doesn't get to rewrite a single word. |
| Document RAG | This layer promises **useful and sourced**, not exact — citations are mandatory, and "no basis found" is a valid answer. |
| Text-to-SQL | At answer time we **don't write SQL** — we match a definition the business already signed off on and fill in its parameters under constraints. |

**文档 RAG 这页照常写,不标"未实现"**(需求方决定,2026-08-24)。因此这页只讲设计取向
(分层切分、带出处、允许概括、无依据兜底),不描述任何界面。

---

## 5. 视觉与排版

### 5.1 演示页字阶(**UI-STYLE 的一处例外,需先改规范**)

UI-STYLE §2 写着「不用 24px 以上的 sans 字号(工作台不是营销页)」。这页是投屏讲稿,
必须放大,所以做法是:**先在 UI-STYLE 补一节 §2.x「演示页字阶(作用域仅 /how-it-works)」**,
把下表写成规范,再在代码里实现。不允许在组件里偷偷写大字号。

| 用途 | 尺寸 |
| --- | --- |
| 屏标题(h2) | Montserrat 700 / 30px / `-.02em` |
| 主张句(开场) | Montserrat 700 / 34px / `-.02em` |
| 段标题(h3) | Montserrat 600 / 20px |
| 正文 | Inter 400 / 17px / 1.65 |
| 强调句(每屏一句) | Inter 600 / 19px |
| 标注 / meta | Inter 400 / 13px `faint`;数字仍走 mono |

其余一切不变:颜色只用既有 token(**不新增 hex**)、圆角与阴影照既有档、动效仅 150ms 一档、
图标 lucide 1.75、不用 emoji、不做渐变(既有那一处例外除外)。

### 5.2 版式

- 内容最大宽 **860px**(业务页是 680px,讲稿行长可以更宽),居中,页面左右留白 48–64px。
- 屏与屏之间间距 88px,屏内段间距 28px;不给每屏套卡片(卡片只用于屏 8 的三个入口)。
- 右侧轨迹面板不挂载(`useRightPanel` 不设值,天然不占宽)。
- 窄屏(<960px)所有多列网格降为单列,图形 SVG 用 `viewBox` + `max-width:100%` 自适应。
- 顶栏标题走既有机制:`AppLayout` 的 `TITLES` 加 `{ prefix: '/how-it-works', title: 'How It Works' }`。

### 5.3 图形

四张图(倒漏斗、治理骨架四步条、回答链路、两条泳道)放在 `pages/how-it-works/figures.tsx`,
不引任何图表库。**落地时把画法从内联 SVG 改成既有 token 的填充块**(2026-08-24,Step 3):
图里的说明句较长,SVG `<text>` 不换行、窄屏必溢出;填充块既符合 UI-STYLE 的「白底 + 填充块」,
也天然自适应。倒漏斗保留几何语义 —— 块宽自上而下递增,表达模型自由度递增。
三类知识出现在图里时用既有识别色(黄/蓝/紫,走 `bg-kb-*`)。

---

## 6. 代码落点与文件清单

这是**公共页面**(不是知识域),按根 `architect.md` §3 的纪律落在 `web/src/pages/`;
新增目录必须带 `claude.md` + `architect.md`。

```
web/src/pages/how-it-works/
  claude.md            职责 + 文件索引 + 指向 architect.md
  architect.md         内容结构、八屏与六段模板、图形清单、"我要改文案去哪"
  content.ts           ★ 全部英文文案与结构化数据(claim / painPoints / layers / comparison / tradeoffs / 三个子页的六段)
  figures.tsx          四张内联 SVG
  Section.tsx          屏骨架(标题 + 强调句 + 正文槽),把 §5.1 的字阶收敛在一处
  OverviewPage.tsx     总页(八屏,只渲染 content.ts)
  LayerPage.tsx        子页模板(按 slug 从 content.ts 取一层的六段)
  index.ts             对外只导出两个页面组件
```

**共享层改动(三处,都是加行)**

| 文件 | 改动 |
| --- | --- |
| `web/src/App.tsx` | 加 `/how-it-works` 与 `/how-it-works/:layer` 两条路由 |
| `web/src/layouts/AppLayout.tsx` | `NAV_MAIN` 最上方加一项(`BookOpen`,label `How It Works`)+ `TITLES` 加一条 |
| `web/src/pages/claude.md` | 表格加一行 |

**纪律**:`content.ts` 是文案的唯一出处,页面组件里不写死任何句子 —— 改讲法不碰布局。
不 import 任何 `domains/*` 的东西(识别色用 `index.css` 的 `bg-kb-*` 工具类,不复用 DomainModule)。

---

## 7. 实施步骤

| Step | 做什么 | 自测/验收 |
| --- | --- | --- |
| 1 | 改 `documents/UI-STYLE.md`:补 §2.x 演示页字阶(作用域限 `/how-it-works`) | 规范里能查到这套字阶,且写明作用域 |
| 2 | 写 `content.ts` 全部英文文案 —— **先交需求方逐句过一遍**,再往下做 | 需求方确认;通读一遍不出现表名/字段名/接口/阈值(G2) |
| 3 | `Section.tsx` + `figures.tsx`:骨架与四张图 | `/styleguide` 无影响;图在 1440 与 900 宽下都不溢出 |
| 4 | `OverviewPage.tsx` 八屏 | 浏览器从上滚到底,八屏顺序与 §3 一致 |
| 5 | `LayerPage.tsx` 三个子页 | 三页六段齐全,主角句在位;`/how-it-works/xxx` 未知 slug 重定向回总页 |
| 6 | 接线:路由 + 侧栏 + 顶栏标题 | 侧栏点进去、刷新直链都对;右侧面板不占宽 |
| 7 | 投屏走查 | 1440×900 全屏读一遍,正文 ≥16px、无横向滚动;窄到 900px 全部单列 |
| 8 | 收尾 | `make lint` + `tsc` 全绿;文档同步(§8)完成 |

---

## 8. 文档同步清单(改完当场做)

- `documents/UI-STYLE.md`:§2.x 演示页字阶(Step 1 就做)
- `web/src/pages/how-it-works/claude.md` + `architect.md`:新建
- `web/src/pages/claude.md`:表格加一行
- `web/src/claude.md`:`App.tsx` 那行的路由清单加 `/how-it-works`
- 根 `architect.md` §3「我要改 X」:加两行 —— 「改说明页的文案」→ `content.ts`;
  「改说明页的图」→ `figures.tsx`;§6 当前进度的页面列表补一句
- `README.md`:功能列表提一句 How It Works 页(对外英文)
- `documents/PRD.md`:§4.4 之后不新增需求条目;仅在 §2.1 前端模块那句里带一笔"另有一个说明页"

---

## 9. 风险与取舍

| 风险 | 应对 |
| --- | --- |
| 文案写成技术文档,失去讲稿性质 | Step 2 单独交需求方过一遍;G2 的判据是硬检查(出现表名即返工) |
| 字阶例外被后续开发误当全站规范 | UI-STYLE 里写明作用域;字阶只在 `Section.tsx` 一处实现 |
| 文档 RAG 那页与实际未实现产生落差 | 该页只讲设计取向、不描述界面,故不依赖实现进度;S2 落地后回看是否要改口径 |
| 内容随系统演进过期 | 文案集中在 `content.ts` 一个文件;文档同步纪律里已挂在根 `architect.md` 的索引表上 |
