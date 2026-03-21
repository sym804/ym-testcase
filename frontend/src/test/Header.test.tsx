import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Header from "../components/Header";

// Mock contexts
const mockUser = {
  id: 1, username: "admin", display_name: "관리자",
  role: "admin", must_change_password: false, created_at: "2026-01-01",
};
const mockLogout = vi.fn();
const mockToggleTheme = vi.fn();

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, logout: mockLogout }),
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
  authApi: { changePassword: vi.fn() },
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
