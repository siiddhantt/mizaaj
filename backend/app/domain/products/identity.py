from app.domain.products.schemas import ProductDraft, ProductSnapshot


def fallback_title(draft: ProductDraft) -> str:
    category = category_title(draft.category.value)
    if draft.color and draft.category.value != "unknown":
        return f"{draft.color.title()} {category}"
    if draft.category.value != "unknown":
        return category
    if draft.color:
        return f"{draft.color.title()} clothing item"
    return "Clothing item"


def product_from_draft(
    draft: ProductDraft,
    *,
    source_capture_id,
    url: str | None = None,
) -> ProductSnapshot:
    return ProductSnapshot(
        brand=draft.brand,
        retailer=draft.retailer,
        title=draft.title or fallback_title(draft),
        sku=draft.sku,
        url=draft.url or url,
        category=draft.category,
        color=draft.color,
        material=draft.material,
        size_options=draft.size_options,
        size_labels=draft.size_labels,
        size_chart=draft.size_chart,
        fit_descriptors=draft.fit_descriptors,
        fabric_composition=draft.fabric_composition,
        care_instructions=draft.care_instructions,
        origin_country=draft.origin_country,
        gender=draft.gender,
        product_identifiers=draft.product_identifiers,
        attributes=draft.attributes,
        extracted_claims=draft.extracted_claims,
        source_capture_id=source_capture_id,
    )


def display_name(product: ProductSnapshot) -> str:
    brand = (product.brand or "").strip()
    title = product.title.strip()
    if brand and title.lower().startswith(brand.lower()):
        return title
    return " - ".join(part for part in [brand, title] if part)


def category_title(category: str) -> str:
    if category == "tshirt":
        return "T-shirt"
    if category == "unknown":
        return "Clothing item"
    return category.replace("_", " ").title()


def is_generic_title(title: str, category: str) -> bool:
    normalized = title.strip().lower()
    category_name = category_title(category).lower()
    return normalized in {
        "untitled captured item",
        "captured item",
        "captured clothing item",
        "clothing item",
        category,
        category_name,
        f"captured {category}",
        f"captured {category_name}",
    }
