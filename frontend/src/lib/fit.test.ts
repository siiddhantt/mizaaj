import { describe, expect, it } from "vitest"

import { confidenceLabel, confidencePercent, normalizeSensitivities } from "@/lib/fit"

describe("fit utilities", () => {
  it("normalizes messy sensitivity text into stable profile values", () => {
    expect(normalizeSensitivities(" tight chest, , long sleeves, scratchy fabric ")).toEqual([
      "tight chest",
      "long sleeves",
      "scratchy fabric",
    ])
  })

  it("clamps confidence values for UI display", () => {
    expect(confidencePercent(-1)).toBe(0)
    expect(confidencePercent(0.612)).toBe(61)
    expect(confidencePercent(2)).toBe(100)
  })

  it("labels recommendation confidence in user-friendly buckets", () => {
    expect(confidenceLabel(0.3)).toBe("Low")
    expect(confidenceLabel(0.6)).toBe("Medium")
    expect(confidenceLabel(0.9)).toBe("High")
  })
})
