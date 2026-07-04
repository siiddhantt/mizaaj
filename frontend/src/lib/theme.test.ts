import { describe, expect, it } from "vitest"

import { applyTheme, resolveInitialTheme } from "@/lib/theme"

describe("theme utilities", () => {
  it("prefers an explicit stored theme over system preference", () => {
    expect(resolveInitialTheme("light", true)).toBe("light")
    expect(resolveInitialTheme("dark", false)).toBe("dark")
  })

  it("falls back to the cinematic dark default when no valid theme is stored", () => {
    expect(resolveInitialTheme(null, true)).toBe("dark")
    expect(resolveInitialTheme("unexpected", false)).toBe("dark")
  })

  it("applies the dark class and color scheme to the root element", () => {
    const root = document.createElement("html")
    applyTheme("dark", root)
    expect(root).toHaveClass("dark")
    expect(root.style.colorScheme).toBe("dark")

    applyTheme("light", root)
    expect(root).not.toHaveClass("dark")
    expect(root.style.colorScheme).toBe("light")
  })
})
