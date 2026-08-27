/**
 * How It Works 说明页的**文案唯一出处**。
 *
 * 体裁纪律(2026-08-26 需求方定,取代 08-24 的「投屏讲稿」定位):**自读优先** ——
 * 一个没时间的人自己点开,前三屏拿到全部精髓;折叠区标题 + 结论句摘要本身就是目录。
 * 投屏讲解场景靠折叠组的 Expand all 一键还原全展开。仍然一律关键词/短语,
 * 句子只留每层一句主角句与每屏一句强调句。
 * 其余纪律见 documents/HOW-IT-WORKS-PLAN.md §6:
 * - 页面组件里不写死任何句子,一律从这里取。
 * - 全篇不出现表名、字段名、函数名、接口路径、阈值数字(G2)。
 * - `**...**` 是唯一行内强调标记,由 Section.tsx 的 <Emphasized> 解析。
 *
 * v2(2026-08-26):加了架构段(STACK / SHELL_CORE / REQUEST_PATH / JOURNEY /
 * EVALUATION / AUTONOMY)与四条立场(PRINCIPLES);每层子页各加两条流程
 * (curation / runtime)。ANSWER_FLOW 与 ROLES 被 REQUEST_PATH 与 JOURNEY 取代,已删。
 * v2.1(同日):架构段一度是独立子页,现已并回总页(一页讲完,不再跳转)。
 * v3(同日):自读优先重排——漏斗每层加例句(FUNNEL.layers[].example)、
 * 五个折叠摘要改结论句、ARCHITECTURE.lede 改写;锚点条在 OverviewPage 删除。
 * v4(2026-08-27):图先于字。新增全局图数据 `SYSTEM_MAP`(两个时钟 + 知识中枢 +
 * 回边 + 留痕);`FUNNEL` 加 title/summary(升为独立一屏)、`LAYERS[].freedom`
 * (三层卡片的自由度计量条)、`JOURNEY.stages[].phase` + `phaseLabels`(闭环分两行)、
 * `STACK.tiers[].seam` + `seamLabel` + `axis`、`EVALUATION.axis`。
 * v5(2026-08-27,需求方纠正 + 补第四种知识):
 * 1. **层级关系改对了**:精准问答 / 智能问数 / **编排(workflow)** 三者**同级** ——
 *    都事先注册意图,回答时一次意图匹配、谁命中谁执行;文档 RAG 不是第三级台阶,
 *    而是**没有任何意图命中时**的兜底。旧的四级倒漏斗 `FUNNEL` 已被 `ROUTING` 取代。
 * 2. **补上第四种知识**:`WORKFLOW`(它是什么 / 四种节点 / 四条纪律 / 已设计未落地)
 *    + `WORKFLOW_EXAMPLE`(客服邮件那条链,逐节点 input / output / 参数绑定)
 *    + `WORKFLOW_CARD`(总页第四张卡,链到自己的子页 `/how-it-works/workflow`)。
 * 3. 连带改口径的地方:`SYSTEM_MAP`(回答期那步 + 知识中枢多一块)、`CLAIM.corollaries` R3、
 *    `REQUEST_PATH`(第 2 步一步三出口)、`COMPARISON`(四列,顺序 = 三家同级 + 兜底)、
 *    `STACK`、`AUTONOMY`、`EVALUATION`、`PAIN_POINTS`、`GATE`。
 */

export type LayerSlug = 'exact-qa' | 'document' | 'text2sql'

export interface LayerCard {
  slug: LayerSlug
  name: string
  /** 识别色工具类(bg-kb-*,不 import domains) */
  dotClass: string
  /** 屏 3 用的关键词定位 */
  positioning: string
  /** 这一层唯一的完整句子:主角句 */
  leadLine: string
  /** 模型自由度 1–3(三层卡片上的三格计量条;与漏斗的 model freedom ↑ 同一口径) */
  freedom: 1 | 2 | 3
}

export const LAYERS: LayerCard[] = [
  {
    slug: 'exact-qa',
    name: 'Exact Q&A',
    dotClass: 'bg-kb-exact-qa',
    positioning: 'one right answer · zero tolerance for drift',
    leadLine:
      "On a confident match we return the human-approved answer **verbatim** — the model doesn't get to rewrite a single word.",
    freedom: 1,
  },
  {
    slug: 'text2sql',
    name: 'Text-to-SQL',
    dotClass: 'bg-kb-text2sql',
    positioning: 'numbers from the database · only inside signed definitions',
    leadLine:
      "At answer time we **don't write SQL** — we match a definition the business already signed off on and fill in its parameters under constraints.",
    freedom: 2,
  },
  {
    slug: 'document',
    name: 'Document RAG',
    dotClass: 'bg-kb-document',
    positioning: 'long-form material · useful & sourced, not exact',
    leadLine:
      'This layer promises **useful and sourced**, not exact — citations are mandatory, and "no basis found" is a valid answer.',
    freedom: 3,
  },
]

export const FREEDOM_LABEL = 'model freedom'

/** 总页卡片区的顺序:两家意图层 → 编排(第四种,同级)→ 文档兜底。
 *  与 ROUTING / COMPARISON 一个口径;`'workflow'` 那张卡的数据在 `WORKFLOW_CARD`。 */
export const KIND_CARD_ORDER: (LayerSlug | 'workflow')[] = [
  'exact-qa',
  'text2sql',
  'workflow',
  'document',
]

/* ───────────────────────── 总页 · 主张与三条推论 ───────────────────────── */

export const CLAIM = {
  headline: "Enterprise agents shouldn't improvise.",
  lede: 'Move the thinking forward: **answer time → curation time**.',
  corollaries: [
    {
      title: 'Decide up front',
      points: [
        'answers & definitions accepted in advance',
        'runtime = match + fill in blanks',
        'controllable · reproducible · attributable',
      ],
    },
    {
      title: 'Business owns the knowledge',
      points: [
        'AI proposes → human approves',
        'nothing unsigned reaches search',
        'every answer has an owner',
      ],
    },
    {
      title: 'RAG is the fallback',
      points: [
        'signed intents first: answers · numbers · workflows',
        'documents only when nothing matched',
        'then an honest "no basis"',
      ],
    },
  ],
  emphasis: 'The hierarchy **is** the design.',
}

/* ───────────────────────── 总页 · 一张全局图 ─────────────────────────
 * 冷读者第一眼要看到的东西:两个时钟(治理期 / 回答期)共用一份已签字的知识,
 * 中间是人审闸门,底下是全程留痕。CLAIM.lede 那句 answer time → curation time
 * 就是这张图。 */

export interface MapStep {
  name: string
  note: string
  /** 人审闸门(黄色识别条,全页黄色只有这一种含义) */
  gate?: boolean
}

export const SYSTEM_MAP = {
  title: 'The whole system, one picture',
  summary: 'two clocks, one signed knowledge base',
  lanes: [
    {
      key: 'curation',
      label: 'Curation time',
      who: 'Business & knowledge owners',
      verb: 'publishes',
      steps: [
        { name: 'Raw material', note: 'handbooks · FAQ exports · a database' },
        { name: 'AI proposes candidates', note: 'drafts — not knowledge yet' },
        {
          name: 'A human accepts, edits or rejects',
          note: 'judgement, not data entry',
          gate: true,
        },
      ] as MapStep[],
    },
    {
      key: 'answer',
      label: 'Answer time',
      who: 'End user · the agent',
      verb: 'reads only what is approved',
      steps: [
        { name: 'A question in plain words', note: 'no mode picker, no tool menu' },
        {
          name: 'Intent match, then fallback',
          note: 'signed intents are peers — documents only if nothing matched',
        },
        { name: 'Answer + sources + trace', note: 'or an honest “no basis found”' },
      ] as MapStep[],
    },
  ],
  hubLabel: 'Approved knowledge',
  hubNote: 'nothing unsigned is searchable',
  hubBlocks: [
    'Approved Q&A pairs',
    'Signed metric definitions',
    'Published workflows',
    'Reviewed passages',
  ],
  returnNote:
    'Coverage gaps and flagged answers re-enter curation at step 01 — the queue is the product.',
  traceLabel: 'Traced end to end',
  traceNote: 'which stage ran · latency · tokens & cost · what was retrieved · why it stopped',
}

/* ───────────────────────── 总页 · 路由的两级结构 ─────────────────────────
 * 2026-08-27 需求方纠正:精准问答 / 智能问数 / 编排三者是**同级**的 —— 它们都事先注册
 * 了自己的意图,回答时先做一次意图匹配、谁命中谁执行;文档 RAG 不是第三级台阶,
 * 而是**没有任何意图命中**时的兜底。旧的四级倒漏斗(FUNNEL)把三家画成了台阶,已删。 */

export interface RoutingIntent {
  label: string
  note: string
  example: string
  dotClass: string
}

export const ROUTING = {
  title: 'One intent check — then, and only then, a fallback',
  summary: 'three signed registries are peers; documents run when nothing matched',
  questionLabel: 'A question in plain words',
  questionNote: 'no mode picker, no tool menu — routing is never the user’s job',
  intentLabel: 'Registered intents · peers, not rungs',
  intentNote: 'every intent here was written, approved and owned before anyone asked',
  intents: [
    {
      label: 'Exact Q&A',
      note: 'one approved answer, returned verbatim',
      example: '“How many days of annual leave do I get?”',
      dotClass: 'bg-kb-exact-qa',
    },
    {
      label: 'Text-to-SQL',
      note: 'a signed definition, parameters filled',
      example: '“What was revenue by region last quarter?”',
      dotClass: 'bg-kb-text2sql',
    },
    {
      label: 'Workflows',
      note: 'a signed sequence of steps, executed',
      example: '“Where is my order? It’s late.”',
      dotClass: 'bg-kb-workflow',
    },
  ] as RoutingIntent[],
  peerNote:
    'Between peers the order is a tie-break, not a hierarchy: the more specific commitment wins, so a workflow beats a bare answer when both match.',
  missLabel: 'no intent matched confidently',
  fallbackLabel: 'Fallback · open retrieval',
  fallback: {
    label: 'Document RAG',
    note: 'summarised · citations mandatory · abstains on thin evidence',
    example: '“Walk me through the incident process.”',
    dotClass: 'bg-kb-document',
  } as RoutingIntent,
  lastLabel: 'And if that finds nothing',
  last: {
    label: 'No basis',
    note: 'say so → the question becomes curation work',
    example: '“Anything nobody has approved yet.”',
    dotClass: 'bg-fainter',
  } as RoutingIntent,
  axes: ['tier 1 = decided in advance', 'fallback = decided on the spot', 'model freedom ↑'],
}

/* ───────────────────────── 总页 · 四条立场 ─────────────────────────
 * 这四条是整套架构的论证起点(面试里最值钱的四句),下面每张图都是它们的落地。 */

export const PRINCIPLES = {
  title: 'Four positions we argue from',
  items: [
    {
      line: 'Agentic where necessary, deterministic where possible.',
      here: 'One bounded turn, a fixed retrieval order — autonomy is spent only where it buys something.',
    },
    {
      line: "The model is probabilistic; the system around it isn't.",
      here: 'Allow-lists, gates and refusal paths live in code — outside the prompt, where they can be tested.',
    },
    {
      line: 'Autonomy scales with consequence, not with capability.',
      here: 'Read and summarise: wide latitude. Write and execute: never the model’s call.',
    },
    {
      line: 'Correctness is not safety.',
      here: 'An answer with no source — or a number from outside a signed definition — fails even when it happens to be right.',
    },
  ],
}

/* ───────────────────────── 总页 · 通用 RAG 的痛点 ───────────────────────── */

export const PAIN_POINTS = {
  title: "Why generic RAG isn't enough",
  summary: '8 familiar failures → 8 design answers',
  rows: [
    { symptom: 'Answers everything, trust nothing', answer: '3 layers, split by error tolerance' },
    { symptom: 'Same question, two answers', answer: 'decided once, at curation time' },
    { symptom: 'Wrong & right look equally official', answer: 'human review gates publishing' },
    { symptom: 'One metric, two numbers', answer: 'one signed definition, nowhere else to live' },
    { symptom: 'Data questions never right', answer: 'governed semantic layer, not prose' },
    { symptom: "Wrong — but where's the fix?", answer: 'every answer carries its trace + sources' },
    { symptom: 'Empty retrieval → starts writing', answer: 'no basis → say so, loudly' },
    {
      symptom: 'Answered — but the task isn’t done',
      answer: 'workflows: a signed sequence, not more chat',
    },
  ],
}

/* ───────────────────────── 总页 · 三层与共同的闸门 ───────────────────────── */

export const GATE = {
  title: 'Four kinds of knowledge, one gate',
  summary: 'nothing unsigned ever reaches search — or gets orchestrated',
  steps: [
    {
      name: 'Raw material',
      keywords: 'FAQ exports · handbooks · a database · a process someone knows by heart',
    },
    { name: 'AI proposes', keywords: 'drafts candidates — not knowledge yet' },
    { name: 'Business approves', keywords: 'accept / edit / reject — the gate' },
    { name: 'Published', keywords: 'only signed-off content is searchable — or referenceable' },
  ],
  emphasis: 'Human-in-the-loop is **the design**, not a patch.',
}

/* ───────────────────────── 总页 · 三层横向对比 ───────────────────────── */

export const COMPARISON = {
  title: 'The four kinds side by side',
  summary: 'three peers, one fallback — accuracy · ownership · freedom · risk',
  columns: ['Exact Q&A', 'Text-to-SQL', 'Workflows', 'Document RAG'],
  /** 表头色点(顺序与 columns 一致;不再按下标去 LAYERS 里取,那会错位) */
  dots: ['bg-kb-exact-qa', 'bg-kb-text2sql', 'bg-kb-workflow', 'bg-kb-document'],
  rows: [
    {
      dimension: 'When it runs',
      cells: [
        'a registered intent matched',
        'a registered intent matched',
        'a registered intent matched',
        'only when nothing matched',
      ],
    },
    {
      dimension: 'Required accuracy',
      cells: [
        'exact, word for word',
        'exact, within definitions',
        'exact per step — the sequence is the promise',
        'useful + honestly sourced',
      ],
    },
    {
      dimension: 'Who defines it',
      cells: [
        'subject owners',
        'data owner + business owner',
        'the process owner, composing signed knowledge',
        'the document itself',
      ],
    },
    {
      dimension: 'Model may…',
      cells: [
        'match → return verbatim',
        'fill parameters, within limits',
        'read the situation, bind parameters, draft wording',
        'summarise, cite everything',
      ],
    },
    {
      dimension: 'Main risk',
      cells: [
        'coverage gaps',
        'right-looking, wrong-meaning query',
        'a step standing on knowledge nobody signed',
        'confident prose, weak basis',
      ],
    },
    {
      dimension: 'Contained by',
      cells: [
        'unanswered → review queue',
        'no free-form SQL · loud refusal',
        'published references only · actions need a human',
        'mandatory citations · abstain',
      ],
    },
  ],
}

/* ───────────────────────── 总页 · 刻意不做的事 ───────────────────────── */

export const TRADEOFFS = {
  title: "What we deliberately don't do",
  summary: 'five costs, chosen knowingly',
  items: [
    { what: 'Coverage costs people', why: 'narrow & trusted > wide & unreliable' },
    { what: 'Cold start is slow', why: 'real questions fill the loop — expected' },
    { what: 'Long tail needs an owner', why: 'unanswered = review queue, not a bug' },
    { what: 'The agent takes no actions', why: 'wrong action ≫ wrong sentence' },
    { what: 'Not built for scale-out', why: 'a design demo, not a load test' },
  ],
}

export const LAYER_CARDS_TITLE = 'The four kinds of knowledge'

/* ═════════════════════════ 总页 · 架构段(六小节常驻) ═════════════════════════ */

export const ARCHITECTURE = {
  title: 'Architecture',
  lede: 'The positions we argue from — and the structure they produce.',
}

/* ── 架构段 1:分层技术架构(自上而下 = 面向用户 → 面向供应商) ── */

export interface StackTier {
  name: string
  owner: string
  blocks: string[]
  /** 这一层之上是供应商接缝(图里画一条虚线 + 说明) */
  seam?: boolean
}

export const STACK = {
  title: 'The stack, tier by tier',
  summary: 'six tiers — the control plane is the one most demos skip',
  tiers: [
    {
      name: 'Surfaces',
      owner: 'everyone who touches the system',
      blocks: ['Chat workbench', 'Curation console', 'Review queue', 'Execution trace panel'],
    },
    {
      name: 'Agent runtime',
      owner: 'AI / platform team',
      blocks: [
        'Intent match across registries',
        'Exact match',
        'Definition match + constrained rewrite',
        'Workflow execution',
        'Hybrid retrieval + rerank (fallback)',
        'Answer composition & citation',
      ],
    },
    {
      name: 'Control plane',
      owner: 'AI / platform team · risk',
      blocks: [
        'Human approval gate',
        'Publish & retire lifecycle',
        'Read-only execution gate',
        'Action gate — prepared, never auto-sent',
        'Citation enforcement',
        'Refusal paths',
        'Trace & audit trail',
      ],
    },
    {
      name: 'Knowledge plane',
      owner: 'business & knowledge owners',
      blocks: [
        'Approved Q&A pairs',
        'Signed metric definitions',
        'Published workflows',
        'Reviewed passages',
        'Retired content',
      ],
    },
    {
      name: 'Data & integration',
      owner: 'IT · data owners',
      blocks: [
        'Uploaded source material',
        'Vector index',
        'Business database (read-only)',
        'File storage',
      ],
    },
    {
      name: 'Model foundation',
      owner: 'vendors — swappable behind one seam',
      blocks: ['Reasoning model', 'Light model', 'Embeddings', 'Reranker', 'Document parser'],
      seam: true,
    },
  ] as StackTier[],
  seamLabel: 'Provider seam — swap a vendor here and no tier above notices',
  axis: ['top = what people touch', 'bottom = what we buy'],
  emphasis: 'Knowledge is **a tier**, not a folder — it has owners, a lifecycle and a gate.',
  notes: [
    'Every tier only knows the one below it. Models sit behind a single provider seam, so changing vendor never reaches the runtime.',
    'The control plane is the tier most demos skip. It is the reason this one can be audited.',
  ],
}

/* ── 架构段 2:确定性外壳 + 有限自主内核 ── */

export const SHELL_CORE = {
  title: 'Deterministic shell, agentic core',
  summary: 'the model reasons — the system decides what it may touch',
  shellLabel: 'Deterministic shell · written in code, testable, outside the prompt',
  coreLabel: 'Agentic core · where the model is genuinely allowed to think',
  shell: [
    'fixed retrieval order',
    'allow-listed knowledge only',
    'no free-form SQL · read-only · bounded',
    'cite or abstain',
    'one bounded turn, no open-ended loops',
    'no side-effecting actions',
    'every stage traced: latency · tokens · cost',
  ],
  core: [
    'read the question in the user’s own words',
    'judge “is this the same question?”',
    'fill the parameters of a signed definition',
    'summarise evidence that was actually retrieved',
    'say when there is no basis',
  ],
  emphasis: "The model is probabilistic. The system around it doesn't have to be.",
}

/* ── 架构段 3:一次请求的全链路 ── */

export interface RequestExit {
  /** 出口标签(哪一家意图命中) */
  label: string
  text: string
  tone: 'exact' | 'text2sql' | 'workflow'
}

export interface RequestStep {
  name: string
  who: string
  detail: string
  /** 单一出口 */
  hit?: string
  /** 多出口(意图匹配那一步:三家同级,谁命中谁执行) */
  exits?: RequestExit[]
  miss?: string
  tone: 'neutral' | 'intent' | 'document' | 'none'
}

export const REQUEST_PATH = {
  title: 'One request, end to end',
  summary: 'match an intent → else fall back to documents → compose → trace',
  steps: [
    {
      name: 'Question arrives',
      who: 'system',
      detail: 'plain words · no mode picker, no tool menu — routing is not the user’s job',
      tone: 'neutral' as const,
    },
    {
      name: 'One pass over every signed intent',
      who: 'model judges the match · code enforces the gate',
      detail:
        'the question is compared with everything the business has registered — approved questions, published definitions, published workflows. The most specific confident match wins; the other two never run.',
      exits: [
        {
          label: 'Exact Q&A',
          text: 'approved answer returned **verbatim**, marked verified',
          tone: 'exact' as const,
        },
        {
          label: 'Text-to-SQL',
          text: 'the number **plus the exact query** that produced it',
          tone: 'text2sql' as const,
        },
        {
          label: 'Workflow',
          text: 'the signed sequence runs — **every node traced**, actions left for a human',
          tone: 'workflow' as const,
        },
      ],
      miss: 'nothing matched confidently · the question is logged as a coverage gap',
      tone: 'intent' as const,
    },
    {
      name: 'Fallback: the documents',
      who: 'model summarises · code checks the evidence',
      detail: 'meaning + keyword retrieval, reranked, evidence assembled',
      hit: 'summary where every claim carries an openable source',
      miss: 'thin evidence is not padded with fluency',
      tone: 'document' as const,
    },
    {
      name: 'Otherwise: nothing',
      who: 'system',
      detail: '“no basis found” is a first-class outcome, not a failure state',
      hit: 'the question joins the curation queue',
      tone: 'none' as const,
    },
  ] as RequestStep[],
  tracedLabel: 'Recorded for every answer',
  traced: [
    'which stage ran, in what order',
    'latency per stage',
    'tokens & cost',
    'what was retrieved, and what was used',
    'why it stopped where it stopped',
  ],
  emphasis: 'Freedom is granted **per kind of knowledge**, never per request.',
}

/* ── 架构段 4:两个角色的闭环 ── */

export interface JourneyStage {
  who: 'ops' | 'user' | 'system'
  /** 闭环的两段:治理期 / 回答期(图里分两行,行内箭头相连) */
  phase: 'curation' | 'answer'
  name: string
  note: string
}

export const JOURNEY = {
  title: 'The loop people actually live in',
  summary: 'every gap and every flag flows back into the curation queue',
  legend: [
    { key: 'ops', label: 'Business / knowledge ops' },
    { key: 'user', label: 'End user' },
    { key: 'system', label: 'System' },
  ],
  phaseLabels: { curation: 'Curation time', answer: 'Answer time' },
  stages: [
    {
      who: 'ops' as const,
      phase: 'curation' as const,
      name: 'Bring raw material',
      note: 'handbooks · exports · a database',
    },
    {
      who: 'system' as const,
      phase: 'curation' as const,
      name: 'AI proposes',
      note: 'candidates — not knowledge yet',
    },
    {
      who: 'ops' as const,
      phase: 'curation' as const,
      name: 'Accept · edit · reject',
      note: 'judgement, not data entry',
    },
    {
      who: 'ops' as const,
      phase: 'curation' as const,
      name: 'Publish & own it',
      note: 'going live is an announcement',
    },
    {
      who: 'user' as const,
      phase: 'answer' as const,
      name: 'Ask in plain words',
      note: 'never picks a layer',
    },
    {
      who: 'system' as const,
      phase: 'answer' as const,
      name: 'Answer + sources + trace',
      note: 'or an honest “no basis”',
    },
    {
      who: 'user' as const,
      phase: 'answer' as const,
      name: 'Flag what’s wrong',
      note: 'goes back to a named owner',
    },
  ] as JourneyStage[],
  returnNote: 'Gaps and flags re-enter at step 01 — the queue is the product, not the backlog.',
  emphasis: 'What the business signs off on is **exactly** what end users receive.',
}

/* ── 架构段 5:四层评估 ── */

export const EVALUATION = {
  title: 'How we know it works',
  summary: 'four levels of checks, re-run on every prompt, model or retrieval change',
  axis: ['L1 cheap & deterministic', 'L4 judgement & production reality'],
  levels: [
    {
      level: 'Component',
      asks: 'Is each part right on its own?',
      checks: [
        'retrieval: does the right material come back at all',
        'matching: same question, or merely a similar one',
        'definitions: does a template mean what the business says it means',
        'structured output keeps its shape',
      ],
    },
    {
      level: 'Trajectory',
      asks: 'Did it get there the right way?',
      checks: [
        'right layer, right order',
        'a workflow ran the nodes it was published with — no improvised detours',
        'stopped at the first confident hit',
        'refused instead of improvising',
        'no retry loops, no wandering',
      ],
    },
    {
      level: 'End to end',
      asks: 'Did the business question actually get answered?',
      checks: [
        'a fixed question set per layer, re-run on every prompt / model / retrieval change',
        'numbers checked back against the source database',
        'unanswered questions counted, not hidden',
      ],
    },
    {
      level: 'Production & safety',
      asks: 'Is it still safe once real people use it?',
      checks: [
        'an answer without a source is a defect, however fluent',
        'refusal wording is a feature — reviewed like any other text',
        'traces make any answer reconstructable after the fact',
        'every real failure becomes a regression case',
      ],
    },
  ],
  emphasis:
    'Deterministic checks wherever the answer is checkable; judgement only where it genuinely isn’t.',
}

/* ── 架构段 6:自主性的边界 ── */

export const AUTONOMY = {
  title: 'Where autonomy stops',
  summary: 'read and summarise freely — write, execute, send: never',
  moreLabel: 'More latitude',
  lessLabel: 'Kept out of the model',
  more: [
    'read approved knowledge',
    'retrieve and rank evidence',
    'summarise, with citations',
    'fill parameters of a signed definition',
    'prepare an action for a human to approve',
    'recommend the next step',
  ],
  less: [
    'writing to any system of record',
    'issuing a query nobody approved',
    'sending anything outward',
    'changing what a business term means',
    'firing a workflow’s action step on its own',
    'publishing knowledge',
  ],
  emphasis:
    'Today the agent takes **no** actions at all — a deliberate choice, and the cheapest one to defend.',
}

/* ═════════════════ 第四种知识:编排(workflow) ═════════════════
 * 前三种知识各自回答一个问题,第四种把它们连起来把一件事做完。三条纪律:
 * 1. 它和精准问答 / 智能问数**同级** —— 也是事先注册意图,命中就执行(见 ROUTING)。
 * 2. 它**不产生新事实**:只能引用已发布的知识,引的是名字不是副本。
 * 3. 画布还没建 —— 文案必须说清「已设计、未落地」;动作节点仍守 AUTONOMY 那条线
 *    (准备好动作,人按下去)。
 * 它和三层一样有自己的子页 `/how-it-works/workflow`(`WorkflowPage`),总页第四张卡链到它。 */

export type WorkflowNodeKind = 'trigger' | 'llm' | 'knowledge' | 'compute' | 'action'

/** 节点类型的短标(图里的 mono 徽标) */
export const WORKFLOW_KIND_LABEL: Record<WorkflowNodeKind, string> = {
  trigger: 'trigger',
  llm: 'llm',
  knowledge: 'knowledge',
  compute: 'code',
  action: 'action',
}

/** 总页第四张卡(三层卡片旁边那张)。它链到本页锚点,不是子页 */
export const WORKFLOW_CARD = {
  name: 'Workflows',
  dotClass: 'bg-kb-workflow',
  positioning: 'many steps, one signed sequence · composes the other three',
  leadLine:
    'A workflow **calls the other three in an order the business signed** — plus code and actions — to finish a task instead of answering a sentence.',
  freedom: 2 as const,
  examples: ['late-order reply', 'refund pre-check', 'onboarding kickoff'],
  /** 编排有自己的子页(`/how-it-works/workflow`),和三层同级地挂在侧栏 */
  to: '/how-it-works/workflow',
  linkLabel: 'See it run',
  badge: 'designed, not built',
}

export const WORKFLOW = {
  title: 'Workflows: knowledge about order',
  lede: 'The other three kinds answer a question. A workflow **finishes a task** — by calling them in an order the business signed off on.',
  summary: 'composition, not new facts',
  builtFromLabel: 'What a workflow is made of',
  referencedLabel: 'Knowledge it may reference — all of it already approved',
  referencedBlocks: [
    { label: 'Approved Q&A pairs', dotClass: 'bg-kb-exact-qa' },
    { label: 'Signed metric definitions', dotClass: 'bg-kb-text2sql' },
    { label: 'Reviewed passages', dotClass: 'bg-kb-document' },
  ],
  referencedArrow: 'referenced by name, never copied',
  canvasLabel: 'One workflow = one signed sequence of nodes',
  builtFromNote:
    'It adds no new facts. It references knowledge that is already published — by name, never by copy — and adds the two things no handbook writes down: the order, and what to do with each result.',
  kinds: [
    {
      kind: 'knowledge' as WorkflowNodeKind,
      label: 'Knowledge node',
      note: 'calls one approved kind — an answer, a number, a passage',
    },
    {
      kind: 'llm' as WorkflowNodeKind,
      label: 'LLM node',
      note: 'judge · classify · write — where the wording is the deliverable',
    },
    {
      kind: 'compute' as WorkflowNodeKind,
      label: 'Code node',
      note: 'branches, thresholds, arithmetic — deterministic on purpose',
    },
    {
      kind: 'action' as WorkflowNodeKind,
      label: 'Action node',
      note: 'reach another system — log it, update a record, notify someone',
    },
  ],
  rules: [
    {
      head: 'Built on top, never beside',
      body: 'A workflow may only reference knowledge that is already approved and published. If a step needs knowledge nobody has signed, the workflow is blocked until someone curates it — orchestration cannot manufacture authority.',
    },
    {
      head: 'Parameters bind themselves',
      body: 'Each node declares what it needs; the model reads the steps before it and fills the blanks — an order number lifted out of an email, a delay in days returned by a query. Nobody wires fields by hand.',
    },
    {
      head: 'A workflow is an intent, too',
      body: 'It registers the questions it serves, exactly like the other two intent layers. Match one of them and the workflow runs instead of an answer being written — same tier, not a deeper one.',
    },
    {
      head: 'The gate does not move',
      body: 'Reading, deciding and drafting are free. Writing, sending, changing a record: the step is prepared and then a human presses the button — the same line as everywhere else here.',
    },
  ],
  statusLabel: 'Status',
  status:
    'Designed, not built. The three kinds a workflow composes are running today; the canvas that composes them is the next slice.',
}

export interface WorkflowStep {
  name: string
  kind: WorkflowNodeKind
  /** 知识节点引用的是哪一种知识(识别色 + 名字) */
  source?: { label: string; dotClass: string }
  input: string
  output: string
  /** 这一步产出、被后面步骤引用的参数(AI 自动认出来的东西) */
  binds?: string[]
  /** 人审闸门(黄色,全页同一含义) */
  gate?: boolean
  /** 一句设计注解 */
  note?: string
}

export const WORKFLOW_EXAMPLE = {
  title: 'One workflow, node by node',
  scenario: 'Support inbox · “where is my order — it’s late”',
  summary: 'eight nodes · three kinds of knowledge · one human gate',
  inLabel: 'in',
  outLabel: 'out',
  bindsLabel: 'binds',
  steps: [
    {
      name: 'An email lands in the support inbox',
      kind: 'trigger' as WorkflowNodeKind,
      input: 'the raw email — sender, subject, body',
      output: 'the message, verbatim, as the workflow’s starting material',
    },
    {
      name: 'Read the intent and the mood',
      kind: 'llm' as WorkflowNodeKind,
      input: 'the email body',
      output: 'intent: order status · mood: anxious, near escalating · order number: SO-10482',
      binds: ['order number', 'mood'],
      note: 'the model is used for judgement here, never for facts',
    },
    {
      name: 'Look that order up',
      kind: 'knowledge' as WorkflowNodeKind,
      source: { label: 'Text-to-SQL', dotClass: 'bg-kb-text2sql' },
      input: 'order number, bound from step 02',
      output: 'in transit · promised 12 Aug · now expected 19 Aug · 7 days late',
      binds: ['days late'],
      note: 'no free-form SQL — it fills the parameters of a definition the business signed',
    },
    {
      name: 'Which delay band is this?',
      kind: 'compute' as WorkflowNodeKind,
      input: '7 days late',
      output: 'band: 4–10 days',
      binds: ['band'],
      note: 'a threshold is a rule, not an opinion — so code decides, the same way every time',
    },
    {
      name: 'What are we allowed to offer for this band?',
      kind: 'knowledge' as WorkflowNodeKind,
      source: { label: 'Exact Q&A', dotClass: 'bg-kb-exact-qa' },
      input: 'band',
      output:
        'the approved handling, word for word: apologise, give the revised date, offer a goodwill credit — no discount, no re-ship',
      note: 'a promise to a customer is exactly the kind of sentence nobody may paraphrase',
    },
    {
      name: 'Which reply template belongs to this band?',
      kind: 'knowledge' as WorkflowNodeKind,
      source: { label: 'Exact Q&A', dotClass: 'bg-kb-exact-qa' },
      input: 'band',
      output: 'the approved template, with blanks: name · order · revised date · gesture',
    },
    {
      name: 'Write the reply',
      kind: 'llm' as WorkflowNodeKind,
      input: 'the template + the approved handling + the mood read in step 02',
      output: 'a draft that keeps every approved sentence and adapts only the tone',
      note: 'the freedom here is stylistic — every promise in the email came from an approved source',
    },
    {
      name: 'Log the enquiry · move the promised date',
      kind: 'action' as WorkflowNodeKind,
      gate: true,
      input: 'the draft + the order',
      output: 'reply sent, enquiry recorded, promised date updated — once a human presses send',
      note: 'the workflow prepares the action and stops there',
    },
  ] as WorkflowStep[],
  traceLabel: 'What the trace shows afterwards',
  traced: [
    'which node ran, in what order',
    'what each node read and returned',
    'which approved knowledge was quoted',
    'where the human stepped in',
  ],
  emphasis:
    'Seven of those eight nodes are worthless on their own: two approved answers, one signed definition, one deterministic rule did the work. **The workflow is the wiring — the knowledge underneath is still the product.**',
}

/* ═════════════════════════ 子页:每层一页 ═════════════════════════ */

export interface FlowStep {
  name: string
  note: string
  /** stop = 链路在这里终止(拒答/兜底),branch = 分岔 */
  kind?: 'go' | 'gate' | 'stop'
}

export interface LayerDetail {
  slug: LayerSlug
  title: string
  /** 主角句(页顶唯一完整句) */
  leadLine: string
  /** 真实问题示例(chips) */
  examples: string[]
  /** 治理期的流程图 */
  curation: { label: string; steps: FlowStep[] }
  /** 回答期的流程图 */
  runtime: { label: string; steps: FlowStep[] }
  /** 四张关键词卡:定位 / 为什么不能临场 / 前期定什么 / 业务在哪介入(重点) */
  cards: { heading: string; bullets: string[]; highlight?: boolean }[]
  /** 回答时:允许 / 不允许(两列) */
  answerTime: { may: string[]; mayNot: string[] }
  /** 刻意不做 */
  doesNot: string[]
}

export const FLOWS_HEADING = 'Two flows: what is settled before, what is left for later'
export const CURATION_LABEL = 'Curation time — where the thinking happens'
export const RUNTIME_LABEL = 'Answer time — what is left to decide'

export const LAYER_DETAILS: Record<LayerSlug, LayerDetail> = {
  'exact-qa': {
    slug: 'exact-qa',
    title: 'Exact Q&A',
    leadLine:
      "On a confident match we return the human-approved answer **verbatim** — the model doesn't get to rewrite a single word.",
    examples: ['leave entitlements', 'approval limits', 'which form starts X'],
    curation: {
      label: CURATION_LABEL,
      steps: [
        { name: 'Source uploaded', note: 'policy docs · FAQ exports' },
        { name: 'Parsed to text', note: 'layout, tables, figures' },
        { name: 'Proofread', note: 'a human fixes what the parser got wrong', kind: 'gate' },
        { name: 'Pairs proposed', note: 'AI drafts question + answer candidates' },
        { name: 'Accept · edit · reject', note: 'the gate — signing, not tidying', kind: 'gate' },
        { name: 'Published & indexed', note: 'alternative wordings indexed with it' },
      ],
    },
    runtime: {
      label: RUNTIME_LABEL,
      steps: [
        { name: 'Question', note: 'user’s own words' },
        { name: 'Closest approved questions', note: 'meaning-based retrieval' },
        { name: 'Same question?', note: 'a yes/no judgement, not a rewrite', kind: 'gate' },
        { name: 'Answer, verbatim', note: 'marked verified · chain stops', kind: 'stop' },
        { name: 'Not confident', note: 'hand down · logged as a coverage gap', kind: 'stop' },
      ],
    },
    cards: [
      {
        heading: 'What it’s for',
        bullets: [
          'asked hundreds of times a year',
          'exactly one right answer',
          'paraphrasing = already wrong',
        ],
      },
      {
        heading: "Why it can't be improvised",
        bullets: [
          'people **act** on these answers',
          '90% right = a liability with a friendly tone',
          'a fluent paraphrase hides the error',
        ],
      },
      {
        heading: 'Settled up front',
        bullets: [
          'the question as people really ask it',
          'the answer, in full, as shown',
          'alternative wordings',
          'an owner to go back to',
        ],
      },
      {
        heading: 'Where the business steps in',
        highlight: true,
        bullets: [
          'AI drafts pairs from what exists',
          'approving = **a commitment**: "this is what we tell people"',
          'accept ≠ publish — going live is an announcement',
        ],
      },
    ],
    answerTime: {
      may: ['decide "is this the same question?"', 'return the approved answer, as written'],
      mayNot: ['rewrite or shorten', 'merge two answers', 'soften a policy', 'add its own caveats'],
    },
    doesNot: [
      'no stretching near-misses',
      'no blending pairs into a third answer',
      'no personalisation',
      'no growing on its own — growth is a review queue',
    ],
  },

  document: {
    slug: 'document',
    title: 'Document RAG',
    leadLine:
      'This layer promises **useful and sourced**, not exact — citations are mandatory, and "no basis found" is a valid answer.',
    examples: ['incident process', 'warranty terms', 'technical manuals'],
    curation: {
      label: CURATION_LABEL,
      steps: [
        { name: 'Document uploaded', note: 'handbooks · manuals · terms' },
        { name: 'Parsed', note: 'layout, tables and figures preserved' },
        { name: 'Cleaned & split', note: 'passages that keep their place in the document' },
        { name: 'Figures described', note: 'a chart nobody can read retrieves nothing' },
        { name: 'Reviewed', note: 'what enters, what gets merged, what retires', kind: 'gate' },
        { name: 'Published as passages', note: 'searchable, each with its origin' },
      ],
    },
    runtime: {
      label: RUNTIME_LABEL,
      steps: [
        { name: 'Question', note: 'reached only if the layers above missed' },
        { name: 'Meaning + keyword retrieval', note: 'two recalls, not one' },
        { name: 'Reranked', note: 'ordering is a different job from finding' },
        { name: 'Enough evidence?', note: 'the honest question, asked in code', kind: 'gate' },
        {
          name: 'Summary + citations',
          note: 'every claim opens back to its passage',
          kind: 'stop',
        },
        { name: 'Thin evidence', note: '“no basis found” — not padded with fluency', kind: 'stop' },
      ],
    },
    cards: [
      {
        heading: 'What it’s for',
        bullets: [
          'too large to curate per-question',
          'a good summary + a pointer is the ask',
          'the fallback layer — by design',
        ],
      },
      {
        heading: "Why it can't be improvised",
        bullets: [
          'can’t approve answers one by one',
          'so the discipline moves: wording → **evidence**',
          '"where did this come from?" is always answerable',
        ],
      },
      {
        heading: 'Settled up front',
        bullets: [
          'how documents split into passages',
          'what each passage carries (its place in the doc)',
          'which collections serve which audience',
          'thin retrieval → abstain, not pad',
        ],
      },
      {
        heading: 'Where the business steps in',
        highlight: true,
        bullets: [
          'decides what **enters** — and what **retires**',
          'a stale handbook = an official-looking wrong answer',
          'checks the parse before publishing',
        ],
      },
    ],
    answerTime: {
      may: ['summarise across passages', 'reorganise and connect'],
      mayNot: [
        'assert without an openable source',
        'fill gaps from world knowledge',
        'pad thin evidence with fluency',
      ],
    },
    doesNot: [
      'no numbers — a figure in a slide is not the current number',
      'no exact-wording promises',
      'not the home of knowledge that deserves curation',
    ],
  },

  text2sql: {
    slug: 'text2sql',
    title: 'Text-to-SQL',
    leadLine:
      "At answer time we **don't write SQL** — we match a definition the business already signed off on and fill in its parameters under constraints.",
    examples: ['revenue by region', 'active customers', 'avg install time'],
    curation: {
      label: CURATION_LABEL,
      steps: [
        { name: 'Read-only connection', note: 'tested before it is stored', kind: 'gate' },
        { name: 'Schema synced', note: 'what exists — and what stays out of play' },
        { name: 'Tables & columns described', note: 'AI drafts, humans correct' },
        { name: 'Intents proposed', note: 'the questions this data can actually answer' },
        { name: 'Template + parameter ranges', note: 'one meaning per business term' },
        { name: 'Two signatures', note: 'data owner + business owner', kind: 'gate' },
        { name: 'Published', note: 'now quotable as the company’s definition' },
      ],
    },
    runtime: {
      label: RUNTIME_LABEL,
      steps: [
        { name: 'Question', note: 'phrased like a person, not like a report' },
        { name: 'Which published intent?', note: 'match, or nothing', kind: 'gate' },
        { name: 'No match', note: 'refuse with the reason — no generation at all', kind: 'stop' },
        { name: 'Parameters filled', note: 'dates, regions, limits — within bounds' },
        { name: 'Execution gate', note: 'read-only · time-bounded · row-bounded', kind: 'gate' },
        { name: 'Number + the exact query', note: 'shown, copyable, checkable', kind: 'stop' },
      ],
    },
    cards: [
      {
        heading: 'What it’s for',
        bullets: [
          'the answer is a number',
          'no document will ever hold it',
          'exact — inside accepted definitions',
        ],
      },
      {
        heading: "Why it can't be improvised",
        bullets: [
          'free-form SQL: most impressive, least trustworthy',
          '"active customer", interpreted three ways',
          'a wrong number is **actionable** — worse than a refusal',
        ],
      },
      {
        heading: 'Settled up front',
        bullets: [
          'which data is in play — and which is not',
          'one meaning per business term',
          'accepted question shapes + what may vary',
          'safe bounds on everything',
        ],
      },
      {
        heading: 'Where the business steps in',
        highlight: true,
        bullets: [
          '**two signatures, two questions**',
          'data owner: "is this where the number comes from?"',
          'business owner: "is this what the term means?"',
          'both accept → the company’s definition, quotable',
        ],
      },
    ],
    answerTime: {
      may: ['recognise which accepted question this is', 'fill its parameters, within limits'],
      mayNot: [
        'author a query',
        'widen a definition',
        'join in something extra',
        'invent an undefined metric',
      ],
    },
    doesNot: [
      'not an exploration tool',
      'never writes to the database — read-only is a boundary',
      'no reaching beyond definitions',
      'undefined metric → work for the business, not a guess',
    ],
  },
}

export const BACK_TO_OVERVIEW = 'Back to the overview'

/* ───────────────────────── 总页页脚 · 署名 ───────────────────────── */

export const AUTHORS = {
  label: 'Designed and built by',
  names: ['Yixing (Ethan) Zheng', 'Delai (Tony) Ye'],
  note: 'An interview demo — the design positions below are the point, not the feature count.',
}

/* ───────────────────────── 侧栏子项(AppLayout 消费) ─────────────────────────
 * 说明页在侧栏是个可展开分组,和 Knowledge Ingestion 一个形状。
 * 子项清单是**这里**的事,AppLayout 不硬编码任何一页。 */

export interface HowItWorksNavItem {
  to: string
  label: string
  /** 侧栏小圆点:三层用识别色,总页用中性线色 */
  dotClass: string
  /** 只在精确匹配时激活(总页需要,否则子页也会点亮它) */
  end?: boolean
}

export const HOW_IT_WORKS_NAV: HowItWorksNavItem[] = [
  { to: '/how-it-works', label: 'Overview', dotClass: 'bg-border-strong', end: true },
  // 顺序 = KIND_CARD_ORDER:两家意图层 → 编排 → 文档兜底,和页面里的层级一致
  ...KIND_CARD_ORDER.map((key) => {
    if (key === 'workflow') {
      return {
        to: WORKFLOW_CARD.to,
        label: WORKFLOW_CARD.name,
        dotClass: WORKFLOW_CARD.dotClass,
      }
    }
    const layer = LAYERS.find((l) => l.slug === key)!
    return { to: `/how-it-works/${layer.slug}`, label: layer.name, dotClass: layer.dotClass }
  }),
]
