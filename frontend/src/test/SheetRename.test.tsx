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
  },
}));

import toast from "react-hot-toast";
import { testCasesApi } from "../api";
import SheetTreeSidebar from "../components/SheetTreeSidebar";

const sheetA: SheetNode = { id: 11, name: "로그인", parent_id: null, sort_order: 0, is_folder: false, tc_count: 3, children: [] };
const sheetB: SheetNode = { id: 12, name: "결제", parent_id: null, sort_order: 1, is_folder: false, tc_count: 2, children: [] };
const flat = [sheetA, sheetB].map(s => ({ ...s, depth: 0, hasChildren: false }));

function renderSidebar(overrides: Partial<{ canEditTC: boolean; activeSheet: string | null }> = {}) {
  const setActiveSheet = vi.fn();
  const onSheetChange = vi.fn();
  render(
    <SheetTreeSidebar
      sheets={[sheetA, sheetB]}
      flatSheets={flat}
      activeSheet={overrides.activeSheet ?? "로그인"}
      setActiveSheet={setActiveSheet}
      expandedSheets={new Set()}
      setExpandedSheets={vi.fn()}
      sidebarOpen
      setSidebarOpen={vi.fn()}
      canEditTC={overrides.canEditTC ?? true}
      projectId={1}
      onSheetChange={onSheetChange}
    />
  );
  return { setActiveSheet, onSheetChange };
}

const renameButtons = () => screen.getAllByTitle(/시트 이름 변경|Rename sheet/);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("시트 이름 변경", () => {
  it("연필 버튼 → 새 이름 Enter 로 API 를 한 번만 부르고 고른 시트를 새 이름으로 옮긴다", async () => {
    vi.mocked(testCasesApi.renameSheet).mockResolvedValue({ id: 11, name: "인증", old_name: "로그인" });
    const { setActiveSheet, onSheetChange } = renderSidebar();

    await userEvent.click(renameButtons()[0]);
    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("로그인");
    await userEvent.clear(input);
    await userEvent.type(input, "인증{Enter}");

    await waitFor(() => expect(onSheetChange).toHaveBeenCalled());
    expect(testCasesApi.renameSheet).toHaveBeenCalledTimes(1);
    expect(testCasesApi.renameSheet).toHaveBeenCalledWith(1, 11, "인증");
    expect(setActiveSheet).toHaveBeenCalledWith("인증");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("고르지 않은 시트를 바꾸면 고른 시트는 그대로 둔다", async () => {
    vi.mocked(testCasesApi.renameSheet).mockResolvedValue({ id: 12, name: "결제2", old_name: "결제" });
    const { setActiveSheet, onSheetChange } = renderSidebar();

    await userEvent.click(renameButtons()[1]);
    const input = screen.getByRole("textbox");
    await userEvent.clear(input);
    await userEvent.type(input, "결제2{Enter}");

    await waitFor(() => expect(onSheetChange).toHaveBeenCalled());
    expect(testCasesApi.renameSheet).toHaveBeenCalledWith(1, 12, "결제2");
    expect(setActiveSheet).not.toHaveBeenCalled();
  });

  it("이름을 더블클릭해도 입력칸이 열린다", async () => {
    renderSidebar();
    await userEvent.dblClick(screen.getByText("결제"));
    expect(screen.getByRole("textbox")).toHaveValue("결제");
  });

  it("Escape 는 취소, 같은 이름이나 빈 이름은 API 를 부르지 않는다", async () => {
    renderSidebar();

    await userEvent.click(renameButtons()[0]);
    await userEvent.type(screen.getByRole("textbox"), "x{Escape}");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();

    await userEvent.click(renameButtons()[0]);
    await userEvent.type(screen.getByRole("textbox"), "{Enter}");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();

    await userEvent.click(renameButtons()[0]);
    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "   {Enter}");
    expect(toast.error).toHaveBeenCalled();

    expect(testCasesApi.renameSheet).not.toHaveBeenCalled();
  });

  it("서버가 거절하면 그 사유를 보여 주고 입력칸을 남긴다", async () => {
    vi.mocked(testCasesApi.renameSheet).mockRejectedValue({ response: { data: { detail: "이미 존재하는 시트 이름입니다." } } });
    const { onSheetChange } = renderSidebar();

    await userEvent.click(renameButtons()[0]);
    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "결제{Enter}");

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(onSheetChange).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toHaveValue("결제");
  });

  it("편집 권한이 없으면 버튼도 더블클릭 편집도 없다", async () => {
    renderSidebar({ canEditTC: false });
    expect(screen.queryAllByTitle(/시트 이름 변경|Rename sheet/)).toHaveLength(0);
    await userEvent.dblClick(screen.getByText("결제"));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
