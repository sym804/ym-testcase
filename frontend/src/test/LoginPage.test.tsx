import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "../pages/LoginPage";
import { renderWithProviders } from "./helpers";

// Mock API
vi.mock("../api", () => ({
  authApi: {
    login: vi.fn(),
    getMe: vi.fn(),
    checkUsername: vi.fn(),
    register: vi.fn(),
    changePassword: vi.fn(),
  },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

import { authApi } from "../api";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("LoginPage", () => {
  it("로그인 폼이 렌더링된다", () => {
    renderWithProviders(<LoginPage />);
    expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("아이디를 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("비밀번호를 입력하세요")).toBeInTheDocument();
  });

  it("빈 필드로 제출하면 에러 메시지를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.click(screen.getByRole("button", { name: "로그인" }));

    expect(screen.getByText("아이디와 비밀번호를 입력해 주세요.")).toBeInTheDocument();
    expect(authApi.login).not.toHaveBeenCalled();
  });

  it("로그인 성공 시 /projects로 이동한다", async () => {
    const user = userEvent.setup();
    const mockUser = {
      id: 1,
      username: "tester",
      display_name: "테스터",
      role: "user",
      must_change_password: false,
      created_at: "2026-01-01",
    };
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: "token",
      token_type: "bearer",
    });
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

    renderWithProviders(<LoginPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "tester");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "pass1234");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/projects");
    });
  });

  it("로그인 실패 시 서버 에러 메시지를 표시한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.login).mockRejectedValue({
      response: { data: { detail: "아이디 또는 비밀번호가 올바르지 않습니다." } },
    });

    renderWithProviders(<LoginPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "wrong");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "wrong");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => {
      expect(
        screen.getByText("아이디 또는 비밀번호가 올바르지 않습니다.")
      ).toBeInTheDocument();
    });
  });

  it("로딩 중에는 버튼이 비활성화된다", async () => {
    const user = userEvent.setup();
    // 로그인을 지연시킴
    vi.mocked(authApi.login).mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    );

    renderWithProviders(<LoginPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "tester");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "pass1234");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    expect(screen.getByRole("button", { name: "로그인 중..." })).toBeDisabled();
  });

  it("회원가입 링크가 있다", () => {
    renderWithProviders(<LoginPage />);
    const link = screen.getByText("회원가입");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/register");
  });
});
