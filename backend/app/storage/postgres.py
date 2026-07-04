from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Uuid, create_engine, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.base import Base
from app.domain.ask.schemas import SavedMemoryRecord
from app.domain.captures.schemas import CaptureResponse
from app.domain.privacy.schemas import UserDataDeletionResult
from app.domain.products.schemas import ProductSnapshot
from app.domain.profiles.schemas import FitProfile, FitProfileUpdate
from app.domain.purchases.schemas import PurchaseRecord


def _now() -> datetime:
    return datetime.now(UTC)


class ProfileRow(Base):
    __tablename__ = "fit_profiles"

    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ProductRow(Base):
    __tablename__ = "product_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class CaptureRow(Base):
    __tablename__ = "captures"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class PurchaseRow(Base):
    __tablename__ = "purchase_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_snapshots.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class MemoryRecordRow(Base):
    __tablename__ = "saved_memory_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class PostgresStore:
    def __init__(self, settings: Settings):
        self.engine = create_engine(_sync_database_url(settings.database_url), pool_pre_ping=True)
        self.sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def get_profile(self, user_id: UUID) -> FitProfile:
        with self.sessionmaker() as session:
            row = session.get(ProfileRow, user_id)
            if row is None:
                profile = FitProfile(user_id=user_id, display_name="New shopper")
                session.add(ProfileRow(user_id=user_id, payload=_dump(profile)))
                session.commit()
                return profile
            return FitProfile.model_validate(row.payload)

    def update_profile(self, user_id: UUID, payload: FitProfileUpdate) -> FitProfile:
        with self.sessionmaker() as session:
            current = self._get_or_create_profile(session, user_id)
            updated = FitProfile.model_validate(
                {
                    **current.model_dump(mode="json"),
                    **payload.model_dump(mode="json", exclude_none=True),
                }
            )
            row = session.get(ProfileRow, user_id)
            if row is None:
                session.add(ProfileRow(user_id=user_id, payload=_dump(updated)))
            else:
                row.payload = _dump(updated)
            session.commit()
            return updated

    def delete_profile(self, user_id: UUID) -> FitProfile:
        with self.sessionmaker() as session:
            row = session.get(ProfileRow, user_id)
            if row is None:
                raise NotFoundError("Fit profile not found")
            profile = FitProfile.model_validate(row.payload)
            session.delete(row)
            session.commit()
            return profile

    def list_products(self) -> list[ProductSnapshot]:
        with self.sessionmaker() as session:
            rows = session.scalars(select(ProductRow).order_by(ProductRow.updated_at.desc())).all()
            return [ProductSnapshot.model_validate(row.payload) for row in rows]

    def get_product(self, product_id: UUID) -> ProductSnapshot:
        with self.sessionmaker() as session:
            row = session.get(ProductRow, product_id)
            if row is None:
                raise NotFoundError("Product snapshot not found")
            return ProductSnapshot.model_validate(row.payload)

    def save_product(self, product: ProductSnapshot) -> ProductSnapshot:
        with self.sessionmaker() as session:
            row = session.get(ProductRow, product.id)
            if row is None:
                session.add(ProductRow(id=product.id, payload=_dump(product)))
            else:
                row.payload = _dump(product)
            session.commit()
            return product

    def delete_product(self, product_id: UUID) -> ProductSnapshot:
        with self.sessionmaker() as session:
            row = session.get(ProductRow, product_id)
            if row is None:
                raise NotFoundError("Product snapshot not found")
            product = ProductSnapshot.model_validate(row.payload)
            session.delete(row)
            session.commit()
            return product

    def save_capture(self, capture: CaptureResponse) -> CaptureResponse:
        with self.sessionmaker() as session:
            row = session.get(CaptureRow, capture.id)
            if row is None:
                session.add(
                    CaptureRow(id=capture.id, user_id=capture.user_id, payload=_dump(capture))
                )
            else:
                row.user_id = capture.user_id
                row.payload = _dump(capture)
            session.commit()
            return capture

    def get_capture(self, capture_id: UUID) -> CaptureResponse:
        with self.sessionmaker() as session:
            row = session.get(CaptureRow, capture_id)
            if row is None:
                raise NotFoundError("Capture not found")
            return CaptureResponse.model_validate(row.payload)

    def list_captures(self, user_id: UUID) -> list[CaptureResponse]:
        with self.sessionmaker() as session:
            rows = session.scalars(
                select(CaptureRow)
                .where(CaptureRow.user_id == user_id)
                .order_by(CaptureRow.updated_at.desc())
            ).all()
            return [CaptureResponse.model_validate(row.payload) for row in rows]

    def delete_capture(self, capture_id: UUID) -> CaptureResponse:
        with self.sessionmaker() as session:
            row = session.get(CaptureRow, capture_id)
            if row is None:
                raise NotFoundError("Capture not found")
            capture = CaptureResponse.model_validate(row.payload)
            session.delete(row)
            session.commit()
            return capture

    def list_purchases(self, user_id: UUID) -> list[PurchaseRecord]:
        with self.sessionmaker() as session:
            rows = session.scalars(
                select(PurchaseRow)
                .where(PurchaseRow.user_id == user_id)
                .order_by(PurchaseRow.updated_at.desc())
            ).all()
            return [PurchaseRecord.model_validate(row.payload) for row in rows]

    def get_purchase(self, purchase_id: UUID) -> PurchaseRecord:
        with self.sessionmaker() as session:
            row = session.get(PurchaseRow, purchase_id)
            if row is None:
                raise NotFoundError("Purchase record not found")
            return PurchaseRecord.model_validate(row.payload)

    def save_purchase(self, purchase: PurchaseRecord) -> PurchaseRecord:
        with self.sessionmaker() as session:
            row = session.get(PurchaseRow, purchase.id)
            if row is None:
                session.add(
                    PurchaseRow(
                        id=purchase.id,
                        user_id=purchase.user_id,
                        product_id=purchase.product_id,
                        payload=_dump(purchase),
                    )
                )
            else:
                row.user_id = purchase.user_id
                row.product_id = purchase.product_id
                row.payload = _dump(purchase)
            session.commit()
            return purchase

    def delete_purchase(self, purchase_id: UUID) -> PurchaseRecord:
        with self.sessionmaker() as session:
            row = session.get(PurchaseRow, purchase_id)
            if row is None:
                raise NotFoundError("Purchase record not found")
            purchase = PurchaseRecord.model_validate(row.payload)
            session.delete(row)
            session.commit()
            return purchase

    def list_saved_memories(self, user_id: UUID) -> list[SavedMemoryRecord]:
        with self.sessionmaker() as session:
            rows = session.scalars(
                select(MemoryRecordRow)
                .where(MemoryRecordRow.user_id == user_id)
                .order_by(MemoryRecordRow.created_at.desc())
            ).all()
            return [SavedMemoryRecord.model_validate(row.payload) for row in rows]

    def get_saved_memory(self, memory_id: UUID) -> SavedMemoryRecord:
        with self.sessionmaker() as session:
            row = session.get(MemoryRecordRow, memory_id)
            if row is None:
                raise NotFoundError("Saved memory not found")
            return SavedMemoryRecord.model_validate(row.payload)

    def save_memory_record(self, record: SavedMemoryRecord) -> SavedMemoryRecord:
        with self.sessionmaker() as session:
            row = session.get(MemoryRecordRow, record.id)
            if row is None:
                session.add(
                    MemoryRecordRow(
                        id=record.id,
                        user_id=record.user_id,
                        payload=_dump(record),
                    )
                )
            else:
                row.user_id = record.user_id
                row.payload = _dump(record)
            session.commit()
            return record

    def delete_memory_record(self, memory_id: UUID) -> SavedMemoryRecord:
        with self.sessionmaker() as session:
            row = session.get(MemoryRecordRow, memory_id)
            if row is None:
                raise NotFoundError("Saved memory not found")
            record = SavedMemoryRecord.model_validate(row.payload)
            session.delete(row)
            session.commit()
            return record

    def delete_saved_memories(self, user_id: UUID) -> int:
        with self.sessionmaker() as session:
            rows = session.scalars(
                select(MemoryRecordRow).where(MemoryRecordRow.user_id == user_id)
            ).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count

    def delete_user_data(self, user_id: UUID) -> UserDataDeletionResult:
        with self.sessionmaker() as session:
            capture_rows = session.scalars(
                select(CaptureRow).where(CaptureRow.user_id == user_id)
            ).all()
            capture_ids = {row.id for row in capture_rows}
            product_rows = session.scalars(select(ProductRow)).all()
            owned_product_rows = [
                row
                for row in product_rows
                if ProductSnapshot.model_validate(row.payload).source_capture_id in capture_ids
            ]
            owned_product_ids = {row.id for row in owned_product_rows}
            purchase_filter = PurchaseRow.user_id == user_id
            if owned_product_ids:
                purchase_filter = or_(
                    purchase_filter,
                    PurchaseRow.product_id.in_(owned_product_ids),
                )
            purchase_rows = session.scalars(select(PurchaseRow).where(purchase_filter)).all()
            memory_rows = session.scalars(
                select(MemoryRecordRow).where(MemoryRecordRow.user_id == user_id)
            ).all()
            profile_row = session.get(ProfileRow, user_id)

            for row in purchase_rows:
                session.delete(row)
            session.flush()
            for row in memory_rows:
                session.delete(row)
            session.flush()
            for row in owned_product_rows:
                session.delete(row)
            session.flush()
            for row in capture_rows:
                session.delete(row)
            session.flush()
            if profile_row is not None:
                session.delete(profile_row)

            session.commit()
            return UserDataDeletionResult(
                profile_deleted=profile_row is not None,
                captures_deleted=len(capture_rows),
                products_deleted=len(owned_product_rows),
                purchases_deleted=len(purchase_rows),
                saved_memories_deleted=len(memory_rows),
            )

    def _get_or_create_profile(self, session: Session, user_id: UUID) -> FitProfile:
        row = session.get(ProfileRow, user_id)
        if row is not None:
            return FitProfile.model_validate(row.payload)
        return FitProfile(user_id=user_id, display_name="New shopper")


def _dump(model) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _sync_database_url(database_url: str) -> str:
    return database_url.replace("+asyncpg", "+psycopg")
