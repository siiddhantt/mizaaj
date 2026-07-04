import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AssistantMarkdown } from "@/components/assistant-markdown"

describe("AssistantMarkdown", () => {
  it("renders assistant answers as structured markdown", () => {
    const { container } = render(
      <AssistantMarkdown content="From your saved memory: Size: Stay with L. - Comfort: Prefer relaxed drape. * Shoulders: Check the seam." />,
    )

    expect(container.querySelectorAll("p")).toHaveLength(1)
    expect(container.querySelectorAll("ul").length).toBeGreaterThanOrEqual(1)
    expect(container.querySelectorAll("li")).toHaveLength(3)
    expect(screen.getByText(/stay with l/i)).toBeInTheDocument()
    expect(screen.getByText(/prefer relaxed drape/i)).toBeInTheDocument()
    expect(screen.getByText(/check the seam/i)).toBeInTheDocument()
  })

  it("skips raw html in assistant answers", () => {
    const { container } = render(
      <AssistantMarkdown content={'**Safe answer** <img src="x" onerror="alert(1)" />'} />,
    )

    expect(screen.getByText("Safe answer")).toBeInTheDocument()
    expect(container.querySelector("img")).toBeNull()
  })
})
