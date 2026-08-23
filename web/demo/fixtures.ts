/** 静态预览版用的固定响应。
 *
 * 来源:2026-08-21 从真后端(`make seed` 之后)抓下来的实际返回 ——
 * `/healthz`、`/api/agents`、`/api/agents/{id}`(kbs/jobs 列表随页面删除,见 S0-PLAN §5)。
 * 手写的部分:会话列表与消息、trace、jobs —— 真库里那几条是冒烟脚本留下的
 * 测试问句("Reply with exactly: SSE OK"),不适合给人看。手写的内容与真接口
 * 同形(字段名来自 openapi 生成的类型),所以页面代码一行都不用为预览让步。
 *
 * 这个文件**不参与正式构建**,只有 `make demo` 打的静态包会用它。
 */

export const FIXTURES: Record<string, unknown> = {
  '/healthz': {
    status: 'ok',
    env: 'dev',
    database: 'ok',
    database_error: null,
    embedding_dim: 1536,
  },

  '/api/agents': {
    items: [
      {
        id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
        name: 'Clenergy Assistant',
        description: 'Default demo agent bound to all three knowledge bases.',
        router_mode: 'rule_llm',
        status: 'active',
        created_at: '2026-08-21T06:32:44.817342Z',
        updated_at: '2026-08-21T06:32:44.817342Z',
      },
    ],
    total: 1,
  },

  '/api/agents/b726d168-53ed-4752-b204-a4b1fe0572f3': {
    id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
    name: 'Clenergy Assistant',
    description: 'Default demo agent bound to all three knowledge bases.',
    router_mode: 'rule_llm',
    status: 'active',
    created_at: '2026-08-21T06:32:44.817342Z',
    updated_at: '2026-08-21T06:32:44.817342Z',
    system_prompt:
      'You are the Clenergy enterprise knowledge assistant. Answer staff and partner questions about Clenergy products, documentation and sales data.\nRules:\n- Answer only from the knowledge provided to you. Never invent specifications, prices, warranty terms or figures.\n- If the knowledge does not cover the question, say so plainly and suggest who to ask.\n- Keep answers concise and factual. Use Australian English.',
    fallback_reply:
      "I don't have this in the knowledge base yet, so I can't answer it reliably. Please check with the product team, and this question will be logged for follow-up.",
    model_cfg: {},
    bindings: [
      {
        id: 'c32f169c-5fa3-485f-9ff4-dce402bbc500',
        kb_id: '8926389c-3d89-4e09-be74-252a42f825a1',
        kb_name: 'Product FAQ (Exact Answers)',
        kb_type: 'exact_qa',
        priority: 10,
        enabled: true,
        top_k: null,
        threshold: null,
        usage_desc:
          'Curated question-answer pairs for policy and specification questions that must be answered word-for-word: warranty terms, certifications, return policy, lead times.',
      },
      {
        id: '023fc7ff-040f-4306-b985-80e468f42604',
        kb_id: 'c1f3a068-6e3c-490b-997e-5bfc83b64e32',
        kb_name: 'Technical Documentation',
        kb_type: 'document',
        priority: 20,
        enabled: true,
        top_k: null,
        threshold: null,
        usage_desc:
          'Installation manuals, datasheets and commissioning guides. Use for how-to and troubleshooting questions that need an answer grounded in a cited document passage.',
      },
      {
        id: '170d1e45-0f5d-4876-afa8-1bfa0068111f',
        kb_id: 'a5ce4a3b-2b12-4a80-9b27-f5d46d1bf0d1',
        kb_name: 'Sales Analytics',
        kb_type: 'text2sql',
        priority: 30,
        enabled: true,
        top_k: null,
        threshold: null,
        usage_desc:
          'Governed semantic layer over the sales database (orders, products, regions). Use for questions about numbers: revenue, volumes, rankings, trends by state or period.',
      },
    ],
  },

  '/api/conversations': {
    items: [
      {
        id: '3f2b1c88-0001-4a10-9f01-aaaa00000001',
        agent_id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
        title: 'What is the warranty period for the PV-ezRack SolarRoof?',
        status: 'active',
        last_message_at: '2026-08-20T04:41:12.000000Z',
        created_at: '2026-08-20T04:40:58.000000Z',
      },
      {
        id: '3f2b1c88-0002-4a10-9f01-aaaa00000002',
        agent_id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
        title: 'Which mounting kit suits a corrugated metal roof in a cyclonic region?',
        status: 'active',
        last_message_at: '2026-08-19T23:12:40.000000Z',
        created_at: '2026-08-19T23:11:02.000000Z',
      },
      {
        id: '3f2b1c88-0003-4a10-9f01-aaaa00000003',
        agent_id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
        title: 'Top five products by revenue in Queensland last quarter',
        status: 'active',
        last_message_at: '2026-08-19T06:55:31.000000Z',
        created_at: '2026-08-19T06:54:07.000000Z',
      },
      {
        id: '3f2b1c88-0004-4a10-9f01-aaaa00000004',
        agent_id: 'b726d168-53ed-4752-b204-a4b1fe0572f3',
        title: 'Rail spacing for 2.3 kPa wind load',
        status: 'active',
        last_message_at: '2026-08-18T02:20:09.000000Z',
        created_at: '2026-08-18T02:19:44.000000Z',
      },
    ],
    total: 4,
  },

  // ---- 对话页:一条完整的历史会话(消息 + trace)----
  '/api/conversations/3f2b1c88-0001-4a10-9f01-aaaa00000001/messages': {
    items: [
      {
        id: 'c4d5e6f7-0000-4a10-9f01-bbbb00000000',
        conversation_id: '3f2b1c88-0001-4a10-9f01-aaaa00000001',
        role: 'user',
        content: 'What is the warranty period for the PV-ezRack SolarRoof?',
        status: 'completed',
        route_decision: null,
        usage: null,
        latency_ms: null,
        created_at: '2026-08-20T04:40:58.000000Z',
      },
      {
        id: 'c4d5e6f7-0001-4a10-9f01-bbbb00000001',
        conversation_id: '3f2b1c88-0001-4a10-9f01-aaaa00000001',
        role: 'assistant',
        content:
          'The PV-ezRack SolarRoof carries a 15 year structural warranty when it is installed to the published torque and span tables. Anodised aluminium components are covered for corrosion for the same period; stainless fasteners are covered for 10 years.',
        status: 'completed',
        route_decision: null,
        usage: {
          prompt_tokens: 218,
          completion_tokens: 61,
          total_tokens: 279,
          cost_usd: '0.001913',
        },
        latency_ms: 2417,
        created_at: '2026-08-20T04:41:12.000000Z',
        // 命中精准问答:答案是人工采纳过的原话,引用要说清"匹配到哪一句、多像、原文在第几页"
        verified: true,
        citations: [
          {
            seq: 1,
            citation_type: 'exact_qa',
            ref_id: 'f1000000-0001-4a10-9f01-eeee00000001',
            snippet:
              'The PV-ezRack SolarRoof carries a 15 year structural warranty when it is installed to the published torque and span tables.',
            extra: {
              score: 0.941,
              matched_question: 'What is the warranty period for the PV-ezRack SolarRoof?',
              is_standard_question: true,
              page_idx: 2,
            },
          },
          {
            seq: 2,
            citation_type: 'exact_qa',
            ref_id: 'f1000000-0002-4a10-9f01-eeee00000002',
            snippet:
              'Anodised aluminium components are covered for corrosion for the same period; stainless fasteners are covered for 10 years.',
            extra: {
              score: 0.883,
              matched_question: 'How long are the fasteners covered for?',
              is_standard_question: false,
              page_idx: 2,
            },
          },
        ],
      },
    ],
    total: 2,
  },

  '/api/traces/c4d5e6f7-0001-4a10-9f01-bbbb00000001': {
    items: [
      {
        id: 'd1e2f3a4-0001-4a10-9f01-cccc00000001',
        message_id: 'c4d5e6f7-0001-4a10-9f01-bbbb00000001',
        stage: 'generate',
        seq: 1,
        status: 'ok',
        input: {
          question: 'What is the warranty period for the PV-ezRack SolarRoof?',
          history_turns: 0,
          prompt: [
            {
              role: 'system',
              content:
                'You are the Clenergy enterprise knowledge assistant. Answer staff and partner questions about Clenergy products, documentation and sales data.',
            },
            { role: 'user', content: 'What is the warranty period for the PV-ezRack SolarRoof?' },
          ],
        },
        output: {
          text: 'The PV-ezRack SolarRoof carries a 15 year structural warranty…',
          finish_reason: 'stop',
        },
        error: null,
        latency_ms: 2417,
        prompt_tokens: 218,
        completion_tokens: 61,
        cost_usd: '0.001913',
        model: 'gpt-5',
        created_at: '2026-08-20T04:41:12.000000Z',
      },
    ],
    total: 1,
  },

}

/** 任务的四个步骤(与 server/app/core/jobs_demo.py 的声明一致) */
const JOB_STEPS = [
  { name: 'fetch', title: 'Fetch source' },
  { name: 'parse', title: 'Parse content' },
  { name: 'extract', title: 'Extract candidates' },
  { name: 'stage', title: 'Write staging items' },
]

const JOB_BASE = {
  kb_id: '8926389c-3d89-4e09-be74-252a42f825a1',
  source_id: null,
  job_type: 'demo_sleep',
  steps: JOB_STEPS,
  params: { items: 20, step_seconds: 2 },
  heartbeat_at: null,
}

function log(step: string, title: string, status: string, message: string, latency_ms = 2003) {
  return { step, title, status, message, latency_ms, at: '2026-08-20T05:10:00.000000Z' }
}


// ---- 审核台:一批待审的 QA 条目 ----
// 预览里的审核**真的能改**:main.tsx 把这个数组当内存库,PATCH / 批量 / 发布都写进它,
// 于是筛选计数、发布按钮都跟着动。数据是假的,流程是真的。
const TOPICS: [string, string][] = [
  ['warranty period', 'The standard warranty covers 5 years on the unit'],
  ['shipping lead time', 'Standard lead time is 6 weeks from order confirmation'],
  ['mounting compatibility', 'The rail system fits tile, metal and flat roofs'],
  ['inverter pairing', 'Any inverter with a 600 V DC input window is supported'],
  ['cycle life', 'Rated for 6000 cycles at 80% depth of discharge'],
]

export type DemoStagingItem = {
  id: string
  job_id: string
  kb_id: string
  item_type: string
  payload: Record<string, unknown>
  origin_ref: Record<string, unknown> | null
  confidence: number
  review_status: string
  review_note: string | null
  reviewed_at: string | null
  published: boolean
  published_ref: Record<string, unknown> | null
  conflict_with: unknown[] | null
  created_at: string
  updated_at: string
}

export const DEMO_JOB_ID = 'e1000000-0001-4a10-9f01-dddd00000001'

/** 与 server/app/core/jobs_demo.py 的 `_fake_item()` 同一套模板与置信度分档。 */
export const STAGING_ITEMS: DemoStagingItem[] = Array.from({ length: 20 }, (_, i) => {
  const [topic, answer] = TOPICS[i % TOPICS.length]
  const model = `HC-${215 + i}`
  return {
    id: `f2000000-${String(i + 1).padStart(4, '0')}-4a10-9f01-eeee00000001`,
    job_id: DEMO_JOB_ID,
    kb_id: JOB_BASE.kb_id,
    item_type: 'qa_pair',
    payload: {
      standard_question: `What is the ${topic} for model ${model}?`,
      answer: `${answer} (${model}).`,
      similar_questions: [`${model} ${topic}`, `${topic} ${model.replace('-', '')}`],
      keywords: [topic.split(' ')[0], model],
    },
    origin_ref: { page: 1 + Math.floor(i / 4), quote: `…${topic}…` },
    confidence: Number((0.62 + (i % 7) * 0.055).toFixed(3)),
    review_status: 'pending',
    review_note: null,
    reviewed_at: null,
    published: false,
    published_ref: null,
    conflict_with: null,
    created_at: '2026-08-20T05:10:08.000000Z',
    updated_at: '2026-08-20T05:10:08.000000Z',
  }
})

// ---- 审核台直链需要的任务详情:预览里唯一保留的任务 ----
// 任务列表页已删(结构调整,见 S0-PLAN §5),预览里审核台用直链 #/jobs/{id}/review 进入,
// ReviewPage 与右栏 JobProgress 都取这一条。
FIXTURES[`/api/jobs/${DEMO_JOB_ID}`] = {
  ...JOB_BASE,
  id: DEMO_JOB_ID,
  status: 'review',
  current_step: null,
  progress: 100,
  step_logs: [
    log('fetch', 'Fetch source', 'ok', 'Loaded 1 source document'),
    log('parse', 'Parse content', 'ok', 'Parsed 8 sections / 1,240 words'),
    log('extract', 'Extract candidates', 'ok', 'Extracted 20 candidate QA pairs'),
    log('stage', 'Write staging items', 'ok', 'Wrote 20 staging items, waiting for review'),
  ],
  error: null,
  stats: { staged: 20 },
  started_at: '2026-08-20T05:10:00.000000Z',
  finished_at: '2026-08-20T05:10:08.000000Z',
  created_at: '2026-08-20T05:10:00.000000Z',
}

// ---- 精准 QA 域:文档列表 / 校对页 / 已发布问答库 ----
// 预览是只读的:上传、保存校对、确认抽取都没有后端可写(main.tsx 的兜底会返回 404 错误体),
// 这里只提供把这两页画出来所需的最小数据,让静态预览与 UI 走查能覆盖到它们。
export const DEMO_DOC_ID = 'a1000000-0001-4a10-9f01-cccc00000001'

const DEMO_DOC = {
  id: DEMO_DOC_ID,
  kb_id: JOB_BASE.kb_id,
  name: 'PV-ezRack SolarRoof installation manual.pdf',
  file_type: 'application/pdf',
  size_bytes: 2_418_664,
  parse_status: 'ok',
  parse_error: null,
  stage: 'review_text',
  parse_job_id: DEMO_JOB_ID,
  extract_job_id: null,
  parse_stats: {
    page_count: 3,
    block_count: 86,
    noise_dropped: 7,
    table_count: 1,
    image_count: 2,
    equation_count: 0,
    elapsed_ms: 8420,
  },
  funnel: { candidates: 20, pending: 20, accepted: 0, rejected: 0 },
  created_at: '2026-08-20T05:09:40.000000Z',
  updated_at: '2026-08-20T05:10:08.000000Z',
}

FIXTURES['/api/exact-qa/documents'] = {
  items: [
    DEMO_DOC,
    {
      ...DEMO_DOC,
      id: 'a1000000-0002-4a10-9f01-cccc00000001',
      name: 'Ground mount PV-ezRack datasheet.pdf',
      size_bytes: 861_204,
      stage: 'done',
      parse_stats: {
        page_count: 2,
        block_count: 41,
        noise_dropped: 3,
        table_count: 2,
        image_count: 1,
        equation_count: 0,
        elapsed_ms: 5110,
      },
      funnel: { candidates: 12, pending: 0, accepted: 11, rejected: 1 },
    },
  ],
  total: 2,
}

FIXTURES[`/api/exact-qa/documents/${DEMO_DOC_ID}`] = DEMO_DOC

FIXTURES[`/api/exact-qa/documents/${DEMO_DOC_ID}/review-text`] = {
  document_id: DEMO_DOC_ID,
  source: 'paged.md',
  reviewed: false,
  images: [],
  pages: [
    { page_idx: 1, width_pt: 595, height_pt: 842 },
    { page_idx: 2, width_pt: 595, height_pt: 842 },
    { page_idx: 3, width_pt: 595, height_pt: 842 },
  ],
  text: [
    '<!-- page: 1 -->',
    '# PV-ezRack SolarRoof — installation manual',
    '',
    'This manual covers the rail, clamp and hook range for tile, metal and flat roofs.',
    'Install to the published torque and span tables; deviations void the structural warranty.',
    '',
    '<!-- page: 2 -->',
    '## Warranty',
    '',
    'The structural warranty is 15 years from the date of installation. Anodised aluminium',
    'components carry the same corrosion cover; stainless fasteners are covered for 10 years.',
    '',
    '| Component | Warranty | Notes |',
    '| --- | --- | --- |',
    '| Rail | 15 years | Structural |',
    '| Clamp | 15 years | Structural |',
    '| Fastener | 10 years | Corrosion only |',
    '',
    '<!-- page: 3 -->',
    '## Torque table',
    '',
    'Tighten all M8 clamp bolts to 12 Nm. Tighten M10 hook bolts to 20 Nm.',
    'Re-check torque after the first 12 months in coastal installations.',
  ].join('\n'),
}

FIXTURES['/api/exact-qa/items'] = {
  items: TOPICS.map(([topic], i) => ({
    id: `a2000000-${String(i + 1).padStart(4, '0')}-4a10-9f01-cccc00000001`,
    kb_id: JOB_BASE.kb_id,
    standard_question: `What is the ${topic} for model HC-${215 + i}?`,
    keywords: [topic.split(' ')[0], `HC-${215 + i}`],
    similar_count: 2,
    status: 'enabled',
    index_faces: 3,
    source_staging_id: null,
    created_at: '2026-08-20T05:12:00.000000Z',
    updated_at: '2026-08-20T05:12:00.000000Z',
  })),
  total: TOPICS.length,
}
