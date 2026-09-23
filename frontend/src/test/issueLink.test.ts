import { describe, it, expect } from "vitest";
import { resolveIssueUrl } from "../utils/issueLink";

describe("resolveIssueUrl", () => {
  it("http(s) 주소는 그대로 쓴다", () => {
    expect(resolveIssueUrl("https://jira.x.com/browse/A-1", null)).toBe("https://jira.x.com/browse/A-1");
    expect(resolveIssueUrl("  http://x.com/1 ", null)).toBe("http://x.com/1");
  });

  it("이슈 키는 Base URL 뒤에 /browse/ 로 붙인다", () => {
    expect(resolveIssueUrl("PROJ-123", "https://jira.x.com")).toBe("https://jira.x.com/browse/PROJ-123");
  });

  it("Base URL 이 /browse/ 로 끝나도 두 번 붙이지 않는다", () => {
    // 관리자 매뉴얼은 이 모양을, 사용자 매뉴얼은 위 모양을 안내한다
    expect(resolveIssueUrl("PROJ-123", "https://x.atlassian.net/browse/")).toBe("https://x.atlassian.net/browse/PROJ-123");
    expect(resolveIssueUrl("PROJ-123", "https://x.atlassian.net/browse")).toBe("https://x.atlassian.net/browse/PROJ-123");
  });

  it("Linear 워크스페이스 주소는 /issue/ 로 붙인다", () => {
    expect(resolveIssueUrl("SYM-123", "https://linear.app/sym")).toBe("https://linear.app/sym/issue/SYM-123");
    expect(resolveIssueUrl("SYM-123", "https://linear.app/sym/issue/")).toBe("https://linear.app/sym/issue/SYM-123");
    // 브라우저 주소창에서 흔히 복사하는 팀 화면 주소
    expect(resolveIssueUrl("SYM-123", "https://linear.app/sym/team/SYM/active")).toBe("https://linear.app/sym/issue/SYM-123");
    expect(resolveIssueUrl("SYM-123", "https://linear.app/sym/?x=1")).toBe("https://linear.app/sym/issue/SYM-123");
  });

  it("주소에 {key} 가 있으면 그 자리에 넣는다", () => {
    expect(resolveIssueUrl("ABC-7", "https://tracker.x.com/items/{key}/view")).toBe("https://tracker.x.com/items/ABC-7/view");
  });

  it("Base URL 이 없거나 키 모양이 아니면 null", () => {
    expect(resolveIssueUrl("PROJ-123", null)).toBeNull();
    expect(resolveIssueUrl("PROJ-123", "")).toBeNull();
    expect(resolveIssueUrl("재현 안 됨", "https://jira.x.com")).toBeNull();
    expect(resolveIssueUrl("", "https://jira.x.com")).toBeNull();
    expect(resolveIssueUrl(null, "https://jira.x.com")).toBeNull();
  });

  it("javascript: 주소는 링크가 되지 않는다", () => {
    expect(resolveIssueUrl("javascript:alert(1)", "https://jira.x.com")).toBeNull();
    expect(resolveIssueUrl("PROJ-1", "javascript:alert(1)//")).toBeNull();
  });
});
