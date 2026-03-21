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

interface AuthContextType {
  user: User | null;
  loading: boolean;
  mustChangePassword: boolean;
  login: (form: LoginForm) => Promise<void>;
  register: (form: RegisterForm) => Promise<void>;
  logout: () => void;
  changePassword: (currentPw: string, newPw: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const me = await authApi.getMe();
      setUser(me);
      setMustChangePassword(me.must_change_password);
    } catch {
      localStorage.removeItem("token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (form: LoginForm) => {
    const data = await authApi.login(form);
    localStorage.setItem("token", data.access_token);
    const me = await authApi.getMe();
    setUser(me);
    if (me.must_change_password) {
      setMustChangePassword(true);
    } else {
      toast.success(`${me.display_name}님, 환영합니다!`);
    }
  };

  const register = async (form: RegisterForm) => {
    if (form.password !== form.confirm_password) {
      throw new Error("비밀번호가 일치하지 않습니다.");
    }
    if (form.password.length < 8) {
      throw new Error("비밀번호는 8자 이상이어야 합니다.");
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
    toast.success("비밀번호가 변경되었습니다.");
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    setMustChangePassword(false);
    toast.success("로그아웃 되었습니다.");
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
