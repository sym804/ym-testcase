import { useEffect, useState } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import PasswordInput from "../components/PasswordInput";
import { errorText, googleErrorMessage } from "../utils/errorMessage";
import { authApi, googleStartUrl } from "../api";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useTranslation("login");
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [searchParams] = useSearchParams();
  // Google 콜백이 실패 사유를 ?error=<코드> 로 넘긴다. 모르는 코드는 일반 실패 문구로.
  const callbackError = searchParams.get("error");
  const callbackMessage = callbackError ? googleErrorMessage(callbackError) : "";

  useEffect(() => {
    let alive = true;
    authApi.config()
      .then((c) => { if (alive) setGoogleEnabled(c.google_enabled); })
      .catch(() => { if (alive) setGoogleEnabled(false); });
    return () => { alive = false; };
  }, []);

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
      setError(errorText(err, t("loginFailed")));
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
            <label style={styles.label} htmlFor="login-username">{t("username")}</label>
            <input
              id="login-username"
              style={styles.input}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("usernamePlaceholder")}
              autoFocus
            />
            <label style={styles.label} htmlFor="login-password">{t("password")}</label>
            <PasswordInput
              id="login-password"
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
            {(error || callbackMessage) && <div style={styles.errorMsg} role="alert">{error || callbackMessage}</div>}
            <button
              type="submit"
              style={styles.submitBtn}
              disabled={loading}
            >
              {loading ? t("submitting") : t("submit")}
            </button>
          </form>
          {googleEnabled && (
            <>
              <div style={styles.divider}>{t("or")}</div>
              <a href={googleStartUrl("login")} style={styles.googleBtn}>
                {t("googleLogin")}
              </a>
            </>
          )}
          <div style={styles.footer}>
            {t("noAccount")}{" "}
            <Link to="/register" style={styles.link}>
              {t("register")}
            </Link>
          </div>
          <div style={styles.hint}>
            {t("forgotPassword")}{" "}
            <Link to="/account-help" style={styles.link}>
              {t("forgotPasswordLink")}
            </Link>
          </div>
        </div>
      </div>
      {/* 화면 바닥에 고정하면 카드가 길 때(Google 버튼) 낮은 화면에서 카드 문구와 겹친다. 카드 아래에 둔다 */}
      <div style={styles.version}>{t("common:version")}</div>
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
    minHeight: "calc(100vh - 56px - 44px)",
    padding: "24px 0",
    boxSizing: "border-box" as const,
  },
  version: {
    height: 44,
    textAlign: "center" as const,
    fontSize: 11,
    color: "var(--text-secondary, #94A3B8)",
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
  divider: {
    marginTop: 16,
    textAlign: "center" as const,
    fontSize: 12,
    color: "var(--text-secondary)",
  },
  googleBtn: {
    display: "block",
    marginTop: 8,
    padding: "11px 0",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
    fontSize: 15,
    fontWeight: 600,
    textAlign: "center" as const,
    textDecoration: "none",
  },
  hint: {
    marginTop: 8,
    textAlign: "center" as const,
    fontSize: 12,
    // opacity 로 흐리게 하면 대비가 같이 죽는다. 이 자리는 0.7 을 곱해 2.76:1 이었다.
    // 톤은 색으로만 낮춘다.
    color: "var(--text-secondary)",
  },
};
