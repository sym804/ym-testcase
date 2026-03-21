import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import PasswordInput from "./PasswordInput";

export default function ChangePasswordModal() {
  const { changePassword, logout } = useAuth();
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPw.length < 8) return;
    if (newPw !== confirmPw) return;
    setLoading(true);
    try {
      await changePassword(currentPw, newPw);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "비밀번호 변경에 실패했습니다.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.wrapper}>
      <div style={s.headerBar}>
        <span style={s.brand}>TC Manager</span>
      </div>
      <div style={s.container}>
        <div style={s.card}>
          <div style={s.icon}>!</div>
          <h2 style={s.heading}>비밀번호 변경 필요</h2>
          <p style={s.desc}>
            보안을 위해 기본 비밀번호를 변경해야 합니다.
            <br />
            8자 이상의 새 비밀번호를 설정해 주세요.
          </p>
          <form onSubmit={handleSubmit} style={s.form}>
            <label style={s.label}>현재 비밀번호</label>
            <PasswordInput
              style={s.input}
              value={currentPw}
              onChange={(e) => { setCurrentPw(e.target.value); setError(""); }}
              placeholder="현재 비밀번호"
              autoFocus
            />
            <label style={s.label}>새 비밀번호</label>
            <PasswordInput
              style={s.input}
              value={newPw}
              onChange={(e) => { setNewPw(e.target.value); setError(""); }}
              placeholder="8자 이상"
            />
            <label style={s.label}>새 비밀번호 확인</label>
            <PasswordInput
              style={s.input}
              value={confirmPw}
              onChange={(e) => { setConfirmPw(e.target.value); setError(""); }}
              placeholder="새 비밀번호 재입력"
            />
            {newPw && newPw.length < 8 && (
              <div style={s.hintMsg}>8자 이상 입력해 주세요.</div>
            )}
            {newPw && confirmPw && newPw !== confirmPw && (
              <div style={s.hintMsg}>비밀번호가 일치하지 않습니다.</div>
            )}
            {error && <div style={s.errorMsg}>{error}</div>}
            <button
              type="submit"
              style={{
                ...s.submitBtn,
                opacity: !currentPw || newPw.length < 8 || newPw !== confirmPw ? 0.5 : 1,
              }}
              disabled={loading || !currentPw || newPw.length < 8 || newPw !== confirmPw}
            >
              {loading ? "변경 중..." : "비밀번호 변경"}
            </button>
          </form>
          <button style={s.logoutBtn} onClick={logout}>
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
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
    width: 420,
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
    textAlign: "center" as const,
  },
  icon: {
    width: 48,
    height: 48,
    borderRadius: "50%",
    backgroundColor: "#FEE2E2",
    color: "#DC2626",
    fontSize: 24,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 auto 16px",
  },
  heading: {
    margin: "0 0 8px",
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  desc: {
    fontSize: 13,
    color: "var(--text-secondary)",
    lineHeight: 1.6,
    margin: "0 0 24px",
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 8,
    textAlign: "left" as const,
  },
  label: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text-secondary)",
    marginTop: 4,
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
  hintMsg: {
    fontSize: 12,
    color: "#BF8700",
    marginTop: -4,
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
    marginTop: 16,
    padding: "12px 0",
    borderRadius: 8,
    border: "none",
    backgroundColor: "#2D4A7A",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  logoutBtn: {
    marginTop: 16,
    padding: "8px 16px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    backgroundColor: "transparent",
    color: "var(--text-secondary)",
    fontSize: 13,
    cursor: "pointer",
  },
};
