/** DomainModule —— 一个知识域对外的全部描述(RESTRUCTURE-PLAN Stage 1)。
 *
 * 路由、导航子项、顶栏标题、识别色、审核渲染器都从这个描述符生成:
 * 共享文件(App / AppLayout / staging registry)只遍历 DOMAINS,不认识任何具体域。
 * 类型单独放这个文件,避免 index.ts 与各域 module.ts 互相 import 成环。
 */

import type { LucideIcon } from 'lucide-react'
import type { ComponentType } from 'react'

import type { ItemRenderers } from '@/components/staging/types'

export type DomainModule = {
  /** 域标识,与后端 KB_TYPES / knowledge_bases.type 一致 */
  key: 'exact_qa' | 'document' | 'text2sql'
  /** 导航子项文案(英文);顶栏标题由它派生("<label> Ingestion") */
  label: string
  /** ingestion 页路由,约定 /ingest/<segment> */
  path: string
  /** 页面空状态用的图标(导航子项用识别色圆点,不用图标) */
  icon: LucideIcon
  /** 识别色工具类(bg-kb-*),色值只存在于 index.css 品牌层(UI-STYLE §2) */
  toneClass: string
  /** ingestion 页组件;当前为空白壳,真实流程确认后由各域开发者重写 */
  IngestPage: ComponentType
  /** item_type → 审核渲染器,汇总进 staging/registry;没有就走 JSON 兜底 */
  renderers?: Record<string, ItemRenderers>
}
