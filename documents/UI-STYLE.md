# 前端风格规范(UI-STYLE)

**基准**:企业级 SaaS 品牌色(navy + 黄)+ 2026-08 的界面改版原型
(原型解包后的可读源码:`tmp/04-prototype-source.html`,改版计划 `tmp/UI-REDESIGN-PLAN.md`)。
**约束力**:所有前端开发遵循本文档;shadcn/ui 主题变量、Tailwind token 以此为唯一来源。改风格先改这里。

> 2026-08 改版说明:品牌 navy 与 yellow 不变,**其余全部换掉**了 ——
> 深色侧栏改浅色、页面灰底改白底、6/12px 圆角改 pill、黄色主 CTA 改 navy。
> 下面写的就是改版后的规范;旧版(深色导航 + 灰底白卡)已作废。

## 0. 视觉基因

- **主色是深海军蓝 `#00205B`**:标题、导航激活态、主按钮、进度条——品牌的绝对核心
- **亮黄 `#FFCB02` 是识别色不是主 CTA**:只用于 Exact Q&A 的身份点与高亮徽标底,面积极小
- **整体白底**,分层靠浅填充块(`#F6F8FB` / `#F4F6F9`)与三档细线,而不是灰底白卡
- **冷灰中性阶**(`#111318` → `#C5C9D2`),比暖灰更贴近 navy,六档拉开层级
- 字体 Montserrat(标题)/ Inter(正文)/ JetBrains Mono(**所有数字**)
- 圆角:控件全 pill,容器 16–18px;**没有渐变(进度卡一处例外)、没有玻璃拟态、没有暗色模式**
- 整体气质:工业、可信、干净、大留白——To B 企业感,不是消费级软件的活泼感

## 1. 设计原则(五条,做任何界面前先过一遍)

1. **Navy 是身份也是行动**:导航激活态、主 CTA、进度填充都用 navy;一屏只有一个 navy 实心按钮
2. **黄色是识别色,不是按钮**:黄只出现在 Exact Q&A 的色点与它的浅底徽标上,不做大面积色块
3. **白底 + 填充块分层**:页面是白的,层次靠 `#F6F8FB`/`#F4F6F9` 填充块、三档细线、五档轻阴影
4. **数字一律等宽**:置信度、耗时、百分比、token、计数、build 号全部 JetBrains Mono ——
   数字对齐本身就是这个工具可信的证据
5. **克制的圆角与动效**:控件 pill / 容器 16–18px;动效只有 `all 150ms ease` 一档,不做弹跳视差

## 2. 设计 Token(Tailwind / CSS 变量唯一来源)

落地在 `web/src/index.css`,三层结构见 §5。下表是第 1 层的事实值。

### 品牌

| Token | 值 | 用途 |
| --- | --- | --- |
| `primary` | `#00205B` | 主按钮、导航激活文字、标题、进度填充 |
| `primary-hover` | `#18206D` | 主按钮 hover |
| `primary-soft` | `#EDF2FB` | 导航激活底、navy 徽标底 |
| `accent` | `#FFCB02` | Exact Q&A 识别色、高亮徽标点 |
| `accent-soft` / `accent-ink` | `#FFF6D9` / `#6B5200` | 黄色徽标的底与字(**黄底永远配深字,不配白字**) |
| `accent-orange` | `#F28601` | 次强调,少用 |
| `dark` | `#111827` | 分段控件激活态,全站唯一一处近黑 |

### 中性阶与面

| Token | 值 | 用途 |
| --- | --- | --- |
| `foreground` | `#111318` | 正文、主标题 |
| `secondary-foreground` | `#5A6172` | 次级正文、未激活导航 |
| `muted-foreground` | `#8A90A0` | 说明文字、meta |
| `faint` | `#9FA5B2` | helper、列表副行 |
| `fainter` | `#B4B9C4` | 占位符、disabled 文字、build stamp |
| `ghost` | `#C5C9D2` | 计数为 0 的数字 |
| `background` / `card` | `#FFFFFF` | 页面与卡片(同色,靠线与阴影分) |
| `nav` | `#FBFCFE` | 左侧导航底 |
| `subtle` | `#F6F8FB` | 输入框填充、次级填充块 |
| `muted` | `#F4F6F9` | 分段控件轨道、静态徽标底、disabled 按钮底 |
| `hover` | `#F1F3F8` | 导航项 hover |

### 线

| Token | 值 | 用途 |
| --- | --- | --- |
| `border-strong` | `#E8EAF0` | 描边控件(次按钮、下拉) |
| `border` | `#EEF0F4` | 结构分隔:侧栏、顶栏、卡片外框 |
| `border-soft` | `#F2F4F7` | 卡片内部分隔 |

### 选中 / 聚焦

| Token | 值 | 用途 |
| --- | --- | --- |
| `selected` / `selected-border` | `#F3F7FE` / `#DCE5F5` | 键盘选中的列表行 |
| `selected-mark` | `#AABDE2` | 选中行的复选框描边 |
| `checkbox-border` | `#DDE1E8` | 未选中的复选框描边 |
| `ring` | `#B9C6DE` | 输入框聚焦边框 |
| `--shadow-focus` | `0 0 0 4px rgb(28 100 242 / .08)` | 输入框聚焦外圈 |

键盘焦点的全局兜底是 `outline: 2px solid var(--primary)`;填充式输入框自己画上面那对聚焦样式。

### 状态(每个状态一对:前景 + 浅底)

| 状态 | 前景 / 浅底 | 用途 |
| --- | --- | --- |
| success | `#1F7A33` / `#EAF6EC` | 通过、完成、置信度 ≥ 0.90;状态点 `#34A853`,时间轴连接线 `#E4EDE5` |
| warning | `#8A5A00` / `#FFF4D6` | 待人工处理、置信度 0.75–0.89 |
| danger | `#B3330E` / `#FDEEE8` | 失败、驳回、置信度 < 0.75;危险按钮字色 `#C4320A`,边 `#F0DDD6`(hover `#FDF4F1` / `#E4B4A5`) |
| info | `#1C64F2` / `#EDF2FB` | 链接、信息态 |

**三类知识的固定识别色**(全站一致:导航点、KB 卡片、引用标记):
精准 QA = `#FFCB02`、文档 RAG = `#5B8DEF`、智能问数 = `#A78BFA`。

### 字体与字阶

| 用途 | 字体栈 |
| --- | --- |
| 页标题 / 品牌字 | `Montserrat, system-ui, sans-serif`,700 |
| 正文 / 控件 | `Inter, -apple-system, system-ui, sans-serif` |
| **所有数字** / 代码 / SQL / kbd | `'JetBrains Mono', ui-monospace, monospace`(400 与 500) |

字阶(全部 Inter,除标注):

| 尺寸 | 用途 |
| --- | --- |
| 19 / 700 Montserrat / `-.01em` | 页标题 |
| 14.5 / 500 | 主输入(标准问) |
| 14 / 400 | 正文、答案输入、主按钮文字 |
| 13.5 / 500(激活 600) | 导航项、列表主行 |
| 13 / 600 | 区块标题、阶段名、分段控件文字 |
| 12.5 / 600 | 字段标签、次级导航、描边控件文字 |
| 11.5 / 400 | helper、列表副行、meta |
| 11 / 500 | micro、计数 |
| mono 10.5–12 | job type、耗时、置信度、kbd、build stamp |
| mono 24 / 30,500,`-.03em` | 百分比、统计大数 |

**不用 24px 以上的 sans 字号**(工作台不是营销页);超过 20px 的只有等宽大数字。

### 圆角 / 阴影 / 间距 / 动效

| Token | 值 |
| --- | --- |
| 圆角 | 按钮/徽标/分段控件 `999px`;输入 `12px`(`--radius`);列表行 `13px`;导航项 `10px` / 子项 `9px`;卡片 `18px`(`--radius-card`)、面板块 `16px`;kbd `5px` |
| 阴影 | `xs 0 1px 3px rgb(17 19 24/.07)`(侧栏激活子项)· `card 0 2px 16px rgb(17 19 24/.04)` · `row 0 2px 10px rgb(28 100 242/.08)`(选中行)· `pill 0 2px 8px rgb(17 24 39/.18)`(深色 Tab)· `cta 0 4px 14px rgb(0 32 91/.22)` → hover `0 6px 18px rgb(0 32 91/.28)` · `pop 0 8px 24px rgb(17 19 24/.10)`(弹层) |
| 间距 | 4px 基数;卡片内距 26–28px;字段间距 24px;区块间 20–24px;内容最大宽 680px |
| 尺寸 | 侧栏 224 · 顶栏 64 · 右面板 320 · 审核列表列 376(视口 < 1400 时收到 322,给详情卡留出放下三个动作的宽度)· 导航项 38 / 子项 32 · 分段控件 32 · 描边控件 34–36 · 主按钮 42 · 徽标 22–24 |
| 动效 | `all 150ms ease`,仅此一档 |

## 3. 布局与核心组件规则

### 三栏布局

- **左侧导航:浅底 `#FBFCFE` + `#EEF0F4` 右边框**,宽 224px;logo 区 64px(黄点 + `KNOWLEDGE`,
  Montserrat 700 13.5px `.12em`);导航项 38px / 圆角 10px / 13.5px;
  **激活项 = `#EDF2FB` 底 + navy 600,没有黄色竖条**;二级项 32px / 圆角 9px,
  激活 = 白底 + `xs` 阴影;底部 build stamp 用 mono 10.5px `#B4B9C4`
- 顶栏:白底,高 64px,下边框 `#EEF0F4`;左边页标题(19/700),右边全局动作用 34px 描边 pill
- **页面上下文行**:需要交代"这一屏在看谁"时(审核台的 job、知识域的身份),
  在标题正下方起一行 —— mono job type / 识别色点 + 状态徽标 + 一句 13px `faint` 描述。
  它与顶栏标题在同一条视觉轴上,但**不并进顶栏**:顶栏是全站外壳,页面不该往里塞内容
- 中间内容区:白底,内距 24/28
- 右侧面板:320px,`#EEF0F4` 左边框,标题行 64px 与顶栏齐平

### 按钮

| 类型 | 样式 |
| --- | --- |
| 主按钮(每屏至多一个) | navy 实心 pill,白字 14/600,高 42,带 `cta` 阴影;hover → `primary-hover` + `cta-hover` |
| 次按钮 | 白底 + `border-strong` 描边 pill,12.5–14/500 `secondary-foreground`;hover 底 `subtle` |
| 危险 | 白底 + `#F0DDD6` 描边 pill + `#C4320A` 字;hover 底 `#FDF4F1`、边 `#E4B4A5` |
| disabled | `muted` 底 + `fainter` 字,无阴影,`cursor:not-allowed` |
| 强调 CTA | **不再有黄色按钮**;需要"看这里"的地方用 navy 主按钮 |

### 工作台组件

- **对话气泡**:用户消息 navy 底白字右对齐(最宽 75%);助手消息是 `subtle` 填充块左对齐
  (最宽 85%),命中精准问答时左侧加 3px 黄色识别条;点中某条看 trace 时套用选中行那套
  (`selected` 底 + `selected-border` 边 + `row` 阴影)
- **引用**:一条一行,不是 pill —— 知识类型识别色圆点 + mono `[n]` + 一行截断的标题 +
  右侧 mono 分数;展开的原文摘录放进 `subtle` 圆角块
- **trace / 任务进度**:竖线时间轴 —— 22px 圆形状态点(成功 `#EAF6EC` 底 + `#34A853` 勾)+
  `#E4EDE5` 连接线;阶段名 13/600,耗时 mono 11px 右对齐;头部是渐变进度卡
  (`linear-gradient(135deg,#EDF3FE,#F6FAFF)`,mono 24px 百分比 + 6px 进度条)
- **审核台**:列表行圆角 13px、内距 10/14、间隔 6px;主行(问题)13.5/500,副行 11.5 `faint` 单行省略;
  **选中 = `selected` 底 + `selected-border` 边 + `row` 阴影 + 问题转 600 navy**,没有左竖条;
  置信度是 mono 11px 的双色 pill(≥0.90 绿 / 0.75–0.89 黄 / <0.75 红)
- **分段控件(Tab)**:`muted` 轨道 pill,内距 4;激活项 = `dark` 实心 pill + 白字 + `pill` 阴影;
  计数用 mono 11px(激活态 `rgba(255,255,255,.65)`,为 0 时 `ghost`)
- **空状态**:一个线性图标 + 一句话 + 一个按钮,不放插画
- **kbd 片**:mono 10.5px,`#FAFBFC` 底 + `#EBEDF2` 边 + 5px 圆角

### 表格与表单

- 表格:表头不用灰底,改 11/600 `muted-foreground` 小标签;行 hover `subtle`,分隔线 `border-soft`,不用斑马纹
- 表单:label 在上(12.5/600 `foreground`);**输入框是填充块** —— `subtle` 底、透明边、12px 圆角、
  单行输入高 36 / 横向内距 16,多行内距 13/16;聚焦 → 白底 + `ring` 边 + `--shadow-focus` 外圈;
  helper 11.5 `faint` 在下方
- Markdown 正文(解析预览、文档内容):13.5/1.75,标题走 Montserrat 四档,
  行内代码 `subtle` 底 + 5px 圆角,表格套一层 `border` 细边圆角容器并在容器内横向滚动

## 4. 明确不做(Don't)

- ❌ 渐变(进度卡那一处除外)、玻璃拟态、暗色模式、插画
- ❌ 黄色实心按钮、黄底白字、大面积黄色区块
- ❌ 深色侧栏、页面级灰底、导航上的黄色竖条(都是旧版做法)
- ❌ 用 Inter 排数字(置信度/耗时/百分比/计数一律 mono)
- ❌ 多于五档的阴影、多于一档的过渡时长、弹跳动画
- ❌ emoji 当图标(统一 lucide-react,`strokeWidth` 1.75,尺寸 13–17)
- ❌ 每屏多个 navy 实心按钮

## 5. 落地方式

1. token 全部写进 `web/src/index.css`,组件内禁止出现裸色值(hex 只允许出现在第 1 层)
2. shadcn/ui 的默认变量已按本文档覆盖(`--primary` → navy 等),组件只认语义变量那一层
3. 字体用 fontsource 本地引入,不走 CDN:Montserrat 600/700、Inter 400/500/600、
   JetBrains Mono 400/500
4. `/styleguide` 隐藏路由页平铺全部 token 与组件态,作为验收对照

**两处实现说明**(不改上面的规范,只说明它长什么样):

- **Tailwind v4 没有 `tailwind.config.js`**:v4 用 CSS 里的 `@theme` 取代 v3 的 `theme.extend`,
  所以第 1 条说的"CSS 变量 + theme.extend"在仓库里是同一个文件 `web/src/index.css`。
  文件内分三层:品牌原色(唯一 hex 出处)→ 语义变量(shadcn 命名)→ `@theme inline` 暴露工具类
- **命名冲突**:Tailwind 从 `--color-primary` 生成的类叫 `text-primary`(主色文字),
  与 §2 表格里"正文色"撞名。落地时正文色叫 `--foreground`(`text-foreground`),
  `text-primary` 保留给"navy 文字"
