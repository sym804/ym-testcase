import { useState, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { authApi } from "../api";
import toast from "react-hot-toast";
import PasswordInput from "../components/PasswordInput";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    password: "",
    confirm_password: "",
    display_name: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [usernameStatus, setUsernameStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const usernameTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkUsername = (username: string) => {
    if (usernameTimer.current) clearTimeout(usernameTimer.current);
    if (username.length < 2) { setUsernameStatus("idle"); return; }
    setUsernameStatus("checking");
    usernameTimer.current = setTimeout(async () => {
      try {
        const { available } = await authApi.checkUsername(username);
        setUsernameStatus(available ? "available" : "taken");
      } catch {
        setUsernameStatus("idle");
      }
    }, 400);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
    if (e.target.name === "username") {
      checkUsername(e.target.value);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.username || !form.password || !form.display_name) {
      setError("모든 필드를 입력해 주세요.");
      return;
    }
    if (usernameStatus === "taken") {
      setError("이미 사용 중인 아이디입니다.");
      return;
    }
    if (form.password.length < 8) {
      setError("비밀번호는 8자 이상이어야 합니다.");
      return;
    }
    if (form.password !== form.confirm_password) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setLoading(true);
    try {
      await register(form);
      toast.success("회원가입이 완료되었습니다. 로그인해 주세요.");
      navigate("/login");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ||
        (err instanceof Error ? err.message : "회원가입에 실패했습니다.");
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.headerBar}>
        <span style={styles.brand}>YM TestCase</span>
      </div>
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.heading}>회원가입</h2>
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>아이디</label>
            <input
              style={styles.input}
              name="username"
              value={form.username}
              onChange={handleChange}
              placeholder="아이디를 입력하세요"
              autoFocus
            />
            {usernameStatus === "checking" && (
              <div style={styles.checkingMsg}>확인 중...</div>
            )}
            {usernameStatus === "available" && (
              <div style={styles.availableMsg}>사용 가능한 아이디입니다.</div>
            )}
            {usernameStatus === "taken" && (
              <div style={styles.takenMsg}>이미 사용 중인 아이디입니다.</div>
            )}
            <label style={styles.label}>표시 이름</label>
            <input
              style={styles.input}
              name="display_name"
              value={form.display_name}
              onChange={handleChange}
              placeholder="표시될 이름을 입력하세요"
            />
            <label style={styles.label}>비밀번호</label>
            <PasswordInput
              style={styles.input}
              name="password"
              value={form.password}
              onChange={handleChange}
              placeholder="비밀번호를 입력하세요"
            />
            <label style={styles.label}>비밀번호 확인</label>
            <PasswordInput
              style={styles.input}
              name="confirm_password"
              value={form.confirm_password}
              onChange={handleChange}
              placeholder="비밀번호를 다시 입력하세요"
            />
            {form.password && form.password.length < 8 && (
              <div style={styles.hintMsg}>비밀번호는 8자 이상이어야 합니다.</div>
            )}
            {form.password && form.confirm_password && form.password !== form.confirm_password && (
              <div style={styles.hintMsg}>비밀번호가 일치하지 않습니다.</div>
            )}
            {error && <div style={styles.errorMsg}>{error}</div>}
            <button type="submit" style={styles.submitBtn} disabled={loading}>
              {loading ? "처리 중..." : "회원가입"}
            </button>
          </form>
          <div style={styles.footer}>
            이미 계정이 있으신가요?{" "}
            <Link to="/login" style={styles.link}>
              로그인
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { minHeight: "100vh", backgroundColor: "var(--bg-page)" },
  headerBar: {
    height: 56,
    backgroundColor: "var(--bg-header)",
    display: "flex",
    alignItems: "center",
    paddingLeft: 24,
  },
  brand: { color: "#fff", fontSize: 20, fontWeight: 700 },
  container: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "calc(100vh - 56px)",
  },
  card: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: "40px 36px",
    width: 400,
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
  },
  heading: {
    margin: "0 0 28px",
    fontSize: 24,
    fontWeight: 700,
    color: "var(--text-primary)",
    textAlign: "center" as const,
  },
  form: { display: "flex", flexDirection: "column" as const, gap: 8 },
  label: { fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginTop: 8 },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  checkingMsg: { fontSize: 12, color: "var(--text-secondary)", marginTop: -2 },
  availableMsg: { fontSize: 12, color: "var(--color-pass)", marginTop: -2 },
  takenMsg: { fontSize: 12, color: "#DC2626", marginTop: -2 },
  hintMsg: {
    fontSize: 12,
    color: "var(--color-block)",
    marginTop: -2,
  },
  errorMsg: {
    marginTop: 4,
    padding: "8px 12px",
    borderRadius: 6,
    backgroundColor: "rgba(220,38,38,0.08)",
    color: "#DC2626",
    fontSize: 13,
  },
  submitBtn: {
    marginTop: 20,
    padding: "12px 0",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  footer: {
    marginTop: 20,
    textAlign: "center" as const,
    fontSize: 14,
    color: "var(--text-secondary)",
  },
  link: { color: "var(--color-link)", fontWeight: 600, textDecoration: "none" },
};
