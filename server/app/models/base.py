"""模型基类与公共约定(约定详见 documents/DB-DESIGN.md §0)。

- 主键统一 uuid,DB 侧 gen_random_uuid() 生成
- created_at / updated_at 统一 timestamptz,DB 侧 now()
- 枚举一律 text + CHECK,不用 PG native enum(加值只改约束,不 ALTER TYPE)
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def enum_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """生成 text 列的枚举 CHECK 约束。"""
    joined = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({joined})", name=name)


class UUIDMixin:
    id: Mapped[uuid.UUID] = uuid_pk()


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    """有更新语义的表:updated_at 由 SQLAlchemy onupdate 维护。"""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
