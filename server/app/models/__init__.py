"""全部 SQLAlchemy 模型的汇总导入口。

Alembic 的 target_metadata 就靠这里把所有模型挂到 Base.metadata 上——
新增模型文件后必须在这里导出,否则 autogenerate 会把它当"待删除的表"。
字段级定义的唯一出处是 documents/DB-DESIGN.md。
"""

from app.models.agent import Agent, AgentKbBinding
from app.models.base import Base
from app.models.conversation import Conversation, Message, MessageCitation
from app.models.document import Chunk, Document
from app.models.evaluation import EvalCase, EvalResult, EvalRun, EvalSet
from app.models.exact_qa import ExactQaItem, ExactQaVector
from app.models.ingest import IngestJob, IngestSource, PublishRecord, StagingItem
from app.models.knowledge import KnowledgeBase
from app.models.observability import Feedback, Trace, UnansweredItem
from app.models.text2sql import (
    ColumnMeta,
    Datasource,
    IntentQuestion,
    IntentVector,
    NonDataFace,
    Relation,
    SqlIntent,
    TableMeta,
)
from app.models.user import User

__all__ = [
    "Base",
    # 基础
    "User",
    "KnowledgeBase",
    # 精准 QA
    "ExactQaItem",
    "ExactQaVector",
    # 文档 RAG
    "Document",
    "Chunk",
    # 智能问数
    "Datasource",
    "TableMeta",
    "ColumnMeta",
    "Relation",
    "SqlIntent",
    "IntentQuestion",
    "NonDataFace",
    "IntentVector",
    # 摄取骨架
    "IngestSource",
    "IngestJob",
    "StagingItem",
    "PublishRecord",
    # Agent 与会话
    "Agent",
    "AgentKbBinding",
    "Conversation",
    "Message",
    "MessageCitation",
    # 观测
    "Trace",
    "Feedback",
    "UnansweredItem",
    # 评测
    "EvalSet",
    "EvalCase",
    "EvalRun",
    "EvalResult",
]
