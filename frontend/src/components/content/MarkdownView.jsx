import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";

const SAFE_LINK = /^(https?:|mailto:)/i;

function linkHref(href) {
  if (typeof href !== "string") {
    return undefined;
  }
  const cleaned = DOMPurify.sanitize(href, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
  return SAFE_LINK.test(cleaned) ? cleaned : undefined;
}

export default function MarkdownView({ text }) {
  return (
    <div className="markdown text-sm leading-6">
      <ReactMarkdown
        skipHtml
        components={{
          a: ({ href, children }) => (
            <a href={linkHref(href)} rel="noreferrer noopener" className="text-accent">
              {children}
            </a>
          ),
          p: ({ children }) => <p className="mb-3">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 list-disc pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal pl-5">{children}</ol>,
          code: ({ children }) => (
            <code className="rounded bg-bg px-1 font-mono text-[0.95em]">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="mb-3 overflow-x-auto rounded-xl bg-bg p-3 font-mono text-sm">
              {children}
            </pre>
          ),
          h1: ({ children }) => <h2 className="mb-2 text-xl font-semibold">{children}</h2>,
          h2: ({ children }) => <h3 className="mb-2 text-lg font-semibold">{children}</h3>,
        }}
      >
        {text || ""}
      </ReactMarkdown>
    </div>
  );
}
