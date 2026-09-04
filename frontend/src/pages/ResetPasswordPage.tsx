import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PasswordInput from "../components/PasswordInput";
import { accountRequestsApi } from "../api/index";

export default function ResetPasswordPage() {
  const { t } = useTranslation("accountHelp");
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!username || !code || !password) {
      setError(t("emptyFields"));
      return;
    }
    if (password.length < 8) {
      setError(t("passwordTooShort"));
      return;
    }
    if (password !== confirm) {
      setError(t("passwordMismatch"));
      return;
    }
    setLoading(true);
    try {
      await accountRequestsApi.resetWithCode(username, code, password);
      setDone(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch {
      setError(t("resetFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>{t("resetTitle")}</h2>
        {done ? (
          <>
            <p style={styles.doneText}>{t("resetDone")}</p>
            <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
          </>
        ) : (
          <>
            <p style={styles.intro}>{t("resetIntro")}</p>
            <form onSubmit={handleSubmit}>
              <label style={styles.label}>
                {t("username")}
                <input style={styles.input} value={username}
                       onChange={(e) => setUsername(e.target.value)}
                       placeholder={t("usernamePlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("code")}
                <input style={styles.input} value={code}
                       onChange={(e) => setCode(e.target.value)}
                       placeholder={t("codePlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("newPassword")}
                <PasswordInput style={styles.input} value={password}
                               onChange={(e) => setPassword(e.target.value)}
                               placeholder={t("newPasswordPlaceholder")} />
              </label>
              <label style={styles.label}>
                {t("confirmPassword")}
                <PasswordInput style={styles.input} value={confirm}
                               onChange={(e) => setConfirm(e.target.value)}
                               placeholder={t("newPasswordPlaceholder")} />
              </label>

              {error && <div style={styles.error}>{error}</div>}

              <button type="submit" disabled={loading} style={styles.submit}>
                {loading ? t("submitting") : t("resetSubmit")}
              </button>
            </form>
            <div style={styles.footer}>
              <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    minHeight: "100vh", backgroundColor: "var(--bg-page)",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
  },
  card: {
    width: "100%", maxWidth: 420, backgroundColor: "var(--bg-card, #fff)",
    borderRadius: 10, padding: 28, border: "1px solid var(--border-color, #E2E8F0)",
  },
  title: { margin: "0 0 12px", fontSize: 20 },
  intro: { fontSize: 13, lineHeight: 1.6, marginBottom: 20, color: "var(--text-secondary, #64748B)" },
  label: { display: "block", fontSize: 13, marginBottom: 14 },
  input: {
    width: "100%", marginTop: 6, padding: "9px 10px", fontSize: 13, boxSizing: "border-box",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
  },
  error: { color: "var(--danger, #DC2626)", fontSize: 12, marginBottom: 12 },
  submit: {
    width: "100%", padding: "10px 0", fontSize: 14, cursor: "pointer",
    border: "none", borderRadius: 6, backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  doneText: { fontSize: 13, lineHeight: 1.6, marginBottom: 20 },
  footer: { marginTop: 18, textAlign: "center", fontSize: 12 },
  link: { color: "var(--accent, #2563EB)", textDecoration: "none" },
};
