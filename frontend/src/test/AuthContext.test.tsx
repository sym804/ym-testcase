import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "../contexts/AuthContext";

// Mock API
vi.mock("../api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
    checkUsername: vi.fn(),
    changePassword: vi.fn(),
  },
}));

// Mock toast
vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import { authApi } from "../api";
import toast from "react-hot-toast";
import { UserRole } from "../types";

const wrapper = ({ children }: { children: ReactNode }) => (
  <MemoryRouter>
    <AuthProvider>{children}</AuthProvider>
  </MemoryRouter>
);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AuthContext", () => {
  describe("초기 상태", () => {
    it("토큰이 없으면 user는 null이고 loading이 false가 된다", async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
      expect(result.current.user).toBeNull();
    });

    it("토큰이 있으면 getMe를 호출하여 사용자를 로드한다", async () => {
      localStorage.setItem("token", "valid-token");
      const mockUser = {
        id: 1,
        username: "tester",
        display_name: "테스터",
        role: UserRole.USER,
        must_change_password: false,
        created_at: "2026-01-01",
      };
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
      expect(result.current.user).toEqual(mockUser);
    });

    it("토큰이 유효하지 않으면 토큰을 제거한다", async () => {
      localStorage.setItem("token", "invalid-token");
      vi.mocked(authApi.getMe).mockRejectedValue(new Error("Unauthorized"));

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });
      expect(result.current.user).toBeNull();
      expect(localStorage.getItem("token")).toBeNull();
    });
  });

  describe("login", () => {
    it("로그인 성공 시 토큰을 저장하고 사용자를 로드한다", async () => {
      const mockUser = {
        id: 1,
        username: "tester",
        display_name: "테스터",
        role: UserRole.USER,
        must_change_password: false,
        created_at: "2026-01-01",
      };
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: "new-token",
        token_type: "bearer",
      });
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await act(async () => {
        await result.current.login({ username: "tester", password: "pass1234" });
      });

      expect(localStorage.getItem("token")).toBe("new-token");
      expect(result.current.user).toEqual(mockUser);
      expect(toast.success).toHaveBeenCalledWith("테스터님, 환영합니다!");
    });

    it("must_change_password가 true이면 환영 메시지를 표시하지 않는다", async () => {
      const mockUser = {
        id: 1,
        username: "tester",
        display_name: "테스터",
        role: UserRole.USER,
        must_change_password: true,
        created_at: "2026-01-01",
      };
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: "new-token",
        token_type: "bearer",
      });
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await act(async () => {
        await result.current.login({ username: "tester", password: "pass1234" });
      });

      expect(result.current.mustChangePassword).toBe(true);
      expect(toast.success).not.toHaveBeenCalled();
    });

    it("로그인 실패 시 에러를 throw한다", async () => {
      vi.mocked(authApi.login).mockRejectedValue({
        response: { data: { detail: "아이디 또는 비밀번호가 올바르지 않습니다." } },
      });

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await expect(
        act(async () => {
          await result.current.login({ username: "wrong", password: "wrong" });
        })
      ).rejects.toBeDefined();
    });
  });

  describe("register", () => {
    it("비밀번호 불일치 시 에러를 throw한다", async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await expect(
        act(async () => {
          await result.current.register({
            username: "new",
            password: "password1",
            confirm_password: "password2",
            display_name: "New",
          });
        })
      ).rejects.toThrow("비밀번호가 일치하지 않습니다.");
    });

    it("비밀번호가 8자 미만이면 에러를 throw한다", async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await expect(
        act(async () => {
          await result.current.register({
            username: "new",
            password: "short",
            confirm_password: "short",
            display_name: "New",
          });
        })
      ).rejects.toThrow("비밀번호는 8자 이상이어야 합니다.");
    });

    it("유효한 폼이면 API를 호출한다", async () => {
      vi.mocked(authApi.register).mockResolvedValue({
        id: 2,
        username: "new",
        display_name: "New",
        role: UserRole.USER as never,
        must_change_password: false,
        created_at: "2026-01-01",
      });

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.loading).toBe(false));

      await act(async () => {
        await result.current.register({
          username: "new",
          password: "password123",
          confirm_password: "password123",
          display_name: "New",
        });
      });

      expect(authApi.register).toHaveBeenCalledWith({
        username: "new",
        password: "password123",
        display_name: "New",
      });
    });
  });

  describe("logout", () => {
    it("로그아웃 시 토큰과 사용자를 제거한다", async () => {
      localStorage.setItem("token", "valid-token");
      const mockUser = {
        id: 1,
        username: "tester",
        display_name: "테스터",
        role: UserRole.USER,
        must_change_password: false,
        created_at: "2026-01-01",
      };
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.user).toEqual(mockUser));

      act(() => {
        result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(localStorage.getItem("token")).toBeNull();
      expect(toast.success).toHaveBeenCalledWith("로그아웃 되었습니다.");
    });
  });

  describe("changePassword", () => {
    it("비밀번호 변경 성공 시 mustChangePassword를 false로 설정한다", async () => {
      localStorage.setItem("token", "valid-token");
      const mockUser = {
        id: 1,
        username: "tester",
        display_name: "테스터",
        role: UserRole.USER,
        must_change_password: true,
        created_at: "2026-01-01",
      };
      const updatedUser = { ...mockUser, must_change_password: false };
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser);
      vi.mocked(authApi.changePassword).mockResolvedValue(updatedUser);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await waitFor(() => expect(result.current.mustChangePassword).toBe(true));

      await act(async () => {
        await result.current.changePassword("old", "newpass123");
      });

      expect(result.current.mustChangePassword).toBe(false);
      expect(result.current.user).toEqual(updatedUser);
      expect(toast.success).toHaveBeenCalledWith("비밀번호가 변경되었습니다.");
    });
  });

  describe("useAuth hook", () => {
    it("AuthProvider 밖에서 사용하면 에러를 throw한다", () => {
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow("useAuth must be used within AuthProvider");
    });
  });
});
