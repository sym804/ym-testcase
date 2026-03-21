import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AdminPage from "../pages/AdminPage";

let mockRole = "admin";

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, username: "admin", display_name: "관리자", role: mockRole, must_change_password: false, created_at: "2026-01-01" },
    logout: vi.fn(),
  }),
}));

vi.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/Header", () => ({
  default: () => <div data-testid="header">Header</div>,
}));

vi.mock("../api", () => ({
  usersApi: {
    list: vi.fn(),
    updateRole: vi.fn(),
    resetPassword: vi.fn(),
    getAllAssignments: vi.fn(),
    assignToAllProjects: vi.fn(),
  },
  projectsApi: { list: vi.fn() },
  membersApi: {
    list: vi.fn(),
    add: vi.fn(),
    updateRole: vi.fn(),
    remove: vi.fn(),
  },
  searchApi: { global: vi.fn() },
  authApi: { getMe: vi.fn() },
}));

import { usersApi, projectsApi, membersApi, searchApi } from "../api";
import toast from "react-hot-toast";

const mockUsers = [
  { id: 1, username: "admin", display_name: "관리자", role: "admin", must_change_password: false, created_at: "2026-01-01T00:00:00" },
  { id: 2, username: "tester1", display_name: "테스터1", role: "user", must_change_password: false, created_at: "2026-01-02T00:00:00" },
];

const mockProjects = [
  { id: 1, name: "프로젝트A", description: "", jira_base_url: null, is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockRole = "admin";
  vi.mocked(usersApi.list).mockResolvedValue(mockUsers);
  vi.mocked(usersApi.updateRole).mockResolvedValue({});
  vi.mocked(usersApi.resetPassword).mockResolvedValue({ temp_password: "TempPass123!" });
  vi.mocked(usersApi.getAllAssignments).mockResolvedValue({});
  vi.mocked(usersApi.assignToAllProjects).mockResolvedValue({ assigned: 1, total_projects: 1 });
  vi.mocked(projectsApi.list).mockResolvedValue(mockProjects);
  vi.mocked(membersApi.list).mockResolvedValue([]);
  vi.mocked(membersApi.add).mockResolvedValue({});
  vi.mocked(membersApi.updateRole).mockResolvedValue({});
  vi.mocked(membersApi.remove).mockResolvedValue(undefined);
  vi.mocked(searchApi.global).mockResolvedValue([]);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>
  );
}

describe("AdminPage", () => {
  it("관리자가 아니면 권한 필요 메시지를 표시한다", async () => {
    mockRole = "user";
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("관리자 권한이 필요합니다.")).toBeInTheDocument();
    });
  });

  it("사용자 관리 제목을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("사용자 관리")).toBeInTheDocument();
    });
  });

  it("사용자 목록을 테이블로 렌더링한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
      expect(screen.getByText("테스터1")).toBeInTheDocument();
    });
  });

  it("역할 변경 셀렉터가 있다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
    });
    // 자기 자신 외의 사용자에 대해 역할 셀렉터가 활성화됨
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThan(0);
  });

  it("비밀번호 초기화 버튼이 있다", async () => {
    renderPage();
    await waitFor(() => {
      // admin 본인 외 사용자에 대해서만 초기화 버튼 있음
      expect(screen.getByText("초기화")).toBeInTheDocument();
    });
  });

  it("비밀번호 초기화 시 임시 비밀번호 모달을 표시한다", async () => {
    const user = userEvent.setup();
    // confirm을 자동 true로
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("초기화")).toBeInTheDocument();
    });

    await user.click(screen.getByText("초기화"));

    await waitFor(() => {
      expect(screen.getByText("비밀번호 초기화 완료")).toBeInTheDocument();
      expect(screen.getByText("TempPass123!")).toBeInTheDocument();
    });
  });

  it("역할을 변경할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
    });

    // disabled가 아닌 셀렉터를 찾아서 역할 변경
    const selects = screen.getAllByRole("combobox");
    const enabledSelects = selects.filter(s => !(s as HTMLSelectElement).disabled);
    expect(enabledSelects.length).toBeGreaterThan(0);

    // tester1의 셀렉터 (일반 사용자 역할 값 "user"를 가진 것)
    const testerSelect = enabledSelects.find(s => (s as HTMLSelectElement).value === "user");
    if (testerSelect) {
      await user.selectOptions(testerSelect, "qa_manager");
      await waitFor(() => {
        expect(usersApi.updateRole).toHaveBeenCalledWith(2, "qa_manager");
      });
    }
  });

  it("프로젝트 배정 관리 버튼이 있다", async () => {
    renderPage();
    await waitFor(() => {
      // user 역할 사용자에게만 "관리" 버튼이 표시됨
      const manageButtons = screen.getAllByText("관리");
      expect(manageButtons.length).toBeGreaterThan(0);
    });
  });
});
