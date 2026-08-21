/** 静态预览版用的固定响应。
 *
 * 来源:2026-08-21 从真后端(`make seed` 之后)抓下来的实际返回 ——
 * `/healthz`、`/api/kbs`、`/api/agents`、`/api/agents/{id}`。
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

  '/api/kbs': {
    items: [
      {
        id: '8926389c-3d89-4e09-be74-252a42f825a1',
        name: 'Product FAQ (Exact Answers)',
        type: 'exact_qa',
        description:
          'Curated question-answer pairs for policy and specification questions that must be answered word-for-word: warranty terms, certifications, return policy, lead times.',
        status: 'active',
        created_at: '2026-08-21T06:32:44.817342Z',
        updated_at: '2026-08-21T06:32:44.817342Z',
      },
      {
        id: 'c1f3a068-6e3c-490b-997e-5bfc83b64e32',
        name: 'Technical Documentation',
        type: 'document',
        description:
          'Installation manuals, datasheets and commissioning guides. Use for how-to and troubleshooting questions that need an answer grounded in a cited document passage.',
        status: 'active',
        created_at: '2026-08-21T06:32:44.817342Z',
        updated_at: '2026-08-21T06:32:44.817342Z',
      },
      {
        id: 'a5ce4a3b-2b12-4a80-9b27-f5d46d1bf0d1',
        name: 'Sales Analytics',
        type: 'text2sql',
        description:
          'Governed semantic layer over the sales database (orders, products, regions). Use for questions about numbers: revenue, volumes, rankings, trends by state or period.',
        status: 'active',
        created_at: '2026-08-21T06:32:44.817342Z',
        updated_at: '2026-08-21T06:32:44.817342Z',
      },
    ],
    total: 3,
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

  // ---- 摄取任务页:一个跑完的、一个失败在 extract 的 ----
  '/api/jobs/types': ['demo_sleep'],
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

Object.assign(FIXTURES, {
  '/api/jobs?limit=20': {
    items: [
      {
        ...JOB_BASE,
        id: 'e1000000-0002-4a10-9f01-dddd00000002',
        status: 'failed',
        current_step: 'extract',
        progress: 50,
        step_logs: [
          log('fetch', 'Fetch source', 'ok', 'Loaded 1 source document'),
          log('parse', 'Parse content', 'ok', 'Parsed 8 sections / 1,240 words'),
          log(
            'extract',
            'Extract candidates',
            'error',
            "RuntimeError: Injected failure at step 'extract' (fail_at param)",
          ),
        ],
        error: {
          code: 'step_failed',
          step: 'extract',
          message: "RuntimeError: Injected failure at step 'extract' (fail_at param)",
        },
        stats: {},
        started_at: '2026-08-20T05:12:00.000000Z',
        finished_at: '2026-08-20T05:12:04.000000Z',
        created_at: '2026-08-20T05:12:00.000000Z',
      },
      {
        ...JOB_BASE,
        id: 'e1000000-0001-4a10-9f01-dddd00000001',
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
      },
    ],
    total: 2,
  },
})

// 单个任务的详情就是列表里的那两条,避免同一份数据写两遍
const JOBS = (FIXTURES['/api/jobs?limit=20'] as { items: { id: string }[] }).items
for (const job of JOBS) FIXTURES[`/api/jobs/${job.id}`] = job
