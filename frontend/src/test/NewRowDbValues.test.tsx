import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../i18n";

// 새 행의 기본값은 화면 표기가 아니라 DB 값이어야 한다.
// 영어로 전환한 상태에서 행을 추가하면 priority 에 "Normal" 이 저장됐다.
// DB 값은 한글 5종이고 표기만 번역하는 구조라, 값 공간이 로케일마다 갈라진다.
// 색상 맵과 편집기 선택지가 그 값을 모르고, 대시보드는 GROUP BY priority 라
// "보통" 과 "Normal" 이 서로 다른 행으로 집계된다(SYM-58 과 같은 뿌리).

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">{props.rowData?.length ?? 0}</div>
  ),
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

const adminProject = {
  id: 1, name: "TestProject", description: "desc", jira_base_url: null,
  is_private: false, created_by: 1, created_at: "2026-01-01",
  updated_at: "2026-01-01", my_role: "admin" as const,
};

//: DB 에 저장되는 우선순위 값. 화면 표기와 다르다.
const DB_PRIORITIES = ["매우 높음", "높음", "보통", "낮음", "매우 낮음"];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 0, children: [] },
  ] as any);
  vi.mocked(testCasesApi.list).mockResolvedValue([] as any);
  vi.mocked(testCasesApi.create).mockImplementation(
    async (_pid: number, row: any) => ({ ...row, id: 99 }) as any
  );
});

afterEach(async () => {
  await i18n.changeLanguage("ko");
});

async function addOneRow(addRowLabel: string) {
  const user = userEvent.setup();
  render(<TestCaseGrid projectId={1} project={adminProject as any} />);
  await waitFor(() => {
    expect(testCasesApi.listSheets).toHaveBeenCalled();
  });
  await user.click(await screen.findByText(addRowLabel));
  await waitFor(() => {
    expect(testCasesApi.create).toHaveBeenCalled();
  });
  return vi.mocked(testCasesApi.create).mock.calls[0][1] as any;
}

describe("새 행의 기본값", () => {
  it("한국어에서 추가한 행의 우선순위는 DB 값이다", async () => {
    const created = await addOneRow("+ 행 추가");
    expect(DB_PRIORITIES).toContain(created.priority);
  });

  it("영어로 바꿔도 우선순위는 같은 DB 값이다", async () => {
    await i18n.changeLanguage("en");
    const created = await addOneRow("+ Add Row");
    expect(DB_PRIORITIES).toContain(created.priority);
    expect(created.priority).not.toBe("Normal");
  });
});
