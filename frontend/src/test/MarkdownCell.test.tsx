import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import MarkdownCell from "../components/MarkdownCell";

function renderCell(value: string, keyword = "") {
  const props = {
    value,
    context: { searchKeyword: keyword },
  } as any;
  return render(<MarkdownCell {...props} />);
}

describe("MarkdownCell", () => {
  it("빈 값이면 아무것도 렌더링하지 않는다", () => {
    const { container } = renderCell("");
    expect(container.innerHTML).toBe("");
  });

  it("마크다운 bold를 strong으로 변환한다", () => {
    const { container } = renderCell("**bold text**");
    const strong = container.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong!.textContent).toBe("bold text");
  });

  it("마크다운 italic을 em으로 변환한다", () => {
    const { container } = renderCell("*italic*");
    const em = container.querySelector("em");
    expect(em).not.toBeNull();
    expect(em!.textContent).toBe("italic");
  });

  it("마크다운 code를 code 태그로 변환한다", () => {
    const { container } = renderCell("`inline code`");
    const code = container.querySelector("code");
    expect(code).not.toBeNull();
    expect(code!.textContent).toBe("inline code");
  });

  it("XSS 공격 태그를 제거한다 (DOMPurify)", () => {
    const { container } = renderCell('<script>alert("xss")</script>safe text');
    expect(container.innerHTML).not.toContain("<script>");
    expect(container.textContent).toContain("safe text");
  });

  it("허용되지 않은 태그를 제거한다 (img, iframe 등)", () => {
    const { container } = renderCell('<img src="x" onerror="alert(1)">text');
    expect(container.innerHTML).not.toContain("<img");
    expect(container.textContent).toContain("text");
  });

  it("키워드 하이라이트를 적용한다", () => {
    const { container } = renderCell("테스트 항목입니다", "테스트");
    const marks = container.querySelectorAll("mark.search-hl");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("테스트");
  });

  it("링크를 a 태그로 변환한다", () => {
    const { container } = renderCell("[link](https://example.com)");
    const a = container.querySelector("a");
    expect(a).not.toBeNull();
    expect(a!.getAttribute("href")).toBe("https://example.com");
    expect(a!.textContent).toBe("link");
  });
});
