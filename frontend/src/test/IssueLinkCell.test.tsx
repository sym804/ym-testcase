import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "../i18n";
import IssueLinkCell from "../components/IssueLinkCell";

const renderCell = (value: string | null, trackerUrl: string | null) =>
  render(<IssueLinkCell {...({ value, context: { trackerUrl } } as any)} />);

describe("IssueLinkCell", () => {
  it("이슈 키는 이슈 관리 도구 주소로 여는 아이콘을 붙인다", () => {
    renderCell("SYM-123", "https://linear.app/sym");
    expect(screen.getByText("SYM-123")).toBeInTheDocument();
    expect(screen.getByTestId("issue-link-open")).toHaveAttribute("href", "https://linear.app/sym/issue/SYM-123");
  });

  it("새 탭으로, 원래 창에 접근하지 못하게 연다", () => {
    renderCell("SYM-123", "https://linear.app/sym");
    const a = screen.getByTestId("issue-link-open");
    expect(a).toHaveAttribute("target", "_blank");
    expect(a).toHaveAttribute("rel", "noopener noreferrer");
    expect(a).toHaveAccessibleName("SYM-123 이슈를 새 탭에서 열기");
  });

  it("아이콘 더블클릭은 셀로 번지지 않는다(브라우저 리스너 기준)", () => {
    // AG Grid 는 셀에 브라우저 리스너를 직접 단다. React 합성 이벤트로만 막으면
    // 편집기가 먼저 열린다(실제로 그랬고 Escape 로도 안 닫혔다). 그래서 부모에
    // 브라우저 리스너를 달고 확인한다.
    const { container } = renderCell("SYM-1", "https://linear.app/sym");
    const onParentDbl = vi.fn();
    container.addEventListener("dblclick", onParentDbl);

    fireEvent.doubleClick(screen.getByTestId("issue-link-open"));
    expect(onParentDbl).not.toHaveBeenCalled();

    // 글자에서의 더블클릭은 셀까지 간다(편집 진입)
    fireEvent.doubleClick(screen.getByText("SYM-1"));
    expect(onParentDbl).toHaveBeenCalledTimes(1);
  });

  it("더블클릭의 두 번째 클릭은 새 탭을 또 열지 않는다", () => {
    renderCell("SYM-1", "https://linear.app/sym");
    const a = screen.getByTestId("issue-link-open");
    const first = fireEvent.click(a, { detail: 1 });
    const second = fireEvent.click(a, { detail: 2 });
    // fireEvent 는 preventDefault 되면 false 를 돌려준다
    expect(first).toBe(true);
    expect(second).toBe(false);
  });

  it("↗ 를 누르면 포커스가 링크에 남지 않고 셀로 돌아간다", async () => {
    // 링크에 포커스가 남으면 다음 Enter 가 닫히지 않는 편집기를 열었다
    render(
      <div className="ag-cell" tabIndex={-1} data-testid="cell">
        <IssueLinkCell {...({ value: "SYM-1", context: { trackerUrl: "https://linear.app/sym" } } as any)} />
      </div>,
    );
    const a = screen.getByTestId("issue-link-open");
    a.addEventListener("click", (e) => e.preventDefault()); // jsdom 이 이동하지 않게
    a.focus();
    fireEvent.click(a, { detail: 1 });
    await new Promise((r) => setTimeout(r, 0));
    expect(document.activeElement).toBe(screen.getByTestId("cell"));
  });

  it("가운데 버튼을 포함해 누르는 순간 포커스는 링크가 아니라 셀로 간다", () => {
    render(
      <div className="ag-cell" tabIndex={-1} data-testid="cell">
        <IssueLinkCell {...({ value: "SYM-1", context: { trackerUrl: "https://linear.app/sym" } } as any)} />
      </div>,
    );
    const a = screen.getByTestId("issue-link-open");
    expect(a).toHaveAttribute("tabindex", "-1");
    for (const button of [0, 1]) {
      (document.body as HTMLElement).focus();
      const notPrevented = fireEvent.mouseDown(a, { button });
      expect(notPrevented, "링크가 포커스를 받으면 다음 Enter 가 닫히지 않는 편집기를 연다").toBe(false);
      expect(document.activeElement).toBe(screen.getByTestId("cell"));
    }
  });

  it("링크에서 누른 Enter 는 셀로 번지지 않는다", () => {
    const { container } = renderCell("SYM-1", "https://linear.app/sym");
    const onParentKey = vi.fn();
    container.addEventListener("keydown", onParentKey);
    fireEvent.keyDown(screen.getByTestId("issue-link-open"), { key: "Enter" });
    expect(onParentKey).not.toHaveBeenCalled();
    // 다른 키는 막지 않는다
    fireEvent.keyDown(screen.getByTestId("issue-link-open"), { key: "ArrowDown" });
    expect(onParentKey).toHaveBeenCalledTimes(1);
  });

  it("값이 링크 아닌 값에서 링크로 바뀌어도 더블클릭이 번지지 않는다", () => {
    // 리스너를 처음 그릴 때만 달면 편집으로 생긴 ↗ 에는 빠진다
    const props = (value: string) => ({ value, context: { trackerUrl: "https://linear.app/sym" } }) as any;
    const { container, rerender } = render(<IssueLinkCell {...props("재현 안 됨")} />);
    const onParentDbl = vi.fn();
    container.addEventListener("dblclick", onParentDbl);
    rerender(<IssueLinkCell {...props("SYM-5")} />);
    fireEvent.doubleClick(screen.getByTestId("issue-link-open"));
    expect(onParentDbl).not.toHaveBeenCalled();
  });

  it("주소는 그대로 연다", () => {
    renderCell("https://jira.x.com/browse/A-1", null);
    expect(screen.getByTestId("issue-link-open")).toHaveAttribute("href", "https://jira.x.com/browse/A-1");
  });

  it("주소를 만들 수 없으면 글자만 보인다", () => {
    renderCell("재현 안 됨", "https://linear.app/sym");
    expect(screen.getByText("재현 안 됨")).toBeInTheDocument();
    expect(screen.queryByTestId("issue-link-open")).toBeNull();
  });

  it("이슈 관리 도구 주소가 없으면 이슈 키에도 링크를 걸지 않는다", () => {
    renderCell("SYM-123", null);
    expect(screen.queryByTestId("issue-link-open")).toBeNull();
  });

  it("javascript: 값은 링크가 되지 않는다", () => {
    renderCell("javascript:alert(1)", "https://linear.app/sym");
    expect(screen.queryByTestId("issue-link-open")).toBeNull();
  });

  it("빈 값은 아무것도 그리지 않는다", () => {
    const { container } = renderCell("", "https://linear.app/sym");
    expect(container).toBeEmptyDOMElement();
  });
});
