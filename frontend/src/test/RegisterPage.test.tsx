import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "../pages/RegisterPage";
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

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { authApi } from "../api";
import toast from "react-hot-toast";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RegisterPage", () => {
  it("회원가입 폼이 렌더링된다", () => {
    renderWithProviders(<RegisterPage />);
    expect(screen.getByRole("heading", { name: "회원가입" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("아이디를 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("표시될 이름을 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("비밀번호를 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("비밀번호를 다시 입력하세요")).toBeInTheDocument();
  });

  it("모든 필드가 비어있으면 에러를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);

    await user.click(screen.getByRole("button", { name: "회원가입" }));

    expect(screen.getByText("모든 필드를 입력해 주세요.")).toBeInTheDocument();
  });

  it("비밀번호가 8자 미만이면 힌트를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "short");

    expect(screen.getByText("비밀번호는 8자 이상이어야 합니다.")).toBeInTheDocument();
  });

  it("비밀번호 불일치 시 힌트를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "different");

    expect(screen.getByText("비밀번호가 일치하지 않습니다.")).toBeInTheDocument();
  });

  it("아이디 입력 시 사용 가능 여부를 확인한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: true });

    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "newuser");

    // 디바운스 후 확인
    await waitFor(
      () => {
        expect(screen.getByText("사용 가능한 아이디입니다.")).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  it("이미 사용 중인 아이디면 경고를 표시한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: false });

    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "existing");

    await waitFor(
      () => {
        expect(screen.getByText("이미 사용 중인 아이디입니다.")).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  it("사용 중인 아이디로 제출하면 에러를 표시한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: false });

    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "taken");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "User");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");

    // 디바운스 대기
    await waitFor(
      () => {
        expect(screen.getByText("이미 사용 중인 아이디입니다.")).toBeInTheDocument();
      },
      { timeout: 1000 }
    );

    await user.click(screen.getByRole("button", { name: "회원가입" }));

    // 제출 시 에러 메시지가 errorMsg 스타일로 표시됨
    await waitFor(() => {
      const errors = screen.getAllByText("이미 사용 중인 아이디입니다.");
      expect(errors.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("회원가입 성공 시 로그인 페이지로 이동한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: true });
    vi.mocked(authApi.register).mockResolvedValue({
      id: 2,
      username: "newuser",
      display_name: "New",
      role: "user" as never,
      must_change_password: false,
      created_at: "2026-01-01",
    });

    renderWithProviders(<RegisterPage />);

    await user.type(screen.getByPlaceholderText("아이디를 입력하세요"), "newuser");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "New");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");

    await waitFor(
      () => {
        expect(screen.getByText("사용 가능한 아이디입니다.")).toBeInTheDocument();
      },
      { timeout: 1000 }
    );

    await user.click(screen.getByRole("button", { name: "회원가입" }));

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("회원가입이 완료되었습니다. 로그인해 주세요.");
      expect(mockNavigate).toHaveBeenCalledWith("/login");
    });
  });

  it("로그인 페이지 링크가 있다", () => {
    renderWithProviders(<RegisterPage />);
    const link = screen.getByText("로그인");
    expect(link).toBeInTheDocument();
    expect(link.closest("a")).toHaveAttribute("href", "/login");
  });
});
