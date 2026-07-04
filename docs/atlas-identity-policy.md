# Mizaaj Atlas Identity Policy

Mizaaj Atlas is a curated public evidence layer. It is not a public review pool, a private user memory, or a source of personal taste.

## Memory Priority

1. Private user memory.
2. Current uploaded product evidence.
3. Exact-product Atlas evidence.
4. Brand/category Atlas evidence.
5. Generic category guidance.

If private memory conflicts with Atlas, private memory wins. Atlas must be labeled as public product evidence in user-facing answers.

## Atlas Record Types

- `product`: a specific purchasable item or variant. It must have brand, retailer, title, category, canonical URL, region, and a stable identifier such as style number, SKU, article number, or product-page id.
- `brand_size_guide`: a brand, region, gender, and category size chart. It is reusable across matching products, but it must not be treated as a product-specific fit guarantee.
- `product_size_guide`: a size chart or garment-measurement table shown on a specific product page. It outranks a generic brand size guide for that product only.
- `category_signal`: brand/category guidance. It can explain uncertainty, but it must not produce confident product-specific advice.

## Public Data Boundaries

Atlas should store public evidence in separate records:

- Product identity and product-page facts: brand, retailer, title, canonical URL, stable identifiers, category, color, fit labels, material, construction, care, product-specific measurements, and source URL.
- Brand size guides: brand, region, gender, category scope, measurement method, size rows, units, source URL, and last verified date.
- Product size guides: product identity, measurement rows, units, source URL, and the exact product or variant they belong to.
- Brand/category caveats: source-backed statements such as "sizes vary by style, cut, and fabric" or "brand recommends one size smaller" when those statements are visible in public source material.

Atlas must not store user outcomes, user preferences, demo prompts, affiliate claims, pricing persuasion, stock status, star ratings, or unverified review claims.

## Size Chart Priority

1. Private user outcome for the same confirmed product.
2. Private user outcome for the same brand and category.
3. Product-specific size guide for an exact product match.
4. Brand size guide with matching brand, region, gender, and category.
5. Generic category guidance.

Brand size charts should be reusable references, not copied into every product record. Product records should reference a matching brand size guide and only carry product-specific measurements when the product page provides them.

## Product Matching Rules

- Exact match: canonical URL, style number, SKU, article number, barcode, or retailer product id.
- Strong match: same brand, same stable identifier, same category, and compatible color or variant.
- Candidate match: same brand, similar normalized title, same category, and compatible color. Candidate matches need user confirmation before linking.
- Weak match: same brand and category only. Weak matches can retrieve category-level Atlas guidance but cannot be used as a product identity.

Mizaaj must not auto-link two products using brand name alone, category alone, color alone, or visual similarity alone.

Semantic retrieval can rank evidence after deterministic filters reduce the search scope. It must not decide product identity by itself.

## Ambiguity Rules

When multiple products could match, Mizaaj should ask the user to choose an existing product, create a new product, or attach more evidence. The app should not silently merge memories into an existing product when identity confidence is low.

## Evidence Hygiene

Atlas seed records may contain:

- Source facts from public product pages or size guides.
- Non-personal derived rules with explicit basis fields and confidence.
- Source URLs and retrieval tags.

Atlas seed records must not contain:

- Demo questions.
- User preferences.
- Unverified social/review claims.
- Affiliate or pricing persuasion.
- Product recommendations that assume a specific user's body or taste.

## Answer Requirements

Ask responses that use Atlas must separate evidence labels:

- `Your memory`
- `Current item`
- `Mizaaj Atlas`

Atlas phrasing should use language like "public product evidence suggests" or "the brand size guide says." It should not say "you liked" or "you experienced" unless that fact came from private memory.
