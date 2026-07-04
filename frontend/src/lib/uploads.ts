import { api } from "@/lib/api"
import type { UploadedAsset } from "@/types"

const uploadTimeoutMs = Number(import.meta.env.VITE_UPLOAD_TIMEOUT_MS ?? 120_000)

export async function uploadCaptureFile(userId: string, file: File): Promise<UploadedAsset> {
  const intent = await api.createUploadIntent({
    user_id: userId,
    file_name: file.name,
    content_type: file.type || "application/octet-stream",
  })

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), uploadTimeoutMs)
  let response: Response
  try {
    response = await fetch(intent.upload_url, {
      method: intent.upload_method,
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
      signal: controller.signal,
    })
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === "AbortError"
    throw new Error(timedOut ? "Upload timed out. Try a smaller image or retry." : "Upload failed.", {
      cause: error,
    })
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`)
  }

  return {
    path: intent.path,
    mime_type: file.type,
    original_name: file.name,
    public_url: intent.public_url,
  }
}
