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
    config: vi.fn(),
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

const created = (over: Record<string, unknown> = {}) => ({
  id: 2,
  username: "newuser",
  display_name: "New",
  role: "user" as never,
  must_change_password: false,
  created_at: "2026-01-01",
  status: "active" as const,
  ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RegisterPage 이메일 가입", () => {
  beforeEach(() => {
    vi.mocked(authApi.config).mockResolvedValue({ google_enabled: false, signup_mode: "email" });
  });

  it("이메일 가입 폼이 렌더링되고 아이디 칸은 없다", async () => {
    renderWithProviders(<RegisterPage />);
    expect(await screen.findByRole("heading", { name: "회원가입" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("이메일을 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("표시될 이름을 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("비밀번호를 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("비밀번호를 다시 입력하세요")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("아이디를 입력하세요")).not.toBeInTheDocument();
  });

  it("모든 필드가 비어있으면 에러를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await user.click(await screen.findByRole("button", { name: "회원가입" }));
    expect(screen.getByText("모든 필드를 입력해 주세요.")).toBeInTheDocument();
  });

  it("비밀번호 검사가 이메일 형식보다 먼저다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("이메일을 입력하세요"), "not-an-email");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "T");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "short");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "short");
    await user.click(screen.getByRole("button", { name: "회원가입" }));
    expect(screen.getAllByText("비밀번호는 8자 이상이어야 합니다.").length).toBeGreaterThanOrEqual(1);
    expect(authApi.register).not.toHaveBeenCalled();
  });

  it("비밀번호 불일치 시 힌트를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "different");
    expect(screen.getByText("비밀번호가 일치하지 않습니다.")).toBeInTheDocument();
  });

  it("이메일로 가입하고 승인 대기면 대기 안내를 보여 준다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.register).mockResolvedValue(created({ username: "ym@example.com", status: "pending" }));
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("이메일을 입력하세요"), "ym@example.com");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "Ym");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");
    await user.click(screen.getByRole("button", { name: "회원가입" }));
    await waitFor(() => {
      expect(authApi.register).toHaveBeenCalledWith({
        email: "ym@example.com", password: "password123", display_name: "Ym",
      });
      expect(toast.success).toHaveBeenCalledWith("가입 신청이 접수됐습니다. 관리자 승인 후 로그인할 수 있습니다.");
      expect(mockNavigate).toHaveBeenCalledWith("/login");
    });
    expect(authApi.checkUsername).not.toHaveBeenCalled();
  });

  it("바로 쓸 수 있으면 완료 안내를 보여 준다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.register).mockResolvedValue(created({ status: "active" }));
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("이메일을 입력하세요"), "ym@example.com");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "Ym");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");
    await user.click(screen.getByRole("button", { name: "회원가입" }));
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("회원가입이 완료되었습니다. 로그인해 주세요.");
    });
  });

  it("서버 검증 오류가 배열로 와도 문구를 보여 준다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.register).mockRejectedValue({
      response: { data: { detail: [{ loc: ["body", "display_name"], msg: "String should have at least 1 character" }] } },
    });
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("이메일을 입력하세요"), "ym@example.com");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "Ym");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");
    await user.click(screen.getByRole("button", { name: "회원가입" }));
    expect(await screen.findByText("회원가입에 실패했습니다.")).toBeInTheDocument();
  });

  it("설정을 못 읽으면 이메일 가입으로 그린다", async () => {
    vi.mocked(authApi.config).mockRejectedValue(new Error("down"));
    renderWithProviders(<RegisterPage />);
    expect(await screen.findByPlaceholderText("이메일을 입력하세요")).toBeInTheDocument();
  });

  it("로그인 페이지 링크가 있다", async () => {
    renderWithProviders(<RegisterPage />);
    const link = await screen.findByText("로그인");
    expect(link.closest("a")).toHaveAttribute("href", "/login");
  });
});

describe("RegisterPage 첫 관리자", () => {
  beforeEach(() => {
    vi.mocked(authApi.config).mockResolvedValue({ google_enabled: false, signup_mode: "bootstrap" });
  });

  it("관리자 계정 만들기 폼에 아이디와 설치 토큰 칸이 있다", async () => {
    renderWithProviders(<RegisterPage />);
    expect(await screen.findByRole("heading", { name: "관리자 계정 만들기" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("아이디를 입력하세요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("운영 환경에서만 필요합니다")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("이메일을 입력하세요")).not.toBeInTheDocument();
  });

  it("아이디 입력 시 사용 가능 여부를 확인한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: true });
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("아이디를 입력하세요"), "admin");
    await waitFor(() => expect(screen.getByText("사용 가능한 아이디입니다.")).toBeInTheDocument(), { timeout: 1000 });
  });

  it("아이디와 토큰으로 첫 관리자를 만든다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: true });
    vi.mocked(authApi.register).mockResolvedValue(created({ username: "admin", role: "admin" as never }));
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("아이디를 입력하세요"), "admin");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "Admin");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("운영 환경에서만 필요합니다"), "t0k");
    await user.click(screen.getByRole("button", { name: "관리자 계정 만들기" }));
    await waitFor(() => {
      expect(authApi.register).toHaveBeenCalledWith({
        username: "admin", password: "password123", display_name: "Admin", bootstrap_token: "t0k",
      });
      expect(mockNavigate).toHaveBeenCalledWith("/login");
    });
  });
});

describe("RegisterPage 경쟁과 모드 전환", () => {
  it("늦게 온 옛 아이디 확인 응답이 지금 입력을 덮지 않는다", async () => {
    vi.mocked(authApi.config).mockResolvedValue({ google_enabled: false, signup_mode: "bootstrap" });
    let releaseOld: (v: { available: boolean }) => void = () => {};
    vi.mocked(authApi.checkUsername)
      .mockImplementationOnce(() => new Promise((r) => { releaseOld = r; }))
      .mockResolvedValueOnce({ available: true });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    const input = await screen.findByPlaceholderText("아이디를 입력하세요");
    await user.type(input, "ab");
    await waitFor(() => expect(authApi.checkUsername).toHaveBeenCalledTimes(1), { timeout: 1000 });
    await user.type(input, "cd");
    await waitFor(() => expect(screen.getByText("사용 가능한 아이디입니다.")).toBeInTheDocument(), { timeout: 1000 });
    releaseOld({ available: false });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("이미 사용 중인 아이디입니다.")).not.toBeInTheDocument();
  });

  it("첫 관리자 화면에서 이미 사용자가 생겼다는 응답을 받으면 이메일 가입으로 바꾼다", async () => {
    vi.mocked(authApi.config)
      .mockResolvedValueOnce({ google_enabled: false, signup_mode: "bootstrap" })
      .mockResolvedValue({ google_enabled: false, signup_mode: "email" });
    vi.mocked(authApi.checkUsername).mockResolvedValue({ available: true });
    vi.mocked(authApi.register).mockRejectedValue({ response: { data: { detail: "이메일로 가입해 주세요." } } });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await user.type(await screen.findByPlaceholderText("아이디를 입력하세요"), "late");
    await user.type(screen.getByPlaceholderText("표시될 이름을 입력하세요"), "L");
    await user.type(screen.getByPlaceholderText("비밀번호를 입력하세요"), "password123");
    await user.type(screen.getByPlaceholderText("비밀번호를 다시 입력하세요"), "password123");
    await user.click(screen.getByRole("button", { name: "관리자 계정 만들기" }));
    expect(await screen.findByPlaceholderText("이메일을 입력하세요")).toBeInTheDocument();
  });
});
