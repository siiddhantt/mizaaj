import type { Components } from "react-markdown"
import ReactMarkdown from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"

const markdownComponents: Components = {
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-5 marker:text-primary">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1.5 pl-5 marker:text-primary">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-6">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="text-foreground/90">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-icy underline decoration-icy/40 underline-offset-4 transition-colors hover:text-foreground"
    >
      {children}
    </a>
  ),
  code: ({ children, className }) => (
    <code className={["rounded-md bg-background/70 px-1.5 py-0.5 text-[0.92em]", className].filter(Boolean).join(" ")}>
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-2xl border border-border/50 bg-background/60 p-3 text-xs leading-5">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-2xl border border-border/50">
      <table className="w-full min-w-96 border-collapse text-left text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-border/50 bg-background/50 px-3 py-2 font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-t border-border/35 px-3 py-2 text-muted-foreground">{children}</td>,
}

export function AssistantMarkdown({ content }: { content: string }) {
  return (
    <div className="mizaaj-markdown text-sm leading-6">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={markdownComponents}
      >
        {normalizeAssistantMarkdown(content)}
      </ReactMarkdown>
    </div>
  )
}

function normalizeAssistantMarkdown(content: string) {
  return content
    .trim()
    .replace(/^(From your saved memory:)\s+([A-Z][A-Za-z/&\s]{1,48}:)/, "$1\n\n- $2")
    .replace(/\s+-\s+(?=[A-Z][A-Za-z/&\s]{1,48}(?::|\s+(?:\u2013|-)))/g, "\n- ")
    .replace(/\s+\*\s+(?=[A-Z][A-Za-z/&\s]{1,48}:)/g, "\n  - ")
}
