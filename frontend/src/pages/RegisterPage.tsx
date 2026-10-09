import { useEffect, useState, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { authApi } from "../api";
import toast from "react-hot-toast";
import PasswordInput from "../components/PasswordInput";
import { errorText } from "../utils/errorMessage";

export default function RegisterPage() {
  const { register } = useAuth();
  const { t } = useTranslation("register");
  const navigate = useNavigate();
  // 사용자가 0명이면 첫 관리자 모드(아이디 가입), 아니면 이메일 가입이다. 설정을 못 읽으면 이메일로.
  const [mode, setMode] = useState<"loading" | "bootstrap" | "email">("loading");
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    confirm_password: "",
    display_name: "",
    bootstrap_token: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [usernameStatus, setUsernameStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const usernameTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 아이디 확인 요청 번호. 늦게 온 옛 응답이 지금 입력의 결과를 덮지 않게 한다.
  const checkSeq = useRef(0);
  const bootstrap = mode === "bootstrap";

  const loadConfig = () => authApi.config()
    .then((c) => setMode(c.signup_mode === "bootstrap" ? "bootstrap" : "email"))
    .catch(() => setMode("email"));

  useEffect(() => {
    let alive = true;
    authApi.config()
      .then((c) => { if (alive) setMode(c.signup_mode === "bootstrap" ? "bootstrap" : "email"); })
      .catch(() => { if (alive) setMode("email"); });
    return () => {
      alive = false;
      checkSeq.current += 1;
      if (usernameTimer.current) clearTimeout(usernameTimer.current);
    };
  }, []);

  const checkUsername = (username: string) => {
    if (usernameTimer.current) clearTimeout(usernameTimer.current);
    const seq = ++checkSeq.current;
    if (username.length < 2) { setUsernameStatus("idle"); return; }
    setUsernameStatus("checking");
    usernameTimer.current = setTimeout(async () => {
      try {
        const { available } = await authApi.checkUsername(username);
        if (seq === checkSeq.current) setUsernameStatus(available ? "available" : "taken");
      } catch {
        if (seq === checkSeq.current) setUsernameStatus("idle");
      }
    }, 400);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
    if (bootstrap && e.target.name === "username") {
      checkUsername(e.target.value);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const id = bootstrap ? form.username : form.email;
    if (!id || !form.password || !form.display_name) {
      setError(t("allFieldsRequired"));
      return;
    }
    if (bootstrap && usernameStatus === "taken") {
      setError(t("usernameTaken"));
      return;
    }
    // 비밀번호 검사가 먼저다. 이메일 형식은 서버가 본다.
    if (form.password.length < 8) {
      setError(t("passwordMinLength"));
      return;
    }
    if (form.password !== form.confirm_password) {
      setError(t("passwordMismatch"));
      return;
    }
    setLoading(true);
    try {
      const created = await register({
        username: bootstrap ? form.username : undefined,
        email: bootstrap ? undefined : form.email,
        password: form.password,
        confirm_password: form.confirm_password,
        display_name: form.display_name,
        bootstrap_token: bootstrap ? form.bootstrap_token : undefined,
      });
      toast.success(created?.status === "pending" ? t("registerPending") : t("registerSuccess"));
      navigate("/login");
    } catch (err: unknown) {
      setError(errorText(err, t("registerFailed")));
      // 첫 관리자 화면을 연 사이 다른 사람이 먼저 가입했다. 이메일 가입 화면으로 바꾼다.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (bootstrap && detail === "이메일로 가입해 주세요.") loadConfig();
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
          {mode === "loading" ? (
            <div style={styles.loadingMsg}>{t("common:loadingData")}</div>
          ) : (
            <>
              <h2 style={styles.heading}>{bootstrap ? t("titleBootstrap") : t("title")}</h2>
              {bootstrap && <p style={styles.bootstrapHelp}>{t("bootstrapHelp")}</p>}
              <form onSubmit={handleSubmit} style={styles.form}>
                {bootstrap ? (
                  <>
                    <label style={styles.label} htmlFor="register-username">{t("username")}</label>
                    <input
                      id="register-username"
                      style={styles.input}
                      name="username"
                      value={form.username}
                      onChange={handleChange}
                      placeholder={t("usernamePlaceholder")}
                      autoFocus
                    />
                    {usernameStatus === "checking" && (
                      <div style={styles.checkingMsg}>{t("checking")}</div>
                    )}
                    {usernameStatus === "available" && (
                      <div style={styles.availableMsg}>{t("usernameAvailable")}</div>
                    )}
                    {usernameStatus === "taken" && (
                      <div style={styles.takenMsg}>{t("usernameTaken")}</div>
                    )}
                  </>
                ) : (
                  <>
                    <label style={styles.label} htmlFor="register-email">{t("email")}</label>
                    <input
                      id="register-email"
                      style={styles.input}
                      name="email"
                      type="text"
                      inputMode="email"
                      autoComplete="email"
                      value={form.email}
                      onChange={handleChange}
                      placeholder={t("emailPlaceholder")}
                      autoFocus
                    />
                  </>
                )}
                <label style={styles.label} htmlFor="register-display-name">{t("displayName")}</label>
                <input
                  id="register-display-name"
                  style={styles.input}
                  name="display_name"
                  value={form.display_name}
                  onChange={handleChange}
                  placeholder={t("displayNamePlaceholder")}
                />
                <label style={styles.label} htmlFor="register-password">{t("password")}</label>
                <PasswordInput
                  id="register-password"
                  style={styles.input}
                  name="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder={t("passwordPlaceholder")}
                />
                <label style={styles.label} htmlFor="register-confirm">{t("confirmPassword")}</label>
                <PasswordInput
                  id="register-confirm"
                  style={styles.input}
                  name="confirm_password"
                  value={form.confirm_password}
                  onChange={handleChange}
                  placeholder={t("confirmPasswordPlaceholder")}
                />
                {form.password && form.password.length < 8 && (
                  <div style={styles.hintMsg}>{t("passwordMinLength")}</div>
                )}
                {form.password && form.confirm_password && form.password !== form.confirm_password && (
                  <div style={styles.hintMsg}>{t("passwordMismatch")}</div>
                )}
                {bootstrap && (
                  <>
                    <label style={styles.label} htmlFor="register-bootstrap-token">{t("bootstrapToken")}</label>
                    <input
                      id="register-bootstrap-token"
                      style={styles.input}
                      name="bootstrap_token"
                      value={form.bootstrap_token}
                      onChange={handleChange}
                      placeholder={t("bootstrapTokenPlaceholder")}
                      autoComplete="off"
                    />
                  </>
                )}
                {error && <div style={styles.errorMsg} role="alert">{error}</div>}
                <button type="submit" style={styles.submitBtn} disabled={loading}>
                  {loading ? t("submitting") : bootstrap ? t("submitBootstrap") : t("submit")}
                </button>
              </form>
              <div style={styles.footer}>
                {t("hasAccount")}{" "}
                <Link to="/login" style={styles.link}>
                  {t("login")}
                </Link>
              </div>
            </>
          )}
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
  bootstrapHelp: {
    margin: "-16px 0 16px",
    fontSize: 13,
    color: "var(--text-secondary)",
    lineHeight: 1.6,
    textAlign: "center" as const,
  },
  loadingMsg: { textAlign: "center" as const, fontSize: 14, color: "var(--text-secondary)" },
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
