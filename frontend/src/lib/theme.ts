export type Theme = "light" | "dark"

const storageKey = "mizaaj-theme"

export function resolveInitialTheme(
  storedValue: string | null,
  _prefersDark: boolean,
): Theme {
  if (storedValue === "light" || storedValue === "dark") return storedValue
  return "dark"
}

export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement) {
  root.classList.toggle("dark", theme === "dark")
  root.style.colorScheme = theme
}

export function readStoredTheme(): Theme {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
  return resolveInitialTheme(window.localStorage.getItem(storageKey), prefersDark)
}

export function storeTheme(theme: Theme) {
  window.localStorage.setItem(storageKey, theme)
}
