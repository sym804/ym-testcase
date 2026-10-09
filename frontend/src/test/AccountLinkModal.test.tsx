import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountLinkModal from "../components/AccountLinkModal";

let mockAuthUser: Record<string, unknown> = {};
const mockRefreshUser = vi.fn();

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user: mockAuthUser, refreshUser: mockRefreshUser }),
}));

vi.mock("../api", () => ({
  authApi: { config: vi.fn(), unlinkGoogle: vi.fn() },
  googleStartUrl: (mode: string) => `/api/auth/google/start?mode=${mode}`,
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

import { authApi } from "../api";
import toast from "react-hot-toast";

const base = { id: 1, username: "me", display_name: "나", role: "user", must_change_password: false, created_at: "2026-01-01" };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(authApi.config).mockResolvedValue({ google_enabled: true, signup_mode: "email" });
});

describe("AccountLinkModal", () => {
  it("연결 안 된 계정에는 Google 계정 연결 링크", async () => {
    mockAuthUser = { ...base, has_password: true, google_linked: false };
    render(<AccountLinkModal onClose={vi.fn()} />);
    const link = await screen.findByRole("link", { name: "Google 계정 연결" });
    expect(link.getAttribute("href")).toContain("mode=link");
  });

  it("Google 로그인이 꺼져 있으면 링크 대신 안내", async () => {
    vi.mocked(authApi.config).mockResolvedValue({ google_enabled: false, signup_mode: "email" });
    mockAuthUser = { ...base, has_password: true, google_linked: false };
    render(<AccountLinkModal onClose={vi.fn()} />);
    expect(await screen.findByText("Google 로그인이 꺼져 있습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Google 계정 연결" })).not.toBeInTheDocument();
  });

  it("연결된 계정은 해제할 수 있다", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(authApi.unlinkGoogle).mockResolvedValue({} as never);
    mockAuthUser = { ...base, has_password: true, google_linked: true };
    render(<AccountLinkModal onClose={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "연결 해제" }));
    await waitFor(() => {
      expect(authApi.unlinkGoogle).toHaveBeenCalled();
      expect(mockRefreshUser).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith("Google 계정 연결을 해제했습니다.");
    });
  });

  it("연결된 Google 계정 주소를 보여 준다", async () => {
    mockAuthUser = { ...base, has_password: true, google_linked: true, google_email: "me@gmail.com" };
    render(<AccountLinkModal onClose={vi.fn()} />);
    expect(await screen.findByText("me@gmail.com")).toBeInTheDocument();
  });

  it("비밀번호 없는 계정은 해제 버튼 대신 안내", async () => {
    mockAuthUser = { ...base, has_password: false, google_linked: true };
    render(<AccountLinkModal onClose={vi.fn()} />);
    expect(await screen.findByText("비밀번호가 없는 계정은 해제할 수 없습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "연결 해제" })).not.toBeInTheDocument();
  });
});
