/** 编排(workflow)域描述符 —— 第四种知识。
 *
 * 与另外三个域不同:**它还没有后端**(2026-08-27 需求方定:先在导航里留个位置,
 * 摆一页设计预览,不做开发)。所以这里没有 `renderers` / `citations` —— 没有候选可审、
 * 也没有引用可渲染;`key` 也不在后端 KB_TYPES 里(见 `../types.ts` 的注释)。
 * 设计说明在 `/how-it-works#workflows`。
 */

import { Workflow } from 'lucide-react'

import type { DomainModule } from '../types'
import { IngestPage } from './IngestPage'

export const workflowDomain: DomainModule = {
  key: 'workflow',
  label: 'Workflow',
  path: '/ingest/workflow',
  icon: Workflow,
  toneClass: 'bg-kb-workflow',
  IngestPage,
}
