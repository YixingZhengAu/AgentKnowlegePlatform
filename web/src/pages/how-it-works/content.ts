/**
 * How It Works 说明页的**文案唯一出处**。
 *
 * 体裁纪律(2026-08-24 需求方定):这是投屏讲稿,**不是文章** ——
 * 面试官不会逐句读,所以一律关键词/短语,句子只留每层一句主角句与每屏一句强调句。
 * 其余纪律见 documents/HOW-IT-WORKS-PLAN.md §6:
 * - 页面组件里不写死任何句子,一律从这里取。
 * - 全篇不出现表名、字段名、函数名、接口路径、阈值数字(G2)。
 * - `**...**` 是唯一行内强调标记,由 Section.tsx 的 <Emphasized> 解析。
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

/* ───────────────────────── 屏 1:主张与三条推论 ───────────────────────── */

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

/* ───────────────────────── 屏 2:通用 RAG 的痛点 ───────────────────────── */

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

/* ───────────────────────── 屏 3:三层与共同的闸门 ───────────────────────── */

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

/* ───────────────────────── 屏 4:一次提问发生了什么 ───────────────────────── */

export const ANSWER_FLOW = {
  title: 'What happens when someone asks',
  summary: 'exact → text-to-sql → documents → "no basis"',
  steps: [
    {
      name: 'Question arrives',
      note: "user's own words · no mode picking",
      tone: 'neutral' as const,
    },
    {
      name: 'Exact answers first',
      note: 'confident match → **verbatim**, chain stops',
      tone: 'exact' as const,
    },
    {
      name: 'Then text-to-SQL',
      note: 'accepted definition → fill parameters · else refuse out loud',
      tone: 'text2sql' as const,
    },
    { name: 'Then documents', note: 'summarise · every claim cited', tone: 'document' as const },
    {
      name: 'Otherwise: nothing',
      note: '"no basis" → feeds the curation queue',
      tone: 'none' as const,
    },
  ],
  emphasis:
    'A ladder of freedom: the less exactness a question demands, the more the model may do.',
}

/* ───────────────────────── 屏 5:两个角色怎么用 ───────────────────────── */

export const ROLES = {
  title: 'Who uses it, and how',
  summary: 'ops team curates · end users just ask',
  lanes: [
    {
      role: 'Business / knowledge ops',
      steps: [
        'bring raw material',
        'read AI proposals',
        'accept · edit · reject',
        'publish & own it',
      ],
      note: 'judgement, not data entry',
    },
    {
      role: 'End user',
      steps: [
        'ask in own words',
        'answer + sources',
        'expand the trace',
        'flag wrong → back to owner',
      ],
      note: 'never picks a mode — routing is our job',
    },
  ],
  emphasis: 'What the business signs off on is **exactly** what end users receive.',
}

/* ───────────────────────── 屏 6:三层横向对比 ───────────────────────── */

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

/* ───────────────────────── 屏 7:刻意不做的事 ───────────────────────── */

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

/* ───────────────────────── 屏 8:进子页 ───────────────────────── */

export const LAYER_CARDS_TITLE = 'The three layers'

/* ───────────────────────── 子页:关键词卡片 ───────────────────────── */

export interface LayerDetail {
  slug: LayerSlug
  title: string
  /** 主角句(页顶唯一完整句) */
  leadLine: string
  /** 真实问题示例(chips) */
  examples: string[]
  /** 四张关键词卡:定位 / 为什么不能临场 / 前期定什么 / 业务在哪介入(重点) */
  cards: { heading: string; bullets: string[]; highlight?: boolean }[]
  /** 回答时:允许 / 不允许(两列) */
  answerTime: { may: string[]; mayNot: string[] }
  /** 刻意不做 */
  doesNot: string[]
}

export const LAYER_DETAILS: Record<LayerSlug, LayerDetail> = {
  'exact-qa': {
    slug: 'exact-qa',
    title: 'Exact Q&A',
    leadLine:
      "On a confident match we return the human-approved answer **verbatim** — the model doesn't get to rewrite a single word.",
    examples: ['leave entitlements', 'approval limits', 'which form starts X'],
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
