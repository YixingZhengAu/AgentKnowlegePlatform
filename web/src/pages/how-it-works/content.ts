/**
 * How It Works 说明页的**文案唯一出处**。
 *
 * 体裁纪律(2026-08-24 需求方定):这是投屏讲稿,**不是文章** ——
 * 面试官不会逐句读,所以一律关键词/短语,句子只留每层一句主角句与每屏一句强调句。
 * 其余纪律见 documents/HOW-IT-WORKS-PLAN.md §6:
 * - 页面组件里不写死任何句子,一律从这里取。
 * - 全篇不出现表名、字段名、函数名、接口路径、阈值数字(G2)。
 * - `**...**` 是唯一行内强调标记,由 Section.tsx 的 <Emphasized> 解析。
 *
 * v2(2026-08-26):加了架构段(STACK / SHELL_CORE / REQUEST_PATH / JOURNEY /
 * EVALUATION / AUTONOMY)与四条立场(PRINCIPLES);每层子页各加两条流程
 * (curation / runtime)。ANSWER_FLOW 与 ROLES 被 REQUEST_PATH 与 JOURNEY 取代,已删。
 * v2.1(同日):架构段一度是独立子页,现已并回总页(一页讲完,不再跳转)。
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
}

export const LAYERS: LayerCard[] = [
  {
    slug: 'exact-qa',
    name: 'Exact Q&A',
    dotClass: 'bg-kb-exact-qa',
    positioning: 'one right answer · zero tolerance for drift',
    leadLine:
      "On a confident match we return the human-approved answer **verbatim** — the model doesn't get to rewrite a single word.",
  },
  {
    slug: 'document',
    name: 'Document RAG',
    dotClass: 'bg-kb-document',
    positioning: 'long-form material · useful & sourced, not exact',
    leadLine:
      'This layer promises **useful and sourced**, not exact — citations are mandatory, and "no basis found" is a valid answer.',
  },
  {
    slug: 'text2sql',
    name: 'Text-to-SQL',
    dotClass: 'bg-kb-text2sql',
    positioning: 'numbers from the database · only inside signed definitions',
    leadLine:
      "At answer time we **don't write SQL** — we match a definition the business already signed off on and fill in its parameters under constraints.",
  },
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
        'only for error-tolerant questions',
        'exact → text-to-sql → documents → "no basis"',
        'retrieval is ordered, not one index',
      ],
    },
  ],
  emphasis: 'The hierarchy **is** the design.',
}

export const FUNNEL = {
  layers: [
    { label: 'Exact Q&A', note: 'written & accepted in advance', dotClass: 'bg-kb-exact-qa' },
    {
      label: 'Text-to-SQL',
      note: 'signed definition + filled parameters',
      dotClass: 'bg-kb-text2sql',
    },
    { label: 'Document RAG', note: 'summarised · citations mandatory', dotClass: 'bg-kb-document' },
    { label: 'No basis', note: 'say so → becomes curation work', dotClass: 'bg-fainter' },
  ],
  axes: ['required accuracy ↓', 'human effort ↓', 'model freedom ↑'],
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
  summary: '7 familiar failures → 7 design answers',
  rows: [
    { symptom: 'Answers everything, trust nothing', answer: '3 layers, split by error tolerance' },
    { symptom: 'Same question, two answers', answer: 'decided once, at curation time' },
    { symptom: 'Wrong & right look equally official', answer: 'human review gates publishing' },
    { symptom: 'One metric, two numbers', answer: 'one signed definition, nowhere else to live' },
    { symptom: 'Data questions never right', answer: 'governed semantic layer, not prose' },
    { symptom: "Wrong — but where's the fix?", answer: 'every answer carries its trace + sources' },
    { symptom: 'Empty retrieval → starts writing', answer: 'no basis → say so, loudly' },
  ],
}

/* ───────────────────────── 总页 · 三层与共同的闸门 ───────────────────────── */

export const GATE = {
  title: 'Three layers, one gate',
  summary: 'raw material → AI proposes → business approves → published',
  steps: [
    { name: 'Raw material', keywords: 'FAQ exports · handbooks · database + docs' },
    { name: 'AI proposes', keywords: 'drafts candidates — not knowledge yet' },
    { name: 'Business approves', keywords: 'accept / edit / reject — the gate' },
    { name: 'Published', keywords: 'only signed-off content is searchable' },
  ],
  emphasis: 'Human-in-the-loop is **the design**, not a patch.',
}

/* ───────────────────────── 总页 · 三层横向对比 ───────────────────────── */

export const COMPARISON = {
  title: 'The three layers side by side',
  summary: 'accuracy · ownership · model freedom · risk',
  columns: ['Exact Q&A', 'Document RAG', 'Text-to-SQL'],
  rows: [
    {
      dimension: 'Required accuracy',
      cells: ['exact, word for word', 'useful + honestly sourced', 'exact, within definitions'],
    },
    {
      dimension: 'Who defines it',
      cells: ['subject owners', 'the document itself', 'data owner + business owner'],
    },
    {
      dimension: 'Model may…',
      cells: [
        'match → return verbatim',
        'summarise, cite everything',
        'fill parameters, within limits',
      ],
    },
    {
      dimension: 'Main risk',
      cells: ['coverage gaps', 'confident prose, weak basis', 'right-looking, wrong-meaning query'],
    },
    {
      dimension: 'Contained by',
      cells: [
        'unanswered → review queue',
        'mandatory citations · abstain',
        'no free-form SQL · loud refusal',
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

export const LAYER_CARDS_TITLE = 'The three layers'

/* ═════════════════════════ 总页 · 架构段(六小节常驻) ═════════════════════════ */

export const ARCHITECTURE = {
  title: 'Architecture',
  lede: 'Six tiers, one request path, one loop — and the controls that sit **outside** the model.',
}

/* ── 架构段 1:分层技术架构(自上而下 = 面向用户 → 面向供应商) ── */

export interface StackTier {
  name: string
  owner: string
  blocks: string[]
}

export const STACK = {
  title: 'The stack, tier by tier',
  summary: 'surfaces · runtime · control plane · knowledge · data · models',
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
        'Ordered routing',
        'Exact match',
        'Intent match + constrained rewrite',
        'Hybrid retrieval + rerank',
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
        'Reviewed passages',
        'Signed metric definitions',
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
    },
  ] as StackTier[],
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

export interface RequestStep {
  name: string
  who: string
  detail: string
  hit?: string
  miss?: string
  tone: 'neutral' | 'exact' | 'text2sql' | 'document' | 'none'
}

export const REQUEST_PATH = {
  title: 'One request, end to end',
  summary: 'route → retrieve in order → compose → trace',
  steps: [
    {
      name: 'Question arrives',
      who: 'system',
      detail: 'plain words · no mode picker, no tool menu — routing is not the user’s job',
      tone: 'neutral' as const,
    },
    {
      name: 'Exact answers first',
      who: 'model judges the match · code enforces the gate',
      detail: 'closest approved questions retrieved, then a same-question check',
      hit: 'approved answer returned **verbatim**, marked verified — chain stops',
      miss: 'hand down · question logged as a coverage gap',
      tone: 'exact' as const,
    },
    {
      name: 'Then the numbers',
      who: 'model fills parameters · code runs the query',
      detail: 'match a published definition, rewrite under constraints, pass the execution gate',
      hit: 'number + the exact query that produced it',
      miss: 'refuse **with the reason** — no generation model is even called',
      tone: 'text2sql' as const,
    },
    {
      name: 'Then the documents',
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
  emphasis: 'Freedom is granted **per layer**, never per request.',
}

/* ── 架构段 4:两个角色的闭环 ── */

export interface JourneyStage {
  who: 'ops' | 'user' | 'system'
  name: string
  note: string
}

export const JOURNEY = {
  title: 'The loop people actually live in',
  summary: 'curate → publish → ask → answer with sources → gap → back to the queue',
  legend: [
    { key: 'ops', label: 'Business / knowledge ops' },
    { key: 'user', label: 'End user' },
    { key: 'system', label: 'System' },
  ],
  stages: [
    { who: 'ops' as const, name: 'Bring raw material', note: 'handbooks · exports · a database' },
    { who: 'system' as const, name: 'AI proposes', note: 'candidates — not knowledge yet' },
    { who: 'ops' as const, name: 'Accept · edit · reject', note: 'judgement, not data entry' },
    { who: 'ops' as const, name: 'Publish & own it', note: 'going live is an announcement' },
    { who: 'user' as const, name: 'Ask in plain words', note: 'never picks a layer' },
    {
      who: 'system' as const,
      name: 'Answer + sources + trace',
      note: 'or an honest “no basis”',
    },
    {
      who: 'user' as const,
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
  summary: 'component → trajectory → outcome → production & safety',
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
  summary: 'read · analyse · summarise  vs  write · execute · send',
  moreLabel: 'More latitude',
  lessLabel: 'Kept out of the model',
  more: [
    'read approved knowledge',
    'retrieve and rank evidence',
    'summarise, with citations',
    'fill parameters of a signed definition',
    'recommend the next step',
  ],
  less: [
    'writing to any system of record',
    'issuing a query nobody approved',
    'sending anything outward',
    'changing what a business term means',
    'publishing knowledge',
  ],
  emphasis:
    'Today the agent takes **no** actions at all — a deliberate choice, and the cheapest one to defend.',
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
  note: 'An interview demo — the design positions above are the point, not the feature count.',
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
  ...LAYERS.map((l) => ({
    to: `/how-it-works/${l.slug}`,
    label: l.name,
    dotClass: l.dotClass,
  })),
]
