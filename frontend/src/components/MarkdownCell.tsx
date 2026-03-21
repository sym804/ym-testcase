import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { CustomCellRendererProps } from "ag-grid-react";

marked.setOptions({ gfm: true });

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightHtml(html: string, keyword: string): string {
  if (!keyword) return html;
  // Split by HTML tags to avoid highlighting inside tags
  const parts = html.split(/(<[^>]*>)/);
  const re = new RegExp(`(${escapeRegExp(keyword)})`, "gi");
  return parts
    .map((part) =>
      part.startsWith("<") ? part : part.replace(re, '<mark class="search-hl">$1</mark>')
    )
    .join("");
}

export default function MarkdownCell(props: CustomCellRendererProps) {
  const raw = typeof props.value === "string" ? props.value : "";
  const keyword: string = (props.context?.searchKeyword as string) || "";

  const html = useMemo(() => {
    if (!raw) return "";
    let result = raw
      .split("\n")
      .map((line) => marked.parseInline(line) as string)
      .join("\n");
    if (keyword) {
      result = highlightHtml(result, keyword);
    }
    // XSS 방어: DOMPurify로 sanitize
    return DOMPurify.sanitize(result, {
      ALLOWED_TAGS: ["strong", "em", "code", "a", "br", "mark", "span", "del", "ul", "ol", "li", "p"],
      ALLOWED_ATTR: ["href", "target", "rel", "class"],
    });
  }, [raw, keyword]);

  if (!raw) return null;

  return (
    <div
      className="md-cell"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
