import type {
  CaptureResponse,
  AskFitResponse,
  AskEvidence,
  CurrentUser,
  FitProfile,
  MemoryContextFact,
  MemoryDraft,
  ProductSnapshot,
  PurchaseRecord,
  PurchaseUpdate,
  RecommendationResponse,
  RememberMemoryDraftsResponse,
  SavedMemoryRecord,
  SystemStatus,
  UploadIntentResponse,
  UploadedAsset,
  UserDataDeletionResult,
} from "@/types"

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080/api/v1"
const defaultTimeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 120_000)
type AuthTokenProvider = () => Promise<string | null>

let authTokenProvider: AuthTokenProvider | null = null

export function setAuthTokenProvider(provider: AuthTokenProvider | null) {
  authTokenProvider = provider
}

export class MizaajApiError extends Error {
  readonly status?: number
  readonly code: "network" | "timeout" | "http" | "parse"

  constructor(message: string, code: MizaajApiError["code"], status?: number, cause?: unknown) {
    super(message, { cause })
    this.name = "MizaajApiError"
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const token = authTokenProvider ? await authTokenProvider() : null
  const timeoutMs = init?.timeoutMs ?? defaultTimeoutMs
  const { timeoutMs: _timeoutMs, ...requestInit } = init ?? {}
  void _timeoutMs
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...requestInit,
      signal: init?.signal ?? controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    })
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "AbortError"
    throw new MizaajApiError(
      timedOut
        ? "Mizaaj took too long to respond. Try again, or switch Cognee to Cloud for faster indexing."
        : `Could not reach Mizaaj API at ${apiBaseUrl}. Is the backend running?`,
      timedOut ? "timeout" : "network",
      undefined,
      error,
    )
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new MizaajApiError(
      errorDetail(body) ?? `Request failed with status ${response.status}`,
      "http",
      response.status,
    )
  }

  if (response.status === 204) return undefined as T

  try {
    return (await response.json()) as T
  } catch (error) {
    throw new MizaajApiError("Mizaaj returned an unreadable response.", "parse", response.status, error)
  }
}

function errorDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null
  const payload = body as Record<string, unknown>
  const error = payload.error

  if (error && typeof error === "object") {
    const message = (error as Record<string, unknown>).message
    if (typeof message === "string" && message.trim()) return message
  }

  if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail
  if (Array.isArray(payload.detail)) {
    const first = payload.detail.find((item) => item && typeof item === "object")
    const message = first ? (first as Record<string, unknown>).msg : null
    if (typeof message === "string" && message.trim()) return message
  }

  return null
}

export const api = {
  getSystemStatus() {
    return request<SystemStatus>("/system/status")
  },
  getCurrentUser() {
    return request<CurrentUser>("/auth/me")
  },
  getProfile(userId: string) {
    return request<FitProfile>(`/profiles/${userId}`)
  },
  updateProfile(userId: string, payload: Partial<FitProfile>) {
    return request<FitProfile>(`/profiles/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    })
  },
  listProducts() {
    return request<ProductSnapshot[]>("/products")
  },
  getProduct(productId: string) {
    return request<ProductSnapshot>(`/products/${productId}`)
  },
  deleteProduct(productId: string) {
    return request<ProductSnapshot>(`/products/${productId}`, {
      method: "DELETE",
    })
  },
  listCaptures(userId: string) {
    return request<CaptureResponse[]>(`/captures/users/${userId}`)
  },
  getCapture(captureId: string) {
    return request<CaptureResponse>(`/captures/${captureId}`)
  },
  deleteCapture(captureId: string) {
    return request<CaptureResponse>(`/captures/${captureId}`, {
      method: "DELETE",
    })
  },
  listPurchases(userId: string) {
    return request<PurchaseRecord[]>(`/purchases/user/${userId}`)
  },
  getPurchase(purchaseId: string) {
    return request<PurchaseRecord>(`/purchases/${purchaseId}`)
  },
  updatePurchase(purchaseId: string, payload: PurchaseUpdate) {
    return request<PurchaseRecord>(`/purchases/${purchaseId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    })
  },
  deletePurchase(purchaseId: string) {
    return request<PurchaseRecord>(`/purchases/${purchaseId}`, {
      method: "DELETE",
    })
  },
  listSavedMemories(userId: string) {
    return request<SavedMemoryRecord[]>(`/ask/memories/users/${userId}`)
  },
  createCapture(payload: {
    user_id: string
    source_type: "manual" | "upload"
    page_url?: string
    text_blocks: string[]
    assets: UploadedAsset[]
    user_notes?: string
  }) {
    return request<CaptureResponse>("/captures", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  confirmCapture(capture: CaptureResponse, acceptedClaimIds: string[]) {
    return request<CaptureResponse>(`/captures/${capture.id}/confirm`, {
      method: "POST",
      body: JSON.stringify({
        product_draft: capture.product_draft,
        accepted_claim_ids: acceptedClaimIds,
      }),
    })
  },
  createPurchase(payload: Omit<PurchaseRecord, "id">) {
    return request<PurchaseRecord>("/purchases", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  createUploadIntent(payload: { user_id: string; file_name: string; content_type: string }) {
    return request<UploadIntentResponse>("/uploads/intent", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  recommend(userId: string, productId: string, targetFit?: string) {
    return request<RecommendationResponse>("/recommendations", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, product_id: productId, target_fit: targetFit }),
    })
  },
  askMizaaj(payload: {
    user_id: string
    question: string
    product_id?: string
    capture_id?: string
    context_notes?: string
  }) {
    return request<AskFitResponse>("/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  rememberMemoryDrafts(payload: {
    user_id: string
    drafts: MemoryDraft[]
    question?: string
    answer?: string
    product_id?: string
    capture_id?: string
    evidence?: AskEvidence[]
    recalled_facts?: MemoryContextFact[]
  }) {
    return request<RememberMemoryDraftsResponse>("/ask/remember", {
      method: "POST",
      body: JSON.stringify(payload),
    })
  },
  deleteSavedMemory(memoryId: string) {
    return request<SavedMemoryRecord>(`/ask/memories/${memoryId}`, {
      method: "DELETE",
    })
  },
  deleteSavedMemories(userId: string) {
    return request<{ deleted: number }>(`/ask/memories/users/${userId}`, {
      method: "DELETE",
    })
  },
  clearCogneeMemory(userId: string) {
    return request<{ status: string; scope: string }>(`/memory/users/${userId}`, {
      method: "DELETE",
    })
  },
  deleteUserData(userId: string) {
    return request<UserDataDeletionResult>(`/memory/users/${userId}/app-data`, {
      method: "DELETE",
      timeoutMs: 180_000,
    })
  },
}
