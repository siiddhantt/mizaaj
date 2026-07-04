from enum import StrEnum


class ClothingCategory(StrEnum):
    shirt = "shirt"
    tshirt = "tshirt"
    trousers = "trousers"
    jeans = "jeans"
    dress = "dress"
    jacket = "jacket"
    shoes = "shoes"
    unknown = "unknown"


class FitOutcome(StrEnum):
    kept = "kept"
    returned = "returned"
    exchanged = "exchanged"
    wishlist = "wishlist"
    unknown = "unknown"


class FitPreference(StrEnum):
    slim = "slim"
    regular = "regular"
    relaxed = "relaxed"
    oversized = "oversized"
    cropped = "cropped"


class CaptureSourceType(StrEnum):
    manual = "manual"
    upload = "upload"
    browser_extension = "browser_extension"


class ClaimStatus(StrEnum):
    extracted = "extracted"
    user_confirmed = "user_confirmed"
    rejected = "rejected"
