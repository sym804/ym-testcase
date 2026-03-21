import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import PasswordInput from "../components/PasswordInput";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username || !password) {
      setError("아이디와 비밀번호를 입력해 주세요.");
      return;
    }
    setLoading(true);
    try {
      await login({ username, password });
      navigate("/projects");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "로그인에 실패했습니다.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.headerBar}>
        <span style={styles.brand}>TC Manager</span>
      </div>
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.heading}>로그인</h2>
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>아이디</label>
            <input
              style={styles.input}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="아이디를 입력하세요"
              autoFocus
            />
            <label style={styles.label}>비밀번호</label>
            <PasswordInput
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
            />
            {error && <div style={styles.errorMsg}>{error}</div>}
            <button
              type="submit"
              style={styles.submitBtn}
              disabled={loading}
            >
              {loading ? "로그인 중..." : "로그인"}
            </button>
          </form>
          <div style={styles.footer}>
            계정이 없으신가요?{" "}
            <Link to="/register" style={styles.link}>
              회원가입
            </Link>
          </div>
          <div style={styles.hint}>
            비밀번호를 잊으셨다면 관리자에게 초기화를 요청하세요.
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    minHeight: "100vh",
    backgroundColor: "var(--bg-page)",
  },
  headerBar: {
    height: 56,
    backgroundColor: "#0F1923",
    display: "flex",
    alignItems: "center",
    paddingLeft: 24,
  },
  brand: {
    color: "#fff",
    fontSize: 20,
    fontWeight: 700,
  },
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
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
  },
  label: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text-secondary)",
    marginTop: 8,
  },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
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
    backgroundColor: "#2D4A7A",
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
  link: {
    color: "#5B9BD5",
    fontWeight: 600,
    textDecoration: "none",
  },
  hint: {
    marginTop: 8,
    textAlign: "center" as const,
    fontSize: 12,
    color: "var(--text-secondary)",
    opacity: 0.7,
  },
};
