import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import "./markdown.css";

/**
 * Renders model output as markdown.
 *
 * Safe by construction: react-markdown builds a React element tree rather
 * than setting innerHTML, and raw HTML in the source is *not* enabled
 * (no rehype-raw), so a caption or model reply containing `<script>` or an
 * `onerror` attribute is rendered as literal text. This matters here — the
 * bearer token lives in localStorage, so an XSS would be a session
 * compromise, and model output is untrusted input.
 *
 * Links get noopener/noreferrer for the same reason.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: content }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {content}
            </a>
          ),
          table: ({ children: content }) => (
            <div className="markdown__table-scroll">
              <table className="data-table">{content}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
