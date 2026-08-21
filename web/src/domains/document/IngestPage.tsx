/** 文档 RAG ingestion 页 —— 空白壳(结构调整决策:空白壳,见 S0-PLAN §5)。
 *  真实流程待需求确认后,由本域开发者在 src/domains/document/ 内自行搭建。 */

import { FileText } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'

export function IngestPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="bg-kb-document size-2.5 rounded-full" />
        <span className="text-muted-foreground text-[12px]">Document RAG knowledge</span>
      </div>
      <div className="bg-card rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
        <EmptyState
          icon={FileText}
          title="Document ingestion"
          description="The ingestion workflow for manuals, datasheets and guides has not been built yet. This workspace is reserved for it."
        />
      </div>
    </div>
  )
}
