import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { authApi, googleStartUrl } from "../api";
import { useAuth } from "../contexts/AuthContext";
import { errorText } from "../utils/errorMessage";

/**
 * Google 계정 연결과 해제.
 *
 * 연결은 페이지 이동(Google 화면을 거쳐 돌아온다)이고 결과는 /projects?account=... 로 온다.
 * 비밀번호가 없는 계정(Google 로만 가입)은 해제하면 들어올 방법이 없어 해제를 막는다.
 */
export default function AccountLinkModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("header");
  const { user, refreshUser } = useAuth();
  const [googleEnabled, setGoogleEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    authApi.config()
      .then((c) => { if (alive) setGoogleEnabled(c.google_enabled); })
      .catch(() => { if (alive) setGoogleEnabled(false); });
    return () => { alive = false; };
  }, []);

  const linked = Boolean(user?.google_linked);
  const hasPassword = user?.has_password !== false;

  const handleUnlink = async () => {
    if (!confirm(t("unlinkGoogleConfirm"))) return;
    setBusy(true);
    try {
      await authApi.unlinkGoogle();
      await refreshUser();
      toast.success(t("googleUnlinked"));
    } catch (err) {
      toast.error(errorText(err, t("googleUnlinkFailed")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="account-link-title">
        <h3 id="account-link-title" style={styles.title}>{t("accountLink")}</h3>
        <p style={styles.help}>{t("accountLinkHelp")}</p>
        <div style={styles.row}>
          <span style={styles.state}>
            {linked ? t("googleLinked") : t("googleNotLinked")}
            {linked && user?.google_email && (
              <span style={styles.linkedEmail}>{user.google_email}</span>
            )}
          </span>
          {linked ? (
            hasPassword ? (
              <button type="button" style={styles.dangerBtn} onClick={handleUnlink} disabled={busy}>
                {t("unlinkGoogle")}
              </button>
            ) : (
              <span style={styles.note}>{t("noPasswordCannotUnlink")}</span>
            )
          ) : googleEnabled === null ? null : googleEnabled ? (
            <a href={googleStartUrl("link")} style={styles.primaryBtn}>{t("linkGoogle")}</a>
          ) : (
            <span style={styles.note}>{t("googleDisabled")}</span>
          )}
        </div>
        <div style={styles.footer}>
          <button type="button" style={styles.secondaryBtn} onClick={onClose}>{t("common:close")}</button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(0,0,0,0.5)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 300,
  },
  modal: {
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    borderRadius: 12,
    padding: 28,
    width: 480,
    maxWidth: "92vw",
    boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
  },
  title: { margin: "0 0 6px", fontSize: 18, fontWeight: 700 },
  help: { margin: "0 0 18px", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 },
  row: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
    padding: "12px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-input)",
  },
  state: { fontSize: 14, fontWeight: 600 },
  linkedEmail: { display: "block", marginTop: 2, fontSize: 12, fontWeight: 400, color: "var(--text-secondary)", wordBreak: "break-all" },
  note: { fontSize: 12, color: "var(--text-secondary)" },
  primaryBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    textDecoration: "none",
  },
  dangerBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid #DC2626",
    backgroundColor: "transparent",
    color: "#DC2626",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  footer: { marginTop: 18, display: "flex", justifyContent: "flex-end" },
  secondaryBtn: {
    padding: "8px 16px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "transparent",
    color: "var(--text-primary)",
    fontSize: 13,
    cursor: "pointer",
  },
};
