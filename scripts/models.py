"""ORM models mirroring db/schema.sql.

These describe the existing tables; they are never used to create them. The
schema file stays the source of truth, so changes there must be reflected
here by hand.
"""
import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text, func
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
        Enum(ArticleStatus, name="article_status"))
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("articles.id", ondelete="CASCADE"))

    software_name: Mapped[str | None] = mapped_column(Text)
    company_name: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)

    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(Text)

    article: Mapped[Article] = relationship(back_populates="findings")

    def __repr__(self) -> str:
        return f"<Finding {self.id} {self.company_name!r} {self.review_status.value}>"
