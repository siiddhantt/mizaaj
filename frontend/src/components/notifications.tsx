import { CheckCircle2, Info, X, XCircle } from "lucide-react"
import { useCallback, useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type NotificationKind = "success" | "error" | "info"

export interface AppNotification {
  id: string
  kind: NotificationKind
  title: string
  detail?: string
}

type NotifyInput = Omit<AppNotification, "id">

function notificationId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<AppNotification[]>([])

  const dismiss = useCallback((id: string) => {
    setNotifications((current) => current.filter((item) => item.id !== id))
  }, [])

  const notify = useCallback(
    (input: NotifyInput) => {
      const notification = { ...input, id: notificationId() }
      setNotifications((current) => {
        const alreadyVisible = current.some(
          (item) =>
            item.kind === input.kind &&
            item.title === input.title &&
            item.detail === input.detail,
        )
        return alreadyVisible ? current : [notification, ...current].slice(0, 4)
      })
      window.setTimeout(() => dismiss(notification.id), input.kind === "error" ? 7000 : 4200)
    },
    [dismiss],
  )

  return {
    notifications,
    dismiss,
    success: (title: string, detail?: string) => notify({ kind: "success", title, detail }),
    error: (title: string, detail?: string) => notify({ kind: "error", title, detail }),
    info: (title: string, detail?: string) => notify({ kind: "info", title, detail }),
  }
}

export function NotificationStack({
  notifications,
  onDismiss,
}: {
  notifications: AppNotification[]
  onDismiss: (id: string) => void
}) {
  if (!notifications.length) return null

  return (
    <div className="pointer-events-none fixed inset-x-3 top-20 z-50 flex flex-col items-end gap-2 sm:left-auto sm:w-[24rem]">
      {notifications.map((notification) => {
        const Icon =
          notification.kind === "success" ? CheckCircle2 : notification.kind === "error" ? XCircle : Info

        return (
          <div
            key={notification.id}
            className={cn(
              "notification-surface pointer-events-auto flex w-full items-start gap-3 rounded-[1.35rem] p-3 soft-enter",
              notification.kind === "error" && "border-destructive/35",
              notification.kind === "success" && "border-secondary/40",
            )}
            role={notification.kind === "error" ? "alert" : "status"}
          >
            <span
              className={cn(
                "mt-0.5 grid size-8 shrink-0 place-items-center rounded-full",
                notification.kind === "error"
                  ? "bg-destructive/12 text-destructive"
                  : notification.kind === "success"
                    ? "bg-secondary/35 text-secondary-foreground"
                    : "bg-primary/10 text-primary",
              )}
            >
              <Icon className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">{notification.title}</span>
              {notification.detail ? (
                <span className="mt-1 block text-sm leading-5 text-muted-foreground">
                  {notification.detail}
                </span>
              ) : null}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="rounded-full"
              aria-label={`Dismiss ${notification.title}`}
              onClick={() => onDismiss(notification.id)}
            >
              <X />
            </Button>
          </div>
        )
      })}
    </div>
  )
}
