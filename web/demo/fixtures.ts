/** 静态预览版用的固定响应。
 *
 * 来源:2026-08-21 从真后端(`make seed` 之后)抓下来的实际返回 ——
 * `/healthz`、`/api/kbs`、`/api/agents`、`/api/agents/{id}`。
 * 只有会话列表是手写的演示数据:真库里那几条是冒烟脚本留下的测试问句,不适合给人看。
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
}
