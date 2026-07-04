import "@testing-library/jest-dom/vitest"
import { vi } from "vitest"

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

Object.defineProperty(window.URL, "createObjectURL", {
  writable: true,
  value: vi.fn(() => "blob:mizaaj-preview"),
})

Object.defineProperty(window.URL, "revokeObjectURL", {
  writable: true,
  value: vi.fn(),
})

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
}

if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = vi.fn()
}

if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = vi.fn()
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}
