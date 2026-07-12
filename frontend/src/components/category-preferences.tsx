import { Plus, Trash2 } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { FitProfile } from "@/types"


type ProfileSetter = (update: (current: FitProfile | null) => FitProfile | null) => void
type Preference = FitProfile["category_preferences"][number]

const quickCategories = ["tshirt", "shirt", "jeans", "trousers"] as const
const availableCategories = [...quickCategories, "jacket"] as const
const availableFits = ["slim", "regular", "relaxed", "oversized", "cropped"] as const


export function CategoryPreferences({
  profile,
  setProfile,
}: {
  profile: FitProfile
  setProfile: ProfileSetter
}) {
  function add(category: Preference["category"]) {
    setProfile((current) => {
      if (!current || current.category_preferences.some((item) => item.category === category)) {
        return current
      }
      return {
        ...current,
        category_preferences: [
          ...current.category_preferences,
          { category, usual_size: "", preferred_fit: "regular" },
        ],
      }
    })
  }

  function update(index: number, value: Partial<Preference>) {
    setProfile((current) =>
      current
        ? {
            ...current,
            category_preferences: current.category_preferences.map((item, itemIndex) =>
              itemIndex === index ? { ...item, ...value } : item,
            ),
          }
        : current,
    )
  }

  function remove(index: number) {
    setProfile((current) =>
      current
        ? {
            ...current,
            category_preferences: current.category_preferences.filter(
              (_, itemIndex) => itemIndex !== index,
            ),
          }
        : current,
    )
  }

  return (
    <div className="mt-6 space-y-4 border-t border-border/45 pt-6">
      <div>
        <h4 className="text-sm font-semibold">Category size baselines</h4>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          Record only sizes you already know. Outcomes can override these baselines later.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {quickCategories.map((category) => (
          <Button
            key={category}
            type="button"
            size="sm"
            variant="outline"
            className="rounded-full bg-background/35"
            disabled={profile.category_preferences.some((item) => item.category === category)}
            onClick={() => add(category)}
          >
            <Plus className="size-3.5" />
            {label(category)}
          </Button>
        ))}
      </div>
      {profile.category_preferences.length ? (
        <div className="space-y-3">
          {profile.category_preferences.map((preference, index) => (
            <div
              key={`${preference.category}-${index}`}
              className="rounded-[1.5rem] border border-border/55 bg-background/30 p-4"
            >
              <div className="grid gap-3 sm:grid-cols-[minmax(0,0.8fr)_minmax(0,0.6fr)_minmax(0,0.8fr)_auto] sm:items-end">
                <Field label="Category">
                  <Select
                    value={preference.category}
                    onValueChange={(value) =>
                      update(index, { category: value as Preference["category"] })
                    }
                  >
                    <SelectTrigger className="w-full rounded-2xl bg-background/45">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {availableCategories.map((category) => (
                        <SelectItem key={category} value={category}>
                          {label(category)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Usual size">
                  <Input
                    value={preference.usual_size}
                    placeholder="M"
                    onChange={(event) => update(index, { usual_size: event.target.value })}
                  />
                </Field>
                <Field label="Preferred fit">
                  <Select
                    value={preference.preferred_fit}
                    onValueChange={(value) =>
                      update(index, { preferred_fit: value as Preference["preferred_fit"] })
                    }
                  >
                    <SelectTrigger className="w-full rounded-2xl bg-background/45">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFits.map((fit) => (
                        <SelectItem key={fit} value={fit}>
                          {label(fit)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="rounded-full"
                  aria-label={`Remove ${preference.category} baseline`}
                  onClick={() => remove(index)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
              <Input
                value={preference.notes ?? ""}
                placeholder="Optional: M works only in relaxed cuts"
                className="mt-3"
                onChange={(event) => update(index, { notes: event.target.value })}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}


function Field({ label: value, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-2">
      <Label>{value}</Label>
      {children}
    </div>
  )
}


function label(value: string) {
  if (value === "tshirt") return "T-shirt"
  return value.charAt(0).toUpperCase() + value.slice(1)
}
