/** 智能问数 ingestion 页 —— 空白壳(结构调整决策:空白壳,见 S0-PLAN §5)。
 *  真实流程待需求确认后,由本域开发者在 src/domains/text2sql/ 内自行搭建。 */

import { Database } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'

export function IngestPage() {
  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex items-center gap-2.5">
        <span className="bg-kb-text2sql size-2.5 rounded-full" />
        <span className="text-faint text-[13px]">Structured data knowledge</span>
      </div>
      <div className="bg-card rounded-[var(--radius-card)] border border-[var(--border)] shadow-[var(--shadow-card)]">
        <EmptyState
          icon={Database}
          title="Text-to-SQL ingestion"
          description="The ingestion workflow for table metadata, metrics and business terms has not been built yet. This workspace is reserved for it."
        />
      </div>
    </div>
  )
}
