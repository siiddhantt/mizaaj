import {
  ArrowLeft,
  ArrowUpRight,
  Camera,
  ChevronDown,
  Check,
  GitBranch,
  ImagePlus,
  Menu,
  MessageCircle,
  MemoryStick,
  Moon,
  Plus,
  Send,
  ShieldCheck,
  Shirt,
  Sparkles,
  Sun,
  Trash2,
  UserRound,
  X,
} from "lucide-react"
import { type ChangeEvent, lazy, type ReactNode, Suspense, useEffect, useMemo, useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { NotificationStack, useNotifications } from "@/components/notifications"
import { api, setAuthTokenProvider } from "@/lib/api"
import { cn } from "@/lib/utils"
import { confidenceLabel, normalizeSensitivities } from "@/lib/fit"
import { applyTheme, readStoredTheme, storeTheme, type Theme } from "@/lib/theme"
import { uploadCaptureFile } from "@/lib/uploads"
import type {
  CaptureResponse,
  AskEvidence,
  AskFitResponse,
  CurrentUser,
  FitOutcome,
  FitProfile,
  MemoryDraft,
  ProductSnapshot,
  PurchaseRecord,
  SavedMemoryRecord,
  SystemStatus,
  UploadedAsset,
} from "@/types"

const localUserId = import.meta.env.VITE_USER_ID ?? "00000000-0000-4000-8000-000000000001"
type AuthTokenProvider = () => Promise<string | null>
const AssistantMarkdown = lazy(() =>
  import("@/components/assistant-markdown").then((module) => ({ default: module.AssistantMarkdown })),
)

const navItems = [
  { id: "ask", label: "Ask", icon: Sparkles },
  { id: "capture", label: "Capture", icon: Camera },
  { id: "memory", label: "Memory", icon: MemoryStick },
  { id: "profile", label: "Profile", icon: UserRound },
] as const

type AppView = (typeof navItems)[number]["id"]
type CaptureAttachmentStatus = "uploading" | "uploaded" | "failed"

interface CaptureAttachment {
  id: string
  file: File
  fileName: string
  mimeType: string
  previewUrl: string | null
  status: CaptureAttachmentStatus
  asset?: UploadedAsset
  error?: string
}

interface MemoryProductItem {
  key: string
  product: ProductSnapshot
  sourceCapture?: CaptureResponse
  linkedMemories: SavedMemoryRecord[]
  purchases: PurchaseRecord[]
  derived: boolean
}

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  response?: AskFitResponse
}

const outcomeOptions: FitOutcome[] = ["kept", "returned", "exchanged"]
const activeViewStorageKey = "mizaaj.activeView"
const memoryProductRoutePrefix = "memory/product/"
const profileSensitivitySuggestions = [
  "shoulder tightness",
  "chest cling",
  "stomach cling",
  "sleeves run long",
  "fabric feels flimsy",
  "prefers relaxed drape",
]
const profileContextSuggestions = [
  "prefer clean minimal graphics",
  "avoid cling around chest and stomach",
  "like relaxed but not sloppy drape",
  "check shoulder seam before buying",
]

function isAppView(value: string | null): value is AppView {
  return navItems.some((item) => item.id === value)
}

function readInitialView(): AppView {
  if (typeof window === "undefined") return "ask"

  const hashView = window.location.hash.replace("#", "")
  if (hashView.startsWith(memoryProductRoutePrefix)) return "memory"
  if (isAppView(hashView)) return hashView

  const storedView = window.localStorage.getItem(activeViewStorageKey)
  if (isAppView(storedView)) return storedView

  return "ask"
}

function readInitialMemoryProductKey() {
  if (typeof window === "undefined") return ""
  return readMemoryProductKeyFromHash(window.location.hash)
}

function readMemoryProductKeyFromHash(hash: string) {
  const value = hash.replace("#", "")
  if (!value.startsWith(memoryProductRoutePrefix)) return ""
  return decodeURIComponent(value.slice(memoryProductRoutePrefix.length))
}

function memoryProductHash(productKey: string) {
  return `#${memoryProductRoutePrefix}${encodeURIComponent(productKey)}`
}

function createAttachmentId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function createPreviewUrl(file: File) {
  if (typeof URL === "undefined" || !URL.createObjectURL) return null
  return URL.createObjectURL(file)
}

function errorMessage(error: unknown, fallback = "Something went wrong") {
  return error instanceof Error ? error.message : fallback
}

export function App({
  authTokenProvider,
  userMenu,
}: {
  authTokenProvider?: AuthTokenProvider
  userMenu?: ReactNode
}) {
  const [activeView, setActiveView] = useState<AppView>(() => readInitialView())
  const [activeMemoryProductKey, setActiveMemoryProductKey] = useState(() => readInitialMemoryProductKey())
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme())
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState("Ready")
  const [appUserId, setAppUserId] = useState(localUserId)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [profile, setProfile] = useState<FitProfile | null>(null)
  const [products, setProducts] = useState<ProductSnapshot[]>([])
  const [purchases, setPurchases] = useState<PurchaseRecord[]>([])
  const [savedMemories, setSavedMemories] = useState<SavedMemoryRecord[]>([])
  const [memoryCaptures, setMemoryCaptures] = useState<Record<string, CaptureResponse>>({})
  const [selectedProductId, setSelectedProductId] = useState("")
  const [memoryProductId, setMemoryProductId] = useState("")
  const [navigationOpen, setNavigationOpen] = useState(false)
  const [askQuestion, setAskQuestion] = useState("")
  const [askContext, setAskContext] = useState("")
  const [askResponse, setAskResponse] = useState<AskFitResponse | null>(null)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [askingMizaaj, setAskingMizaaj] = useState(false)
  const [memorySheetOpen, setMemorySheetOpen] = useState(false)
  const [rememberingDrafts, setRememberingDrafts] = useState(false)
  const [deletingMemoryId, setDeletingMemoryId] = useState<string | null>(null)
  const [clearingMemories, setClearingMemories] = useState(false)
  const [selectedDraftIds, setSelectedDraftIds] = useState<Set<string>>(new Set())
  const [captureText, setCaptureText] = useState("")
  const [captureUrl, setCaptureUrl] = useState("")
  const [captureAttachments, setCaptureAttachments] = useState<CaptureAttachment[]>([])
  const [uploadInputVersion, setUploadInputVersion] = useState(0)
  const [extractingCapture, setExtractingCapture] = useState(false)
  const [confirmingCapture, setConfirmingCapture] = useState(false)
  const [latestCapture, setLatestCapture] = useState<CaptureResponse | null>(null)
  const [acceptedClaims, setAcceptedClaims] = useState<Set<string>>(new Set())
  const [purchaseSize, setPurchaseSize] = useState("M")
  const [purchaseOutcome, setPurchaseOutcome] = useState<FitOutcome>("kept")
  const [purchaseNotes, setPurchaseNotes] = useState("")
  const previewUrls = useRef<Set<string>>(new Set())
  const notifications = useNotifications()

  const captureAssets = useMemo(
    () => captureAttachments.flatMap((attachment) => (attachment.asset ? [attachment.asset] : [])),
    [captureAttachments],
  )
  const uploadingAttachmentCount = captureAttachments.filter(
    (attachment) => attachment.status === "uploading",
  ).length
  const failedAttachmentCount = captureAttachments.filter(
    (attachment) => attachment.status === "failed",
  ).length

  useEffect(() => {
    setAuthTokenProvider(authTokenProvider ?? null)
    void loadWorkspace()
    return () => setAuthTokenProvider(null)
  }, [authTokenProvider])

  useEffect(
    () => () => {
      previewUrls.current.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
      previewUrls.current.clear()
    },
    [],
  )

  useEffect(() => {
    window.localStorage.setItem(activeViewStorageKey, activeView)

    const nextHash =
      activeView === "memory" && activeMemoryProductKey
        ? memoryProductHash(activeMemoryProductKey)
        : `#${activeView}`

    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash)
    }
  }, [activeView, activeMemoryProductKey])

  useEffect(() => {
    function syncViewFromHash() {
      const hashView = window.location.hash.replace("#", "")
      if (hashView.startsWith(memoryProductRoutePrefix)) {
        setActiveView("memory")
        setActiveMemoryProductKey(readMemoryProductKeyFromHash(window.location.hash))
        return
      }
      if (isAppView(hashView)) {
        setActiveView(hashView)
        setActiveMemoryProductKey("")
      }
    }

    window.addEventListener("hashchange", syncViewFromHash)
    return () => window.removeEventListener("hashchange", syncViewFromHash)
  }, [])

  useEffect(() => {
    applyTheme(theme)
    storeTheme(theme)
  }, [theme])

  async function withStatus(action: () => Promise<void>) {
    setLoading(true)
    try {
      await action()
    } catch (error) {
      const message = errorMessage(error)
      setStatus(message)
      notifications.error("Action failed", message)
    } finally {
      setLoading(false)
    }
  }

  async function loadWorkspace() {
    await withStatus(async () => {
      const [currentUser, loadedSystemStatus] = await Promise.all([
        api.getCurrentUser(),
        api.getSystemStatus().catch(() => null),
      ])
      setAppUserId(currentUser.user_id)
      setCurrentUser(currentUser)
      setSystemStatus(loadedSystemStatus)
      const [
        loadedProfile,
        loadedProducts,
        loadedPurchases,
        loadedSavedMemories,
        loadedCaptures,
      ] = await Promise.all([
        api.getProfile(currentUser.user_id),
        api.listProducts(),
        api.listPurchases(currentUser.user_id),
        api.listSavedMemories(currentUser.user_id),
        api.listCaptures(currentUser.user_id).catch(() => []),
      ])
      setProfile(loadedProfile)
      setProducts(loadedProducts)
      setPurchases(loadedPurchases)
      setSavedMemories(loadedSavedMemories)
      setMemoryCaptures(Object.fromEntries(loadedCaptures.map((capture) => [capture.id, capture])))
      setSelectedProductId("")
      setStatus("Private memory loaded")
    })
  }

  async function saveProfile() {
    if (!profile) return
    await withStatus(async () => {
      const updated = await api.updateProfile(appUserId, profile)
      setProfile(updated)
      setStatus("Profile saved")
      notifications.success("Profile saved", "Your private memory is being kept in sync.")
    })
  }

  async function handleFiles(event: ChangeEvent<HTMLInputElement>, nextView: AppView = "capture") {
    const input = event.currentTarget
    const files = Array.from(input.files ?? [])
    input.value = ""
    setUploadInputVersion((current) => current + 1)
    if (!files.length) return

    setActiveView(nextView)
    setActiveMemoryProductKey("")
    setLatestCapture(null)
    setAcceptedClaims(new Set())
    if (nextView === "ask") setSelectedProductId("")
    const attachments = files.map((file) => {
      const previewUrl = createPreviewUrl(file)
      if (previewUrl) previewUrls.current.add(previewUrl)

      return {
        id: createAttachmentId(),
        file,
        fileName: file.name || "Camera photo",
        mimeType: file.type || "image/jpeg",
        previewUrl,
        status: "uploading" as const,
      }
    })

    setCaptureAttachments((current) => [...current, ...attachments])
    setStatus(`${attachments.length} photo${attachments.length > 1 ? "s" : ""} attaching`)

    const results = await Promise.all(attachments.map((attachment) => uploadAttachment(attachment)))
    const uploaded = results.filter(Boolean).length
    const failed = results.length - uploaded

    if (failed) {
      setStatus(`${uploaded} uploaded, ${failed} failed`)
      notifications.error("Some photos failed", "Retry failed images before extraction.")
    } else {
      setStatus(`${uploaded} photo${uploaded === 1 ? "" : "s"} attached`)
      notifications.success(`${uploaded} photo${uploaded === 1 ? "" : "s"} attached`)
    }
  }

  async function handleAskFiles(event: ChangeEvent<HTMLInputElement>) {
    await handleFiles(event, "ask")
  }

  async function uploadAttachment(attachment: CaptureAttachment) {
    try {
      const asset = await uploadCaptureFile(appUserId, attachment.file)
      setCaptureAttachments((current) =>
        current.map((item) =>
          item.id === attachment.id
            ? {
                ...item,
                asset,
                error: undefined,
                status: "uploaded",
              }
            : item,
        ),
      )
      return true
    } catch (error) {
      setCaptureAttachments((current) =>
        current.map((item) =>
          item.id === attachment.id
            ? {
                ...item,
                error: errorMessage(error, "Upload failed"),
                status: "failed",
              }
            : item,
        ),
      )
      return false
    }
  }

  function removeCaptureAttachment(attachment: CaptureAttachment) {
    if (attachment.previewUrl && previewUrls.current.has(attachment.previewUrl)) {
      URL.revokeObjectURL(attachment.previewUrl)
      previewUrls.current.delete(attachment.previewUrl)
    }

    setCaptureAttachments((current) => current.filter((item) => item.id !== attachment.id))
    setLatestCapture(null)
    setAcceptedClaims(new Set())
  }

  function clearCaptureAttachments() {
    captureAttachments.forEach((attachment) => {
      if (attachment.previewUrl && previewUrls.current.has(attachment.previewUrl)) {
        URL.revokeObjectURL(attachment.previewUrl)
        previewUrls.current.delete(attachment.previewUrl)
      }
    })
    setCaptureAttachments([])
    setLatestCapture(null)
    setAcceptedClaims(new Set())
    setStatus("Item evidence cleared")
  }

  function retryCaptureAttachment(id: string) {
    const attachment = captureAttachments.find((item) => item.id === id)
    if (!attachment) return

    setLatestCapture(null)
    setAcceptedClaims(new Set())

    setCaptureAttachments((current) =>
      current.map((item) =>
        item.id === id
          ? {
              ...item,
              error: undefined,
              status: "uploading",
            }
          : item,
      ),
    )

    void uploadAttachment(attachment).then((uploaded) => {
      setStatus(uploaded ? "Photo attached" : "Photo upload failed")
    })
  }

  async function extractCapture(nextView: AppView = "capture") {
    if (uploadingAttachmentCount) {
      setStatus("Wait for photos to finish uploading")
      return
    }

    const hasEvidence = Boolean(captureText.trim() || captureUrl.trim() || captureAssets.length)
    if (!hasEvidence) {
      setStatus(
        failedAttachmentCount
          ? "Photo upload failed. Retry it or add product text."
          : "Add a photo, page URL, or product text first.",
      )
      setActiveView("capture")
      return
    }

    setExtractingCapture(true)
    setStatus("Extracting draft...")
    try {
      await withStatus(async () => {
        const capture = await api.createCapture({
          user_id: appUserId,
          source_type: captureAssets.length ? "upload" : "manual",
          page_url: captureUrl || undefined,
          text_blocks: [captureText].filter(Boolean),
          assets: captureAssets,
          user_notes: purchaseNotes || undefined,
        })
        setLatestCapture(capture)
        setMemoryCaptures((current) => ({ ...current, [capture.id]: capture }))
        setAcceptedClaims(new Set(capture.product_draft.extracted_claims.map((claim) => claim.id)))
        setActiveView(nextView)
        setStatus(nextView === "ask" ? "Item context ready" : "Draft ready")
        notifications.success("Item details extracted", "Review the draft before saving it as memory.")
      })
    } finally {
      setExtractingCapture(false)
    }
  }

  async function confirmCapture() {
    if (!latestCapture) return
    setConfirmingCapture(true)
    setStatus("Remembering with Cognee...")
    try {
      await withStatus(async () => {
        const confirmed = await api.confirmCapture(latestCapture, [...acceptedClaims])
        setLatestCapture(confirmed)
        if (confirmed.product_snapshot) {
          setProducts((current) => [confirmed.product_snapshot as ProductSnapshot, ...current])
          setSelectedProductId(confirmed.product_snapshot.id)
        }
        setActiveView("ask")
        setStatus(confirmed.memory_status === "indexed" ? "Facts remembered" : "Product saved")
        notifications.success("Item remembered", "Mizaaj can now use this product in future answers.")
      })
    } finally {
      setConfirmingCapture(false)
    }
  }

  async function askMizaaj(question = askQuestion) {
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion) {
      setStatus("Ask a fit question first.")
      return
    }
    if (uploadingAttachmentCount) {
      setStatus("Wait for photos to finish uploading before asking.")
      return
    }
    if (captureAssets.length && !latestCapture) {
      setStatus("Extract item details first so Mizaaj can use the photos.")
      notifications.info("Extract item details first so Mizaaj can use the photos.")
      return
    }

    const userMessage: ChatMessage = {
      id: createAttachmentId(),
      role: "user",
      content: trimmedQuestion,
    }
    setAskingMizaaj(true)
    setChatMessages((current) => [...current, userMessage])
    setStatus("Mizaaj is reading your private memory...")
    try {
      await withStatus(async () => {
        const response = await api.askMizaaj({
          user_id: appUserId,
          question: trimmedQuestion,
          product_id: latestCapture?.product_snapshot?.id,
          capture_id: latestCapture?.id,
          context_notes: askContext.trim() || undefined,
        })
        setAskResponse(response)
        setChatMessages((current) => [
          ...current,
          {
            id: createAttachmentId(),
            role: "assistant",
            content: response.answer,
            response,
          },
        ])
        setSelectedDraftIds(new Set(response.memory_drafts.map((draft) => draft.id)))
        setMemorySheetOpen(false)
        setAskQuestion("")
        setStatus("Answer ready")
        if (response.confidence < 0.45) {
          notifications.info("Low-confidence answer", "Add item photos or a try-on outcome for stronger advice.")
        }
      })
    } finally {
      setAskingMizaaj(false)
    }
  }

  async function rememberAskDrafts() {
    if (!askResponse) return

    const drafts = askResponse.memory_drafts.filter((draft) => selectedDraftIds.has(draft.id))
    if (!drafts.length) {
      setStatus("Choose at least one memory card to save.")
      return
    }

    setRememberingDrafts(true)
    setStatus("Saving selected memory with Cognee...")
    try {
      await withStatus(async () => {
        const response = await api.rememberMemoryDrafts({
          user_id: appUserId,
          drafts,
          question: askResponse.question,
          answer: askResponse.answer,
          product_id: memoryProductId || latestCapture?.product_snapshot?.id,
          capture_id: latestCapture?.id,
          evidence: askResponse.evidence,
          recalled_facts: askResponse.recalled_facts,
        })
        if (response.memory_record) {
          setSavedMemories((current) => [response.memory_record as SavedMemoryRecord, ...current])
        }
        if (response.memory_record?.product_id) {
          const refreshedProducts = await api.listProducts()
          setProducts(refreshedProducts)
          if (latestCapture) {
            const refreshedCapture = await api.getCapture(latestCapture.id).catch(() => null)
            if (refreshedCapture) {
              setLatestCapture(refreshedCapture)
              setMemoryCaptures((current) => ({ ...current, [refreshedCapture.id]: refreshedCapture }))
            }
          }
        }
        setMemorySheetOpen(false)
        setStatus(response.memory_status === "indexed" ? "Memory saved" : "Memory save failed")
        if (response.memory_status === "indexed") {
          notifications.success("Memory saved", "This answer can now be recalled by Mizaaj.")
        } else {
          notifications.error("Memory save failed", response.memory_error ?? "The record is saved, but indexing failed.")
        }
      })
    } finally {
      setRememberingDrafts(false)
    }
  }

  async function deleteSavedMemory(memoryId: string) {
    setDeletingMemoryId(memoryId)
    setStatus("Deleting memory...")
    try {
      await withStatus(async () => {
        await api.deleteSavedMemory(memoryId)
        setSavedMemories((current) => current.filter((record) => record.id !== memoryId))
        setStatus("Memory deleted")
        notifications.success("Memory deleted")
      })
    } finally {
      setDeletingMemoryId(null)
    }
  }

  async function clearSavedMemories() {
    if (!savedMemories.length) return
    setClearingMemories(true)
    setStatus("Clearing saved memories...")
    try {
      await withStatus(async () => {
        const response = await api.deleteSavedMemories(appUserId)
        setSavedMemories([])
        setStatus(response.deleted ? "Saved memories cleared" : "No saved memories to clear")
        notifications.success(response.deleted ? "Saved memories cleared" : "No saved memories to clear")
      })
    } finally {
      setClearingMemories(false)
    }
  }

  function toggleMemoryDraft(id: string) {
    setSelectedDraftIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function prepareMemoryFromResponse(response: AskFitResponse) {
    setAskResponse(response)
    setMemoryProductId(latestCapture?.product_snapshot?.id || "")
    setSelectedDraftIds(new Set(response.memory_drafts.map((draft) => draft.id)))
    setMemorySheetOpen(true)
  }

  async function logPurchase() {
    const outcomeProductId = memoryProductId || latestCapture?.product_snapshot?.id || selectedProductId
    if (!outcomeProductId) return
    await withStatus(async () => {
      const purchase = await api.createPurchase({
        user_id: appUserId,
        product_id: outcomeProductId,
        purchased_size: purchaseSize,
        outcome: purchaseOutcome,
        fit_rating: purchaseOutcome === "kept" ? 4 : 2,
        comfort_rating: 4,
        silhouette_rating: 4,
        fit_notes: purchaseNotes,
      })
      setPurchases((current) => [purchase, ...current])
      setActiveView("memory")
      setActiveMemoryProductKey("")
      setStatus("Outcome remembered")
      notifications.success("Try-on outcome remembered", "Future answers can use this fit signal.")
    })
  }

  function toggleClaim(id: string) {
    setAcceptedClaims((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function updateSensitivities(value: string) {
    setProfile((current) =>
      current
        ? {
            ...current,
            sensitivities: normalizeSensitivities(value),
          }
        : current,
    )
  }

  function navigateToView(view: AppView) {
    setActiveView(view)
    if (view !== "memory") setActiveMemoryProductKey("")
    if (view === "memory") setActiveMemoryProductKey("")
    setNavigationOpen(false)
  }

  return (
    <TooltipProvider>
      <main className="app-shell min-h-dvh" aria-busy={loading}>
        <div className="ambient-grid" aria-hidden="true" />
        <header className="sticky top-0 z-30 border-b border-border/35 bg-background/70 backdrop-blur-2xl">
          <div className="mx-auto flex h-16 w-full max-w-[100dvw] items-center gap-3 px-3 sm:px-5 xl:px-8">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Open navigation"
                  className="rounded-full lg:hidden"
                  onClick={() => setNavigationOpen(true)}
                >
                  <Menu />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Menu</TooltipContent>
            </Tooltip>

            <div className="flex min-w-0 flex-1 items-center gap-3">
              <BrandMark />
            </div>

            {userMenu ? <div className="grid size-9 place-items-center">{userMenu}</div> : null}

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Toggle theme"
                  onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
                >
                  {theme === "dark" ? <Sun /> : <Moon />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Theme</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <Sheet open={navigationOpen} onOpenChange={setNavigationOpen}>
          <SheetContent
            side="left"
            className="glass-panel h-[100dvh] w-[min(22rem,calc(100dvw-1rem))] gap-0 overflow-hidden border-border/55 p-0"
          >
            <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 pt-14">
              <AppNavigation activeView={activeView} onSelect={navigateToView} compact />
            </div>
            <div className="shrink-0 p-4">
              <a
                href="https://github.com/siiddhantt"
                target="_blank"
                rel="noreferrer"
                className="glass-chip flex items-center justify-center gap-2 rounded-2xl px-3 py-2 text-sm font-medium text-muted-foreground transition hover:text-foreground"
              >
                <GitBranch className="size-4" />
                github.com/siiddhantt
              </a>
            </div>
          </SheetContent>
        </Sheet>

        <div
          className={cn(
            "grid w-full min-w-0 max-w-[100dvw] gap-5 px-3 pt-4 sm:px-5 lg:min-h-[calc(100dvh-5rem)] lg:grid-cols-[14rem_minmax(0,1fr)] lg:pb-6 lg:px-8 2xl:grid-cols-[16rem_minmax(0,1fr)]",
            activeView === "ask" ? "pb-5 sm:pb-6" : "pb-8",
          )}
        >
          <aside className="hidden lg:block">
            <div className="sticky top-20">
              <AppNavigation activeView={activeView} onSelect={navigateToView} />
            </div>
          </aside>

          <section className="min-w-0 max-w-full space-y-5 lg:min-h-[calc(100dvh-6rem)]">
            {activeView === "ask" ? (
              <AskView
                products={products}
                memoryProductId={memoryProductId}
                setMemoryProductId={setMemoryProductId}
                setSelectedProductId={setSelectedProductId}
                question={askQuestion}
                setQuestion={setAskQuestion}
                response={askResponse}
                asking={askingMizaaj}
                ask={askMizaaj}
                messages={chatMessages}
                prepareMemory={prepareMemoryFromResponse}
                memorySheetOpen={memorySheetOpen}
                setMemorySheetOpen={setMemorySheetOpen}
                selectedDraftIds={selectedDraftIds}
                toggleDraft={toggleMemoryDraft}
                rememberDrafts={rememberAskDrafts}
                rememberingDrafts={rememberingDrafts}
                captureAttachments={captureAttachments}
                uploadedCount={captureAssets.length}
                uploadingCount={uploadingAttachmentCount}
                failedCount={failedAttachmentCount}
                latestCapture={latestCapture}
                extractingCapture={extractingCapture}
                extractCapture={() => extractCapture("ask")}
                removeAttachment={removeCaptureAttachment}
                retryAttachment={retryCaptureAttachment}
                clearAttachments={clearCaptureAttachments}
                handleFiles={handleAskFiles}
                inputVersion={uploadInputVersion}
                purchaseSize={purchaseSize}
                setPurchaseSize={setPurchaseSize}
                purchaseOutcome={purchaseOutcome}
                setPurchaseOutcome={setPurchaseOutcome}
                purchaseNotes={purchaseNotes}
                setPurchaseNotes={setPurchaseNotes}
                logPurchase={logPurchase}
                onCapture={() => setActiveView("capture")}
              />
            ) : null}

            {activeView === "profile" ? (
              profile ? (
                <ProfileView
                  profile={profile}
                  systemStatus={systemStatus}
                  setProfile={setProfile}
                  updateSensitivities={updateSensitivities}
                  saveProfile={saveProfile}
                />
              ) : (
                <ProfileFallback status={status} onRetry={() => void loadWorkspace()} />
              )
            ) : null}

            {activeView === "capture" ? (
              <CaptureView
                status={status}
                captureText={captureText}
                setCaptureText={setCaptureText}
                captureUrl={captureUrl}
                setCaptureUrl={setCaptureUrl}
                captureAttachments={captureAttachments}
                uploadedCount={captureAssets.length}
                uploadingCount={uploadingAttachmentCount}
                failedCount={failedAttachmentCount}
                extracting={extractingCapture}
                handleFiles={handleFiles}
                inputVersion={uploadInputVersion}
                removeCaptureAttachment={removeCaptureAttachment}
                retryCaptureAttachment={retryCaptureAttachment}
                extractCapture={() => extractCapture("capture")}
                latestCapture={latestCapture}
                acceptedClaims={acceptedClaims}
                toggleClaim={toggleClaim}
                confirmCapture={confirmCapture}
                confirming={confirmingCapture}
              />
            ) : null}

            {activeView === "memory" ? (
              <MemoryView
                purchases={purchases}
                products={products}
                savedMemories={savedMemories}
                memoryCaptures={memoryCaptures}
                activeProductKey={activeMemoryProductKey}
                onOpenProduct={(productKey) => {
                  setActiveView("memory")
                  setActiveMemoryProductKey(productKey)
                }}
                onBackToMemory={() => setActiveMemoryProductKey("")}
                deletingMemoryId={deletingMemoryId}
                clearingMemories={clearingMemories}
                onDeleteMemory={(memoryId) => void deleteSavedMemory(memoryId)}
                onClearMemories={() => void clearSavedMemories()}
              />
            ) : null}
          </section>

        </div>

        <NotificationStack notifications={notifications.notifications} onDismiss={notifications.dismiss} />
      </main>
    </TooltipProvider>
  )
}

function AppNavigation({
  activeView,
  onSelect,
  compact = false,
}: {
  activeView: AppView
  onSelect: (view: AppView) => void
  compact?: boolean
}) {
  const items = (
    <div className="space-y-1">
      {navItems.map((item) => (
        <button
          key={item.id}
          className={cn(
            "flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left text-sm font-medium text-muted-foreground transition-colors",
            compact && "h-12 rounded-[1.35rem] px-4",
            activeView === item.id
              ? "bg-primary/12 text-primary"
              : "hover:bg-accent/70 hover:text-accent-foreground",
          )}
          onClick={() => onSelect(item.id)}
        >
          <item.icon className="size-4" />
          {item.label}
        </button>
      ))}
    </div>
  )

  if (compact) {
    return items
  }

  return (
    <Card className="glass-panel rounded-[1.75rem] border-border/55 bg-card/78 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Workspace</CardTitle>
        <CardDescription>Private fit memory</CardDescription>
      </CardHeader>
      <CardContent className="px-3 pb-3">{items}</CardContent>
    </Card>
  )
}

function BrandMark() {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="mizaaj-brand-chip relative flex size-8 shrink-0 items-center justify-center rounded-full">
        <span className="mizaaj-mark-glow absolute inset-1 rounded-full" />
        <span className="mizaaj-mark-dot relative size-2 rounded-full" />
      </span>
      <span className="min-w-0">
        <span className="block truncate font-display text-xl font-normal leading-none tracking-tight text-foreground">
          Mizaaj
        </span>
        <span className="mt-1 block truncate text-xs font-normal italic leading-none text-muted-foreground sm:text-sm">
          Your taste, remembered.
        </span>
      </span>
    </div>
  )
}

function AskView({
  products,
  memoryProductId,
  setMemoryProductId,
  setSelectedProductId,
  question,
  setQuestion,
  response,
  asking,
  ask,
  messages,
  prepareMemory,
  memorySheetOpen,
  setMemorySheetOpen,
  selectedDraftIds,
  toggleDraft,
  rememberDrafts,
  rememberingDrafts,
  captureAttachments,
  uploadedCount,
  uploadingCount,
  failedCount,
  latestCapture,
  extractingCapture,
  extractCapture,
  removeAttachment,
  retryAttachment,
  clearAttachments,
  handleFiles,
  inputVersion,
  purchaseSize,
  setPurchaseSize,
  purchaseOutcome,
  setPurchaseOutcome,
  purchaseNotes,
  setPurchaseNotes,
  logPurchase,
  onCapture,
}: {
  products: ProductSnapshot[]
  memoryProductId: string
  setMemoryProductId: (value: string) => void
  setSelectedProductId: (value: string) => void
  question: string
  setQuestion: (value: string) => void
  response: AskFitResponse | null
  asking: boolean
  ask: (question?: string) => Promise<void>
  messages: ChatMessage[]
  prepareMemory: (response: AskFitResponse) => void
  memorySheetOpen: boolean
  setMemorySheetOpen: (open: boolean) => void
  selectedDraftIds: Set<string>
  toggleDraft: (id: string) => void
  rememberDrafts: () => Promise<void>
  rememberingDrafts: boolean
  captureAttachments: CaptureAttachment[]
  uploadedCount: number
  uploadingCount: number
  failedCount: number
  latestCapture: CaptureResponse | null
  extractingCapture: boolean
  extractCapture: () => Promise<void>
  removeAttachment: (attachment: CaptureAttachment) => void
  retryAttachment: (id: string) => void
  clearAttachments: () => void
  handleFiles: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
  inputVersion: number
  purchaseSize: string
  setPurchaseSize: (value: string) => void
  purchaseOutcome: FitOutcome
  setPurchaseOutcome: (value: FitOutcome) => void
  purchaseNotes: string
  setPurchaseNotes: (value: string) => void
  logPurchase: () => Promise<void>
  onCapture: () => void
}) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const prompts = [
    "Should I size up?",
    "Will this match my taste?",
    "What should I remember?",
  ]
  const hasDraftQuestion = question.trim().length > 0
  const hasConversation = messages.length > 0 || asking
  const selectedDraftCount = response?.memory_drafts.filter((draft) => selectedDraftIds.has(draft.id)).length ?? 0
  const attachmentStatus = uploadingCount
    ? `${uploadingCount} uploading`
    : failedCount
      ? `${failedCount} failed, ${uploadedCount} ready`
      : captureAttachments.length
        ? latestCapture
          ? "Item details ready"
          : `${uploadedCount} attached`
        : "No item attached"
  const canExtractAttachment = captureAttachments.length > 0 && uploadedCount > 0 && !latestCapture
  const showAttachmentStatus =
    captureAttachments.length > 0 || uploadingCount > 0 || failedCount > 0 || canExtractAttachment

  useEffect(() => {
    const composer = composerRef.current
    if (!composer) return

    composer.style.height = "auto"
    composer.style.height = `${Math.min(composer.scrollHeight, 144)}px`
  }, [question])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: "end", behavior: "smooth" })
  }, [messages.length, asking])

  return (
    <div className="mx-auto w-full max-w-6xl">
      <section className="glass-panel flex h-[calc(100dvh-6.5rem)] min-h-0 min-w-0 flex-col overflow-hidden rounded-[1.75rem] sm:h-[calc(100dvh-7rem)] sm:rounded-[2.25rem] lg:h-[calc(100dvh-7rem)]">
        <div
          className={cn(
            "shrink-0 border-b border-border/45 px-4 sm:px-6",
            hasConversation ? "py-2.5 sm:py-3" : "py-3 sm:py-4",
          )}
        >
          <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0">
              <h2
                className={cn(
                  "font-display font-normal leading-tight text-gradient",
                  hasConversation ? "text-xl sm:text-2xl" : "text-[1.6rem] sm:text-4xl",
                )}
              >
                Ask Mizaaj.
              </h2>
              <p
                className={cn(
                  "mt-1 hidden max-w-2xl font-display text-sm italic leading-6 text-muted-foreground sm:block",
                  hasConversation && "lg:hidden",
                )}
              >
                Your taste remembers what size charts forget.
              </p>
            </div>
            <div className="grid w-full min-w-0 grid-cols-2 gap-2 sm:w-auto sm:grid-cols-none sm:flex sm:flex-wrap sm:items-center sm:justify-end">
              <CapturePillInput
                id="ask-camera"
                icon={<Camera />}
                label="Take photo"
                capture="environment"
                inputVersion={inputVersion}
                onChange={handleFiles}
              />
              <CapturePillInput
                id="ask-gallery"
                icon={<ImagePlus />}
                label="Add images"
                multiple
                inputVersion={inputVersion}
                onChange={handleFiles}
              />
              <Button
                variant="outline"
                className="col-span-2 h-10 min-w-0 justify-center rounded-full bg-background/35 px-3 text-xs sm:col-span-1 sm:w-auto sm:px-4 sm:text-sm"
                onClick={onCapture}
              >
                <Plus />
                Build memory
              </Button>
            </div>
          </div>
          {showAttachmentStatus || latestCapture ? (
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2 text-xs text-muted-foreground sm:mt-4">
              {showAttachmentStatus ? (
                <span className="glass-chip max-w-full truncate rounded-full px-3 py-1.5">{attachmentStatus}</span>
              ) : null}
              {canExtractAttachment ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 max-w-full rounded-full bg-background/35 px-3 text-xs"
                  onClick={() => void extractCapture()}
                  disabled={extractingCapture || uploadingCount > 0}
                >
                  <Sparkles className="size-3.5" />
                  <span className="truncate">{extractingCapture ? "Extracting..." : "Extract item details"}</span>
                </Button>
              ) : null}
              {latestCapture && !latestCapture.confirmed ? (
                <span className="glass-chip max-w-full truncate rounded-full px-3 py-1.5 text-icy">
                  Temporary item context
                </span>
              ) : null}
            </div>
          ) : null}
          {captureAttachments.length && !hasConversation ? (
            <AskAttachmentTray
              attachments={captureAttachments}
              onRemove={removeAttachment}
              onRetry={retryAttachment}
              onClear={clearAttachments}
            />
          ) : null}
        </div>

        <div
          className={cn(
            "min-h-0 flex-1 space-y-4 scroll-smooth px-4 pb-4 pt-4 sm:px-6 sm:pb-7 sm:pt-5 lg:px-8",
            messages.length || asking ? "overflow-y-auto" : "overflow-hidden",
          )}
        >
          {messages.length ? (
            messages.map((message) => (
              <ChatBubble
                key={message.id}
                message={message}
                onPrepareMemory={prepareMemory}
              />
            ))
          ) : (
            <div
              className={cn(
                "grid h-full min-h-0 place-items-center overflow-hidden rounded-[1.5rem] border border-dashed border-border/60 bg-background/18 px-4 py-6 text-center sm:min-h-[20rem] sm:p-6",
                hasDraftQuestion && "max-sm:hidden",
              )}
            >
              <div className="min-w-0">
                <div className="mx-auto mb-3 grid size-10 place-items-center rounded-full bg-primary/10 text-primary sm:mb-4 sm:size-12">
                  <MessageCircle className="size-4 sm:size-5" />
                </div>
                <p className="text-sm font-medium sm:text-base">Start with the thing you are unsure about.</p>
                <p className="mx-auto mt-1.5 max-w-md text-xs leading-5 text-muted-foreground max-[430px]:hidden sm:mt-2 sm:text-sm sm:leading-6">
                  Ask about size, drape, fabric feel, or what Mizaaj should remember.
                </p>
                {!hasDraftQuestion ? (
                  <div className="mx-auto mt-4 flex max-w-[min(30rem,100%)] flex-wrap justify-center gap-2 max-[430px]:hidden sm:mt-5">
                    {prompts.map((prompt) => (
                      <button
                        key={prompt}
                        className="min-h-7 max-w-full rounded-full border border-border/55 bg-background/45 px-3 py-1 text-center text-xs font-medium leading-tight text-muted-foreground backdrop-blur transition-colors hover:border-primary/35 hover:text-foreground"
                        onClick={() => {
                          void ask(prompt)
                        }}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          )}
          {asking ? (
            <div className="flex justify-start">
              <div className="glass-chip rounded-[1.35rem] px-4 py-3 text-sm text-muted-foreground">
                Reading private memory...
              </div>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>

        <div className="relative shrink-0 bg-gradient-to-t from-background/92 via-background/58 to-transparent px-3 pb-[calc(env(safe-area-inset-bottom)+1rem)] pt-4 backdrop-blur-xl sm:px-5 sm:pb-5 sm:pt-6 lg:px-8">
          <div className="mx-auto w-full max-w-5xl">
            <div className="flex min-w-0 items-end gap-2 rounded-[2rem] border border-border/55 bg-card/78 p-1.5 shadow-xl shadow-black/12 backdrop-blur-2xl sm:p-2">
              <textarea
                ref={composerRef}
                id="ask-question"
                aria-label="Ask Mizaaj"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask what fits your taste..."
                rows={1}
                className="max-h-28 min-h-12 min-w-0 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-4 py-3 text-base leading-6 text-foreground shadow-none outline-none placeholder:text-muted-foreground focus:ring-0 sm:max-h-36"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    void ask()
                  }
                }}
              />
              <Button
                size="lg"
                aria-label="Send question to Mizaaj"
                className="size-12 rounded-full px-0 sm:w-auto sm:px-5"
                onClick={() => void ask()}
                disabled={asking}
              >
                <Send />
                <span className="hidden sm:inline">{asking ? "Asking" : "Ask"}</span>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Sheet open={memorySheetOpen} onOpenChange={setMemorySheetOpen}>
        <SheetContent
          className="glass-panel h-[100dvh] w-full gap-0 overflow-hidden border-border/55 p-0 sm:max-w-lg"
          side="right"
        >
          <SheetHeader className="shrink-0 border-b border-border/50 p-5 pr-12">
            <SheetTitle>Remember from this chat</SheetTitle>
            <SheetDescription>
              Approve the facts worth recalling next time. Nothing becomes memory until you save it.
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
            {response ? (
              <>
                <div className="rounded-2xl border border-border/55 bg-background/35 p-3">
                  <Label htmlFor="memory-product-link" className="text-sm font-medium">
                    Product identity
                  </Label>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Link this chat and any attached photos to an existing product, or keep it as a general memory.
                  </p>
                  <Select
                    value={memoryProductId || "unlinked"}
                    onValueChange={(value) => {
                      const productId = value === "unlinked" ? "" : value
                      setMemoryProductId(productId)
                      if (productId) setSelectedProductId(productId)
                    }}
                  >
                    <SelectTrigger id="memory-product-link" className="mt-3 w-full min-w-0 rounded-2xl bg-background/45">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unlinked">General fit memory</SelectItem>
                      {products.map((product) => (
                        <SelectItem key={product.id} value={product.id}>
                          {productDisplayName(product)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">Suggested memory cards</p>
                  <Badge variant="outline" className="glass-chip rounded-full">
                    {selectedDraftCount} selected
                  </Badge>
                </div>
                <div className="space-y-3">
                  {response.memory_drafts.map((draft) => (
                    <MemoryDraftCard
                      key={draft.id}
                      draft={draft}
                      selected={selectedDraftIds.has(draft.id)}
                      onToggle={() => toggleDraft(draft.id)}
                    />
                  ))}
                </div>
                <details className="group rounded-2xl border border-border/55 bg-background/35 p-3">
                  <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium">
                    Also save try-on outcome
                    <ChevronDown className="size-4 transition-transform group-open:rotate-180" />
                  </summary>
                  <div className="mt-4 space-y-3">
                    <Input
                      value={purchaseSize}
                      placeholder="Size"
                      className="rounded-2xl bg-background/45"
                      onChange={(event) => setPurchaseSize(event.target.value)}
                    />
                    <Select value={purchaseOutcome} onValueChange={(value) => setPurchaseOutcome(value as FitOutcome)}>
                      <SelectTrigger className="w-full min-w-0 rounded-2xl bg-background/45">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {outcomeOptions.map((outcome) => (
                          <SelectItem key={outcome} value={outcome}>
                            {outcome}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Textarea
                      value={purchaseNotes}
                      placeholder="Shoulders, chest, fabric feel, silhouette..."
                      className="min-h-24 rounded-2xl bg-background/45"
                      onChange={(event) => setPurchaseNotes(event.target.value)}
                    />
                    <Button
                      className="w-full rounded-2xl"
                      onClick={logPurchase}
                      disabled={!(memoryProductId || latestCapture?.product_snapshot?.id)}
                    >
                      <Check />
                      Remember outcome
                    </Button>
                  </div>
                </details>
              </>
            ) : (
              <EmptyState icon={<MemoryStick />} title="No reply selected" detail="Ask Mizaaj first, then remember a reply." />
            )}
          </div>
          <SheetFooter className="shrink-0 border-t border-border/50 bg-background/92 p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] backdrop-blur-xl sm:p-5">
            <Button
              className="w-full rounded-2xl"
              onClick={rememberDrafts}
              disabled={!response || rememberingDrafts || selectedDraftCount === 0}
            >
              <MemoryStick />
              {rememberingDrafts ? "Saving memory..." : "Save selected memory"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  )
}

function ChatBubble({
  message,
  onPrepareMemory,
}: {
  message: ChatMessage
  onPrepareMemory: (response: AskFitResponse) => void
}) {
  const isUser = message.role === "user"

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[min(56rem,96%)] rounded-[1.5rem] border px-4 py-3 text-sm leading-6 shadow-sm",
          isUser
            ? "border-primary/20 bg-primary text-primary-foreground"
            : "border-border/70 bg-background/42 backdrop-blur-xl",
        )}
      >
        {!isUser ? (
          <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-icy">
            <Sparkles className="size-3" />
            Mizaaj
          </div>
        ) : null}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <Suspense fallback={<p className="whitespace-pre-wrap">{message.content}</p>}>
            <AssistantMarkdown content={message.content} />
          </Suspense>
        )}
        {message.response ? (
          <div className="mt-4 space-y-3">
            <div className="flex min-w-0 flex-wrap gap-2">
              {message.response.evidence.slice(0, 4).map((item) => (
                <Badge
                  key={`${item.label}-${item.source}`}
                  variant="outline"
                  className="glass-chip max-w-full truncate rounded-full"
                >
                  {formatEvidenceLabel(item)}
                </Badge>
              ))}
              <Badge variant="outline" className="glass-chip max-w-full truncate rounded-full">
                {confidenceLabel(message.response.confidence)}
              </Badge>
            </div>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-muted-foreground">
                Why Mizaaj said this
                <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" />
              </summary>
              <div className="mt-2 space-y-2">
                {message.response.evidence.length ? (
                  message.response.evidence.map((item) => (
                    <div key={`${item.source}-${item.detail}`} className="rounded-xl border border-border/50 bg-background/35 p-3">
                      <p className="text-xs font-medium">{formatEvidenceLabel(item)}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {formatEvidenceDetail(item)}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl border border-border/50 bg-background/35 p-3 text-xs leading-5 text-muted-foreground">
                    No saved memory matched strongly yet. Add item photos or remember a try-on outcome to ground future answers.
                  </p>
                )}
              </div>
            </details>
            <Button
              variant="outline"
              size="sm"
              className="rounded-full bg-background/35"
              onClick={() => onPrepareMemory(message.response as AskFitResponse)}
            >
              <MemoryStick />
              Remember this
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function CapturePillInput({
  id,
  icon,
  label,
  multiple = false,
  capture,
  inputVersion,
  onChange,
}: {
  id: string
  icon: ReactNode
  label: string
  multiple?: boolean
  capture?: "environment" | "user"
  inputVersion: number
  onChange: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
}) {
  return (
    <label
      htmlFor={id}
      className="inline-flex h-10 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-full border border-border bg-background/35 px-3 text-xs font-medium shadow-xs backdrop-blur transition-colors hover:bg-accent hover:text-accent-foreground sm:w-auto sm:shrink-0 sm:px-4 sm:text-sm"
    >
      {icon}
      <span className="truncate">{label}</span>
      <input
        key={`${id}-${inputVersion}`}
        id={id}
        className="sr-only"
        type="file"
        accept="image/*"
        capture={capture}
        multiple={multiple}
        onChange={onChange}
      />
    </label>
  )
}

function AskAttachmentTray({
  attachments,
  onRemove,
  onRetry,
  onClear,
}: {
  attachments: CaptureAttachment[]
  onRemove: (attachment: CaptureAttachment) => void
  onRetry: (id: string) => void
  onClear: () => void
}) {
  return (
    <div className="mt-3 overflow-hidden rounded-[1.35rem] border border-border/45 bg-background/25 p-2 backdrop-blur-xl">
      <div className="mb-2 flex items-center justify-between gap-3 px-1">
        <p className="text-xs font-medium text-muted-foreground">
          {attachments.length} photo{attachments.length === 1 ? "" : "s"} attached
        </p>
        <button
          type="button"
          className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          onClick={onClear}
        >
          Clear
        </button>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {attachments.map((attachment) => {
          const imageUrl = attachment.previewUrl ?? attachment.asset?.public_url ?? undefined
          return (
            <div
              key={attachment.id}
              className="relative size-20 shrink-0 overflow-hidden rounded-2xl border border-border/55 bg-muted/45"
            >
              {imageUrl ? (
                <img
                  src={imageUrl}
                  alt={attachment.fileName}
                  className="size-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="grid size-full place-items-center text-muted-foreground">
                  <ImagePlus className="size-5" />
                </div>
              )}
              <button
                type="button"
                aria-label={`Remove ${attachment.fileName}`}
                className="absolute right-1 top-1 grid size-6 place-items-center rounded-full bg-background/85 text-foreground shadow-sm backdrop-blur"
                onClick={() => onRemove(attachment)}
              >
                <X className="size-3" />
              </button>
              <span className="absolute bottom-1 left-1 rounded-full bg-background/85 px-1.5 py-0.5 text-[10px] font-medium backdrop-blur">
                {attachment.status === "uploaded"
                  ? "Ready"
                  : attachment.status === "failed"
                    ? "Failed"
                    : "Uploading"}
              </span>
              {attachment.status === "failed" ? (
                <button
                  type="button"
                  className="absolute inset-x-1 top-8 rounded-full bg-background/90 px-1.5 py-0.5 text-[10px] font-medium"
                  onClick={() => onRetry(attachment.id)}
                >
                  Retry
                </button>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function MemoryDraftCard({
  draft,
  selected,
  onToggle,
}: {
  draft: MemoryDraft
  selected: boolean
  onToggle: () => void
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        "flex w-full min-w-0 items-start gap-3 rounded-2xl border p-3 text-left transition-colors",
        selected
          ? "border-primary/45 bg-primary/10"
          : "border-border/55 bg-background/35 hover:bg-muted/45",
      )}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onToggle()
        }
      }}
    >
      <Checkbox checked={selected} className="mt-0.5" />
      <span className="min-w-0">
        <span className="block text-xs font-semibold uppercase text-muted-foreground">
          {draft.kind.replaceAll("_", " ")}
        </span>
        <span className="mt-1 block break-words text-sm leading-6">{draft.text}</span>
      </span>
    </div>
  )
}

function ProfileView({
  profile,
  systemStatus,
  setProfile,
  updateSensitivities,
  saveProfile,
}: {
  profile: FitProfile
  systemStatus: SystemStatus | null
  setProfile: (update: (current: FitProfile | null) => FitProfile | null) => void
  updateSensitivities: (value: string) => void
  saveProfile: () => Promise<void>
}) {
  const memoryProvider = systemStatus?.memory_provider.replace("_", " ") ?? "memory"
  const cloudEnabled = systemStatus?.memory_provider === "cognee_cloud"

  function addSensitivity(value: string) {
    setProfile((current) =>
      current
        ? {
            ...current,
            sensitivities: normalizeSensitivities([...current.sensitivities, value].join(", ")),
          }
        : current,
    )
  }

  function addProfileContext(value: string) {
    setProfile((current) => {
      if (!current) return current
      const currentNotes = current.body_notes?.trim()
      if (currentNotes?.toLowerCase().includes(value.toLowerCase())) return current
      return {
        ...current,
        body_notes: [currentNotes, value].filter(Boolean).join(", "),
      }
    })
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <section className="glass-panel overflow-hidden rounded-[2rem] p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <Badge variant="outline" className="glass-chip w-fit rounded-full px-3 py-1">
              <ShieldCheck className="size-3.5" />
              Private to your account
            </Badge>
            <h2 className="mt-5 font-display text-4xl font-normal leading-tight text-gradient sm:text-5xl">
              Build your fit taste.
            </h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base">
              Add the body context and comfort signals Mizaaj should weigh before it answers size,
              silhouette, fabric, and try-on questions.
            </p>
          </div>
          <div className="grid gap-2 sm:min-w-72 sm:grid-cols-2 lg:grid-cols-1">
            <div className="rounded-[1.5rem] border border-border/55 bg-background/35 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Recall engine</p>
              <p className="mt-2 text-lg font-semibold capitalize">{memoryProvider}</p>
            </div>
            <div className="rounded-[1.5rem] border border-border/55 bg-background/35 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Saved signals</p>
              <p className="mt-2 text-lg font-semibold">{profile.sensitivities.length}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(20rem,0.65fr)]">
        <section className="glass-panel rounded-[2rem] p-5 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-xl font-semibold">Fit profile</h3>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Keep this lightweight. Mizaaj gets sharper when outcomes and saved chats add evidence later.
              </p>
            </div>
            <Button onClick={saveProfile} className="w-full rounded-full sm:w-auto">
              <Check />
              Save profile
            </Button>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Field label="Display name" htmlFor="display-name">
              <Input
                id="display-name"
                value={profile.display_name}
                placeholder="Sid"
                onChange={(event) =>
                  setProfile((current) =>
                    current ? { ...current, display_name: event.target.value } : current,
                  )
                }
              />
            </Field>
            <Field label="Height" htmlFor="height">
              <Input
                id="height"
                type="number"
                value={profile.height_cm ?? ""}
                placeholder="Height in cm"
                onChange={(event) =>
                  setProfile((current) =>
                    current ? { ...current, height_cm: Number(event.target.value) || null } : current,
                  )
                }
              />
            </Field>
          </div>

          <div className="mt-5 space-y-3">
            <Field label="Fit signals Mizaaj should remember" htmlFor="sensitivities">
              <Textarea
                id="sensitivities"
                value={profile.sensitivities.join(", ")}
                onChange={(event) => updateSensitivities(event.target.value)}
                placeholder="Example: avoid clingy chest fit, prefer relaxed shoulders, check sleeve length..."
                className="min-h-32 rounded-[1.5rem]"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              {profileSensitivitySuggestions.map((suggestion) => {
                const selected = profile.sensitivities.includes(suggestion)
                return (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => addSensitivity(suggestion)}
                    disabled={selected}
                    className={cn(
                      "rounded-full border border-border/60 bg-background/35 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-primary/45 hover:text-foreground disabled:cursor-default disabled:border-primary/35 disabled:bg-primary/15 disabled:text-foreground",
                    )}
                  >
                    {suggestion}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="mt-5 space-y-3">
            <Field label="Personal context" htmlFor="body-notes">
              <Textarea
                id="body-notes"
                value={profile.body_notes ?? ""}
                onChange={(event) =>
                  setProfile((current) =>
                    current ? { ...current, body_notes: event.target.value } : current,
                  )
                }
                placeholder="Example: I like black tees with subtle artwork, relaxed drape, and no cling around chest or stomach."
                className="min-h-28 rounded-[1.5rem]"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              {profileContextSuggestions.map((suggestion) => {
                const selected = profile.body_notes?.toLowerCase().includes(suggestion.toLowerCase()) ?? false
                return (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => addProfileContext(suggestion)}
                    disabled={selected}
                    className="rounded-full border border-border/60 bg-background/35 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-primary/45 hover:text-foreground disabled:cursor-default disabled:border-primary/35 disabled:bg-primary/15 disabled:text-foreground"
                  >
                    {suggestion}
                  </button>
                )
              })}
            </div>
            <p className="text-xs leading-5 text-muted-foreground">
              Saved context is indexed into private memory and used as a guardrail for future fit answers.
            </p>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="glass-panel rounded-[2rem] p-5">
            <div className="flex items-center gap-3">
              <span className="grid size-11 place-items-center rounded-full bg-primary/15 text-primary">
                <MemoryStick className="size-5" />
              </span>
              <div>
                <p className="text-sm font-semibold">Cognee memory</p>
                <p className="text-xs text-muted-foreground">
                  {cloudEnabled ? "Cloud graph recall is active." : "Local recall fallback is active."}
                </p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge variant="outline" className="glass-chip rounded-full capitalize">
                {memoryProvider}
              </Badge>
              {systemStatus ? (
                <Badge
                  variant={!cloudEnabled || systemStatus.cognee_cloud_configured ? "secondary" : "outline"}
                  className="rounded-full"
                >
                  {cloudEnabled
                    ? systemStatus.cognee_cloud_configured
                      ? "Connected"
                      : "Needs key"
                    : "OSS fallback"}
                </Badge>
              ) : null}
            </div>
          </section>

          <section className="glass-panel rounded-[2rem] p-5">
            <p className="text-sm font-semibold">Usage</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {systemStatus?.cloud_usage
                ? "Cloud indexing and recall use Cognee credits; billing stays in the Cognee dashboard."
                : "Local Cognee does not spend Cloud credits. Extraction and local recall can still use OpenRouter."}
            </p>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ProfileFallback({ status, onRetry }: { status: string; onRetry: () => void }) {
  const offline = status.toLowerCase().includes("could not reach")

  return (
    <Card className="glass-panel mx-auto max-w-5xl rounded-[2rem] border-border/55 bg-card/70 shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Private fit profile</CardTitle>
            <CardDescription>
              Your profile appears here once Mizaaj can reach the backend.
            </CardDescription>
          </div>
          <Badge variant="outline" className="rounded-full">
            {offline ? "Offline" : "Loading"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-[1.5rem] border border-border/55 bg-background/35 p-5">
          <p className="text-sm font-medium">
            {offline ? "Backend connection needed" : "Loading your private profile"}
          </p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {offline
              ? "Start the API server, then retry. Mizaaj keeps profile, capture, memory, and purchase data behind the API."
              : "This should only take a moment."}
          </p>
          <Button className="mt-4 rounded-full" variant="outline" onClick={onRetry}>
            <Sparkles />
            Retry
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function CaptureView({
  status,
  captureText,
  setCaptureText,
  captureUrl,
  setCaptureUrl,
  captureAttachments,
  uploadedCount,
  uploadingCount,
  failedCount,
  extracting,
  handleFiles,
  inputVersion,
  removeCaptureAttachment,
  retryCaptureAttachment,
  extractCapture,
  latestCapture,
  acceptedClaims,
  toggleClaim,
  confirmCapture,
  confirming,
}: {
  status: string
  captureText: string
  setCaptureText: (value: string) => void
  captureUrl: string
  setCaptureUrl: (value: string) => void
  captureAttachments: CaptureAttachment[]
  uploadedCount: number
  uploadingCount: number
  failedCount: number
  extracting: boolean
  handleFiles: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
  inputVersion: number
  removeCaptureAttachment: (attachment: CaptureAttachment) => void
  retryCaptureAttachment: (id: string) => void
  extractCapture: () => Promise<void>
  latestCapture: CaptureResponse | null
  acceptedClaims: Set<string>
  toggleClaim: (id: string) => void
  confirmCapture: () => Promise<void>
  confirming: boolean
}) {
  return (
    <div className="mx-auto grid w-full max-w-7xl min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(26rem,0.8fr)]">
      <Card className="glass-panel rounded-[2rem] border-border/55 bg-card/70 shadow-sm">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Capture item evidence</CardTitle>
              <CardDescription>Photograph tags, size charts, receipts, or product pages.</CardDescription>
            </div>
            <Camera className="size-5 text-primary" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <CaptureUploadButton
              id="capture-camera"
              icon={<Camera />}
              title="Take photo"
              detail="Camera, tag, receipt, or size chart."
              capture="environment"
              inputVersion={inputVersion}
              onChange={handleFiles}
            />
            <CaptureUploadButton
              id="capture-gallery"
              icon={<ImagePlus />}
              title="Add images"
              detail="Select several screenshots or photos."
              multiple
              inputVersion={inputVersion}
              onChange={handleFiles}
            />
          </div>
          {captureAttachments.length ? (
            <div className="space-y-3 rounded-[1.5rem] border border-border/55 bg-background/35 p-3">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-medium">Photos</p>
                <span className="text-xs text-muted-foreground">
                  {uploadingCount
                    ? `${uploadingCount} uploading`
                    : failedCount
                      ? `${failedCount} failed, ${uploadedCount} ready`
                      : `${uploadedCount} ready for extraction`}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                {captureAttachments.map((attachment) => (
                  <AssetPreview
                    key={attachment.id}
                    attachment={attachment}
                    onRemove={removeCaptureAttachment}
                    onRetry={retryCaptureAttachment}
                  />
                ))}
              </div>
            </div>
          ) : null}
          <div className="rounded-[1.5rem] border border-border/55 bg-background/35 p-3">
            <div className="mb-3">
              <p className="text-sm font-medium">Optional details</p>
              <p className="text-sm text-muted-foreground">
                Paste product text or a link when photos miss the important facts.
              </p>
            </div>
            <div className="space-y-3">
              <Field label="Product or order text" htmlFor="capture-text">
                <Textarea
                  id="capture-text"
                  value={captureText}
                  onChange={(event) => setCaptureText(event.target.value)}
                  className="min-h-28"
                />
              </Field>
              <Field label="Page URL" htmlFor="capture-url">
                <Input
                  id="capture-url"
                  value={captureUrl}
                  placeholder="https://..."
                  onChange={(event) => setCaptureUrl(event.target.value)}
                />
              </Field>
            </div>
          </div>
          <Button className="w-full sm:w-fit" onClick={extractCapture} disabled={extracting}>
            <Sparkles />
            {extracting ? "Extracting draft..." : "Extract draft"}
          </Button>
          <CaptureActionNotice status={status} extracting={extracting} />
        </CardContent>
      </Card>

      <Card className="glass-panel rounded-[2rem] border-border/55 bg-card/70 shadow-sm">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Review extracted facts</CardTitle>
              <CardDescription>Approve the claims that should become memory.</CardDescription>
            </div>
            <Badge variant={latestCapture ? "secondary" : "outline"} className="rounded-full">
              {latestCapture ? "Ready" : "Waiting"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {latestCapture ? (
            <div className="space-y-3">
              {latestCapture.product_draft.extracted_claims.map((claim) => (
                <div
                  key={claim.id}
                  role="button"
                  tabIndex={0}
                  className="flex w-full items-start gap-3 rounded-2xl border border-border/55 bg-background/45 p-3 text-left transition-colors hover:bg-muted/45"
                  onClick={() => toggleClaim(claim.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      toggleClaim(claim.id)
                    }
                  }}
                >
                  <Checkbox checked={acceptedClaims.has(claim.id)} className="mt-0.5" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{formatPredicate(claim.predicate)}</span>
                    <span className="block break-words text-sm text-muted-foreground">
                      {claim.value}
                      {formatClaimSource(claim.source) ? ` from ${formatClaimSource(claim.source)}` : ""}
                    </span>
                  </span>
                </div>
              ))}
              <Button className="w-full sm:w-fit" onClick={confirmCapture} disabled={confirming}>
                <MemoryStick />
                {confirming ? "Remembering..." : "Confirm and remember"}
              </Button>
              {confirming ? (
                <div className="rounded-2xl border border-border/55 bg-background/35 px-3 py-2 text-sm">
                  <p className="font-medium">Indexing confirmed facts with Cognee...</p>
                  <p className="mt-1 text-muted-foreground">This can take a few seconds on local memory.</p>
                </div>
              ) : null}
              {latestCapture.confirmed ? (
                <div className="rounded-2xl border border-border/55 bg-background/45 p-3 text-sm">
                  <p className="font-medium">
                    {latestCapture.memory_status === "indexed"
                      ? "Cognee memory indexed"
                      : "Product saved"}
                  </p>
                  {latestCapture.memory_status === "failed" ? (
                    <p className="mt-1 text-muted-foreground">
                      Memory indexing failed, but the product snapshot was saved.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState icon={<Sparkles />} title="No draft yet" detail="Run extraction to review claims." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function CaptureActionNotice({ status, extracting }: { status: string; extracting: boolean }) {
  const actionStatuses = [
    "Add a photo",
    "Could not",
    "Draft ready",
    "Extracting",
    "OpenRouter",
    "Photo upload failed",
    "Request failed",
    "Uploaded image",
    "Wait for photos",
  ]
  const shouldShow = extracting || actionStatuses.some((prefix) => status.startsWith(prefix))

  if (!shouldShow) return null

  const message = extracting ? "Extracting draft..." : status
  const isError =
    message.startsWith("Could not") ||
    message.startsWith("OpenRouter") ||
    message.startsWith("Photo upload failed") ||
    message.startsWith("Request failed") ||
    message.startsWith("Uploaded image")

  return (
    <div
      className={cn(
        "rounded-2xl border px-3 py-2 text-sm",
        isError ? "border-destructive/45 bg-destructive/10" : "border-border/55 bg-background/35",
      )}
      role={isError ? "alert" : "status"}
    >
      <p className="font-medium">{message}</p>
    </div>
  )
}

function CaptureUploadButton({
  id,
  icon,
  title,
  detail,
  multiple = false,
  capture,
  inputVersion,
  onChange,
}: {
  id: string
  icon: ReactNode
  title: string
  detail: string
  multiple?: boolean
  capture?: "environment" | "user"
  inputVersion: number
  onChange: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
}) {
  return (
    <label
      htmlFor={id}
      className="flex min-h-28 cursor-pointer items-start gap-3 rounded-[1.5rem] border border-dashed border-border/70 bg-muted/45 p-4 transition-colors hover:bg-muted/70"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-primary/12 text-primary">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{title}</span>
        <span className="mt-1 block text-sm leading-5 text-muted-foreground">{detail}</span>
      </span>
      <input
        key={`${id}-${inputVersion}`}
        id={id}
        className="sr-only"
        type="file"
        accept="image/*"
        capture={capture}
        multiple={multiple}
        onChange={onChange}
      />
    </label>
  )
}

function AssetPreview({
  attachment,
  onRemove,
  onRetry,
}: {
  attachment: CaptureAttachment
  onRemove: (attachment: CaptureAttachment) => void
  onRetry: (id: string) => void
}) {
  const name = attachment.fileName
  const imageUrl = attachment.previewUrl ?? attachment.asset?.public_url
  const shouldRenderImage = Boolean(imageUrl && attachment.mimeType.startsWith("image/"))
  const statusText =
    attachment.status === "uploaded" ? "Uploaded" : attachment.status === "failed" ? "Failed" : "Uploading"

  return (
    <div className="group relative aspect-square min-w-0 overflow-hidden rounded-2xl border border-border/55 bg-muted/50">
      {shouldRenderImage ? (
        <img src={imageUrl ?? ""} alt={name} className="size-full object-cover" loading="lazy" />
      ) : (
        <div className="grid size-full place-items-center text-muted-foreground">
          <ImagePlus className="size-7" />
        </div>
      )}
      <button
        type="button"
        aria-label={`Remove ${name}`}
        className="absolute right-1.5 top-1.5 grid size-7 place-items-center rounded-full bg-background/85 text-foreground shadow-sm backdrop-blur transition-colors hover:bg-background"
        onClick={() => onRemove(attachment)}
      >
        <X className="size-3.5" />
      </button>
      <div className="absolute left-1.5 top-1.5 rounded-full bg-background/85 px-2 py-1 text-[10px] font-medium text-foreground shadow-sm backdrop-blur">
        {statusText}
      </div>
      {attachment.status === "failed" ? (
        <button
          type="button"
          className="absolute inset-x-2 top-1/2 -translate-y-1/2 rounded-md bg-background/90 px-2 py-1.5 text-xs font-medium shadow-sm backdrop-blur"
          onClick={() => onRetry(attachment.id)}
        >
          Retry upload
        </button>
      ) : null}
      <div className="absolute inset-x-0 bottom-0 bg-background/86 px-2 py-1 text-[11px] font-medium backdrop-blur">
        <p className="truncate">{name}</p>
        {attachment.status === "failed" && attachment.error ? (
          <p className="truncate text-[10px] text-destructive">{attachment.error}</p>
        ) : null}
      </div>
    </div>
  )
}

function MemoryView({
  purchases,
  products,
  savedMemories,
  memoryCaptures,
  activeProductKey,
  onOpenProduct,
  onBackToMemory,
  deletingMemoryId,
  clearingMemories,
  onDeleteMemory,
  onClearMemories,
}: {
  purchases: PurchaseRecord[]
  products: ProductSnapshot[]
  savedMemories: SavedMemoryRecord[]
  memoryCaptures: Record<string, CaptureResponse>
  activeProductKey: string
  onOpenProduct: (productKey: string) => void
  onBackToMemory: () => void
  deletingMemoryId: string | null
  clearingMemories: boolean
  onDeleteMemory: (memoryId: string) => void
  onClearMemories: () => void
}) {
  const productsByCapture = new Map(
    products
      .filter((product) => product.source_capture_id)
      .map((product) => [product.source_capture_id as string, product]),
  )
  const productItems: MemoryProductItem[] = [
    ...products.map((product) => ({
      key: `product:${product.id}`,
      product,
      sourceCapture: product.source_capture_id ? memoryCaptures[product.source_capture_id] : undefined,
      linkedMemories: savedMemories.filter(
        (record) =>
          record.product_id === product.id ||
          (!record.product_id && record.capture_id === product.source_capture_id),
      ),
      purchases: purchases.filter((purchase) => purchase.product_id === product.id),
      derived: false,
    })),
    ...uniqueIds(
      savedMemories
        .filter(
          (record) =>
            !record.product_id &&
            record.capture_id &&
            memoryCaptures[record.capture_id] &&
            !productsByCapture.has(record.capture_id),
        )
        .map((record) => record.capture_id as string),
    ).map((captureId) => {
      const capture = memoryCaptures[captureId]
      return {
        key: `capture:${captureId}`,
        product: productFromCapture(capture),
        sourceCapture: capture,
        linkedMemories: savedMemories.filter((record) => !record.product_id && record.capture_id === captureId),
        purchases: [],
        derived: true,
      }
    }),
  ]
  const unlinkedMemories = savedMemories.filter(
    (record) => !record.product_id && (!record.capture_id || !memoryCaptures[record.capture_id]),
  )
  const routedProductItem = productItems.find((item) => item.key === activeProductKey)

  if (activeProductKey) {
    return routedProductItem ? (
      <ProductMemoryDetail
        item={routedProductItem}
        memoryCaptures={memoryCaptures}
        deletingMemoryId={deletingMemoryId}
        onDeleteMemory={onDeleteMemory}
        onBack={onBackToMemory}
      />
    ) : (
      <div className="mx-auto max-w-5xl space-y-5">
        <Button variant="ghost" className="rounded-full" onClick={onBackToMemory}>
          <ArrowLeft />
          Back to memory
        </Button>
        <div className="glass-panel rounded-[2rem] p-8 text-center">
          <p className="font-medium">Product memory not found</p>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            This product may have been deleted or the local memory shelf has not finished loading.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="glass-panel rounded-[2rem] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-3xl font-normal text-gradient">Memory</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Conversations and try-on outcomes you approved for Mizaaj to remember.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {savedMemories.length ? (
              <Button
                variant="outline"
                size="sm"
                className="h-9 rounded-full border-white/10 bg-white/[0.04] px-3 text-xs text-muted-foreground shadow-sm shadow-black/10 backdrop-blur-xl hover:border-primary/35 hover:bg-primary/10 hover:text-foreground"
                onClick={onClearMemories}
                disabled={clearingMemories}
              >
                <Trash2 className="size-3.5" />
                {clearingMemories ? "Clearing..." : "Clear chats"}
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-medium text-muted-foreground">Products</h3>
        </div>
        {productItems.length ? (
          <div className="-mx-3 flex snap-x gap-4 overflow-x-auto px-3 pb-2">
            {productItems.map((item) => (
              <ProductMemoryCard
                key={item.key}
                item={item}
                memoryCaptures={memoryCaptures}
                onOpen={() => onOpenProduct(item.key)}
              />
            ))}
          </div>
        ) : (
          <div className="glass-panel rounded-[2rem] p-8 text-center">
            <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-primary/10 text-primary">
              <Shirt className="size-5" />
            </div>
            <p className="font-medium">No curated products yet</p>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
              Confirm a capture to create the first product identity, then attach future chats and photos to it.
            </p>
          </div>
        )}
      </section>

      {unlinkedMemories.length ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-medium text-muted-foreground">General memories</h3>
          </div>
          {unlinkedMemories.map((record) => (
            <SavedMemoryCard
              key={record.id}
              record={record}
              capture={record.capture_id ? memoryCaptures[record.capture_id] : undefined}
              deleting={deletingMemoryId === record.id}
              onDelete={() => onDeleteMemory(record.id)}
            />
          ))}
        </section>
      ) : null}
    </div>
  )
}

function ProductMemoryCard({
  item,
  memoryCaptures,
  onOpen,
}: {
  item: MemoryProductItem
  memoryCaptures: Record<string, CaptureResponse>
  onOpen: () => void
}) {
  const { product, sourceCapture, linkedMemories, purchases, derived } = item
  const linkedCaptures = uniqueCaptures([
    sourceCapture,
    ...linkedMemories.map((record) => (record.capture_id ? memoryCaptures[record.capture_id] : undefined)),
  ])
  const heroImage = linkedCaptures.flatMap(captureImageAssets)[0]
  const imageCount = linkedCaptures.flatMap(captureImageAssets).length
  const sizes = product.size_labels.length
    ? product.size_labels.map((item) => [item.system, item.label].filter(Boolean).join(" "))
    : product.size_options

  return (
    <button
      type="button"
      className={cn(
        "glass-panel w-[18.5rem] shrink-0 snap-start overflow-hidden rounded-[2rem] p-0 text-left transition",
        "hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10",
        "sm:w-[23rem] lg:w-[25rem]",
      )}
      onClick={onOpen}
      aria-label={`Open ${productDisplayName(product)} memory`}
    >
      <div className="flex flex-col gap-4 p-4">
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-[1.5rem] border border-border/50 bg-muted/35">
          {heroImage ? (
            <img
              src={heroImage.public_url ?? ""}
              alt={heroImage.original_name || productDisplayName(product)}
              className="size-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="grid size-full place-items-center text-muted-foreground">
              <Shirt className="size-8" />
            </div>
          )}
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-background/75 px-3 py-2 text-xs backdrop-blur">
            <span>{imageCount || linkedCaptures.length} evidence</span>
            {derived ? <span>created from chat</span> : null}
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="line-clamp-2 text-base font-semibold leading-6">{productDisplayName(product)}</p>
              <p className="mt-1 truncate text-sm text-muted-foreground">
                {product.material || product.color || product.category}
              </p>
            </div>
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border border-border/55 bg-background/45 text-muted-foreground">
              <ArrowUpRight className="size-4" />
            </span>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            {[
              `${linkedMemories.length} saved chat${linkedMemories.length === 1 ? "" : "s"}`,
              `${purchases.length} outcome${purchases.length === 1 ? "" : "s"}`,
            ].join(" / ")}
          </p>
          {sizes.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {sizes.slice(0, 6).map((size) => (
                <Badge key={size} variant="secondary" className="rounded-full">
                  {size}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </button>
  )
}

function ProductMemoryDetail({
  item,
  memoryCaptures,
  deletingMemoryId,
  onDeleteMemory,
  onBack,
}: {
  item: MemoryProductItem
  memoryCaptures: Record<string, CaptureResponse>
  deletingMemoryId: string | null
  onDeleteMemory: (memoryId: string) => void
  onBack: () => void
}) {
  const { product, sourceCapture, linkedMemories, purchases } = item
  const linkedCaptures = uniqueCaptures([
    sourceCapture,
    ...linkedMemories.map((record) => (record.capture_id ? memoryCaptures[record.capture_id] : undefined)),
  ])
  const images = linkedCaptures.flatMap((capture) =>
    captureImageAssets(capture).map((asset) => ({ capture, asset })),
  )
  const sizes = product.size_labels.length
    ? product.size_labels.map((size) => [size.system, size.label].filter(Boolean).join(" "))
    : product.size_options

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <div className="flex items-center justify-between gap-3">
        <Button
          variant="ghost"
          className="h-10 rounded-full border border-border/40 bg-background/35 px-3 text-sm backdrop-blur hover:bg-accent/70"
          onClick={onBack}
          aria-label="Back to memory"
        >
          <ArrowLeft className="size-4" />
          Memory
        </Button>
      </div>

      <section className="glass-panel overflow-hidden rounded-[2rem]">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]">
        <div className="border-b border-border/45 p-4 sm:p-5 lg:border-b-0 lg:border-r">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Selected product</p>
              <h3 className="mt-2 text-2xl font-semibold leading-tight">{productDisplayName(product)}</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {[product.color, product.material, product.category].filter(Boolean).join(" / ")}
              </p>
            </div>
            {sizes.length ? (
              <div className="flex shrink-0 flex-wrap gap-2">
                {sizes.slice(0, 6).map((size) => (
                  <Badge key={size} variant="secondary" className="rounded-full">
                    {size}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>

          <div className="mt-6 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evidence timeline</p>
              <span className="text-xs text-muted-foreground">
                {images.length || linkedCaptures.length} evidence item{(images.length || linkedCaptures.length) === 1 ? "" : "s"}
              </span>
            </div>
            {images.length ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {images.map(({ asset }, index) => (
                  <a
                    key={`${asset.path}-${index}`}
                    href={asset.public_url ?? undefined}
                    target="_blank"
                    rel="noreferrer"
                    className={cn(
                      "group relative overflow-hidden rounded-[1.35rem] border border-border/55 bg-muted/35",
                      index === 0 && "col-span-2 row-span-2",
                    )}
                  >
                    <img
                      src={asset.public_url ?? ""}
                      alt={asset.original_name || "Captured clothing evidence"}
                      className={cn(
                        "size-full object-cover transition-transform duration-300 group-hover:scale-105",
                        index === 0 ? "aspect-[4/3]" : "aspect-square",
                      )}
                      loading="lazy"
                    />
                    <span className="absolute inset-x-0 bottom-0 truncate bg-background/80 px-3 py-2 text-xs font-medium backdrop-blur">
                      {asset.original_name || "photo"}
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <div className="rounded-[1.5rem] border border-dashed border-border/65 p-6 text-sm text-muted-foreground">
                This product has capture context, but no viewable image assets yet.
              </div>
            )}
            {linkedCaptures.length ? (
              <div className="grid gap-3 pt-2 sm:grid-cols-2">
                {linkedCaptures.map((capture) => (
                  <CaptureEvidenceSummary key={capture.id} capture={capture} />
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="space-y-6 p-4 sm:p-5">
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Linked conversations</p>
            {linkedMemories.length ? (
              linkedMemories.map((record) => (
                <SavedMemoryCard
                  key={record.id}
                  record={record}
                  deleting={deletingMemoryId === record.id}
                  onDelete={() => onDeleteMemory(record.id)}
                  compact
                />
              ))
            ) : (
              <p className="rounded-[1.5rem] border border-dashed border-border/55 bg-background/25 p-4 text-sm leading-6 text-muted-foreground">
                Ask Mizaaj with new photos, then save the answer to link more context to this product.
              </p>
            )}
          </div>

          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Try-on outcomes</p>
            {purchases.length ? (
              <div className="grid gap-2">
                {purchases.map((purchase) => (
                  <div key={purchase.id} className="rounded-2xl border border-border/55 bg-background/30 p-3">
                    <p className="text-sm font-medium">
                      {purchase.outcome} in {purchase.purchased_size}
                    </p>
                    {purchase.fit_notes ? (
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">{purchase.fit_notes}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-[1.5rem] border border-dashed border-border/55 bg-background/25 p-4 text-sm leading-6 text-muted-foreground">
                No try-on outcome saved yet.
              </p>
            )}
          </div>
        </div>
        </div>
      </section>
    </div>
  )
}

function CaptureEvidenceSummary({ capture }: { capture: CaptureResponse }) {
  const draft = capture.product_snapshot ?? capture.product_draft
  const title = [draft.brand, draft.title].filter(Boolean).join(" - ") || "Captured item"
  const imageCount = captureImageAssets(capture).length

  return (
    <div className="rounded-[1.25rem] border border-border/55 bg-background/30 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {imageCount} image{imageCount === 1 ? "" : "s"} / {capture.confirmed ? "confirmed" : "capture context"}
          </p>
        </div>
        <Badge variant="outline" className="shrink-0 rounded-full">
          {capture.confirmed ? "confirmed" : "draft"}
        </Badge>
      </div>
    </div>
  )
}

function SavedMemoryCard({
  record,
  capture,
  deleting,
  onDelete,
  compact = false,
}: {
  record: SavedMemoryRecord
  capture?: CaptureResponse
  deleting?: boolean
  onDelete?: () => void
  compact?: boolean
}) {
  const savedAt = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(record.created_at))

  return (
    <details className={cn("glass-panel group rounded-[1.75rem] p-4", compact && "bg-background/25 shadow-none")}>
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4">
        <span className="min-w-0">
          <span className="block text-sm font-medium">{record.question}</span>
          <span className="mt-1 line-clamp-2 block text-sm leading-6 text-muted-foreground">
            {record.answer || "Saved selected memory cards."}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <Badge variant={record.memory_status === "indexed" ? "secondary" : "outline"} className="rounded-full">
            {record.memory_status}
          </Badge>
          {onDelete ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 rounded-full"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onDelete()
              }}
              disabled={deleting}
              aria-label={`Delete memory from ${savedAt}`}
            >
              <Trash2 className="size-4" />
            </Button>
          ) : null}
          <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
        </span>
      </summary>

      <div className="mt-4 space-y-4 border-t border-border/50 pt-4">
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="glass-chip rounded-full px-3 py-1.5">{savedAt}</span>
          <span className="glass-chip rounded-full px-3 py-1.5">
            {record.remembered.length} memory cards
          </span>
          {record.capture_id ? (
            <span className="glass-chip rounded-full px-3 py-1.5">
              {capture ? `${capture.assets.length} source photo${capture.assets.length === 1 ? "" : "s"}` : "Source capture"}
            </span>
          ) : null}
        </div>
        {capture ? <MemorySourceCapture capture={capture} /> : null}
        {record.answer ? (
          <div className="rounded-2xl border border-border/55 bg-background/35 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Answer</p>
            <p className="mt-2 text-sm leading-6">{record.answer}</p>
          </div>
        ) : null}
        <div className="grid gap-3 lg:grid-cols-2">
          {record.remembered.map((draft) => (
            <div key={draft.id} className="rounded-2xl border border-border/55 bg-background/35 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {draft.kind.replaceAll("_", " ")}
              </p>
              <p className="mt-2 text-sm leading-6">{draft.text}</p>
            </div>
          ))}
        </div>
        {record.evidence.length ? (
          <details className="group/evidence">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-muted-foreground">
              Evidence used
              <ChevronDown className="size-4 transition-transform group-open/evidence:rotate-180" />
            </summary>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {record.evidence.map((item) => (
                <div key={`${item.source}-${item.detail}`} className="rounded-2xl border border-border/55 bg-background/25 p-3">
                  <p className="text-xs font-medium">{formatEvidenceLabel(item)}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {formatEvidenceDetail(item)}
                  </p>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </details>
  )
}

function MemorySourceCapture({ capture }: { capture: CaptureResponse }) {
  const imageAssets = captureImageAssets(capture)
  const draft = capture.product_snapshot ?? capture.product_draft
  const title = [draft.brand, draft.title].filter(Boolean).join(" - ") || "Captured item"

  return (
    <div className="rounded-2xl border border-border/55 bg-background/30 p-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Source evidence</p>
          <p className="mt-1 truncate text-sm font-medium">{title}</p>
        </div>
        <Badge variant="outline" className="w-fit rounded-full">
          {capture.confirmed ? "confirmed item" : "temporary capture"}
        </Badge>
      </div>

      {imageAssets.length ? (
        <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {imageAssets.map((asset) => (
            <a
              key={asset.path}
              href={asset.public_url ?? undefined}
              target="_blank"
              rel="noreferrer"
              className="group relative aspect-square overflow-hidden rounded-2xl border border-border/50 bg-muted/40"
            >
              <img
                src={asset.public_url ?? ""}
                alt={asset.original_name || "Captured clothing evidence"}
                className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
              />
              <span className="absolute inset-x-0 bottom-0 truncate bg-background/80 px-2 py-1 text-[10px] font-medium backdrop-blur">
                {asset.original_name || "photo"}
              </span>
            </a>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          This memory is linked to a capture, but that capture has no viewable image assets.
        </p>
      )}
    </div>
  )
}

function isImageAsset(asset: UploadedAsset) {
  const mime = asset.mime_type?.toLowerCase() ?? ""
  const url = asset.public_url?.toLowerCase() ?? asset.path.toLowerCase()
  return mime.startsWith("image/") || /\.(avif|gif|jpe?g|png|webp)$/.test(url)
}

function captureImageAssets(capture: CaptureResponse) {
  return capture.assets.filter((asset) => asset.public_url && isImageAsset(asset))
}

function productFromCapture(capture: CaptureResponse): ProductSnapshot {
  if (capture.product_snapshot) return capture.product_snapshot
  const draft = capture.product_draft
  return {
    ...draft,
    id: capture.id,
    title: draft.title || fallbackDisplayTitle(draft.category, draft.color),
    url: draft.url || capture.page_url,
    source_capture_id: capture.id,
  }
}

function fallbackDisplayTitle(category: ProductSnapshot["category"], color?: string | null) {
  const categoryName = categoryDisplayName(category)
  if (color && category !== "unknown") return `${titleCase(color)} ${categoryName}`
  if (category !== "unknown") return categoryName
  if (color) return `${titleCase(color)} clothing item`
  return "Clothing item"
}

function uniqueCaptures(captures: Array<CaptureResponse | undefined>) {
  const seen = new Set<string>()
  return captures.filter((capture): capture is CaptureResponse => {
    if (!capture || seen.has(capture.id)) return false
    seen.add(capture.id)
    return true
  })
}

function uniqueIds(ids: string[]) {
  return Array.from(new Set(ids))
}

function formatPredicate(value: string) {
  return value.replaceAll("_", " ")
}

function formatClaimSource(value: string) {
  const source = value.trim()
  if (!source) return ""
  if (source.includes("mizaaj-uploads") || source.includes("/captures/")) return "image"
  if (source.startsWith("http://") || source.startsWith("https://")) return "product page"
  return source
}

function formatEvidenceLabel(item: AskEvidence) {
  const source = item.source.toLowerCase()
  const label = item.label.toLowerCase()
  if (source.includes("cognee") || label.includes("cognee")) return "Private memory"
  if (source.startsWith("purchase:")) return "Past outcome"
  if (source.startsWith("product:")) return "Current item"
  if (source.startsWith("profile:")) return "Fit profile"
  return item.label
}

function formatEvidenceDetail(item: AskEvidence) {
  const raw = item.detail.trim()
  const extracted =
    matchFirst(raw, [
      /chunk\s+\d+\s+of\s+document\s+[0-9a-f-]{24,}.*?:\s*["“]([\s\S]+?)["”](?:\s*$|\s+-\s+chunk)/i,
      /['"]answer['"]:\s*['"]([\s\S]+?)['"]\s*,\s*['"]?(?:structured|source|score|metadata|raw)/,
      /['"]answer['"]:\s*['"](.+?)['"]/,
      /['"]text['"]:\s*['"](.+?)['"]/,
      /value['"]?:\s*['"](.+?)['"]/,
      /raw=\{['"]value['"]:\s*['"](.+?)['"]\}/,
      /text=['"](.+?)['"]\s+(?:dataset_name|metadata|source|score|$)/,
    ]) ?? raw

  const clean = extracted
    .split(/\bEvidence:\s*/i)[0]
    .replaceAll("\\n", " ")
    .replaceAll("\\'", "'")
    .replaceAll('\\"', '"')
    .replace(/\*\*/g, "")
    .replace(/\b(?:document|data_id|chunk_id)\s*:?\s*[0-9a-f-]{24,}\b/gi, "")
    .replace(/\bchunk\s+\d+\s+of\s+document\s+[0-9a-f-]{24,}:?/gi, "")
    .replace(/\b(kind|search_type|dataset_name|metadata|raw)=['"]?[^'"]*['"]?/g, "")
    .replace(/\s+/g, " ")
    .trim()

  return clean.length > 260 ? `${clean.slice(0, 257).trim()}...` : clean
}

function matchFirst(value: string, patterns: RegExp[]) {
  for (const pattern of patterns) {
    const match = value.match(pattern)
    if (match?.[1]) return match[1]
  }
  return null
}

function productDisplayName(product: ProductSnapshot) {
  const brand = product.brand?.trim() ?? ""
  const displayTitle = brand && product.title.toLowerCase().startsWith(brand.toLowerCase())
    ? product.title.slice(brand.length).trim()
    : product.title
  const title = isGenericProductTitle(displayTitle, product.category)
    ? fallbackProductTitle(product)
    : displayTitle
  return [brand, title].filter(Boolean).join(" - ")
}

function isGenericProductTitle(title: string, category: ProductSnapshot["category"]) {
  const normalized = title.trim().toLowerCase()
  return (
    normalized === "untitled captured item" ||
    normalized === "captured item" ||
    normalized === "captured clothing item" ||
    normalized === category ||
    normalized === categoryDisplayName(category).toLowerCase() ||
    normalized === `captured ${category}` ||
    normalized === `captured ${categoryDisplayName(category).toLowerCase()}`
  )
}

function fallbackProductTitle(product: ProductSnapshot) {
  return fallbackDisplayTitle(product.category, product.color)
}

function categoryDisplayName(category: ProductSnapshot["category"]) {
  if (category === "tshirt") return "T-shirt"
  if (category === "unknown") return "Clothing item"
  return titleCase(category.replaceAll("_", " "))
}

function titleCase(value: string) {
  return value
    .trim()
    .split(/\s+/)
    .map((part) => (part ? `${part[0].toUpperCase()}${part.slice(1).toLowerCase()}` : part))
    .join(" ")
}

function ProductSummary({ product }: { product: ProductSnapshot }) {
  const visibleSizes = product.size_labels.length
    ? product.size_labels.map((item) => [item.system, item.label].filter(Boolean).join(" "))
    : product.size_options
  const composition = product.fabric_composition
    .map((item) =>
      [item.percentage === null || item.percentage === undefined ? null : `${item.percentage}%`, item.material]
        .filter(Boolean)
        .join(" "),
    )
    .join(", ")

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border/55 bg-background/45 p-3 shadow-sm shadow-black/5 backdrop-blur sm:p-4">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {productDisplayName(product)}
          </p>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {composition || product.material || "Material unknown"}
          </p>
        </div>
        <Badge variant="outline" className="max-w-full truncate rounded-full bg-background/50 sm:max-w-28">
          {product.category}
        </Badge>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {visibleSizes.map((size) => (
          <Badge key={size} variant="secondary" className="rounded-full">
            {size}
          </Badge>
        ))}
      </div>
    </div>
  )
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor?: string
  children: ReactNode
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  )
}

function EmptyState({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <div className="flex min-h-44 flex-col items-center justify-center rounded-lg border border-dashed border-border/70 bg-muted/35 p-6 text-center">
      <div className="mb-3 grid size-10 place-items-center rounded-full bg-background text-primary">{icon}</div>
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
    </div>
  )
}
