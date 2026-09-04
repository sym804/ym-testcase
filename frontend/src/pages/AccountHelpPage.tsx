import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { accountRequestsApi } from "../api/index";

type Tab = "find_id" | "reset_password";

export default function AccountHelpPage() {
  const { t } = useTranslation("accountHelp");
  const [tab, setTab] = useState<Tab>("find_id");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const identifier = tab === "find_id" ? displayName : username;
    if (!identifier || !contact) {
      setError(t("emptyFields"));
      return;
    }
    setLoading(true);
    try {
      await accountRequestsApi.submit({
        request_type: tab,
        claimed_display_name: tab === "find_id" ? displayName : undefined,
        claimed_username: tab === "reset_password" ? username : undefined,
        contact,
        note: note || undefined,
      });
      setDone(true);
    } catch {
      setError(t("failed"));
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div style={styles.wrapper}>
        <div style={styles.card}>
          <h2 style={styles.title}>{t("title")}</h2>
          <p style={styles.doneText}>{t("submitted")}</p>
          <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.card}>
        <h2 style={styles.title}>{t("title")}</h2>

        <div style={styles.tabs}>
          <button type="button" onClick={() => setTab("find_id")}
                  style={tab === "find_id" ? styles.tabOn : styles.tab}>
            {t("tabFindId")}
          </button>
          <button type="button" onClick={() => setTab("reset_password")}
                  style={tab === "reset_password" ? styles.tabOn : styles.tab}>
            {t("tabResetPassword")}
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {tab === "find_id" ? (
            <label style={styles.label}>
              {t("displayName")}
              <input style={styles.input} value={displayName}
                     onChange={(e) => setDisplayName(e.target.value)}
                     placeholder={t("displayNamePlaceholder")} />
            </label>
          ) : (
            <label style={styles.label}>
              {t("username")}
              <input style={styles.input} value={username}
                     onChange={(e) => setUsername(e.target.value)}
                     placeholder={t("usernamePlaceholder")} />
            </label>
          )}

          <label style={styles.label}>
            {t("contact")}
            <input style={styles.input} value={contact}
                   onChange={(e) => setContact(e.target.value)}
                   placeholder={t("contactPlaceholder")} />
          </label>

          <label style={styles.label}>
            {t("note")}
            <textarea style={{ ...styles.input, height: 72 }} value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder={t("notePlaceholder")} />
          </label>

          {error && <div style={styles.error}>{error}</div>}

          <button type="submit" disabled={loading} style={styles.submit}>
            {loading ? t("submitting") : t("submit")}
          </button>
        </form>

        <div style={styles.footer}>
          <Link to="/login" style={styles.link}>{t("backToLogin")}</Link>
        </div>
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
  title: { margin: "0 0 20px", fontSize: 20 },
  tabs: { display: "flex", gap: 8, marginBottom: 20 },
  tab: {
    flex: 1, padding: "8px 0", cursor: "pointer", fontSize: 13,
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
    backgroundColor: "transparent", color: "var(--text-secondary, #64748B)",
  },
  tabOn: {
    flex: 1, padding: "8px 0", cursor: "pointer", fontSize: 13, fontWeight: 600,
    border: "1px solid var(--accent, #2563EB)", borderRadius: 6,
    backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
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
