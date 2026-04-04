import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import type { User, LoginForm, RegisterForm } from "../types";
import { authApi } from "../api";
import toast from "react-hot-toast";
import i18n from "../i18n";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  mustChangePassword: boolean;
  login: (form: LoginForm) => Promise<void>;
  register: (form: RegisterForm) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (currentPw: string, newPw: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  const loadUser = useCallback(async () => {
    try {
      const me = await authApi.getMe();
      setUser(me);
      setMustChangePassword(me.must_change_password);
    } catch {
      // 쿠키 없거나 만료 — 미로그인 상태
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (form: LoginForm) => {
    await authApi.login(form);
    // 서버가 httpOnly 쿠키를 설정하므로 별도 저장 불필요
    const me = await authApi.getMe();
    setUser(me);
    if (me.must_change_password) {
      setMustChangePassword(true);
    } else {
      toast.success(i18n.t("header:welcomeMessage", { name: me.display_name }));
    }
  };

  const register = async (form: RegisterForm) => {
    if (form.password !== form.confirm_password) {
      throw new Error(i18n.t("header:passwordMismatch"));
    }
    if (form.password.length < 8) {
      throw new Error(i18n.t("header:passwordMinLength"));
    }
    await authApi.register({
      username: form.username,
      password: form.password,
      display_name: form.display_name,
    });
  };

  const changePassword = async (currentPw: string, newPw: string) => {
    const updated = await authApi.changePassword(currentPw, newPw);
    setUser(updated);
    setMustChangePassword(false);
    toast.success(i18n.t("header:passwordChanged"));
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // 서버 에러여도 클라이언트 상태는 정리
    }
    setUser(null);
    setMustChangePassword(false);
    toast.success(i18n.t("header:logoutSuccess"));
  };

  return (
    <AuthContext.Provider value={{ user, loading, mustChangePassword, login, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
