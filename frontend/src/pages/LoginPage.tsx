import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import PasswordInput from "../components/PasswordInput";
import { translateError } from "../utils/errorMessage";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useTranslation("login");
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username || !password) {
      setError(t("emptyFields"));
      return;
    }
    setLoading(true);
    try {
      await login({ username, password, remember_me: rememberMe });
      navigate("/projects");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ? translateError(detail) : t("loginFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.headerBar}>
        <span style={styles.brand}>{t("common:brandName")}</span>
      </div>
      <div style={styles.container}>
        <div style={styles.card}>
          <h2 style={styles.heading}>{t("title")}</h2>
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>{t("username")}</label>
            <input
              style={styles.input}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("usernamePlaceholder")}
              autoFocus
            />
            <label style={styles.label}>{t("password")}</label>
            <PasswordInput
              style={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("passwordPlaceholder")}
            />
            <label style={styles.rememberMe}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              {t("rememberMe")}
            </label>
            {error && <div style={styles.errorMsg}>{error}</div>}
            <button
              type="submit"
              style={styles.submitBtn}
              disabled={loading}
            >
              {loading ? t("submitting") : t("submit")}
            </button>
          </form>
          <div style={styles.footer}>
            {t("noAccount")}{" "}
            <Link to="/register" style={styles.link}>
              {t("register")}
            </Link>
          </div>
          <div style={styles.hint}>
            {t("forgotPassword")}
          </div>
        </div>
      </div>
      <div style={{ position: "absolute", bottom: 16, width: "100%", textAlign: "center", fontSize: 11, color: "var(--text-secondary, #94A3B8)" }}>
        {t("common:version")}
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
    backgroundColor: "var(--bg-header)",
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
  link: {
    color: "var(--color-link)",
    fontWeight: 600,
    textDecoration: "none",
  },
  rememberMe: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 14,
    color: "var(--text-secondary)",
    marginTop: 8,
    cursor: "pointer",
  },
  hint: {
    marginTop: 8,
    textAlign: "center" as const,
    fontSize: 12,
    color: "var(--text-secondary)",
    opacity: 0.7,
  },
};
