import { useEffect, useRef } from "react";
import type { CustomCellRendererProps } from "ag-grid-react";
import { useTranslation } from "react-i18next";
import { resolveIssueUrl } from "../utils/issueLink";

/**
 * 이슈 링크 칸. 글자는 그대로 두고, 이동할 주소가 있으면 옆에 ↗ 를 붙인다.
 *
 * ★글자 전체를 링크로 만들지 않는다. 이 칸은 편집 칸이라 더블클릭으로 편집에
 *   들어가는데, 글자가 링크면 더블클릭 한 번에 새 탭이 두 번 열린다.
 *
 * 주소는 context.trackerUrl(프로젝트의 이슈 관리 도구 주소)로 만든다. 규칙은
 * 리포트와 같은 resolveIssueUrl 이다.
 */
export default function IssueLinkCell(props: CustomCellRendererProps) {
  const { t } = useTranslation("testrun");
  const linkRef = useRef<HTMLAnchorElement>(null);
  const raw = props.value != null ? String(props.value) : "";
  const url = raw ? resolveIssueUrl(raw, props.context?.trackerUrl as string | null | undefined) : null;

  // ★↗ 는 셀 편집과 엮이면 안 된다. 두 가지를 브라우저 리스너로 막는다. React 의
  //   합성 이벤트는 AG Grid 가 셀에 직접 단 리스너보다 늦게 돌아서 막지 못한다.
  //   1. 더블클릭이 셀로 번지면 편집기가 열리고, 그 편집기는 Escape 로 안 닫혔다.
  //   2. 링크가 포커스를 가지면 다음 Enter 가 같은 상태의 편집기를 열었다
  //      (왼쪽 클릭, 가운데 버튼 클릭 모두). 그래서 링크는 포커스를 받지 않고,
  //      누르는 순간 포커스를 셀로 보낸다. 링크 이동은 click/auxclick 이 그대로 한다.
  useEffect(() => {
    const el = linkRef.current;
    if (!el) return;
    const stop = (e: Event) => e.stopPropagation();
    const keepFocusOnCell = (e: MouseEvent) => {
      e.preventDefault();
      (el.closest(".ag-cell") as HTMLElement | null)?.focus();
    };
    const stopEnter = (e: KeyboardEvent) => {
      if (e.key === "Enter") e.stopPropagation();
    };
    el.addEventListener("dblclick", stop);
    el.addEventListener("mousedown", keepFocusOnCell);
    el.addEventListener("keydown", stopEnter);
    return () => {
      el.removeEventListener("dblclick", stop);
      el.removeEventListener("mousedown", keepFocusOnCell);
      el.removeEventListener("keydown", stopEnter);
    };
  }, [url]);

  if (!raw) return null;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, maxWidth: "100%" }}>
      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{raw}</span>
      {url && (
        <a
          ref={linkRef}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="issue-link-open"
          aria-label={t("issueLinkOpen", { key: raw })}
          title={url}
          // 셀 안의 링크라 Tab 으로 닿지 않는다. 포커스를 받지 않게 둔다(위 주석 2)
          tabIndex={-1}
          onClick={(e) => {
            // 더블클릭의 두 번째 클릭은 새 탭을 또 열지 않는다
            if (e.detail > 1) e.preventDefault();
            // 포커스가 어떤 경로로든 링크에 와 있었으면 셀로 돌려놓는다
            const cell = e.currentTarget.closest(".ag-cell") as HTMLElement | null;
            setTimeout(() => cell?.focus(), 0);
          }}
          // 셀 글자를 드래그해 복사할 때 ↗ 가 섞이지 않게 한다
          style={{ color: "var(--color-link)", textDecoration: "none", fontWeight: 700, userSelect: "none" }}
        >
          ↗
        </a>
      )}
    </span>
  );
}
