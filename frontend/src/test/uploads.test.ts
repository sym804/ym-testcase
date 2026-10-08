import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api/client", () => ({
  default: { post: vi.fn(), get: vi.fn() },
  API_BASE_URL: "http://api.example",
}));

import client from "../api/client";
import { stageUpload, UploadTooLargeError, resetUploadCache, tooLargeMessage, uploadErrorMessage } from "../api/uploads";

const LIMITS = { upload_limits: { attachment: 100, tc_import: 50, result_import: 80 }, direct_upload: false };

function file(name: string, size: number) {
  return new File([new Uint8Array(size)], name, { type: "text/csv" });
}

beforeEach(() => {
  vi.clearAllMocks();
  resetUploadCache();
  vi.mocked(client.get).mockResolvedValue({ data: LIMITS });
  vi.mocked(client.post).mockResolvedValue({
    data: { upload_id: "u1", method: "PUT", url: "/api/uploads/u1/content?token=t", headers: { "content-type": "text/csv" } },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200 }));
});

describe("stageUpload", () => {
  it("발급받고 직접 PUT 한 뒤 upload_id 를 돌려준다", async () => {
    const f = file("a.csv", 10);
    await expect(stageUpload("tc_import", f)).resolves.toBe("u1");
    expect(client.post).toHaveBeenCalledWith("/api/uploads", {
      purpose: "tc_import", filename: "a.csv", size: 10, content_type: "text/csv",
    });
    expect(fetch).toHaveBeenCalledWith("http://api.example/api/uploads/u1/content?token=t", {
      method: "PUT", body: f, headers: { "content-type": "text/csv" },
    });
  });

  it("발급 주소가 절대 주소면 그대로 쓰고 쿠키를 싣지 않는다", async () => {
    vi.mocked(client.post).mockResolvedValue({
      data: { upload_id: "u2", method: "PUT", url: "https://x.supabase.co/storage/v1/object/upload/sign/b/k?token=T", headers: {} },
    });
    await stageUpload("attachment", file("a.png", 5));
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("https://x.supabase.co/storage/v1/object/upload/sign/b/k?token=T");
    expect((init as RequestInit).credentials).toBeUndefined();
  });

  it("상한을 넘으면 발급하지 않고 UploadTooLargeError", async () => {
    await expect(stageUpload("tc_import", file("big.csv", 51))).rejects.toBeInstanceOf(UploadTooLargeError);
    expect(client.post).not.toHaveBeenCalled();
  });

  it("PUT 이 413 이면 UploadTooLargeError, 다른 실패는 일반 오류", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 413 } as Response);
    await expect(stageUpload("tc_import", file("a.csv", 10))).rejects.toBeInstanceOf(UploadTooLargeError);
    resetUploadCache();
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 500 } as Response);
    const err = await stageUpload("tc_import", file("b.csv", 10)).catch((e) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err).not.toBeInstanceOf(UploadTooLargeError);
  });

  it("같은 파일과 목적이면 한 번만 올린다(미리보기 뒤 가져오기)", async () => {
    const f = file("a.csv", 10);
    await stageUpload("tc_import", f);
    await stageUpload("tc_import", f);
    expect(client.post).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("목적이 다르거나 파일이 다르면 따로 올린다", async () => {
    const f = file("a.csv", 10);
    await stageUpload("tc_import", f);
    await stageUpload("result_import", f);
    await stageUpload("tc_import", file("a.csv", 10));
    expect(client.post).toHaveBeenCalledTimes(3);
  });

  it("실패한 업로드는 캐시하지 않아 다시 시도할 수 있다", async () => {
    const f = file("a.csv", 10);
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 500 } as Response);
    await expect(stageUpload("tc_import", f)).rejects.toThrow();
    await expect(stageUpload("tc_import", f)).resolves.toBe("u1");
  });
});

describe("tooLargeMessage", () => {
  const t = ((key: string, opts?: Record<string, unknown>) => `${key}${opts ? JSON.stringify(opts) : ""}`) as never;

  it("사전 검사 오류는 상한 MB 를 넣어 안내한다", () => {
    expect(tooLargeMessage(new UploadTooLargeError(50 * 1024 * 1024), t)).toBe('common:uploadTooLarge{"mb":"50"}');
  });

  it("서버나 프록시의 413 도 용량 초과로 본다(본문이 JSON 이 아니어도)", () => {
    expect(tooLargeMessage({ response: { status: 413, data: "<html>" } }, t)).toBe("common:uploadTooLargeNoLimit");
  });

  it("다른 오류는 null", () => {
    expect(tooLargeMessage({ response: { status: 500 } }, t)).toBeNull();
    expect(tooLargeMessage(new Error("x"), t)).toBeNull();
  });
});

describe("uploadErrorMessage", () => {
  const t = ((key: string, opts?: Record<string, unknown>) => `${key}${opts ? JSON.stringify(opts) : ""}`) as never;

  it("413 은 용량 초과 안내가 이긴다", () => {
    expect(uploadErrorMessage({ response: { status: 413, data: { detail: "x" } } }, t, "fallback")).toBe("common:uploadTooLargeNoLimit");
  });

  it("서버 detail 이 있으면 그것을 보여준다", () => {
    expect(uploadErrorMessage({ response: { status: 400, data: { detail: "시트가 비어 있습니다" } } }, t, "fallback")).toBe("시트가 비어 있습니다");
  });

  it("detail 이 없으면 주어진 기본 문구", () => {
    expect(uploadErrorMessage(new Error("network"), t, "fallback")).toBe("fallback");
  });
});
