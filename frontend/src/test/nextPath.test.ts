import { describe, it, expect } from "vitest";
import { safeNextPath, loginPathFor } from "../utils/nextPath";

describe("safeNextPath", () => {
  it("사이트 안 경로는 그대로", () => {
    expect(safeNextPath("/projects/3?tab=run")).toBe("/projects/3?tab=run");
  });

  it.each([null, "", "projects", "//evil.com", "/\\evil.com", "https://evil.com", "/a b", "/login", "/login?next=/x"])(
    "%s 는 목록으로", (raw) => {
      expect(safeNextPath(raw)).toBe("/projects");
    });
});

describe("loginPathFor", () => {
  it("지금 주소를 next 로 싣는다", () => {
    expect(loginPathFor("/projects/3", "?tab=run")).toBe("/login?next=%2Fprojects%2F3%3Ftab%3Drun");
  });

  it("목록과 루트는 next 를 붙이지 않는다", () => {
    expect(loginPathFor("/projects")).toBe("/login");
    expect(loginPathFor("/")).toBe("/login");
  });
});
