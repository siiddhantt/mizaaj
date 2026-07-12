import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { App } from "@/App"

const apiMocks = vi.hoisted(() => ({
  askMizaaj: vi.fn(),
  confirmCapture: vi.fn(),
  createCapture: vi.fn(),
  createPurchase: vi.fn(),
  deleteSavedMemories: vi.fn(),
  deleteSavedMemory: vi.fn(),
  getCurrentUser: vi.fn(),
  getCapture: vi.fn(),
  getProfile: vi.fn(),
  getSystemStatus: vi.fn(),
  listCaptures: vi.fn(),
  listSavedMemories: vi.fn(),
  listProducts: vi.fn(),
  listPurchases: vi.fn(),
  rememberMemoryDrafts: vi.fn(),
  recommend: vi.fn(),
  updateProfile: vi.fn(),
}))

const uploadMocks = vi.hoisted(() => ({
  uploadCaptureFile: vi.fn(),
}))

vi.mock("@/lib/api", () => ({
  api: apiMocks,
  setAuthTokenProvider: vi.fn(),
}))

vi.mock("@/lib/uploads", () => ({
  uploadCaptureFile: uploadMocks.uploadCaptureFile,
}))

const sampleProfile = {
  user_id: "00000000-0000-4000-8000-000000000001",
  display_name: "Sid",
  height_cm: 178,
  weight_kg: null,
  body_notes: null,
  sensitivities: ["tight chest", "long sleeves"],
  category_preferences: [],
}

const sampleProduct = {
  id: "11111111-1111-4111-8111-111111111111",
  brand: "Zara",
  retailer: "Zara",
  title: "Linen Blend Relaxed Shirt",
  sku: null,
  url: null,
  category: "shirt",
  color: null,
  material: "linen, cotton",
  size_options: ["S", "M", "L"],
  size_labels: [],
  size_chart: [],
  fit_descriptors: [],
  fabric_composition: [],
  care_instructions: [],
  origin_country: null,
  gender: null,
  product_identifiers: [],
  attributes: [],
  extracted_claims: [],
  source_capture_id: null,
}

const extractedCapture = {
  id: "22222222-2222-4222-8222-222222222222",
  user_id: sampleProfile.user_id,
  source_type: "manual",
  page_url: null,
  text_blocks: ["Zara linen shirt"],
  assets: [],
  user_notes: null,
  confirmed: false,
  memory_status: "not_indexed",
  memory_error: null,
  product_snapshot: null,
  product_draft: {
    brand: "Zara",
    retailer: null,
    title: "Zara linen shirt",
    sku: null,
    url: null,
    category: "shirt",
    color: null,
    material: "linen",
    size_options: ["S", "M", "L"],
    size_labels: [],
    size_chart: [],
    fit_descriptors: [],
    fabric_composition: [],
    care_instructions: [],
    origin_country: null,
    gender: null,
    product_identifiers: [],
    attributes: [],
    extracted_claims: [
      {
        id: "33333333-3333-4333-8333-333333333333",
        subject: "Zara linen shirt",
        predicate: "material",
        value: "linen",
        source: "manual_input",
        confidence: 0.79,
        status: "extracted",
      },
    ],
  },
}

const imageCapture = {
  ...extractedCapture,
  id: "66666666-6666-4666-8666-666666666666",
  assets: [
    {
      path: "users/local/captures/tag.jpg",
      mime_type: "image/jpeg",
      original_name: "tag.jpg",
      public_url: "http://localhost:9000/mizaaj-uploads/users/local/captures/tag.jpg",
    },
    {
      path: "users/local/captures/tee.jpg",
      mime_type: "image/jpeg",
      original_name: "tee.jpg",
      public_url: "http://localhost:9000/mizaaj-uploads/users/local/captures/tee.jpg",
    },
    {
      path: "users/local/captures/fit.jpg",
      mime_type: "image/jpeg",
      original_name: "fit.jpg",
      public_url: "http://localhost:9000/mizaaj-uploads/users/local/captures/fit.jpg",
    },
  ],
}

const askResponse = {
  user_id: sampleProfile.user_id,
  question: "What size should I buy?",
  answer: "Start with M for Zara - Linen Blend Relaxed Shirt.",
  confidence: 0.72,
  evidence: [
    {
      label: "Cognee memory",
      detail: "Zara shirt in M was returned because the chest felt tight.",
      source: "cognee",
    },
  ],
  recalled_facts: [
    {
      text: "Zara shirt in M was returned because the chest felt tight.",
      source: "cognee",
      score: 2,
    },
  ],
  memory_drafts: [
    {
      id: "44444444-4444-4444-8444-444444444444",
      kind: "fit_preference",
      subject: `user:${sampleProfile.user_id}:ask_note`,
      text: "User fit note: I prefer relaxed drape.",
      source: "ask",
      confidence: 0.7,
      tags: ["signal:user_note"],
    },
  ],
  reasoning_status: "grounded" as const,
}

const savedMemoryRecord = {
  id: "55555555-5555-4555-8555-555555555555",
  user_id: sampleProfile.user_id,
  question: askResponse.question,
  answer: askResponse.answer,
  product_id: sampleProduct.id,
  capture_id: null,
  evidence: askResponse.evidence,
  recalled_facts: askResponse.recalled_facts,
  remembered: askResponse.memory_drafts,
  memory_status: "indexed",
  memory_error: null,
  created_at: "2026-07-02T00:00:00Z",
}

const savedMemoryWithCapture = {
  ...savedMemoryRecord,
  product_id: null,
  capture_id: imageCapture.id,
}

describe("Mizaaj app", () => {
  afterEach(() => cleanup())

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    window.history.replaceState(null, "", "/")
    apiMocks.getCurrentUser.mockResolvedValue({
      user_id: sampleProfile.user_id,
      subject: "local-dev",
      provider: "local",
    })
    apiMocks.getSystemStatus.mockResolvedValue({
      app_name: "Mizaaj API",
      environment: "test",
      store_provider: "memory",
      memory_provider: "cognee_local",
      atlas_provider: "seed",
      atlas_dataset_name: "mizaaj_atlas_seed_v2",
      upload_provider: "s3",
      extraction_provider: "openrouter",
      cognee_dataset_prefix: "mizaaj_private",
      cognee_cloud_configured: false,
      cognee_timeout_seconds: 90,
      cloud_usage: null,
    })
    apiMocks.getProfile.mockResolvedValue(sampleProfile)
    apiMocks.listProducts.mockResolvedValue([sampleProduct])
    apiMocks.listPurchases.mockResolvedValue([])
    apiMocks.listCaptures.mockResolvedValue([])
    apiMocks.listSavedMemories.mockResolvedValue([])
    apiMocks.getCapture.mockResolvedValue(extractedCapture)
    apiMocks.createCapture.mockResolvedValue(extractedCapture)
    apiMocks.createPurchase.mockResolvedValue({
      id: "77777777-7777-4777-8777-777777777777",
      user_id: sampleProfile.user_id,
      product_id: sampleProduct.id,
      purchased_size: "M",
      outcome: "kept",
      fit_rating: 5,
      comfort_rating: 4,
      silhouette_rating: 4,
      fit_notes: "Relaxed shoulders without chest cling.",
    })
    apiMocks.askMizaaj.mockResolvedValue(askResponse)
    apiMocks.rememberMemoryDrafts.mockResolvedValue({
      user_id: sampleProfile.user_id,
      remembered: askResponse.memory_drafts,
      memory_status: "indexed",
      memory_error: null,
      memory_record: savedMemoryRecord,
    })
    uploadMocks.uploadCaptureFile.mockReset()
  })

  async function navigateViaSidebar(name: RegExp) {
    await userEvent.click(screen.getByRole("button", { name: /open navigation/i }))
    await userEvent.click(await screen.findByRole("button", { name }))
  }

  it("asks private fit memory and saves selected memory cards", async () => {
    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole("combobox", { name: /product identity/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/linen blend relaxed shirt/i)).not.toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText(/ask mizaaj/i))
    await userEvent.type(screen.getByLabelText(/ask mizaaj/i), "What size should I buy?")
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))

    expect(apiMocks.askMizaaj).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: sampleProfile.user_id,
        question: "What size should I buy?",
      }),
    )
    expect(await screen.findByText(/start with m/i)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /should i size up/i })).not.toBeInTheDocument()
    await userEvent.click(await screen.findByRole("button", { name: /remember this/i }))
    expect(await screen.findByText(/user fit note/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("combobox", { name: /product identity/i }))
    await userEvent.click(await screen.findByRole("option", { name: /zara - linen blend relaxed shirt/i }))

    await userEvent.click(screen.getByRole("button", { name: /save selected memory/i }))

    expect(apiMocks.rememberMemoryDrafts).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: sampleProfile.user_id,
        drafts: askResponse.memory_drafts,
        question: askResponse.question,
        answer: askResponse.answer,
        product_id: sampleProduct.id,
      }),
    )
  })

  it("renders the authenticated user menu slot in the header", async () => {
    render(<App userMenu={<button aria-label="Open user profile">Sid</button>} />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))

    expect(screen.getByRole("button", { name: /open user profile/i })).toBeInTheDocument()
  })

  it("sends recent conversation turns for grounded follow-up questions", async () => {
    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await userEvent.type(screen.getByLabelText(/ask mizaaj/i), "What size should I buy?")
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))
    await screen.findByText(/start with m/i)

    await userEvent.type(screen.getByLabelText(/ask mizaaj/i), "What about the sleeves?")
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))

    await waitFor(() => expect(apiMocks.askMizaaj).toHaveBeenCalledTimes(2))
    expect(apiMocks.askMizaaj.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        question: "What about the sleeves?",
        conversation: [
          expect.objectContaining({ role: "user", content: "What size should I buy?" }),
          expect.objectContaining({ role: "assistant", content: askResponse.answer }),
        ],
        session_id: expect.any(String),
      }),
    )
  })

  it("saves an approved structured outcome with chat memory", async () => {
    apiMocks.askMizaaj.mockResolvedValue({
      ...askResponse,
      question: "I kept M and the shoulders felt relaxed.",
      outcome_draft: {
        purchased_size: "M",
        outcome: "kept",
        fit_rating: 5,
        comfort_rating: 4,
        silhouette_rating: 4,
        fit_notes: "Relaxed shoulders without chest cling.",
        confidence: 0.9,
      },
    })
    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await userEvent.type(
      screen.getByLabelText(/ask mizaaj/i),
      "I kept M and the shoulders felt relaxed.",
    )
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))
    await userEvent.click(await screen.findByRole("button", { name: /remember this/i }))
    await userEvent.click(screen.getByRole("combobox", { name: /product identity/i }))
    await userEvent.click(
      await screen.findByRole("option", { name: /zara - linen blend relaxed shirt/i }),
    )
    await userEvent.click(screen.getByRole("button", { name: /save memory and outcome/i }))

    await waitFor(() => expect(apiMocks.createPurchase).toHaveBeenCalledTimes(1))
    expect(apiMocks.createPurchase).toHaveBeenCalledWith(
      expect.objectContaining({
        product_id: sampleProduct.id,
        purchased_size: "M",
        outcome: "kept",
        fit_notes: "Relaxed shoulders without chest cling.",
      }),
    )
  })

  it("keeps the Memory page focused on approved memories", async () => {
    apiMocks.listProducts.mockResolvedValue([])
    apiMocks.listSavedMemories.mockResolvedValue([savedMemoryWithCapture])
    apiMocks.listCaptures.mockResolvedValue([imageCapture])

    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^memory$/i)

    expect(await screen.findByText("Products")).toBeInTheDocument()
    expect((await screen.findAllByText(/zara - linen shirt/i)).length).toBeGreaterThan(0)
    expect(screen.queryByText("No curated products yet")).not.toBeInTheDocument()
    expect(screen.queryByText("General memories")).not.toBeInTheDocument()
    expect(screen.queryByText(/identity managed by mizaaj/i)).not.toBeInTheDocument()
    expect(screen.queryByText("Fit timeline")).not.toBeInTheDocument()
    expect(screen.queryByText(/new shopper/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /open zara - linen shirt memory/i }))
    expect(window.location.hash).toContain("#memory/product/")
    expect(await screen.findByText("Evidence timeline")).toBeInTheDocument()
    expect(screen.getByText("Linked conversations")).toBeInTheDocument()
    expect(screen.getAllByAltText("tag.jpg").length).toBeGreaterThan(0)
    expect(screen.getAllByAltText("tee.jpg").length).toBeGreaterThan(0)
    expect(screen.getAllByAltText("fit.jpg").length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole("button", { name: /back to memory/i }))
    expect(window.location.hash).toBe("#memory")
    expect(screen.queryByText("Evidence timeline")).not.toBeInTheDocument()
  })

  it("starts a grounded conversation from a saved product", async () => {
    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^memory$/i)
    await userEvent.click(
      await screen.findByRole("button", {
        name: /open zara - linen blend relaxed shirt memory/i,
      }),
    )
    await userEvent.click(screen.getByRole("button", { name: /ask about this/i }))

    expect(await screen.findByText(/using saved product: zara/i)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/ask mizaaj/i), "What worked last time?")
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))

    expect(apiMocks.askMizaaj).toHaveBeenCalledWith(
      expect.objectContaining({
        product_id: sampleProduct.id,
        question: "What worked last time?",
      }),
    )
  })

  it("requires extraction before asking with attached item photos", async () => {
    uploadMocks.uploadCaptureFile.mockResolvedValue({
      path: "captures/tag.jpg",
      mime_type: "image/jpeg",
      original_name: "tag.jpg",
      public_url: "http://localhost:9000/mizaaj-uploads/captures/tag.jpg",
    })

    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await userEvent.upload(
      screen.getByLabelText(/add images/i),
      new File(["tag"], "tag.jpg", { type: "image/jpeg" }),
    )
    expect(await screen.findAllByText(/1 photo attached/i)).not.toHaveLength(0)

    await userEvent.type(screen.getByLabelText(/ask mizaaj/i), "Should I buy this?")
    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))

    expect(await screen.findByText("Extract item details first so Mizaaj can use the photos.")).toBeInTheDocument()
    expect(apiMocks.askMizaaj).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: /^extract item details$/i }))

    await waitFor(() => expect(apiMocks.createCapture).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/temporary item context/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /send question to mizaaj/i }))

    expect(apiMocks.askMizaaj).toHaveBeenCalledWith(
      expect.objectContaining({
        capture_id: extractedCapture.id,
        product_id: undefined,
      }),
    )
  })

  it("loads private profile data and creates a reviewable capture draft", async () => {
    render(<App />)

    expect(await screen.findByText("Mizaaj")).toBeInTheDocument()
    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    expect(screen.queryByText("Session flow")).not.toBeInTheDocument()

    await navigateViaSidebar(/^capture$/i)
    await userEvent.type(
      screen.getByLabelText(/product or order text/i),
      "Zara linen shirt. Sizes S M L.",
    )
    await userEvent.click(screen.getByRole("button", { name: /extract draft/i }))

    expect(apiMocks.createCapture).toHaveBeenCalledWith(
      expect.objectContaining({
        source_type: "manual",
        text_blocks: expect.arrayContaining([expect.stringContaining("Zara")]),
      }),
    )
    expect(await screen.findByText("Review extracted facts")).toBeInTheDocument()
    expect(screen.getByText("material")).toBeInTheDocument()
    expect(screen.getByText(/linen from manual_input/i)).toBeInTheDocument()
  })

  it("explains why extraction cannot run without evidence", async () => {
    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^capture$/i)
    await userEvent.click(screen.getByRole("button", { name: /extract draft/i }))

    expect(await screen.findAllByText("Add a photo, page URL, or product text first.")).not.toHaveLength(0)
    expect(apiMocks.createCapture).not.toHaveBeenCalled()
  })

  it("keeps multiple uploaded photos visible in the capture flow", async () => {
    uploadMocks.uploadCaptureFile
      .mockResolvedValueOnce({
        path: "captures/tag.jpg",
        mime_type: "image/jpeg",
        original_name: "tag.jpg",
        public_url: "http://localhost:9000/mizaaj-uploads/captures/tag.jpg",
      })
      .mockResolvedValueOnce({
        path: "captures/size-chart.jpg",
        mime_type: "image/jpeg",
        original_name: "size-chart.jpg",
        public_url: "http://localhost:9000/mizaaj-uploads/captures/size-chart.jpg",
      })

    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^capture$/i)

    const galleryInput = screen.getByLabelText(/add images/i)
    await userEvent.upload(galleryInput, [
      new File(["tag"], "tag.jpg", { type: "image/jpeg" }),
      new File(["size chart"], "size-chart.jpg", { type: "image/jpeg" }),
    ])

    expect(await screen.findAllByText("2 ready for extraction")).not.toHaveLength(0)
    expect(screen.getByText("tag.jpg")).toBeInTheDocument()
    expect(screen.getByText("size-chart.jpg")).toBeInTheDocument()
    expect(window.location.hash).toBe("#capture")
  })

  it("keeps repeated camera captures attached", async () => {
    uploadMocks.uploadCaptureFile
      .mockResolvedValueOnce({
        path: "captures/camera-1.jpg",
        mime_type: "image/jpeg",
        original_name: "camera.jpg",
        public_url: "http://localhost:9000/mizaaj-uploads/captures/camera-1.jpg",
      })
      .mockResolvedValueOnce({
        path: "captures/camera-2.jpg",
        mime_type: "image/jpeg",
        original_name: "camera.jpg",
        public_url: "http://localhost:9000/mizaaj-uploads/captures/camera-2.jpg",
      })

    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^capture$/i)

    await userEvent.upload(
      screen.getByLabelText(/take photo/i),
      new File(["first"], "camera.jpg", { type: "image/jpeg" }),
    )
    expect(await screen.findAllByText("1 ready for extraction")).not.toHaveLength(0)

    await userEvent.upload(
      screen.getByLabelText(/take photo/i),
      new File(["second"], "camera.jpg", { type: "image/jpeg" }),
    )

    expect(await screen.findAllByText("2 ready for extraction")).not.toHaveLength(0)
    expect(uploadMocks.uploadCaptureFile).toHaveBeenCalledTimes(2)
    expect(screen.getAllByText("camera.jpg")).toHaveLength(2)
  })

  it("keeps uploaded photos attached and reports extraction failures", async () => {
    uploadMocks.uploadCaptureFile.mockResolvedValue({
      path: "captures/tag.jpg",
      mime_type: "image/jpeg",
      original_name: "tag.jpg",
      public_url: "http://localhost:9000/mizaaj-uploads/captures/tag.jpg",
    })
    apiMocks.createCapture.mockRejectedValue(new Error("OpenRouter extraction failed: image unavailable"))

    render(<App />)

    await waitFor(() => expect(apiMocks.getProfile).toHaveBeenCalledTimes(1))
    await navigateViaSidebar(/^capture$/i)

    await userEvent.upload(
      screen.getByLabelText(/take photo/i),
      new File(["tag"], "tag.jpg", { type: "image/jpeg" }),
    )
    expect(await screen.findAllByText("1 ready for extraction")).not.toHaveLength(0)

    await userEvent.click(screen.getByRole("button", { name: /extract draft/i }))

    expect(await screen.findAllByText("OpenRouter extraction failed: image unavailable")).not.toHaveLength(0)
    expect(apiMocks.createCapture).toHaveBeenCalledWith(
      expect.objectContaining({
        source_type: "upload",
        assets: expect.arrayContaining([
          expect.objectContaining({
            original_name: "tag.jpg",
          }),
        ]),
      }),
    )
    expect(screen.getByText("tag.jpg")).toBeInTheDocument()
  })
})
