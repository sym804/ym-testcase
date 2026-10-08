import { describe, it, expect, vi, beforeEach } from "vitest";

// client 만 모킹하고 uploads 는 실제 모듈을 쓴다. 캐시가 처리 요청 결과에 맞게 비워지는지 본다.
vi.mock("../api/client", () => ({
  default: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
  API_BASE_URL: "",
}));

import client from "../api/client";
import { testCasesApi, testRunsApi, attachmentsApi } from "../api";
import { resetUploadCache } from "../api/uploads";

const LIMITS = { upload_limits: { attachment: 1000, tc_import: 1000, result_import: 1000 }, direct_upload: false };
let issued = 0;

function stagings() {
  return vi.mocked(client.post).mock.calls.filter(([url]) => url === "/api/uploads").length;
}

function httpError(status: number) {
  return Object.assign(new Error(`HTTP ${status}`), { response: { status } });
}

beforeEach(() => {
  vi.clearAllMocks();
  resetUploadCache();
  issued = 0;
  vi.mocked(client.get).mockResolvedValue({ data: LIMITS });
  vi.mocked(client.post).mockImplementation(async (url: string) => {
    if (url === "/api/uploads") {
      issued += 1;
      return { data: { upload_id: `u${issued}`, method: "PUT", url: `/api/uploads/u${issued}/content?token=t`, headers: {} } };
    }
    return { data: {} };
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200 }));
});

const xlsx = () => new File(["x"], "tc.xlsx");

function purposes() {
  return vi.mocked(client.post).mock.calls
    .filter(([url]) => url === "/api/uploads")
    .map(([, body]) => (body as { purpose: string }).purpose);
}

describe("스테이징 캐시와 처리 요청", () => {
  it("미리보기 뒤 가져오기는 한 번만 올린다", async () => {
    const f = xlsx();
    await testCasesApi.previewImport(1, f);
    await testCasesApi.importExcel(1, f);
    expect(stagings()).toBe(1);
  });

  it("가져오기가 끝난 뒤 같은 File 로 다시 가져오면 새로 올린다(서버가 이미 처리한 id)", async () => {
    const f = xlsx();
    await testCasesApi.importExcel(1, f);
    await testCasesApi.importExcel(1, f);
    expect(stagings()).toBe(2);
    expect(purposes()).toEqual(["tc_import", "tc_import"]);
    const ids = vi.mocked(client.post).mock.calls
      .filter(([url]) => url === "/api/projects/1/testcases/import")
      .map(([, , cfg]) => (cfg as { params: { upload_id: string } }).params.upload_id);
    expect(ids).toEqual(["u1", "u2"]);
  });

  it("결과 가져오기: dry run 뒤 적용은 한 번, 적용 뒤 다시 적용은 새로 올린다", async () => {
    const f = new File(["x"], "r.csv");
    await testRunsApi.importResults(1, 2, f, { dryRun: true, keepExecuted: false });
    await testRunsApi.importResults(1, 2, f, { dryRun: false, keepExecuted: false });
    expect(stagings()).toBe(1);
    await testRunsApi.importResults(1, 2, f, { dryRun: false, keepExecuted: false });
    expect(stagings()).toBe(2);
    expect(purposes()).toEqual(["result_import", "result_import"]);
  });

  it("첨부는 같은 File 을 두 번 올려도 각각 올린다", async () => {
    const f = new File(["x"], "a.png");
    await attachmentsApi.upload(3, f);
    await attachmentsApi.upload(3, f);
    expect(stagings()).toBe(2);
    expect(purposes()).toEqual(["attachment", "attachment"]);
  });

  it("미리보기가 404/409 면(만료·처리됨) 다음 시도는 새로 올린다", async () => {
    const f = xlsx();
    const base = vi.mocked(client.post).getMockImplementation()!;
    vi.mocked(client.post).mockImplementation(async (url: string, ...rest: unknown[]) => {
      if (url.endsWith("/import/preview") && issued === 1) throw httpError(404);
      return base(url, ...(rest as []));
    });
    await expect(testCasesApi.previewImport(1, f)).rejects.toThrow();
    await testCasesApi.previewImport(1, f);
    expect(stagings()).toBe(2);
  });

  it("미리보기가 다른 이유로 실패하면 id 를 그대로 쓴다(서버가 처리하지 않았다)", async () => {
    const f = xlsx();
    const base = vi.mocked(client.post).getMockImplementation()!;
    let failed = false;
    vi.mocked(client.post).mockImplementation(async (url: string, ...rest: unknown[]) => {
      if (url.endsWith("/import/preview") && !failed) {
        failed = true;
        throw httpError(400);
      }
      return base(url, ...(rest as []));
    });
    await expect(testCasesApi.previewImport(1, f)).rejects.toThrow();
    await testCasesApi.previewImport(1, f);
    expect(stagings()).toBe(1);
  });
});
