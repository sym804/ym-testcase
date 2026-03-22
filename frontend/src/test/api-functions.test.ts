import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api/client", () => ({
  default: {
    post: vi.fn(),
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

import client from "../api/client";
import { testCasesApi } from "../api";

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
    it("POST /api/projects/{id}/testcases/import/preview 를 FormData와 함께 호출한다", async () => {
      const preview = { sheets: [{ name: "Sheet1", tc_count: 15 }] };
      vi.mocked(client.post).mockResolvedValue({ data: preview });

      const file = new File(["dummy"], "test.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const result = await testCasesApi.previewImport(5, file);

      expect(client.post).toHaveBeenCalledWith(
        "/api/projects/5/testcases/import/preview",
        expect.any(FormData),
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      // FormData에 file이 포함되어 있는지 확인
      const callArgs = vi.mocked(client.post).mock.calls[0];
      const formData = callArgs[1] as FormData;
      expect(formData.get("file")).toBe(file);
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
        expect.any(FormData),
        {
          headers: { "Content-Type": "multipart/form-data" },
          params: { sheet_names: "기능,UI" },
        }
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
        expect.any(FormData),
        {
          headers: { "Content-Type": "multipart/form-data" },
          params: {},
        }
      );
      expect(result).toEqual(importResult);
    });
  });
});
