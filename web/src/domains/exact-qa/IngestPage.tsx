/** 精准 QA ingestion 页 —— 空白壳(RESTRUCTURE-PLAN 决策 3)。
 *  真实流程待需求确认后,由本域开发者在 src/domains/exact-qa/ 内自行搭建。 */

import { MessageSquareText } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'

export function IngestPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="bg-kb-exact-qa size-2.5 rounded-full" />
        <span className="text-muted-foreground text-[12px]">Exact Q&A knowledge</span>
      </div>
      <div className="bg-card rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
        <EmptyState
          icon={MessageSquareText}
          title="Exact Q&A ingestion"
          description="The ingestion workflow for curated question-answer pairs has not been built yet. This workspace is reserved for it."
        />
      </div>
    </div>
  )
}
