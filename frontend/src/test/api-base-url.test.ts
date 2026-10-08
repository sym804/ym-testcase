import { describe, it, expect, vi, afterEach } from "vitest";

// VITE_API_URL 끝의 슬래시를 떼야 직접 이어 붙이는 주소(스테이징 PUT, 미리보기 img)가 // 로 깨지지 않는다.
describe("API_BASE_URL", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("끝 슬래시를 뗀다", async () => {
    vi.stubEnv("VITE_API_URL", "https://api.example/");
    vi.resetModules();
    const { API_BASE_URL } = await import("../api/client");
    expect(API_BASE_URL).toBe("https://api.example");
  });

  it("비어 있으면 빈 문자열(같은 출처)", async () => {
    vi.stubEnv("VITE_API_URL", "");
    vi.resetModules();
    const { API_BASE_URL } = await import("../api/client");
    expect(API_BASE_URL).toBe("");
  });
});
