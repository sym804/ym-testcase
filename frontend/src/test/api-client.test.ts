import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock axios before importing client
vi.mock("axios", () => {
  const requestInterceptors: Array<{ fulfilled: (c: unknown) => unknown; rejected: (e: unknown) => unknown }> = [];
  const responseInterceptors: Array<{ fulfilled: (r: unknown) => unknown; rejected: (e: unknown) => unknown }> = [];

  const instance = {
    interceptors: {
      request: {
        use: (fulfilled: (c: unknown) => unknown, rejected: (e: unknown) => unknown) => {
          requestInterceptors.push({ fulfilled, rejected });
        },
      },
      response: {
        use: (fulfilled: (r: unknown) => unknown, rejected: (e: unknown) => unknown) => {
          responseInterceptors.push({ fulfilled, rejected });
        },
      },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    _requestInterceptors: requestInterceptors,
    _responseInterceptors: responseInterceptors,
  };

  return {
    default: {
      create: () => instance,
    },
    __instance: instance,
  };
});

let client: typeof import("../api/client").default = undefined!;
let instance: {
  _requestInterceptors: Array<{ fulfilled: (c: unknown) => unknown; rejected: (e: unknown) => unknown }>;
  _responseInterceptors: Array<{ fulfilled: (r: unknown) => unknown; rejected: (e: unknown) => unknown }>;
};

beforeEach(async () => {
  vi.resetModules();
  const mod = await import("../api/client");
  client = mod.default;
  const axiosMod = await import("axios");
  instance = (axiosMod as unknown as { __instance: typeof instance }).__instance;
});

describe("API Client Interceptors", () => {
  describe("Request Interceptor", () => {
    it("토큰이 있으면 Authorization 헤더를 추가한다", () => {
      localStorage.setItem("token", "test-jwt-token");
      const interceptor = instance._requestInterceptors[0];
      const config = { headers: {} as Record<string, string> };
      const result = interceptor.fulfilled(config) as typeof config;
      expect(result.headers.Authorization).toBe("Bearer test-jwt-token");
    });

    it("토큰이 없으면 Authorization 헤더를 추가하지 않는다", () => {
      const interceptor = instance._requestInterceptors[0];
      const config = { headers: {} as Record<string, string> };
      const result = interceptor.fulfilled(config) as typeof config;
      expect(result.headers.Authorization).toBeUndefined();
    });
  });

  describe("Response Interceptor", () => {
    it("401 응답 시 토큰을 제거하고 로그인 페이지로 리다이렉트한다", async () => {
      localStorage.setItem("token", "some-token");
      const originalHref = window.location.href;

      // Mock window.location
      vi.spyOn(window, "location", "get").mockReturnValue({
        ...window.location,
        pathname: "/projects",
        href: "/projects",
      } as Location);

      // location.href setter를 위한 별도 처리
      Object.defineProperty(window, "location", {
        value: { ...window.location, pathname: "/projects", href: "/projects" },
        writable: true,
        configurable: true,
      });

      const interceptor = instance._responseInterceptors[0];
      const error = { response: { status: 401 } };

      await expect(interceptor.rejected(error)).rejects.toEqual(error);
      expect(localStorage.getItem("token")).toBeNull();

      // Restore
      Object.defineProperty(window, "location", {
        value: { ...window.location, pathname: originalHref },
        writable: true,
        configurable: true,
      });
    });

    it("401이 아닌 에러는 그대로 reject한다", async () => {
      const interceptor = instance._responseInterceptors[0];
      const error = { response: { status: 500 } };
      await expect(interceptor.rejected(error)).rejects.toEqual(error);
    });

    it("정상 응답은 그대로 반환한다", () => {
      const interceptor = instance._responseInterceptors[0];
      const response = { data: { ok: true }, status: 200 };
      expect(interceptor.fulfilled(response)).toEqual(response);
    });
  });
});

void client; // ensure client is referenced
