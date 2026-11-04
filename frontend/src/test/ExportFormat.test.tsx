// TC 내보내기 창의 형식 선택 (SYM-211)
// 형식을 고르면 API 에 그 형식이 가고, 받은 파일 이름의 확장자가 형식과 같아야 한다.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("ag-grid-react", () => ({
  AgGridReact: () => <div data-testid="ag-grid" />,
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testCasesApi: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), bulkDelete: vi.fn(),
    listSheets: vi.fn(), createSheet: vi.fn(), deleteSheet: vi.fn(),
    previewImport: vi.fn(), importExcel: vi.fn(), exportExcel: vi.fn(),
    bulkUpdate: vi.fn(), delete: vi.fn(), restore: vi.fn(),
  },
  historyApi: { getTestCaseHistory: vi.fn(), getProjectHistory: vi.fn() },
}));

import { testCasesApi } from "../api";
import TestCaseGrid from "../components/TestCaseGrid";

const project = {
  id: 7, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin" as const,
};

let downloads: string[] = [];
const origCreate = document.createElement.bind(document);

beforeEach(() => {
  vi.clearAllMocks();
  downloads = [];
  // 시트가 없으면 빈 화면 안내만 나오고 툴바가 없다
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 0, children: [] },
  ]);
  vi.mocked(testCasesApi.list).mockResolvedValue([]);
  vi.mocked(testCasesApi.exportExcel).mockResolvedValue(new Blob(["x"]));
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(document, "createElement").mockImplementation((tag: string, opts?: ElementCreationOptions) => {
    const el = origCreate(tag, opts);
    if (tag === "a") {
      (el as HTMLAnchorElement).click = () => { downloads.push((el as HTMLAnchorElement).download); };
    }
    return el;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function openModal() {
  render(<TestCaseGrid projectId={project.id} project={project} />);
  await waitFor(() => expect(testCasesApi.list).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "Export" }));
}

describe("TC 내보내기 형식", () => {
  it("기본은 Excel 이고 .xlsx 로 받는다", async () => {
    await openModal();
    await userEvent.click(screen.getByRole("button", { name: "다운로드" }));
    await waitFor(() => expect(testCasesApi.exportExcel).toHaveBeenCalledWith(7, false, false, "xlsx"));
    expect(downloads).toEqual(["testcases_7.xlsx"]);
  });

  it("Markdown 을 고르면 md 로 요청하고 .md 로 받는다", async () => {
    await openModal();
    await userEvent.click(screen.getByLabelText("Markdown (.md)"));
    await userEvent.click(screen.getByLabelText("시트 분리 (시트별 표)"));
    await userEvent.click(screen.getByRole("button", { name: "다운로드" }));
    await waitFor(() => expect(testCasesApi.exportExcel).toHaveBeenCalledWith(7, true, false, "md"));
    expect(downloads).toEqual(["testcases_7.md"]);
  });

  it("Markdown 에서는 셀 메모 안내 대신 Markdown 안내를 보인다", async () => {
    await openModal();
    expect(screen.getByText(/셀 메모로/)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Markdown (.md)"));
    expect(screen.getByText("끄면 참조 문구를 그대로 둡니다.")).toBeInTheDocument();
    expect(screen.queryByText(/셀 메모로/)).not.toBeInTheDocument();
  });
});
