"""ORM models — the source of truth for the schema.

Alembic autogenerates migrations from these, so a column added here becomes a
migration rather than a hand-edited SQL file.
"""
import enum
from datetime import datetime

from sqlalchemy import (BigInteger, DateTime, Enum, ForeignKey, Index, Text,
                        func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ArticleStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(Text, unique=True)
    source: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus, name="article_status"),
        server_default=ArticleStatus.processing.value)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())

    # ON DELETE CASCADE is enforced by the database; passive_deletes lets it,
    # rather than having the ORM load and delete each finding itself.
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="article", cascade="all, delete", passive_deletes=True,
        order_by="Finding.id")

    @property
    def title(self) -> str | None:
        return (self.raw_payload or {}).get("title")

    def __repr__(self) -> str:
        return f"<Article {self.id} {self.status.value} {self.url[:48]!r}>"


class Finding(Base):
    __tablename__ = "findings"

    # One finding per (article, software, domain). COALESCE is required
    # because NULLs are never equal to each other in a plain unique index, so
    # two findings with no software and no domain would both be allowed.
    __table_args__ = (
        Index("findings_unique_article_breach",
              "article_id",
              text("COALESCE(software_name, '')"),
              text("COALESCE(domain, '')"),
              unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("articles.id", ondelete="CASCADE"))

    software_name: Mapped[str | None] = mapped_column(Text)
    company_name: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)

    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"),
        server_default=ReviewStatus.pending.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)

    article: Mapped[Article] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return f"<Finding {self.id} {self.company_name!r} {self.review_status.value}>"
