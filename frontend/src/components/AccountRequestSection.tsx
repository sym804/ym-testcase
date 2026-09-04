import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { accountRequestsApi, usersApi, type AccountRequestItem } from "../api/index";
import type { User } from "../types";

export default function AccountRequestSection() {
  const { t } = useTranslation("admin");
  const [items, setItems] = useState<AccountRequestItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [results, setResults] = useState<{ id: number; text: string; note: string }[]>([]);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [reqs, us] = await Promise.all([
        accountRequestsApi.list("pending"),
        usersApi.list(),
      ]);
      // await 이후에 상태를 지워야 effect 콜백 안에서 동기적으로 setState 되지 않는다
      // (eslint react-hooks 규칙 위반 방지). 성공했을 때만 지우므로 기존 에러 메시지도
      // 새로고침이 실제로 성공하기 전까지 유지된다.
      setError("");
      setItems(reqs);
      setUsers(us);
    } catch {
      setError(t("accountRequests.failed"));
    }
  }, [t]);

  useEffect(() => {
    // load 내부의 setState는 전부 await 뒤(성공 시) 또는 catch 안에서만 실행되어
    // effect 호출 시점에 동기적으로 실행되지 않는다. 하지만 react-hooks/set-state-in-effect
    // 규칙은 함수 본문을 정적으로만 훑어 await 이전/이후를 구분하지 못해 오탐이 발생하므로
    // 이 한 줄에서만 규칙을 끈다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
      const entry =
        res.request_type === "find_id"
          ? {
              id: item.id,
              text: res.username ?? "",
              note: t("accountRequests.usernameFound"),
            }
          : {
              id: item.id,
              text: res.code ?? "",
              note:
                t("accountRequests.codeIssued") +
                (res.code_expires_at
                  ? ` (${t("accountRequests.expiresAt")}: ${new Date(res.code_expires_at).toLocaleString()})`
                  : ""),
            };
      // 승인 결과는 이전 항목을 덮어쓰지 않고 누적한다. 코드는 서버에 해시로만
      // 남기 때문에, 관리자가 직접 닫기 전까지 화면에서 사라지면 영구히 잃는다.
      setResults((prev) => [...prev, entry]);
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const reject = async (item: AccountRequestItem) => {
    const reason = window.prompt(t("accountRequests.rejectReason"));
    if (reason === null) return; // 취소는 반려가 아니다
    setError("");
    try {
      await accountRequestsApi.reject(item.id, reason);
      await load();
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const copyResult = async (entry: { id: number; text: string }) => {
    try {
      await navigator.clipboard.writeText(entry.text);
      setCopiedId(entry.id);
      window.setTimeout(() => {
        setCopiedId((cur) => (cur === entry.id ? null : cur));
      }, 1500);
    } catch {
      setError(t("accountRequests.failed"));
    }
  };

  const dismissResult = (id: number) => {
    setResults((prev) => prev.filter((r) => r.id !== id));
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

      {results.length > 0 && (
        <div style={s.resultsWrap}>
          {results.map((r) => (
            <div key={r.id} style={s.result}>
              <div style={s.resultNote}>{r.note}</div>
              <div style={s.resultRow}>
                <code style={s.code}>{r.text}</code>
                <button style={s.copyBtn} onClick={() => void copyResult(r)}>
                  {copiedId === r.id ? t("accountRequests.copied") : t("accountRequests.copy")}
                </button>
                <button style={s.copyBtn} onClick={() => dismissResult(r.id)}>
                  {t("common:close")}
                </button>
              </div>
            </div>
          ))}
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
  resultsWrap: { display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 },
  result: {
    padding: 12, borderRadius: 6,
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
