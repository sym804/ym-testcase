import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { SheetNode } from "../types";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testCasesApi: {
    createSheet: vi.fn(),
    deleteSheet: vi.fn(),
    renameSheet: vi.fn(),
    copySheet: vi.fn(),
  },
}));

import toast from "react-hot-toast";
import { testCasesApi } from "../api";
import SheetTreeSidebar from "../components/SheetTreeSidebar";

const child: SheetNode = { id: 21, name: "로그인", parent_id: 20, sort_order: 0, is_folder: false, tc_count: 3, children: [] };
const folder: SheetNode = { id: 20, name: "웹", parent_id: null, sort_order: 0, is_folder: true, tc_count: 0, children: [child] };
const sheetB: SheetNode = { id: 12, name: "결제", parent_id: null, sort_order: 1, is_folder: false, tc_count: 2, children: [] };
const flat = [
  { ...folder, depth: 0, hasChildren: true },
  { ...child, depth: 1, hasChildren: false },
  { ...sheetB, depth: 0, hasChildren: false },
];

function renderSidebar(overrides: Partial<{ canEditTC: boolean }> = {}) {
  const setActiveSheet = vi.fn();
  const onSheetChange = vi.fn();
  const setExpandedSheets = vi.fn();
  render(
    <SheetTreeSidebar
      sheets={[folder, sheetB]}
      flatSheets={flat}
      activeSheet="결제"
      setActiveSheet={setActiveSheet}
      expandedSheets={new Set([20])}
      setExpandedSheets={setExpandedSheets}
      sidebarOpen
      setSidebarOpen={vi.fn()}
      canEditTC={overrides.canEditTC ?? true}
      projectId={7}
      onSheetChange={onSheetChange}
    />
  );
  return { setActiveSheet, onSheetChange, setExpandedSheets };
}

const copyButtons = () => screen.queryAllByRole("button", { name: /시트 복사|Copy sheet/ });

beforeEach(() => {
  vi.clearAllMocks();
});

describe("시트 복사", () => {
  it("폴더에는 복사 버튼이 없고 시트마다 하나씩 있다", () => {
    renderSidebar();
    // 로그인(폴더 아래), 결제. 폴더 '웹' 은 제외
    expect(copyButtons()).toHaveLength(2);
  });

  it("시트 행 없이 TC 만 있는 호환 노드(id 0)에는 복사 버튼이 없다", () => {
    const legacy: SheetNode = { id: 0, name: "옛 시트", parent_id: null, sort_order: 999, is_folder: false, tc_count: 4, children: [] };
    render(
      <SheetTreeSidebar
        sheets={[sheetB, legacy]}
        flatSheets={[{ ...sheetB, depth: 0, hasChildren: false }, { ...legacy, depth: 0, hasChildren: false }]}
        activeSheet="결제"
        setActiveSheet={vi.fn()}
        expandedSheets={new Set()}
        setExpandedSheets={vi.fn()}
        sidebarOpen
        setSidebarOpen={vi.fn()}
        canEditTC
        projectId={7}
        onSheetChange={vi.fn()}
      />
    );
    expect(copyButtons()).toHaveLength(1);
  });

  it("권한이 없으면 복사 버튼을 보여 주지 않는다", () => {
    renderSidebar({ canEditTC: false });
    expect(copyButtons()).toHaveLength(0);
  });

  it("누르면 그 시트 id 로 API 를 부르고 새 시트를 고르며 부모 폴더를 펼친다", async () => {
    vi.mocked(testCasesApi.copySheet).mockResolvedValue({
      id: 30, name: "로그인 (복사)", parent_id: 20, sort_order: 1, is_folder: false,
      tc_count: 3, children: [], source_id: 21,
    });
    const { setActiveSheet, onSheetChange, setExpandedSheets } = renderSidebar();

    await userEvent.click(copyButtons()[0]);

    await waitFor(() => expect(onSheetChange).toHaveBeenCalled());
    expect(testCasesApi.copySheet).toHaveBeenCalledWith(7, 21);
    expect(setActiveSheet).toHaveBeenCalledWith("로그인 (복사)");
    expect(setExpandedSheets).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledTimes(1);
  });

  it("응답 전에 두 번 눌러도 요청은 한 번만 보낸다", async () => {
    let resolve!: (v: Awaited<ReturnType<typeof testCasesApi.copySheet>>) => void;
    vi.mocked(testCasesApi.copySheet).mockImplementation(() => new Promise(r => { resolve = r; }));
    const { onSheetChange } = renderSidebar();

    const btn = copyButtons()[1];
    await userEvent.click(btn);
    await userEvent.click(btn);
    resolve({ id: 31, name: "결제 (복사)", parent_id: null, sort_order: 2, is_folder: false, tc_count: 2, children: [], source_id: 12 });

    await waitFor(() => expect(onSheetChange).toHaveBeenCalled());
    expect(testCasesApi.copySheet).toHaveBeenCalledTimes(1);
  });

  it("서버가 거절하면 그 사유를 보여 주고 시트를 바꾸지 않는다", async () => {
    vi.mocked(testCasesApi.copySheet).mockRejectedValue({
      response: { data: { detail: "폴더는 복사할 수 없습니다. 시트를 골라 주세요." } },
    });
    const { setActiveSheet, onSheetChange } = renderSidebar();

    await userEvent.click(copyButtons()[1]);

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("폴더는 복사할 수 없습니다. 시트를 골라 주세요."));
    expect(setActiveSheet).not.toHaveBeenCalled();
    expect(onSheetChange).not.toHaveBeenCalled();
  });

  it("사유 없이 실패하면 기본 실패 문구를 보여 주고, 다시 누를 수 있다", async () => {
    vi.mocked(testCasesApi.copySheet).mockRejectedValueOnce(new Error("network"));
    renderSidebar();

    await userEvent.click(copyButtons()[1]);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("시트 복사에 실패했습니다."));

    vi.mocked(testCasesApi.copySheet).mockResolvedValueOnce({
      id: 32, name: "결제 (복사)", parent_id: null, sort_order: 2, is_folder: false, tc_count: 2, children: [], source_id: 12,
    });
    await userEvent.click(copyButtons()[1]);
    await waitFor(() => expect(testCasesApi.copySheet).toHaveBeenCalledTimes(2));
  });

  it("키보드 Enter 로도 복사한다", async () => {
    vi.mocked(testCasesApi.copySheet).mockResolvedValue({
      id: 33, name: "결제 (복사)", parent_id: null, sort_order: 2, is_folder: false, tc_count: 2, children: [], source_id: 12,
    });
    renderSidebar();

    copyButtons()[1].focus();
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(testCasesApi.copySheet).toHaveBeenCalledWith(7, 12));
  });
});
