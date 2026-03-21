import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../contexts/AuthContext";
import App from "../App";
import { UserRole } from "../types";

// Mock API
vi.mock("../api", () => ({
  authApi: {
    login: vi.fn(),
    getMe: vi.fn(),
    checkUsername: vi.fn(),
    register: vi.fn(),
    changePassword: vi.fn(),
  },
  projectsApi: { list: vi.fn().mockResolvedValue([]) },
  overviewApi: {
    get: vi.fn().mockResolvedValue({
      total_projects: 0,
      total_testcases: 0,
      total_testruns: 0,
      avg_pass_rate: 0,
      project_summaries: [],
    }),
  },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

import { authApi } from "../api";

beforeEach(() => {
  vi.clearAllMocks();
});

function renderApp(initialRoute = "/") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("App Routing", () => {
  describe("비인증 상태", () => {
    it("/login 경로에서 로그인 페이지를 렌더링한다", async () => {
      renderApp("/login");
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
      });
    });

    it("/register 경로에서 회원가입 페이지를 렌더링한다", async () => {
      renderApp("/register");
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "회원가입" })).toBeInTheDocument();
      });
    });

    it("/projects 접근 시 로그인 페이지로 리다이렉트된다", async () => {
      renderApp("/projects");
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
      });
    });

    it("/ 접근 시 로그인 페이지로 리다이렉트된다", async () => {
      renderApp("/");
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
      });
    });

    it("알 수 없는 경로에서도 로그인 페이지로 리다이렉트된다", async () => {
      renderApp("/unknown-route");
      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
      });
    });
  });

  describe("인증 상태", () => {
    const mockUser = {
      id: 1,
      username: "tester",
      display_name: "테스터",
      role: UserRole.USER,
      must_change_password: false,
      created_at: "2026-01-01",
    };

    it("인증된 사용자는 프로젝트 목록에 접근할 수 있다", async () => {
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      renderApp("/projects");

      // 로딩 후 프로젝트 페이지 표시 확인
      await waitFor(() => {
        expect(screen.queryByText("로딩 중...")).not.toBeInTheDocument();
      });
      // 로그인 페이지가 아님을 확인
      expect(screen.queryByPlaceholderText("아이디를 입력하세요")).not.toBeInTheDocument();
    });

    it("must_change_password가 true이면 비밀번호 변경 모달을 표시한다", async () => {
      vi.mocked(authApi.getMe).mockResolvedValue({
        ...mockUser,
        must_change_password: true,
      });

      renderApp("/projects");

      await waitFor(() => {
        expect(screen.getByText("비밀번호 변경 필요")).toBeInTheDocument();
      });
    });
  });

  describe("ProtectedRoute", () => {
    it("로딩 중에는 로딩 메시지를 표시한다", () => {
      // getMe를 지연시켜 loading 상태 유지
      vi.mocked(authApi.getMe).mockImplementation(
        () => new Promise(() => {}) // 영원히 pending
      );

      renderApp("/projects");
      expect(screen.getByText("로딩 중...")).toBeInTheDocument();
    });
  });
});
