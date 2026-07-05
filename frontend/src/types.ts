export type ClothingCategory =
  | "shirt"
  | "tshirt"
  | "trousers"
  | "jeans"
  | "dress"
  | "jacket"
  | "shoes"
  | "unknown"

export type CaptureSourceType = "manual" | "upload" | "browser_extension"
export type FitOutcome = "kept" | "returned" | "exchanged" | "wishlist" | "unknown"

export interface CategorySizePreference {
  category: ClothingCategory
  usual_size: string
  preferred_fit: "slim" | "regular" | "relaxed" | "oversized" | "cropped"
  notes?: string | null
}

export interface FitProfile {
  user_id: string
  display_name: string
  height_cm?: number | null
  weight_kg?: number | null
  body_notes?: string | null
  sensitivities: string[]
  category_preferences: CategorySizePreference[]
}

export interface UploadedAsset {
  path: string
  mime_type?: string | null
  original_name?: string | null
  public_url?: string | null
}

export interface CurrentUser {
  user_id: string
  subject: string
  provider: "local" | "clerk" | string
}

export interface UploadIntentResponse {
  bucket: string
  path: string
  provider: string
  upload_url: string
  upload_method: "PUT"
  public_url?: string | null
  max_upload_mb: number
  metadata: Record<string, string>
}

export interface ExtractedClaim {
  id: string
  subject: string
  predicate: string
  value: string
  source: string
  confidence: number
  status: "extracted" | "user_confirmed" | "rejected"
}

export interface SizeLabel {
  label: string
  system?: string | null
  region?: string | null
  audience?: string | null
}

export interface TextileComposition {
  material: string
  percentage?: number | null
  component?: string | null
}

export interface CareInstruction {
  instruction: string
  category?: string | null
}

export interface ProductIdentifier {
  kind: string
  value: string
}

export interface ProductAttribute {
  name: string
  value: string
}

export interface ProductDraft {
  brand?: string | null
  retailer?: string | null
  title?: string | null
  sku?: string | null
  url?: string | null
  category: ClothingCategory
  color?: string | null
  material?: string | null
  size_options: string[]
  size_labels: SizeLabel[]
  size_chart: Array<{ size: string; measurements: Array<{ name: string; value: number; unit: string }> }>
  fit_descriptors: string[]
  fabric_composition: TextileComposition[]
  care_instructions: CareInstruction[]
  origin_country?: string | null
  gender?: string | null
  product_identifiers: ProductIdentifier[]
  attributes: ProductAttribute[]
  extracted_claims: ExtractedClaim[]
}

export interface ProductSnapshot extends ProductDraft {
  id: string
  title: string
  source_capture_id?: string | null
}

export interface CaptureResponse {
  id: string
  user_id: string
  source_type: CaptureSourceType
  page_url?: string | null
  text_blocks: string[]
  assets: UploadedAsset[]
  user_notes?: string | null
  product_draft: ProductDraft
  product_snapshot?: ProductSnapshot | null
  confirmed: boolean
  memory_status: "not_indexed" | "indexing" | "indexed" | "failed" | string
  memory_error?: string | null
}

export interface PurchaseRecord {
  id: string
  user_id: string
  product_id: string
  purchased_size: string
  outcome: FitOutcome
  purchased_at?: string | null
  fit_rating: number
  comfort_rating: number
  silhouette_rating: number
  fit_notes?: string | null
}

export type PurchaseUpdate = Partial<Omit<PurchaseRecord, "id" | "user_id" | "product_id">>

export interface UserDataDeletionResult {
  profile_deleted: boolean
  captures_deleted: number
  products_deleted: number
  purchases_deleted: number
  saved_memories_deleted: number
  cognee_memory_deleted: boolean
}

export interface SystemStatus {
  app_name: string
  environment: string
  store_provider: string
  memory_provider: "cognee_local" | "cognee_cloud"
  atlas_provider: "seed" | "cognee_cloud" | "disabled"
  atlas_dataset_name: string
  upload_provider: string
  extraction_provider: string
  cognee_dataset_prefix: string
  cognee_cloud_configured: boolean
  cognee_timeout_seconds: number
  cloud_usage?: {
    live_usage_available: boolean
    billing_url: string
    token_price_usd_per_million: number
    note: string
  } | null
}

export interface RecommendationResponse {
  user_id: string
  product_id: string
  recommended_size?: string | null
  confidence: number
  summary: string
  risks: string[]
  evidence: Array<{ label: string; detail: string; source: string }>
}

export type MemoryDraftKind =
  | "product_fact"
  | "fit_preference"
  | "fit_outcome"
  | "brand_pattern"
  | "size_mapping"
  | "uncertainty"

export interface MemoryContextFact {
  text: string
  source: string
  score?: number | null
}

export interface AskEvidence {
  label: string
  detail: string
  source: string
}

export interface MemoryDraft {
  id: string
  kind: MemoryDraftKind
  subject: string
  text: string
  source: string
  confidence: number
  tags: string[]
}

export interface AskFitResponse {
  user_id: string
  question: string
  answer: string
  confidence: number
  evidence: AskEvidence[]
  recalled_facts: MemoryContextFact[]
  memory_drafts: MemoryDraft[]
}

export interface RememberMemoryDraftsResponse {
  user_id: string
  remembered: MemoryDraft[]
  memory_status: "indexed" | "failed" | string
  memory_error?: string | null
  memory_record?: SavedMemoryRecord | null
}

export interface SavedMemoryRecord {
  id: string
  user_id: string
  question: string
  answer: string
  product_id?: string | null
  capture_id?: string | null
  evidence: AskEvidence[]
  recalled_facts: MemoryContextFact[]
  remembered: MemoryDraft[]
  memory_status: "indexed" | "failed" | string
  memory_error?: string | null
  created_at: string
}
