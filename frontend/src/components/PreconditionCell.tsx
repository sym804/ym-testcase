import { useCallback, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { marked } from "marked";
import DOMPurify from "dompurify";
import type { CustomCellRendererProps } from "ag-grid-react";
import { parseRef, resolveRef, type PreconditionRef } from "../utils/precondition";

marked.setOptions({ gfm: true });

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function inlineHtml(text: string, keyword: string): string {
  let html = marked.parseInline(text) as string;
  if (keyword) {
    const re = new RegExp(`(${escapeRegExp(keyword)})`, "gi");
    html = html
      .split(/(<[^>]*>)/)
      .map((part) => (part.startsWith("<") ? part : part.replace(re, '<mark class="search-hl">$1</mark>')))
      .join("");
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["strong", "em", "code", "a", "br", "mark", "span", "del", "ul", "ol", "li", "p"],
    ALLOWED_ATTR: ["href", "target", "rel", "class"],
  });
}

/** "3. " 같은 항목 번호 접두사와 본문을 분리한다. */
const NUM_PREFIX_RE = /^(\d+\.\s*)?([\s\S]*)$/;

const POPUP_WIDTH = 400;

interface PopupState {
  ref: PreconditionRef;
  left: number;
  top: number;
  placeAbove: boolean;
}

export default function PreconditionCell(props: CustomCellRendererProps) {
  const raw = typeof props.value === "string" ? props.value : "";
  const keyword: string = (props.context?.searchKeyword as string) || "";
  const ctxIndex = props.context?.preconditionIndex as Map<string, string> | undefined;
  const index = useMemo(() => ctxIndex ?? new Map<string, string>(), [ctxIndex]);

  const [popup, setPopup] = useState<PopupState | null>(null);
  const hideTimer = useRef<number | null>(null);

  const show = useCallback((ref: PreconditionRef, el: HTMLElement) => {
    if (hideTimer.current !== null) {
      window.clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
    const r = el.getBoundingClientRect();
    const placeAbove = r.bottom + 240 > window.innerHeight && r.top > 240;
    setPopup({
      ref,
      left: Math.min(Math.max(8, r.left), window.innerWidth - POPUP_WIDTH - 8),
      top: placeAbove ? r.top - 6 : r.bottom + 6,
      placeAbove,
    });
  }, []);

  const hide = useCallback(() => {
    hideTimer.current = window.setTimeout(() => setPopup(null), 60);
  }, []);

  const lines = useMemo(() => raw.split("\n"), [raw]);
  const resolved = useMemo(
    () => (popup ? resolveRef(popup.ref, index) : null),
    [popup, index],
  );

  if (!raw) return null;

  return (
    <div className="md-cell">
      {lines.map((line, i) => {
        const m = NUM_PREFIX_RE.exec(line);
        const numPrefix = m?.[1] ?? "";
        const body = m?.[2] ?? line;
        const ref = parseRef(body);

        if (!ref) {
          return (
            <div key={i} dangerouslySetInnerHTML={{ __html: inlineHtml(line, keyword) }} />
          );
        }
        return (
          <div key={i}>
            {numPrefix}
            <span
              className="pre-ref"
              tabIndex={0}
              onMouseEnter={(e) => show(ref, e.currentTarget)}
              onMouseLeave={hide}
              onFocus={(e) => show(ref, e.currentTarget)}
              onBlur={hide}
            >
              {body.trim()}
            </span>
          </div>
        );
      })}

      {popup && resolved &&
        createPortal(
          <div
            className="pre-ref-popup"
            style={{
              left: popup.left,
              top: popup.placeAbove ? undefined : popup.top,
              bottom: popup.placeAbove ? window.innerHeight - popup.top : undefined,
              width: POPUP_WIDTH,
            }}
          >
            <div className="pre-ref-popup-title">{resolved.title}</div>
            <ol className="pre-ref-popup-list">
              {resolved.items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ol>
          </div>,
          document.body,
        )}
    </div>
  );
}
