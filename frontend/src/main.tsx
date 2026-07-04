import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { lazy, StrictMode, Suspense } from "react"
import { createRoot } from "react-dom/client"

import { App } from "@/App"
import "@/styles/globals.css"

const queryClient = new QueryClient()
const root = document.getElementById("root")
const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined
const ClerkAuth = lazy(() => import("@/ClerkAuth"))

if (!root) {
  throw new Error("Root element not found")
}

function LoadingShell() {
  return (
    <main className="app-shell grid min-h-dvh place-items-center px-5">
      <div className="ambient-grid" aria-hidden="true" />
      <section className="glass-panel relative z-10 rounded-[2rem] px-6 py-5 text-center">
        <p className="font-display text-2xl font-normal text-gradient">Mizaaj</p>
        <p className="mt-2 text-sm text-muted-foreground">Opening private memory...</p>
      </section>
    </main>
  )
}

function AppRoot() {
  const app = clerkPublishableKey ? (
    <Suspense fallback={<LoadingShell />}>
      <ClerkAuth publishableKey={clerkPublishableKey} />
    </Suspense>
  ) : (
    <App />
  )

  return <QueryClientProvider client={queryClient}>{app}</QueryClientProvider>
}

createRoot(root).render(
  <StrictMode>
    <AppRoot />
  </StrictMode>,
)
