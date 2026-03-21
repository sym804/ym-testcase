import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChangePasswordModal from "../components/ChangePasswordModal";
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
import { UserRole } from "../types";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChangePasswordModal", () => {
  it("비밀번호 변경 폼이 렌더링된다", () => {
    renderWithProviders(<ChangePasswordModal />);
    expect(screen.getByText("비밀번호 변경 필요")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("현재 비밀번호")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("8자 이상")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("새 비밀번호 재입력")).toBeInTheDocument();
  });

  it("8자 미만이면 힌트를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChangePasswordModal />);

    await user.type(screen.getByPlaceholderText("8자 이상"), "short");

    expect(screen.getByText("8자 이상 입력해 주세요.")).toBeInTheDocument();
  });

  it("비밀번호 불일치 시 힌트를 표시한다", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChangePasswordModal />);

    await user.type(screen.getByPlaceholderText("8자 이상"), "password123");
    await user.type(screen.getByPlaceholderText("새 비밀번호 재입력"), "different");

    expect(screen.getByText("비밀번호가 일치하지 않습니다.")).toBeInTheDocument();
  });

  it("조건 미충족 시 제출 버튼이 비활성화된다", () => {
    renderWithProviders(<ChangePasswordModal />);
    const btn = screen.getByRole("button", { name: "비밀번호 변경" });
    expect(btn).toBeDisabled();
  });

  it("유효한 입력 시 비밀번호를 변경한다", async () => {
    const user = userEvent.setup();
    const updatedUser = {
      id: 1,
      username: "tester",
      display_name: "테스터",
      role: UserRole.USER,
      must_change_password: false,
      created_at: "2026-01-01",
    };
    vi.mocked(authApi.changePassword).mockResolvedValue(updatedUser);

    renderWithProviders(<ChangePasswordModal />);

    await user.type(screen.getByPlaceholderText("현재 비밀번호"), "oldpass123");
    await user.type(screen.getByPlaceholderText("8자 이상"), "newpass123");
    await user.type(screen.getByPlaceholderText("새 비밀번호 재입력"), "newpass123");

    const btn = screen.getByRole("button", { name: "비밀번호 변경" });
    expect(btn).not.toBeDisabled();

    await user.click(btn);

    await waitFor(() => {
      expect(authApi.changePassword).toHaveBeenCalledWith("oldpass123", "newpass123");
    });
  });

  it("변경 실패 시 에러 메시지를 표시한다", async () => {
    const user = userEvent.setup();
    vi.mocked(authApi.changePassword).mockRejectedValue({
      response: { data: { detail: "현재 비밀번호가 올바르지 않습니다." } },
    });

    renderWithProviders(<ChangePasswordModal />);

    await user.type(screen.getByPlaceholderText("현재 비밀번호"), "wrongpass");
    await user.type(screen.getByPlaceholderText("8자 이상"), "newpass123");
    await user.type(screen.getByPlaceholderText("새 비밀번호 재입력"), "newpass123");
    await user.click(screen.getByRole("button", { name: "비밀번호 변경" }));

    await waitFor(() => {
      expect(screen.getByText("현재 비밀번호가 올바르지 않습니다.")).toBeInTheDocument();
    });
  });

  it("로그아웃 버튼이 있다", () => {
    renderWithProviders(<ChangePasswordModal />);
    expect(screen.getByText("로그아웃")).toBeInTheDocument();
  });
});
