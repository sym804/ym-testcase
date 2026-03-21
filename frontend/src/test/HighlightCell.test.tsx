import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HighlightCell from "../components/HighlightCell";

// ag-grid CustomCellRendererProps를 최소한으로 모방
function renderCell(value: string | number | null, keyword = "") {
  const props = {
    value,
    context: { searchKeyword: keyword },
  } as any;
  return render(<HighlightCell {...props} />);
}

describe("HighlightCell", () => {
  it("값이 없으면 아무것도 렌더링하지 않는다", () => {
    const { container } = renderCell(null);
    expect(container.textContent).toBe("");
  });

  it("키워드 없이 텍스트를 그대로 표시한다", () => {
    renderCell("로그인 테스트");
    expect(screen.getByText("로그인 테스트")).toBeInTheDocument();
  });

  it("키워드가 있으면 mark 태그로 하이라이트한다", () => {
    const { container } = renderCell("로그인 테스트 케이스", "테스트");
    const marks = container.querySelectorAll("mark.search-hl");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("테스트");
  });

  it("대소문자 무관하게 하이라이트한다", () => {
    const { container } = renderCell("Login Test Case", "test");
    const marks = container.querySelectorAll("mark.search-hl");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("Test");
  });

  it("숫자 값도 문자열로 변환하여 표시한다", () => {
    renderCell(42);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("여러 매칭을 모두 하이라이트한다", () => {
    const { container } = renderCell("test abc test def test", "test");
    const marks = container.querySelectorAll("mark.search-hl");
    expect(marks).toHaveLength(3);
  });
});
