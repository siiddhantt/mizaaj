from uuid import UUID

from app.core.errors import NotFoundError
from app.domain.ask.schemas import SavedMemoryRecord
from app.domain.captures.schemas import CaptureResponse
from app.domain.common import ClothingCategory, FitOutcome, FitPreference
from app.domain.privacy.schemas import UserDataDeletionResult
from app.domain.products.schemas import Measurement, ProductSnapshot, SizeMeasurementSet
from app.domain.profiles.schemas import CategorySizePreference, FitProfile, FitProfileUpdate
from app.domain.purchases.schemas import PurchaseRecord

LOCAL_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class InMemoryStore:
    def __init__(self):
        self.profiles: dict[UUID, FitProfile] = {}
        self.products: dict[UUID, ProductSnapshot] = {}
        self.captures: dict[UUID, CaptureResponse] = {}
        self.purchases: dict[UUID, PurchaseRecord] = {}
        self.memory_records: dict[UUID, SavedMemoryRecord] = {}

    def initialize(self) -> None:
        return None

    @classmethod
    def seeded(cls) -> "InMemoryStore":
        store = cls()
        store.profiles[LOCAL_USER_ID] = FitProfile(
            user_id=LOCAL_USER_ID,
            display_name="Sid",
            height_cm=178,
            sensitivities=["tight chest", "long sleeves", "scratchy fabric"],
            category_preferences=[
                CategorySizePreference(
                    category=ClothingCategory.shirt,
                    usual_size="M",
                    preferred_fit=FitPreference.relaxed,
                    notes="Avoid slim fits unless chest measurement is generous.",
                ),
                CategorySizePreference(
                    category=ClothingCategory.shoes,
                    usual_size="9",
                    preferred_fit=FitPreference.regular,
                    notes="Prefers wider toe box.",
                ),
            ],
        )
        products = [
            ProductSnapshot(
                brand="Uniqlo",
                retailer="Uniqlo",
                title="Oxford Regular Fit Shirt",
                category=ClothingCategory.shirt,
                material="cotton",
                size_options=["S", "M", "L", "XL"],
                size_chart=[
                    SizeMeasurementSet(
                        size="M",
                        measurements=[
                            Measurement(name="chest", value=108),
                            Measurement(name="length", value=74),
                        ],
                    )
                ],
            ),
            ProductSnapshot(
                brand="Zara",
                retailer="Zara",
                title="Linen Blend Relaxed Shirt",
                category=ClothingCategory.shirt,
                material="linen, cotton",
                size_options=["S", "M", "L", "XL"],
                size_chart=[
                    SizeMeasurementSet(
                        size="M",
                        measurements=[
                            Measurement(name="chest", value=104),
                            Measurement(name="length", value=73),
                        ],
                    )
                ],
            ),
        ]
        for product in products:
            store.products[product.id] = product
        kept = PurchaseRecord(
            user_id=LOCAL_USER_ID,
            product_id=products[0].id,
            purchased_size="M",
            outcome=FitOutcome.kept,
            fit_rating=5,
            comfort_rating=4,
            silhouette_rating=4,
            fit_notes="Shoulders and chest felt right; sleeves were acceptable.",
        )
        returned = PurchaseRecord(
            user_id=LOCAL_USER_ID,
            product_id=products[1].id,
            purchased_size="M",
            outcome=FitOutcome.returned,
            fit_rating=2,
            comfort_rating=3,
            silhouette_rating=3,
            fit_notes="Chest felt tight even though the relaxed silhouette looked good.",
        )
        store.purchases[kept.id] = kept
        store.purchases[returned.id] = returned
        return store

    def get_profile(self, user_id: UUID) -> FitProfile:
        profile = self.profiles.get(user_id)
        if profile is None:
            profile = FitProfile(user_id=user_id, display_name="New shopper")
            self.profiles[user_id] = profile
        return profile

    def update_profile(self, user_id: UUID, payload: FitProfileUpdate) -> FitProfile:
        current = self.get_profile(user_id)
        updated = FitProfile.model_validate(
            {
                **current.model_dump(mode="json"),
                **payload.model_dump(mode="json", exclude_none=True),
            }
        )
        self.profiles[user_id] = updated
        return updated

    def delete_profile(self, user_id: UUID) -> FitProfile:
        try:
            return self.profiles.pop(user_id)
        except KeyError as exc:
            raise NotFoundError("Fit profile not found") from exc

    def list_products(self) -> list[ProductSnapshot]:
        return list(self.products.values())

    def get_product(self, product_id: UUID) -> ProductSnapshot:
        try:
            return self.products[product_id]
        except KeyError as exc:
            raise NotFoundError("Product snapshot not found") from exc

    def save_product(self, product: ProductSnapshot) -> ProductSnapshot:
        self.products[product.id] = product
        return product

    def delete_product(self, product_id: UUID) -> ProductSnapshot:
        product = self.get_product(product_id)
        del self.products[product_id]
        return product

    def save_capture(self, capture: CaptureResponse) -> CaptureResponse:
        self.captures[capture.id] = capture
        return capture

    def get_capture(self, capture_id: UUID) -> CaptureResponse:
        try:
            return self.captures[capture_id]
        except KeyError as exc:
            raise NotFoundError("Capture not found") from exc

    def list_captures(self, user_id: UUID) -> list[CaptureResponse]:
        return [item for item in self.captures.values() if item.user_id == user_id]

    def delete_capture(self, capture_id: UUID) -> CaptureResponse:
        capture = self.get_capture(capture_id)
        del self.captures[capture_id]
        return capture

    def list_purchases(self, user_id: UUID) -> list[PurchaseRecord]:
        return [item for item in self.purchases.values() if item.user_id == user_id]

    def get_purchase(self, purchase_id: UUID) -> PurchaseRecord:
        try:
            return self.purchases[purchase_id]
        except KeyError as exc:
            raise NotFoundError("Purchase record not found") from exc

    def save_purchase(self, purchase: PurchaseRecord) -> PurchaseRecord:
        self.purchases[purchase.id] = purchase
        return purchase

    def delete_purchase(self, purchase_id: UUID) -> PurchaseRecord:
        purchase = self.get_purchase(purchase_id)
        del self.purchases[purchase_id]
        return purchase

    def list_saved_memories(self, user_id: UUID) -> list[SavedMemoryRecord]:
        records = [item for item in self.memory_records.values() if item.user_id == user_id]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_saved_memory(self, memory_id: UUID) -> SavedMemoryRecord:
        try:
            return self.memory_records[memory_id]
        except KeyError as exc:
            raise NotFoundError("Saved memory not found") from exc

    def save_memory_record(self, record: SavedMemoryRecord) -> SavedMemoryRecord:
        self.memory_records[record.id] = record
        return record

    def delete_memory_record(self, memory_id: UUID) -> SavedMemoryRecord:
        record = self.get_saved_memory(memory_id)
        del self.memory_records[memory_id]
        return record

    def delete_saved_memories(self, user_id: UUID) -> int:
        ids = [
            memory_id
            for memory_id, record in self.memory_records.items()
            if record.user_id == user_id
        ]
        for memory_id in ids:
            del self.memory_records[memory_id]
        return len(ids)

    def delete_user_data(self, user_id: UUID) -> UserDataDeletionResult:
        capture_ids = {capture.id for capture in self.list_captures(user_id)}
        product_ids = {
            product.id
            for product in self.products.values()
            if product.source_capture_id in capture_ids
        }
        purchase_ids = [
            purchase_id
            for purchase_id, purchase in self.purchases.items()
            if purchase.user_id == user_id or purchase.product_id in product_ids
        ]
        memory_ids = [
            memory_id
            for memory_id, record in self.memory_records.items()
            if record.user_id == user_id
        ]

        for purchase_id in purchase_ids:
            del self.purchases[purchase_id]
        for product_id in product_ids:
            del self.products[product_id]
        for capture_id in capture_ids:
            del self.captures[capture_id]
        for memory_id in memory_ids:
            del self.memory_records[memory_id]

        profile_deleted = self.profiles.pop(user_id, None) is not None
        return UserDataDeletionResult(
            profile_deleted=profile_deleted,
            captures_deleted=len(capture_ids),
            products_deleted=len(product_ids),
            purchases_deleted=len(purchase_ids),
            saved_memories_deleted=len(memory_ids),
        )
