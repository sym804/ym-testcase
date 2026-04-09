import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useEffect, useRef, useState } from "react";
import { projectsApi, searchApi, authApi } from "../api";
import PasswordInput from "./PasswordInput";
import type { Project, TestCase } from "../types";
import { UserRole } from "../types";
import toast from "react-hot-toast";
import { translateError } from "../utils/errorMessage";

export default function Header() {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation("header");
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const toggleLang = () => {
    const next = i18n.language === "ko" ? "en" : "ko";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  };
  const location = useLocation();
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(null);

  // Extract project ID from URL
  const projectMatch = location.pathname.match(/^\/projects\/(\d+)/);
  const urlProjectId = projectMatch ? parseInt(projectMatch[1]) : null;

  useEffect(() => {
    if (user) {
      projectsApi.list().then(setProjects).catch(() => {});
    }
  }, [user]);

  useEffect(() => {
    setCurrentProjectId(urlProjectId);
  }, [urlProjectId]);

  // Global search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<TestCase[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // User menu dropdown
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showChangePw, setShowChangePw] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const handleSearch = (q: string) => {
    setSearchQuery(q);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (q.length < 2) { setSearchResults([]); setShowSearch(false); return; }
    searchTimer.current = setTimeout(async () => {
      try {
        const data = await searchApi.global(q);
        setSearchResults(data);
        setShowSearch(true);
      } catch (err) { console.warn("search error", err); }
    }, 300);
  };

  // 검색 타이머 cleanup (#4)
  useEffect(() => {
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const highlight = (text: string, query: string) => {
    if (!query || query.length < 2) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const parts = text.split(new RegExp(`(${escaped})`, "gi"));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase()
        ? <mark key={i} style={{ backgroundColor: "var(--bg-warning-light)", color: "var(--text-warning)", padding: "0 1px", borderRadius: 2 }}>{part}</mark>
        : part
    );
  };

  if (!user) return null;

  const roleBadgeColor: Record<string, string> = {
    admin: "var(--color-fail)",
    qa_manager: "var(--color-block)",
    user: "#6B7280",
  };

  const roleLabelMap: Record<string, string> = {
    admin: t("role.admin"),
    qa_manager: t("role.qaManager"),
    user: t("role.user"),
  };

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <span
          role="button"
          tabIndex={0}
          style={styles.title}
          onClick={() => navigate("/projects")}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate("/projects"); } }}
        >
          YM TestCase
        </span>
      </div>

      <div style={styles.center}>
        {projects.length > 0 && (
          <select
            style={styles.projectSelect}
            value={currentProjectId ?? ""}
            onChange={(e) => {
              const id = e.target.value;
              if (id) navigate(`/projects/${id}`);
            }}
          >
            <option value="">{t("projectSelect")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
        <div style={{ position: "relative", marginLeft: 12 }} ref={searchRef}>
          <input
            style={styles.searchInput}
            type="text"
            placeholder={t("searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowSearch(true)}
          />
          {showSearch && searchResults.length > 0 && (
            <div style={styles.searchDropdown}>
              {searchResults.slice(0, 15).map((tc) => (
                <div
                  key={tc.id}
                  role="button"
                  tabIndex={0}
                  style={styles.searchItem}
                  onClick={() => {
                    navigate(`/projects/${tc.project_id}?tab=tc&highlight=${encodeURIComponent(tc.tc_id)}`);
                    setShowSearch(false);
                    setSearchQuery("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigate(`/projects/${tc.project_id}?tab=tc&highlight=${encodeURIComponent(tc.tc_id)}`);
                      setShowSearch(false);
                      setSearchQuery("");
                    }
                  }}
                >
                  <span style={styles.searchTcId}>{highlight(tc.tc_id, searchQuery)}</span>
                  <span style={styles.searchText}>{highlight(`${tc.depth1 || ""}${tc.depth2 ? ` > ${tc.depth2}` : ""}`, searchQuery)}</span>
                </div>
              ))}
              {searchResults.length > 15 && (
                <div style={{ padding: "6px 12px", fontSize: 11, color: "#94A3B8" }}>
                  {t("moreResults", { count: searchResults.length - 15 })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div style={styles.right}>
        <button style={styles.themeBtn} onClick={toggleTheme} title={theme === "light" ? t("darkMode") : t("lightMode")}>
          {theme === "light" ? "\u{1F319}" : "\u{2600}\u{FE0F}"}
        </button>
        <button onClick={toggleLang} title={i18n.language === "ko" ? "Switch to English" : "Switch to Korean"}
          style={styles.adminBtn}>
          {i18n.language === "ko" ? "EN" : "KO"}
        </button>
        <button style={styles.adminBtn} onClick={() => navigate("/manual")}>
          {t("help")}
        </button>
        {(user.role === UserRole.ADMIN || user.role === UserRole.QA_MANAGER) && (
          <button style={styles.adminBtn} onClick={() => navigate("/admin-manual")}>
            {t("adminManual")}
          </button>
        )}
        {user.role === UserRole.ADMIN && (
          <button style={styles.adminBtn} onClick={() => navigate("/admin")}>
            {t("admin")}
          </button>
        )}
        <div style={{ position: "relative" }} ref={userMenuRef}>
          <button
            style={styles.userBtn}
            onClick={() => setShowUserMenu((v) => !v)}
          >
            <span style={styles.userName}>{user.display_name}</span>
            <span
              style={{
                ...styles.roleBadge,
                backgroundColor: roleBadgeColor[user.role] || "#6B7280",
              }}
            >
              {roleLabelMap[user.role] || user.role.toUpperCase()}
            </span>
            <span style={{ fontSize: 10, marginLeft: 4, color: "#94A3B8" }}>&#9662;</span>
          </button>
          {showUserMenu && (
            <div style={styles.userDropdown}>
              <button
                style={styles.userMenuItem}
                onClick={() => { setShowUserMenu(false); setShowChangePw(true); }}
              >
                {t("changePassword")}
              </button>
              <button
                style={{ ...styles.userMenuItem, color: "var(--color-fail)" }}
                onClick={() => { setShowUserMenu(false); logout(); }}
              >
                {t("logout")}
              </button>
            </div>
          )}
        </div>
        {showChangePw && (
          <ChangePasswordInline onClose={() => setShowChangePw(false)} />
        )}
      </div>
    </header>
  );
}

function ChangePasswordInline({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("header");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const valid = currentPw && newPw.length >= 8 && newPw === confirmPw;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!valid) return;
    setLoading(true);
    try {
      await authApi.changePassword(currentPw, newPw);
      toast.success(t("passwordChanged"));
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ? translateError(detail) : t("passwordChangeFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={modalStyles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 style={modalStyles.title}>{t("changePasswordTitle")}</h3>
        <form onSubmit={handleSubmit} style={modalStyles.form}>
          <label style={modalStyles.label}>{t("currentPassword")}</label>
          <PasswordInput style={modalStyles.input} value={currentPw} onChange={(e) => { setCurrentPw(e.target.value); setError(""); }} autoFocus />
          <label style={modalStyles.label}>{t("newPassword")}</label>
          <PasswordInput style={modalStyles.input} value={newPw} onChange={(e) => { setNewPw(e.target.value); setError(""); }} placeholder={t("newPasswordPlaceholder")} />
          <label style={modalStyles.label}>{t("newPasswordConfirm")}</label>
          <PasswordInput style={modalStyles.input} value={confirmPw} onChange={(e) => { setConfirmPw(e.target.value); setError(""); }} />
          {newPw && newPw.length < 8 && <div style={modalStyles.hint}>{t("minLengthHint")}</div>}
          {newPw && confirmPw && newPw !== confirmPw && <div style={modalStyles.hint}>{t("passwordMismatch")}</div>}
          {error && <div style={modalStyles.errorMsg}>{error}</div>}
          <div style={modalStyles.buttons}>
            <button type="button" style={modalStyles.cancelBtn} onClick={onClose}>{t("common:cancel")}</button>
            <button type="submit" style={{ ...modalStyles.submitBtn, opacity: valid ? 1 : 0.4 }} disabled={!valid || loading}>
              {loading ? t("changing") : t("change")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const modalStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)", display: "flex",
    justifyContent: "center", alignItems: "center", zIndex: 1000,
  },
  modal: {
    backgroundColor: "var(--bg-card)", borderRadius: 12,
    padding: "28px 32px", width: 380, boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
  },
  title: { margin: "0 0 20px", fontSize: 18, fontWeight: 700, color: "var(--text-primary)" },
  form: { display: "flex", flexDirection: "column" as const, gap: 8 },
  label: { fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginTop: 4 },
  input: {
    padding: "9px 12px", borderRadius: 6, border: "1px solid var(--border-input)",
    fontSize: 14, outline: "none", backgroundColor: "var(--bg-input)", color: "var(--text-primary)",
  },
  hint: { fontSize: 12, color: "var(--color-block)", marginTop: -4 },
  errorMsg: {
    marginTop: 4, padding: "8px 12px", borderRadius: 6,
    backgroundColor: "rgba(220,38,38,0.08)", color: "#DC2626", fontSize: 13,
  },
  buttons: { display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" },
  cancelBtn: {
    padding: "8px 16px", borderRadius: 6, border: "1px solid var(--border-input)",
    backgroundColor: "transparent", color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
  },
  submitBtn: {
    padding: "8px 20px", borderRadius: 6, border: "none",
    backgroundColor: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
  },
};

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    height: 52,
    padding: "0 24px",
    backgroundColor: "var(--bg-header)",
    color: "var(--text-header)",
    position: "sticky",
    top: 0,
    zIndex: 100,
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  left: {
    display: "flex",
    alignItems: "center",
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    letterSpacing: "-0.5px",
    cursor: "pointer",
    color: "var(--text-header)",
  },
  center: {
    display: "flex",
    alignItems: "center",
  },
  projectSelect: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-header)",
    backgroundColor: "var(--bg-header-input)",
    color: "var(--text-header)",
    fontSize: 13,
    minWidth: 200,
    outline: "none",
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  userName: {
    fontSize: 14,
    color: "var(--text-header-secondary)",
  },
  roleBadge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 4,
    color: "#fff",
  },
  adminBtn: {
    padding: "5px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-header)",
    backgroundColor: "transparent",
    color: "var(--text-header-secondary)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  themeBtn: {
    padding: "4px 8px",
    borderRadius: 6,
    border: "1px solid var(--border-header)",
    backgroundColor: "transparent",
    fontSize: 16,
    cursor: "pointer",
    lineHeight: 1,
  },
  userBtn: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "5px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-header)",
    backgroundColor: "transparent",
    cursor: "pointer",
  },
  userDropdown: {
    position: "absolute" as const,
    top: "100%",
    right: 0,
    marginTop: 6,
    minWidth: 150,
    backgroundColor: "var(--bg-card)",
    borderRadius: 8,
    boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
    zIndex: 300,
    overflow: "hidden",
  },
  userMenuItem: {
    display: "block",
    width: "100%",
    padding: "10px 16px",
    border: "none",
    backgroundColor: "transparent",
    color: "var(--text-primary)",
    fontSize: 13,
    textAlign: "left" as const,
    cursor: "pointer",
  },
  searchInput: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-header)",
    backgroundColor: "var(--bg-header-input)",
    color: "var(--text-header)",
    fontSize: 13,
    width: 200,
    outline: "none",
  },
  searchDropdown: {
    position: "absolute" as const,
    top: "100%",
    left: 0,
    marginTop: 4,
    width: 360,
    maxHeight: 400,
    overflow: "auto",
    backgroundColor: "var(--bg-card)",
    borderRadius: 8,
    boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
    zIndex: 300,
  },
  searchItem: {
    padding: "8px 12px",
    cursor: "pointer",
    borderBottom: "1px solid var(--border-color)",
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  searchTcId: {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--color-link)",
    whiteSpace: "nowrap" as const,
  },
  searchText: {
    fontSize: 12,
    color: "var(--text-secondary)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
};
