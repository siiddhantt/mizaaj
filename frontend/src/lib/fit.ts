import type { FitProfile, PurchaseRecord } from "@/types"

export function normalizeSensitivities(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function confidencePercent(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 100)
}

export function confidenceLabel(value: number): "Low" | "Medium" | "High" {
  if (value >= 0.75) return "High"
  if (value >= 0.5) return "Medium"
  return "Low"
}

export function memoryTimelineFrom(profile: FitProfile | null, purchases: PurchaseRecord[]) {
  return [
    ...(profile
      ? [
          {
            title: "Fit profile",
            detail: `${profile.display_name}: ${profile.sensitivities.join(", ")}`,
          },
        ]
      : []),
    ...purchases.map((purchase) => ({
      title: `Purchase ${purchase.purchased_size}`,
      detail: `${purchase.outcome} - ${purchase.fit_notes ?? "No notes"}`,
    })),
  ]
}
