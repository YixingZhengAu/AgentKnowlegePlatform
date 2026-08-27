# how-it-works · 结构说明

## 这页是什么

把「为什么这么设计」与「结构长什么样」讲完的说明页。
不放实现细节(不出现表名、字段名、接口路径、阈值),不做深链,不动后端。
**体裁:自读优先**(2026-08-26 需求方定,取代 08-24 的「投屏讲稿」定位):
一个没时间的人自己点开,前三屏拿到全部精髓;投屏讲解靠折叠组的 Expand all 还原全展开。
仍然一律关键词/短语,完整句只留两类 —— 每层一句主角句、每段一句强调句。

**v2(2026-08-26)**:原来只有「主张 + 三层」,架构讲得不够专业。于是补了架构内容:
六层技术架构 / 外壳内核 / 一次请求 / 角色闭环 / 四层评估 / 自主性边界,每层子页也各加
两条流程图;侧栏做成可展开分组,和 Knowledge Ingestion 一个形状。架构思想的来源是面试
复盘笔记里那几条(deterministic shell + agentic core、autonomy 按后果分级、四层评估、
correctness ≠ safety)。

**v2.1(同日,需求方定)**:架构内容一度是独立子页 `/how-it-works/architecture`,现已
**并回总页** —— 「为什么这么设计 → 结构长什么样」本就是一条论证,拆两页反而要来回跳。
子页与其入口卡片(`ARCH_LINK`)已删。

**v3(同日,需求方定)**:自读优先重排(计划 §12)。四个动作:**提前、收折、加例子、
砍重复**。三层卡片提到第二屏、request path 拎出独立成块;架构五小节 + 原四区共 9 个
折叠区默认收起,顶部 Expand all / Collapse all 统一开合;锚点条删除(折叠列表取代其
目录功能);漏斗每层加例句、折叠摘要改结论句;常驻黄条只剩 2 条(CLAIM + REQUEST_PATH)。

**v4(2026-08-27,需求方定)**:**图先于字**(计划 §13)。读者很忙,重点必须靠图给,
不靠句子给。三个动作:
1. **补一张全局图**(`SystemMapFigure`,常驻第一块):左治理期 / 右回答期两条泳道,
   都落到中间的「已签字的知识」,底下一条回边 + 一条留痕轨。整页唯一的「一图看懂」入口,
   把 `CLAIM.lede` 那句 answer time → curation time 画出来。
2. **每张图都看得见方向**:步骤之间一律有箭头(`FlowArrow`,可带原因标签),
   分岔一律左右分开(请求链路改成判定流程图:**命中往右出绿块、未命中沿主干往下**),
   闭环一律有虚线回边;治理骨架四步之间补箭头,闭环拆成治理/回答两行,
   评估四级串成一条链、检查项做成 chips,技术架构标出 T6→T1 与**供应商接缝**,
   自主性边界中间加一道带锁的虚线。
3. **图注化**:漏斗升为独立一屏(`FUNNEL.title` / `.summary`),三层卡片加
   `FreedomMeter` 三格自由度条(与漏斗 model freedom ↑ 同一口径),文字退成图的注解。

**v5(同日,需求方纠正 + 补最后一块拼图)**:计划 §14。两件事:

1. **层级关系改对了**。原来那张四级倒漏斗(`FUNNEL`)把「精准问答 → 智能问数 → 文档 → 无依据」
   画成四级台阶,读者会以为文档 RAG 是第三档知识。真实层级是:**精准问答 / 智能问数 /
   编排三者同级** —— 都事先注册意图,回答时一次意图匹配、谁命中谁执行,同级之间只有
   「谁更具体」的 tie-break(实现上按固定顺序落这个 tie-break,与 `core/chat.py` 一致);
   **文档 RAG 是兜底**,只在无人命中时才跑。新图 `RoutingFigure`:三家**并排等宽**在一个框里,
   往下一条带原因的箭头才是兜底,再往下是「说没有依据」。一次请求那张图同步改成
   **一步三出口**(意图那一步右侧三个绿块并列)。
2. **补上第四种知识:编排(workflow)**。它**不产生新事实**,只把前三种按签过字的顺序连起来,
   再加代码节点(阈值/分支)与动作节点(写库/外发,守人审那道闸)。它**和三层一样有自己的子页**
   `/how-it-works/workflow`(`WorkflowPage`,侧栏里四页并列):概念图(已发布的知识 → 引用 →
   四种节点)+ 四条纪律 W1–W4 + 那条客服邮件编排逐节点的 input / output / 参数绑定 +
   一句「已设计、未落地」。卡片区第四张卡链到它;摄取侧的占位页在 `src/domains/workflow/`。
   路由上 `/how-it-works/workflow` 在 `:layer` 之前显式声明(它不是 `LayerSlug`)。

## 两级结构

| 路由                   | 页面           | 内容                                                                                                                       |
| ---------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `/how-it-works`        | `OverviewPage` | **为什么 + 是什么**:主张 + 全局图 → 路由漏斗(例句)+ R1–R3 → 三层卡片(例子 chips + 自由度条)→ 一次请求(判定流程图)→ 架构段(四条立场常驻 + 五小节折叠)→ 四折叠区 → 署名 |
| `/how-it-works/:layer` | `LayerPage`    | **怎么做**:一层一页,含治理期 / 回答期两条流程                                                                              |
| `/how-it-works/workflow` | `WorkflowPage` | **第四种知识**:概念图 + W1–W4 + 「已设计、未落地」+ 客服邮件那条编排逐节点 |

侧栏子项清单是 `content.ts` 的 `HOW_IT_WORKS_NAV`(总页 + 四种知识各一页,顺序 = `KIND_CARD_ORDER`:
两家意图层 → 编排 → 文档兜底),由 `AppLayout` 遍历渲染 —— **AppLayout 不硬编码任何一页**,
和 DOMAINS 同一纪律。

## 总页(常驻 + 折叠)

| 块                                                                           | 数据来源                       | 图                  |
| ---------------------------------------------------------------------------- | ------------------------------ | ------------------- |
| 常驻:The claim + **全局图**(整页第一眼)                                       | `CLAIM` + `SYSTEM_MAP`         | `SystemMapFigure`   |
| 常驻:**两级路由**(三家同级 + 兜底 + 无依据)+ R1–R3 | `ROUTING` + `CLAIM.corollaries` | `RoutingFigure` |
| 常驻:The four kinds of knowledge(例子 chips + 自由度条) | `LAYERS` + `WORKFLOW_CARD` + `KIND_CARD_ORDER` | 四张卡片 + `FreedomMeter` |
| 常驻:One request, end to end                                                 | `REQUEST_PATH`                 | `RequestPathFigure` |
| 常驻:Architecture 开场(标题 + lede + 四条立场)                               | `ARCHITECTURE` + `PRINCIPLES`  | 四张卡              |
| 折叠:架构五小节(stack / shell-core / journey / evaluation / autonomy,见下表) | 五个数据块                     | 五张图              |
| 折叠:Why generic RAG isn’t enough                                            | `PAIN_POINTS`                  | —                   |
| 折叠:Three layers, one gate                                                  | `GATE` + `LAYERS`              | `GateFigure`        |
| 折叠:The three layers side by side                                           | `COMPARISON`                   | 表(全页唯一)        |
| 折叠:What we deliberately don’t do                                           | `TRADEOFFS`                    | —                   |
| **页首:署名**(v5.1 从页脚挪到页首)                                          | `AUTHORS`                      | —                   |

折叠区由 `Section.tsx` 的 `CollapsibleScreen` 实现:默认收起,折叠态一行 =
24px 标题 + 13px **结论句**摘要(`*.summary`),9 行拼起来就是目录。
它是受控/非受控两用:传 `open` + `onToggle` 受控(总页把 9 个折叠区的开合状态
提升为 `openIds: Set<string>`,折叠组顶部一个 Expand all / Collapse all 文本按钮
统一开合),不传则内部自持状态。常驻黄条(`Emphasis`)恰好 2 条:CLAIM 与
REQUEST_PATH;其余 emphasis 随所在小节进折叠区。
三条推论(`CLAIM.corollaries`)是全篇地基;**层级口径**(v5):精准问答 / Text-to-SQL / 编排
同级(注册意图,命中即执行),文档 RAG 是兜底,再往下是「说没有依据」—— 与后端
`core/chat.py` 的 stage 顺序不矛盾:那个固定顺序就是同级之间的 tie-break。
命名纪律:该层全站叫 **Text-to-SQL**;第四种叫 **Workflows**(不叫 orchestration)。

## 架构段(总页内:开场常驻,五小节折叠)

开场 = `ScreenTitle` + lede + 四条立场(`PRINCIPLES`);`REQUEST_PATH` 已拎出到
常驻区独立成块(30px `ScreenTitle`);其余五小节进折叠组(标题走 `CollapsibleScreen`
的 24px)。锚点条(v2.1 的 `ANCHORS`)已删,折叠列表取代其目录功能。

| 小节                                    | 数据来源       | 图                  | 讲什么                                                       |
| --------------------------------------- | -------------- | ------------------- | ------------------------------------------------------------ |
| One request, end to end(常驻) | `REQUEST_PATH` | `RequestPathFigure` | **判定流程图**:意图那一步**一步三出口**(三家同级各一个绿块),未命中沿主干往下到兜底(箭头带原因)+ 全程留痕 |
| The stack, tier by tier(折叠)           | `STACK`        | `StackFigure`       | 六层 T6→T1 + 每层 owner,箭头向上表示谁支撑谁,底部一条供应商接缝虚线 |
| Deterministic shell, agentic core(折叠) | `SHELL_CORE`   | `ShellCoreFigure`   | 外壳是代码写的确定性约束,内核才是模型真正能想的地方          |
| The loop people actually live in(折叠)  | `JOURNEY`      | `JourneyFigure`     | 七步闭环拆治理 / 回答两行,行内箭头相连,末尾一条虚线回边到 01 |
| How we know it works(折叠)              | `EVALUATION`   | `EvaluationFigure`  | 四级评估串成一条链(L1→L4),检查项做 chips                    |
| Where autonomy stops(折叠)              | `AUTONOMY`     | `AutonomyFigure`    | 读/析/摘宽松,写/执行/外发不给,中间一道带锁的虚线            |

**口径纪律**:评估那段只写现在真做得到的事(固定评测集复跑、数字回源核对、无出处即缺陷),
不写没落地的平台能力;`AUTONOMY` 最后一句明说「今天这个 agent 不做任何动作」。

## 子页

`LAYER_DETAILS[slug]`,三页同一结构:主角句 + 示例 chips → **两条流程**
(`curation` / `runtime`,`FlowFigure` 渲染,`kind: gate` 打黄色 GATE 徽标、`kind: stop`
打灰色 END 徽标)→ 四张关键词卡(业务介入那张黄色识别条高亮)→ **may / may not 两列**
(绿底/红底)→ Deliberately doesn’t。

两条流程是这次 v2 的重点:左边治理期、右边回答期,一眼看出「重活在前面做完了」。
文档 RAG 那页**照常写、不标未实现**(需求方 2026-08-24 决定)。

## 排版

`Section.tsx` 收敛 UI-STYLE §2「演示页字阶(作用域仅 /how-it-works)」:主张 34 / 屏标题 30 /
折叠区标题 24 / 段标题 20 / 正文 17·1.65 / 强调 19 / meta 13。内容最大宽 860px,
常驻大块间距 64px(`mt-16` + 分隔线),右侧面板不挂载。
行内强调只支持 `**...**`,由 `<Emphasized>` 解析。

`figures.tsx` 用填充块 + lucide 箭头而非 SVG:图里的说明句较长,SVG `<text>` 不换行、
窄屏必溢出;填充块既合「白底 + 填充块」的基调,也天然自适应(1000 / 1440px 实测无横向滚动)。
方向感全靠通用零件 `FlowArrow`(down / right,可带一句原因标签,标签走 `<Emphasized>`)。
**同级用并排、兜底用下一行**(`RoutingFigure`):层级关系必须靠版面表达,不靠句子解释;
旧的倒漏斗(块宽递增 = 自由度递增)因为把同级画成了台阶,已删。
黄色只出现在两处语义上一致的地方:三层里的 Exact Q&A 识别色,以及**人审闸门**
(治理骨架第 3 步 / 流程图的 GATE / 闭环里的 ops 步)。

## 我要改 X 去哪

| 要改                 | 去哪                                                                                                                        |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 任何一句文案         | `content.ts`(唯一出处)                                                                                                      |
| 图的画法             | `figures.tsx`                                                                                                               |
| 侧栏里说明页的子项   | `content.ts` 的 `HOW_IT_WORKS_NAV`(AppLayout 只遍历)                                                                        |
| 字号 / 行长 / 段间距 | `Section.tsx` + 各页面的容器类                                                                                              |
| 架构段加一小节       | `content.ts` 加数据 + `figures.tsx` 加图 + `OverviewPage.tsx` 折叠组加 `<CollapsibleScreen>` 并把 id 加进 `COLLAPSIBLE_IDS` |
| 漏斗某层的例句       | `content.ts` 的 `FUNNEL.layers[].example`                                                                                   |
| 署名                 | `content.ts` 的 `AUTHORS`                                                                                                   |
| 总页加一个折叠区     | `content.ts` 加数据 + `OverviewPage.tsx` 加一个 `<CollapsibleScreen>` 并把 id 加进 `COLLAPSIBLE_IDS`                        |
| 路由层级(谁跟谁同级 / 谁是兜底) | `content.ts` 的 `ROUTING` + `figures.tsx` 的 `RoutingFigure`;改完必须同步 `REQUEST_PATH.steps[1].exits` 与 `COMPARISON` 的列顺序 |
| 编排那一节(概念 / 四条纪律 / 例子) | `content.ts` 的 `WORKFLOW` / `WORKFLOW_EXAMPLE`;图在 `figures.tsx` 的 `WorkflowConceptFigure` / `WorkflowExampleFigure` |
| 卡片区的顺序或多一张卡 | `content.ts` 的 `KIND_CARD_ORDER`(+ 卡片数据);`OverviewPage.tsx` 只遍历它 |
