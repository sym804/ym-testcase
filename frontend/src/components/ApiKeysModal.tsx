import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { authApi } from "../api";
import { translateError } from "../utils/errorMessage";
import type { ApiKeyItem } from "../types";

const EXPIRY_OPTIONS: (number | null)[] = [30, 90, 180, 365, null];

const errorDetail = (err: unknown) =>
  (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;

/** 서버 시각은 tz 없는 KST 문자열이다. 변환하지 않고 잘라 보여 준다. */
const shortTime = (v: string | null) => (v ? v.replace("T", " ").slice(0, 16) : "-");

/**
 * 본인 API 키 목록 · 발급 · 폐기.
 *
 * 원문은 발급 직후 한 번만 보여 준다. 서버는 해시만 남기므로 창을 닫으면 다시 볼 수 없다.
 */
export default function ApiKeysModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("header");
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState<number | null>(90);
  const [created, setCreated] = useState<{ name: string; key: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setKeys(await authApi.listApiKeys());
    } catch (err) {
      const detail = errorDetail(err);
      toast.error(detail ? translateError(detail) : t("apiKeyLoadFailed"));
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast.error(t("apiKeyNameRequired")); return; }
    setBusy(true);
    try {
      const res = await authApi.createApiKey(name.trim(), expiry);
      setCreated({ name: res.name, key: res.key });
      setName("");
      await load();
    } catch (err) {
      const detail = errorDetail(err);
      toast.error(detail ? translateError(detail) : t("apiKeyCreateFailed"));
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (k: ApiKeyItem) => {
    if (!confirm(t("apiKeyRevokeConfirm", { name: k.name }))) return;
    try {
      await authApi.revokeApiKey(k.id);
      toast.success(t("apiKeyRevoked", { name: k.name }));
      await load();
    } catch (err) {
      const detail = errorDetail(err);
      toast.error(detail ? translateError(detail) : t("apiKeyRevokeFailed"));
    }
  };

  const copyKey = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.key);
      toast.success(t("apiKeyCopied"));
    } catch {
      toast.error(t("apiKeyCopyFailed"));
    }
  };

  const statusLabel = (s: ApiKeyItem["status"]) =>
    s === "active" ? t("apiKeyActive") : s === "expired" ? t("apiKeyExpired") : t("apiKeyRevokedStatus");

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="api-keys-title">
        <h3 id="api-keys-title" style={styles.title}>{t("apiKeys")}</h3>
        <p style={styles.help}>{t("apiKeyHelp")}</p>

        {created && (
          <div style={styles.createdBox} data-testid="api-key-created">
            <div style={styles.createdHead}>{t("apiKeyCreatedHead", { name: created.name })}</div>
            <div style={styles.keyRow}>
              <code style={styles.keyText}>{created.key}</code>
              <button type="button" style={styles.secondaryBtn} onClick={copyKey}>{t("apiKeyCopy")}</button>
            </div>
            <div style={styles.warn}>{t("apiKeyShownOnce")}</div>
          </div>
        )}

        <form style={styles.form} onSubmit={handleCreate}>
          <label style={styles.field}>
            <span style={styles.label}>{t("apiKeyName")}</span>
            <input
              style={styles.input}
              value={name}
              maxLength={100}
              placeholder={t("apiKeyNamePlaceholder")}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label style={styles.field}>
            <span style={styles.label}>{t("apiKeyExpiry")}</span>
            <select
              style={styles.input}
              value={expiry === null ? "none" : String(expiry)}
              onChange={(e) => setExpiry(e.target.value === "none" ? null : Number(e.target.value))}
            >
              {EXPIRY_OPTIONS.map((d) => (
                <option key={String(d)} value={d === null ? "none" : String(d)}>
                  {d === null ? t("apiKeyNoExpiry") : t("apiKeyDays", { count: d })}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" style={{ ...styles.submitBtn, opacity: busy ? 0.5 : 1 }} disabled={busy}>
            {t("apiKeyCreate")}
          </button>
        </form>

        {keys.length === 0 ? (
          <p style={styles.empty}>{t("apiKeyEmpty")}</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>{t("apiKeyName")}</th>
                <th style={styles.th}>{t("apiKeyPrefix")}</th>
                <th style={styles.th}>{t("apiKeyCreatedAt")}</th>
                <th style={styles.th}>{t("apiKeyLastUsed")}</th>
                <th style={styles.th}>{t("apiKeyExpiresAt")}</th>
                <th style={styles.th}>{t("apiKeyStatus")}</th>
                <th style={styles.th} />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} style={k.status === "active" ? undefined : styles.inactiveRow}>
                  <td style={styles.td}>{k.name}</td>
                  <td style={{ ...styles.td, fontFamily: "monospace" }}>{k.prefix}…</td>
                  <td style={styles.td}>{shortTime(k.created_at)}</td>
                  <td style={styles.td}>{shortTime(k.last_used_at)}</td>
                  <td style={styles.td}>{k.expires_at ? shortTime(k.expires_at) : t("apiKeyNoExpiry")}</td>
                  <td style={styles.td}>{statusLabel(k.status)}</td>
                  <td style={styles.td}>
                    {k.status === "active" && (
                      <button
                        type="button"
                        style={styles.revokeBtn}
                        onClick={() => handleRevoke(k)}
                        aria-label={t("apiKeyRevokeLabel", { name: k.name })}
                      >
                        {t("apiKeyRevoke")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div style={styles.actions}>
          <button type="button" style={styles.cancelBtn} onClick={onClose}>{t("common:close")}</button>
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
    width: 760,
    maxWidth: "92vw",
    maxHeight: "85vh",
    overflowY: "auto",
    boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
  },
  title: { margin: "0 0 6px", fontSize: 18, fontWeight: 700 },
  help: { margin: "0 0 16px", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, whiteSpace: "pre-line" },
  createdBox: {
    border: "1px solid var(--accent)",
    borderRadius: 8,
    padding: 14,
    marginBottom: 16,
    backgroundColor: "var(--bg-input)",
  },
  createdHead: { fontWeight: 600, fontSize: 14, marginBottom: 8 },
  keyRow: { display: "flex", gap: 8, alignItems: "center" },
  keyText: {
    flex: 1,
    minWidth: 0,
    padding: "8px 10px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    fontSize: 13,
    wordBreak: "break-all",
  },
  warn: { marginTop: 8, fontSize: 12, color: "var(--text-secondary)" },
  form: { display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 },
  field: { display: "flex", flexDirection: "column", gap: 4, flex: "1 1 180px" },
  label: { fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" },
  input: {
    padding: "8px 12px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  empty: { fontSize: 13, color: "var(--text-secondary)" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "left", padding: "6px 8px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)", fontWeight: 600 },
  td: { padding: "8px", borderBottom: "1px solid var(--border-color)", verticalAlign: "middle" },
  inactiveRow: { color: "var(--text-secondary)" },
  actions: { display: "flex", justifyContent: "flex-end", marginTop: 20 },
  cancelBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 14,
    cursor: "pointer",
  },
  secondaryBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid var(--accent)",
    backgroundColor: "var(--bg-card)",
    color: "var(--accent)",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  submitBtn: {
    padding: "9px 18px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  revokeBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid var(--color-fail)",
    backgroundColor: "transparent",
    color: "var(--color-fail)",
    fontSize: 12,
    cursor: "pointer",
  },
};
