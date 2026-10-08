import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api/client", () => ({
  default: {
    post: vi.fn(),
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

// 업로드는 스테이징으로 먼저 올리고 upload_id 만 보낸다. 그 흐름은 uploads.test.ts 가 본다.
vi.mock("../api/uploads", () => ({ stageUpload: vi.fn().mockResolvedValue("uid-1") }));
import client from "../api/client";
import { testCasesApi } from "../api";
import { stageUpload } from "../api/uploads";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("testCasesApi", () => {
  describe("createSheet", () => {
    it("POST /api/projects/{id}/testcases/sheets 를 name body와 함께 호출한다", async () => {
      const mockResponse = { data: { name: "체크리스트", tc_count: 0 } };
      vi.mocked(client.post).mockResolvedValue(mockResponse);

      const result = await testCasesApi.createSheet(7, "체크리스트");

      expect(client.post).toHaveBeenCalledWith(
        "/api/projects/7/testcases/sheets",
        { name: "체크리스트", parent_id: null, is_folder: false }
      );
      expect(result).toEqual({ name: "체크리스트", tc_count: 0 });
    });
  });

  describe("deleteSheet", () => {
    it("DELETE /api/projects/{id}/testcases/sheets/{encodedName} 를 호출한다 (한글 인코딩)", async () => {
      const mockResponse = { data: { deleted: 5, sheet: "체크리스트" } };
      vi.mocked(client.delete).mockResolvedValue(mockResponse);

      const result = await testCasesApi.deleteSheet(3, "체크리스트");

      expect(client.delete).toHaveBeenCalledWith(
        `/api/projects/3/testcases/sheets/${encodeURIComponent("체크리스트")}`
      );
      expect(result).toEqual({ deleted: 5, sheet: "체크리스트" });
    });
  });

  describe("bulkDelete", () => {
    it("DELETE /api/projects/{id}/testcases/bulk 를 ids 쉼표 구분 params로 호출한다", async () => {
      const mockResponse = { data: { deleted: 3 } };
      vi.mocked(client.delete).mockResolvedValue(mockResponse);

      const result = await testCasesApi.bulkDelete(2, [10, 20, 30]);

      expect(client.delete).toHaveBeenCalledWith(
        "/api/projects/2/testcases/bulk",
        { params: { ids: "10,20,30" } }
      );
      expect(result).toEqual({ deleted: 3 });
    });
  });

  describe("listSheets", () => {
    it("GET /api/projects/{id}/testcases/sheets 를 호출한다", async () => {
      const sheets = [
        { name: "기본", tc_count: 10 },
        { name: "체크리스트", tc_count: 5 },
      ];
      vi.mocked(client.get).mockResolvedValue({ data: sheets });

      const result = await testCasesApi.listSheets(4);

      expect(client.get).toHaveBeenCalledWith(
        "/api/projects/4/testcases/sheets"
      );
      expect(result).toEqual(sheets);
    });
  });

  describe("previewImport", () => {
    it("POST /api/projects/{id}/testcases/import/preview 를 upload_id 와 함께 호출한다", async () => {
      const preview = { sheets: [{ name: "Sheet1", tc_count: 15 }] };
      vi.mocked(client.post).mockResolvedValue({ data: preview });

      const file = new File(["dummy"], "test.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const result = await testCasesApi.previewImport(5, file);

      expect(client.post).toHaveBeenCalledWith(
        "/api/projects/5/testcases/import/preview",
        null,
        { params: { upload_id: "uid-1" } }
      );
      // 파일은 스테이징 업로드로 같은 목적에 넘겼는지 확인
      expect(stageUpload).toHaveBeenCalledWith("tc_import", file);
      expect(result).toEqual(preview);
    });
  });

  describe("importExcel with sheetNames", () => {
    it("params에 sheet_names가 포함된다", async () => {
      const importResult = { imported: 10, sheets: [{ sheet: "기능", imported: 10 }] };
      vi.mocked(client.post).mockResolvedValue({ data: importResult });

      const file = new File(["dummy"], "test.xlsx");

      const result = await testCasesApi.importExcel(6, file, ["기능", "UI"]);

      expect(client.post).toHaveBeenCalledWith(
        "/api/projects/6/testcases/import",
        null,
        { params: { sheet_names: "기능,UI", upload_id: "uid-1" } }
      );
      expect(result).toEqual(importResult);
    });
  });

  describe("importExcel without sheetNames", () => {
    it("sheetNames가 없으면 params가 빈 객체이다", async () => {
      const importResult = { imported: 5, sheets: [{ sheet: "Sheet1", imported: 5 }] };
      vi.mocked(client.post).mockResolvedValue({ data: importResult });

      const file = new File(["dummy"], "test.xlsx");

      const result = await testCasesApi.importExcel(6, file);

      expect(client.post).toHaveBeenCalledWith(
        "/api/projects/6/testcases/import",
        null,
        { params: { upload_id: "uid-1" } }
      );
      expect(result).toEqual(importResult);
    });
  });
});
