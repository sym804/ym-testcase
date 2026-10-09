import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StrictMode } from "react";
import Header from "../components/Header";
import { UserRole } from "../types";

// Mock contexts
const mockUser = {
  id: 1, username: "admin", display_name: "관리자",
  role: UserRole.ADMIN, must_change_password: false, created_at: "2026-01-01",
};
const mockLogout = vi.fn();
const mockToggleTheme = vi.fn();

let mockAuthUser: Record<string, unknown> = mockUser;

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user: mockAuthUser, logout: mockLogout, refreshUser: vi.fn() }),
}));

vi.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: mockToggleTheme }),
}));

vi.mock("../api", () => ({
  projectsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 1, name: "프로젝트A" },
      { id: 2, name: "프로젝트B" },
    ]),
  },
  searchApi: {
    global: vi.fn().mockResolvedValue([
      { id: 1, project_id: 1, tc_id: "TC-001", depth1: "로그인", depth2: "정상" },
    ]),
  },
  authApi: {
    changePassword: vi.fn(),
    config: vi.fn().mockResolvedValue({ google_enabled: true, signup_mode: "email" }),
    unlinkGoogle: vi.fn(),
  },
  googleStartUrl: (mode: string) => `/api/auth/google/start?mode=${mode}`,
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderHeader(route = "/projects") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Header />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockAuthUser = mockUser;
});

describe("Header", () => {
  it("YM TestCase 브랜드를 표시한다", async () => {
    renderHeader();
    expect(screen.getByText("YM TestCase")).toBeInTheDocument();
  });

  it("프로젝트 드롭다운을 표시한다", async () => {
    renderHeader();
    await waitFor(() => {
      expect(screen.getByText("프로젝트A")).toBeInTheDocument();
    });
  });

  it("검색 입력란을 표시한다", () => {
    renderHeader();
    expect(screen.getByPlaceholderText("TC 검색...")).toBeInTheDocument();
  });

  it("사용자 이름과 역할을 표시한다", () => {
    renderHeader();
    expect(screen.getByText("관리자")).toBeInTheDocument();
    expect(screen.getByText("ADMIN")).toBeInTheDocument();
  });

  it("admin 사용자에게 관리 버튼을 표시한다", () => {
    renderHeader();
    expect(screen.getByText("관리")).toBeInTheDocument();
    expect(screen.getByText("운영 매뉴얼")).toBeInTheDocument();
  });

  it("도움말 버튼을 표시한다", () => {
    renderHeader();
    expect(screen.getByText("도움말")).toBeInTheDocument();
  });

  it("테마 토글 버튼이 있다", () => {
    renderHeader();
    const btn = screen.getByTitle("다크 모드");
    expect(btn).toBeInTheDocument();
  });

  it("YM TestCase 클릭 시 /projects로 이동한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("YM TestCase"));
    expect(mockNavigate).toHaveBeenCalledWith("/projects");
  });

  it("사용자 메뉴 클릭 시 드롭다운을 표시한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("관리자"));
    expect(screen.getByText("비밀번호 변경")).toBeInTheDocument();
    expect(screen.getByText("로그아웃")).toBeInTheDocument();
  });

  it("로그아웃 클릭 시 logout을 호출한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("관리자"));
    await user.click(screen.getByText("로그아웃"));
    expect(mockLogout).toHaveBeenCalled();
  });

  it("2자 미만 검색어는 결과를 표시하지 않는다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.type(screen.getByPlaceholderText("TC 검색..."), "a");
    // 결과 드롭다운이 나타나지 않아야 함
    expect(screen.queryByText("TC-001")).not.toBeInTheDocument();
  });

  it("2자 이상 검색 시 결과를 표시한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.type(screen.getByPlaceholderText("TC 검색..."), "로그인");
    await waitFor(() => {
      expect(screen.getByText(/TC-001/)).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it("비밀번호 변경 메뉴 클릭 시 모달을 표시한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("관리자"));
    await user.click(screen.getByText("비밀번호 변경"));
    await waitFor(() => {
      expect(screen.getByText("현재 비밀번호")).toBeInTheDocument();
      expect(screen.getByText("새 비밀번호")).toBeInTheDocument();
      expect(screen.getByText("새 비밀번호 확인")).toBeInTheDocument();
    });
  });

  it("도움말 버튼 클릭 시 navigate('/manual')을 호출한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("도움말"));
    expect(mockNavigate).toHaveBeenCalledWith("/manual");
  });

  it("관리 버튼 클릭 시 navigate('/admin')을 호출한다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("관리"));
    expect(mockNavigate).toHaveBeenCalledWith("/admin");
  });
});

describe("Header 계정 연결", () => {
  it("사용자 메뉴에 계정 연결이 있고 창을 연다", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByText("관리자"));
    await user.click(screen.getByRole("button", { name: "계정 연결" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("비밀번호 없는 계정에는 비밀번호 변경 메뉴가 없다", async () => {
    const user = userEvent.setup();
    mockAuthUser = { ...mockUser, has_password: false, google_linked: true };
    renderHeader();
    await user.click(screen.getByText("관리자"));
    expect(screen.getByRole("button", { name: "계정 연결" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "비밀번호 변경" })).not.toBeInTheDocument();
  });

  it("연결 성공 결과를 한 번 알린다", async () => {
    const toast = (await import("react-hot-toast")).default;
    renderHeader("/projects?account=linked");
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Google 계정을 연결했습니다."));
    expect(mockNavigate).toHaveBeenCalledWith("/projects", { replace: true });
  });

  it("빈 계정을 정리하고 연결한 결과를 알린다", async () => {
    const toast = (await import("react-hot-toast")).default;
    renderHeader("/projects?account=merged");
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(
      "Google 계정을 연결했습니다. 이 Google 계정으로 만들어져 있던 빈 계정은 정리했습니다."));
  });

  it("연결 실패 사유를 알린다", async () => {
    const toast = (await import("react-hot-toast")).default;
    renderHeader("/projects?account=already_linked");
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("이 Google 계정은 이미 다른 계정에 연결돼 있습니다."));
  });
});

describe("Header 콜백 알림 한 번", () => {
  it("StrictMode 에서도 연결 결과를 한 번만 알린다", async () => {
    const toast = (await import("react-hot-toast")).default;
    render(
      <StrictMode>
        <MemoryRouter initialEntries={["/projects?account=linked"]}>
          <Header />
        </MemoryRouter>
      </StrictMode>
    );
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 50));
    expect(vi.mocked(toast.success).mock.calls.filter((c) => c[0] === "Google 계정을 연결했습니다.")).toHaveLength(1);
  });
});
