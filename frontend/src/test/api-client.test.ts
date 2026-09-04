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
  describe("Request Interceptor (CSRF)", () => {
    it("POST 요청 시 csrf_token 쿠키가 있으면 X-CSRF-Token 헤더를 추가한다", () => {
      Object.defineProperty(document, "cookie", { value: "csrf_token=test-csrf-123", writable: true, configurable: true });
      const interceptor = instance._requestInterceptors[0];
      const config = { method: "post", headers: {} as Record<string, string> };
      const result = interceptor.fulfilled(config) as typeof config;
      expect(result.headers["X-CSRF-Token"]).toBe("test-csrf-123");
      Object.defineProperty(document, "cookie", { value: "", writable: true, configurable: true });
    });

    it("GET 요청에는 CSRF 헤더를 추가하지 않는다", () => {
      Object.defineProperty(document, "cookie", { value: "csrf_token=test-csrf-123", writable: true, configurable: true });
      const interceptor = instance._requestInterceptors[0];
      const config = { method: "get", headers: {} as Record<string, string> };
      const result = interceptor.fulfilled(config) as typeof config;
      expect(result.headers["X-CSRF-Token"]).toBeUndefined();
      Object.defineProperty(document, "cookie", { value: "", writable: true, configurable: true });
    });

    it("csrf_token 쿠키가 없으면 헤더를 추가하지 않는다", () => {
      Object.defineProperty(document, "cookie", { value: "", writable: true, configurable: true });
      const interceptor = instance._requestInterceptors[0];
      const config = { method: "post", headers: {} as Record<string, string> };
      const result = interceptor.fulfilled(config) as typeof config;
      expect(result.headers["X-CSRF-Token"]).toBeUndefined();
    });
  });

  describe("Response Interceptor", () => {
    it("401 응답 시 로그인 페이지로 리다이렉트한다", async () => {
      Object.defineProperty(window, "location", {
        value: { ...window.location, pathname: "/projects", href: "/projects" },
        writable: true,
        configurable: true,
      });

      const interceptor = instance._responseInterceptors[0];
      const error = { response: { status: 401 } };

      await expect(interceptor.rejected(error)).rejects.toEqual(error);
      expect(window.location.href).toBe("/login");
    });

    it("인증이 필요한 경로(/projects)에서 401을 받으면 href 를 /login 으로 바꾼다", async () => {
      Object.defineProperty(window, "location", {
        value: { ...window.location, pathname: "/projects", href: "http://localhost/projects" },
        writable: true,
        configurable: true,
      });

      const interceptor = instance._responseInterceptors[0];
      const error = { response: { status: 401 } };

      await expect(interceptor.rejected(error)).rejects.toEqual(error);
      expect(window.location.href).toBe("/login");
    });

    it.each(["/login", "/register", "/account-help", "/reset-password"])(
      "비로그인 공개 경로 %s 에서는 401을 받아도 href 를 바꾸지 않는다",
      async (pathname) => {
        const initialHref = `http://localhost${pathname}`;
        Object.defineProperty(window, "location", {
          value: { ...window.location, pathname, href: initialHref },
          writable: true,
          configurable: true,
        });

        const interceptor = instance._responseInterceptors[0];
        const error = { response: { status: 401 } };

        // /reset-password/verify 는 잘못된/만료된 코드에도 401을 내려주므로,
        // 이 경로에서 401은 세션 만료가 아니라 정상적인 실패 응답이다.
        // 여기서 리다이렉트가 걸리면 resetFailed 에러 문구를 절대 볼 수 없다.
        await expect(interceptor.rejected(error)).rejects.toEqual(error);
        expect(window.location.href).toBe(initialHref);
      }
    );

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
