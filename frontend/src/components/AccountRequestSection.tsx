import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { accountRequestsApi, usersApi, type AccountRequestItem } from "../api/index";
import type { User } from "../types";

export default function AccountRequestSection() {
  const { t } = useTranslation("admin");
  const [items, setItems] = useState<AccountRequestItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [result, setResult] = useState<{ id: number; text: string; note: string } | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [reqs, us] = await Promise.all([
        accountRequestsApi.list("pending"),
        usersApi.list(),
      ]);
      setItems(reqs);
      setUsers(us);
    } catch {
      setError(t("accountRequests.failed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const approve = async (item: AccountRequestItem) => {
    const userId = picked[item.id];
    if (!userId) {
      setError(t("accountRequests.needUser"));
      return;
    }
    setError("");
    try {
      const res = await accountRequestsApi.approve(item.id, userId);
      if (res.request_type === "find_id") {
        setResult({
          id: item.id,
          text: res.username ?? "",
          note: t("accountRequests.usernameFound"),
        });
      } else {
        const until = res.code_expires_at
          ? ` (${t("accountRequests.expiresAt")}: ${new Date(res.code_expires_at).toLocaleString()})`
          : "";
        setResult({
          id: item.id,
          text: res.code ?? "",
          note: t("accountRequests.codeIssued") + until,
        });
      }
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const reject = async (item: AccountRequestItem) => {
    const reason = window.prompt(t("accountRequests.rejectReason")) ?? "";
    setError("");
    try {
      await accountRequestsApi.reject(item.id, reason);
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const label = (item: AccountRequestItem) =>
    item.request_type === "find_id"
      ? t("accountRequests.typeFindId")
      : t("accountRequests.typeResetPassword");

  const claimed = (item: AccountRequestItem) =>
    item.claimed_username ?? item.claimed_display_name ?? "";

  return (
    <section style={s.section}>
      <h3 style={s.title}>{t("accountRequests.title")}</h3>

      {result && (
        <div style={s.result}>
          <div style={s.resultNote}>{result.note}</div>
          <div style={s.resultRow}>
            <code style={s.code}>{result.text}</code>
            <button style={s.copyBtn}
                    onClick={() => void navigator.clipboard.writeText(result.text)}>
              {t("accountRequests.copy")}
            </button>
          </div>
        </div>
      )}

      {error && <div style={s.error}>{error}</div>}

      <div style={s.actions}>
        <button style={s.refreshBtn} onClick={() => void load()}>
          {t("accountRequests.refresh")}
        </button>
      </div>

      {items.length === 0 ? (
        <p style={s.empty}>{t("accountRequests.empty")}</p>
      ) : (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>{t("accountRequests.colType")}</th>
              <th style={s.th}>{t("accountRequests.colClaimed")}</th>
              <th style={s.th}>{t("accountRequests.colContact")}</th>
              <th style={s.th}>{t("accountRequests.colNote")}</th>
              <th style={s.th}>{t("accountRequests.colCreated")}</th>
              <th style={s.th}>{t("accountRequests.colActions")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td style={s.td}>{label(item)}</td>
                <td style={s.td}>{claimed(item)}</td>
                <td style={s.td}>{item.contact}</td>
                <td style={s.td}>{item.note ?? ""}</td>
                <td style={s.td}>{new Date(item.created_at).toLocaleDateString()}</td>
                <td style={s.td}>
                  <select
                    style={s.select}
                    value={picked[item.id] ?? ""}
                    onChange={(e) =>
                      setPicked((p) => ({ ...p, [item.id]: Number(e.target.value) }))
                    }
                  >
                    <option value="">{t("accountRequests.selectUser")}</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.username} ({u.display_name})
                      </option>
                    ))}
                  </select>
                  <button style={s.approveBtn} onClick={() => void approve(item)}>
                    {t("accountRequests.approve")}
                  </button>
                  <button style={s.rejectBtn} onClick={() => void reject(item)}>
                    {t("accountRequests.reject")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

const s: Record<string, React.CSSProperties> = {
  section: { marginTop: 32 },
  title: { fontSize: 16, margin: "0 0 12px" },
  actions: { marginBottom: 8 },
  refreshBtn: {
    padding: "6px 12px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 6,
    backgroundColor: "transparent",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left", padding: "8px 10px", fontWeight: 600,
    borderBottom: "1px solid var(--border-color, #E2E8F0)",
  },
  td: {
    padding: "8px 10px", verticalAlign: "top",
    borderBottom: "1px solid var(--border-color, #E2E8F0)",
  },
  select: { marginRight: 6, fontSize: 12, padding: "4px 6px" },
  approveBtn: {
    marginRight: 4, padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "none", borderRadius: 4, backgroundColor: "var(--accent, #2563EB)", color: "#fff",
  },
  rejectBtn: {
    padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 4,
    backgroundColor: "transparent",
  },
  empty: { fontSize: 13, color: "var(--text-secondary, #64748B)" },
  error: { color: "var(--danger, #DC2626)", fontSize: 12, marginBottom: 8 },
  result: {
    padding: 12, marginBottom: 12, borderRadius: 6,
    border: "1px solid var(--accent, #2563EB)",
  },
  resultNote: { fontSize: 12, marginBottom: 8 },
  resultRow: { display: "flex", alignItems: "center", gap: 8 },
  code: { fontSize: 14, fontFamily: "monospace", letterSpacing: 1 },
  copyBtn: {
    padding: "4px 10px", fontSize: 12, cursor: "pointer",
    border: "1px solid var(--border-color, #E2E8F0)", borderRadius: 4,
    backgroundColor: "transparent",
  },
};
