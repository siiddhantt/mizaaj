import {
  ClerkProvider,
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
  useAuth,
} from "@clerk/react"

import { App } from "@/App"

function AuthenticatedApp() {
  const { getToken } = useAuth()
  return <App authTokenProvider={getToken} userMenu={<UserButton />} />
}

function AuthGate() {
  return (
    <>
      <Show when="signed-in">
        <AuthenticatedApp />
      </Show>
      <Show when="signed-out">
        <main className="app-shell grid min-h-dvh place-items-center px-5">
          <div className="ambient-grid" aria-hidden="true" />
          <section className="glass-panel relative z-10 w-full max-w-lg rounded-[2rem] p-6 text-center shadow-2xl">
            <p className="text-sm font-medium text-icy">Private AI fit memory</p>
            <h1 className="mt-4 font-display text-4xl font-normal text-gradient">Mizaaj</h1>
            <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
              Sign in to keep your fit memory private across captures, questions, and try-on outcomes.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
              <SignInButton mode="modal">
                <button className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-medium text-primary-foreground shadow-lg shadow-black/20">
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-background/45 px-6 text-sm font-medium backdrop-blur">
                  Create account
                </button>
              </SignUpButton>
            </div>
          </section>
        </main>
      </Show>
    </>
  )
}

export default function ClerkAuth({ publishableKey }: { publishableKey: string }) {
  return (
    <ClerkProvider publishableKey={publishableKey}>
      <AuthGate />
    </ClerkProvider>
  )
}
