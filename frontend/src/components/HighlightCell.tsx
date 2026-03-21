import { useMemo } from "react";
import type { CustomCellRendererProps } from "ag-grid-react";

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export default function HighlightCell(props: CustomCellRendererProps) {
  const raw = props.value != null ? String(props.value) : "";
  const keyword: string = (props.context?.searchKeyword as string) || "";

  const parts = useMemo(() => {
    if (!raw || !keyword) return null;
    const re = new RegExp(`(${escapeRegExp(keyword)})`, "gi");
    return raw.split(re);
  }, [raw, keyword]);

  if (!raw) return null;
  if (!parts) return <>{raw}</>;

  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === keyword.toLowerCase() ? (
          <mark key={i} className="search-hl">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}
