"""待审内容(staging_items)的出入参 —— 审核台的契约。

`payload` 是 jsonb,这里保持成宽松的 dict:它的结构按 `item_type` 变化
(见 DB-DESIGN §8),由前端对应的渲染器解释。为每种 item_type 各生成一套 API 类型
没有收益 —— 泛型审核台的全部意义就是**不认识** payload 里有什么。
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.ingest import REVIEW_STATUSES
from app.schemas.common import ORMModel

ReviewStatus = str  # 取值见 app/models/ingest.py REVIEW_STATUSES(CHECK 约束在 DB 侧兜底)
# 正则必须锚定:不加 ^$ 的话 "xapproved" 也能通过校验,错值一路走到 DB 的 CHECK 才被拦
REVIEW_STATUS_PATTERN = f"^({'|'.join(REVIEW_STATUSES)})$"


class StagingItemOut(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    kb_id: uuid.UUID
    # 决定前端用哪个渲染器:qa_pair / chunk / table_meta / metric / term
    item_type: str
    payload: dict
    origin_ref: dict | None
    confidence: float | None
    review_status: str
    review_note: str | None
    reviewed_at: datetime | None
    published: bool
    published_ref: dict | None
    conflict_with: list | None
    created_at: datetime
    updated_at: datetime


class StagingItemPatch(BaseModel):
    """审一条。三个字段都可选:只改状态、只改内容、只加备注都是合法请求。

    `payload` 是**顶层键浅合并**(见 core/staging.py::merge_payload);
    只传 payload 不传状态时,状态自动变 `modified`。
    """

    payload: dict | None = None
    review_status: ReviewStatus | None = Field(default=None, pattern=REVIEW_STATUS_PATTERN)
    review_note: str | None = None


class StagingBulkRequest(BaseModel):
    """批量通过/驳回:审核几十条时这是主要动作,不是附属功能。"""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    review_status: ReviewStatus = Field(pattern=REVIEW_STATUS_PATTERN)


class StagingBulkResult(BaseModel):
    updated: int


class StagingSummary(BaseModel):
    """一个 job 下的审核进度。审核台顶部的筛选标签直接渲染它,不在前端数数
    (前端只拿到当前页的条目,数不准)。"""

    total: int
    pending: int
    approved: int
    rejected: int
    modified: int
    published: int


class PublishResult(BaseModel):
    """发布结果 = 一条审计记录 + 发布后的 job 状态。"""

    record_id: uuid.UUID
    job_id: uuid.UUID
    job_status: str
    published: int
    item_counts: dict
    created_at: datetime
