import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { projectsApi, overviewApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import type { Project } from "../types";
import { UserRole } from "../types";
import toast from "react-hot-toast";
import Header from "../components/Header";

interface ProjectSummary {
  id: number;
  name: string;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
  progress: number;
  pass_rate: number;
}

interface OverviewData {
  summary: {
    total_projects: number;
    total_tc: number;
    pass: number;
    fail: number;
    block: number;
    na: number;
    not_started: number;
    progress: number;
    pass_rate: number;
  };
  projects: ProjectSummary[];
}

const RESULT_COLORS = {
  pass: "var(--color-pass)",
  fail: "var(--color-fail)",
  block: "var(--color-block)",
  na: "#6B7280",
  not_started: "#D1D5DB",
};

function ProgressBar({ data, noTcLabel }: { data: { pass: number; fail: number; block: number; na: number; not_started: number; total: number }; noTcLabel?: string }) {
  if (data.total === 0) return <div style={s.barEmpty}>{noTcLabel || "No TC"}</div>;
  const segments = [
    { key: "pass", val: data.pass, color: RESULT_COLORS.pass },
    { key: "fail", val: data.fail, color: RESULT_COLORS.fail },
    { key: "block", val: data.block, color: RESULT_COLORS.block },
    { key: "na", val: data.na, color: RESULT_COLORS.na },
    { key: "ns", val: data.not_started, color: RESULT_COLORS.not_started },
  ];
  return (
    <div style={s.barTrack}>
      {segments.map((seg) =>
        seg.val > 0 ? (
          <div
            key={seg.key}
            style={{
              width: `${(seg.val / data.total) * 100}%`,
              backgroundColor: seg.color,
              height: "100%",
              transition: "width 0.3s",
            }}
            title={`${seg.key.toUpperCase()}: ${seg.val}`}
          />
        ) : null
      )}
    </div>
  );
}

export default function ProjectListPage() {
  const { user } = useAuth();
  const { t, i18n } = useTranslation("project");
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", jira_base_url: "", is_private: false });
  const [creating, setCreating] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const loadData = async () => {
    try {
      const [projList, ov] = await Promise.all([
        projectsApi.list(),
        overviewApi.get(),
      ]);
      setProjects(projList);
      setOverview(ov);
    } catch (err) {
      console.error(err);
      toast.error(t("loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error(t("nameRequired"));
      return;
    }
    if (form.name.trim().length > 100) {
      toast.error(t("nameMaxLength"));
      return;
    }
    setCreating(true);
    try {
      await projectsApi.create(form);
      toast.success(t("createSuccess"));
      setShowModal(false);
      setForm({ name: "", description: "", jira_base_url: "", is_private: false });
      loadData();
    } catch (err) {
      console.error(err);
      toast.error(t("createFailed"));
    } finally {
      setCreating(false);
    }
  };

  const toggleSelect = (id: number, e?: { stopPropagation?: () => void }) => {
    e?.stopPropagation?.();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    const names = projects.filter((p) => selectedIds.has(p.id)).map((p) => p.name);
    if (!confirm(t("deleteConfirm", { count: names.length, names: names.join("\n") }))) return;
    setDeleting(true);
    let deleted = 0;
    for (const id of selectedIds) {
      try {
        await projectsApi.delete(id);
        deleted++;
      } catch (err) {
        console.error(`Failed to delete project ${id}`, err);
      }
    }
    toast.success(t("deleteSuccess", { count: deleted }));
    setSelectedIds(new Set());
    setDeleting(false);
    loadData();
  };

  const isAdmin = user?.role === UserRole.ADMIN || user?.role === UserRole.QA_MANAGER;
  const sm = overview?.summary;

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
      <Header />
      <div style={s.container}>

        {/* ── 전체 대시보드 ── */}
        {!loading && sm && (
          <section style={s.section}>
            <h2 style={s.sectionTitle}>{t("overview")}</h2>

            {/* Summary cards */}
            <div style={s.summaryGrid}>
              <div style={s.summaryCard}>
                <div style={s.summaryLabel}>{t("totalProjects")}</div>
                <div style={s.summaryValue}>{sm.total_projects}</div>
              </div>
              <div style={s.summaryCard}>
                <div style={s.summaryLabel}>{t("totalTC")}</div>
                <div style={s.summaryValue}>{sm.total_tc}</div>
              </div>
              <div style={s.summaryCard}>
                <div style={s.summaryLabel}>{t("progress")}</div>
                <div style={{ ...s.summaryValue, color: "var(--accent)" }}>{sm.progress}%</div>
              </div>
              <div style={s.summaryCard}>
                <div style={s.summaryLabel}>{t("passRate")}</div>
                <div style={{ ...s.summaryValue, color: RESULT_COLORS.pass }}>{sm.pass_rate}%</div>
              </div>
            </div>

            {/* Overall bar */}
            <div style={s.overallBar}>
              <div style={s.barLabelRow}>
                <span style={{ ...s.legend, color: RESULT_COLORS.pass }}>PASS {sm.pass}</span>
                <span style={{ ...s.legend, color: RESULT_COLORS.fail }}>FAIL {sm.fail}</span>
                <span style={{ ...s.legend, color: RESULT_COLORS.block }}>BLOCK {sm.block}</span>
                <span style={{ ...s.legend, color: RESULT_COLORS.na }}>N/A {sm.na}</span>
                <span style={{ ...s.legend, color: "#94A3B8" }}>{t("notStarted")} {sm.not_started}</span>
              </div>
              <ProgressBar data={{ ...sm, total: sm.total_tc }} noTcLabel={t("noTC")} />
            </div>

            {/* 프로젝트 추가/삭제 버튼 */}
            {isAdmin && (
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 8 }}>
                {selectedIds.size > 0 && (
                  <button style={s.deleteBtn} onClick={handleBulkDelete} disabled={deleting}>
                    {deleting ? t("common:deleting") : t("deleteCount", { count: selectedIds.size })}
                  </button>
                )}
                <button style={s.newBtn} onClick={() => setShowModal(true)}>
                  {t("newProject")}
                </button>
              </div>
            )}

            {/* Per-project table */}
            {overview.projects.length > 0 && (
              <>
              <div style={s.tableWrap}>
                <table style={s.table}>
                  <thead>
                    <tr>
                      {isAdmin && (
                        <th style={{ ...s.th, width: 36, textAlign: "center" }}>
                          <input
                            type="checkbox"
                            checked={overview.projects.length > 0 && overview.projects.every((p) => selectedIds.has(p.id))}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedIds(new Set(overview.projects.map((p) => p.id)));
                              } else {
                                setSelectedIds(new Set());
                              }
                            }}
                            style={{ width: 15, height: 15, cursor: "pointer" }}
                          />
                        </th>
                      )}
                      <th style={s.th}>{t("table.project")}</th>
                      <th style={{ ...s.th, ...s.thNum }}>TC</th>
                      <th style={{ ...s.th, ...s.thNum }}>PASS</th>
                      <th style={{ ...s.th, ...s.thNum }}>FAIL</th>
                      <th style={{ ...s.th, ...s.thNum }}>BLOCK</th>
                      <th style={{ ...s.th, ...s.thNum }}>N/A</th>
                      <th style={{ ...s.th, ...s.thNum }}>{t("notStarted")}</th>
                      <th style={{ ...s.th, width: 200 }}>{t("table.progress")}</th>
                      <th style={{ ...s.th, ...s.thNum }}>Pass Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.projects.map((p) => (
                      <tr
                        key={p.id}
                        style={{
                          ...s.tr,
                          backgroundColor: selectedIds.has(p.id) ? "rgba(45,74,122,0.08)" : undefined,
                        }}
                        onClick={() => navigate(`/projects/${p.id}`)}
                      >
                        {isAdmin && (
                          <td style={{ ...s.td, textAlign: "center" as const }} onClick={(e) => { e.stopPropagation(); toggleSelect(p.id, e); }}>
                            <input
                              type="checkbox"
                              checked={selectedIds.has(p.id)}
                              onChange={(e) => { e.stopPropagation(); toggleSelect(p.id); }}
                              style={{ width: 15, height: 15, cursor: "pointer" }}
                            />
                          </td>
                        )}
                        <td style={s.tdName}>{p.name}</td>
                        <td style={s.tdNum}>{p.total}</td>
                        <td style={{ ...s.tdNum, color: RESULT_COLORS.pass }}>{p.pass}</td>
                        <td style={{ ...s.tdNum, color: RESULT_COLORS.fail }}>{p.fail}</td>
                        <td style={{ ...s.tdNum, color: RESULT_COLORS.block }}>{p.block}</td>
                        <td style={{ ...s.tdNum, color: RESULT_COLORS.na }}>{p.na}</td>
                        <td style={s.tdNum}>{p.not_started}</td>
                        <td style={s.td}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <ProgressBar data={p} noTcLabel={t("noTC")} />
                            <span style={{ fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>{p.progress}%</span>
                          </div>
                        </td>
                        <td style={{ ...s.tdNum, color: RESULT_COLORS.pass, fontWeight: 700 }}>
                          {p.pass_rate}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </>
            )}
          </section>
        )}

        {/* ── 프로젝트 목록 ── */}
        <section style={s.section}>
          <h2 style={{ ...s.sectionTitle, marginBottom: 16 }}>{t("projects")}</h2>

          {loading ? (
            <div style={s.loading}>{t("common:loadingData")}</div>
          ) : projects.length === 0 ? (
            <div style={s.empty}>{t("noProjects")}</div>
          ) : (
            <div style={s.grid}>
              {projects.map((p) => {
                const ps = overview?.projects.find((x) => x.id === p.id);
                return (
                  <div
                    key={p.id}
                    role="button"
                    tabIndex={0}
                    style={s.card}
                    onClick={() => navigate(`/projects/${p.id}`)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate(`/projects/${p.id}`); } }}
                    onMouseEnter={(e) => {
                      const el = e.currentTarget as HTMLDivElement;
                      el.style.borderTopColor = "var(--accent)";
                      el.style.borderLeftColor = "var(--accent)";
                      el.style.borderRightColor = "var(--accent)";
                      el.style.borderBottomColor = "var(--accent)";
                    }}
                    onMouseLeave={(e) => {
                      const el = e.currentTarget as HTMLDivElement;
                      el.style.borderTopColor = "";
                      el.style.borderLeftColor = "";
                      el.style.borderRightColor = "";
                      el.style.borderBottomColor = "";
                    }}
                  >
                    <div style={s.cardAccent} />
                    <h3 style={s.cardTitle}>{p.name}</h3>
                    <p style={s.cardDesc}>{p.description || t("noDescription")}</p>
                    {ps && (
                      <div style={s.cardStats}>
                        <ProgressBar data={ps} noTcLabel={t("noTC")} />
                        <div style={s.cardStatRow}>
                          <span>TC {ps.total}</span>
                          <span style={{ color: RESULT_COLORS.pass }}>P {ps.pass}</span>
                          <span style={{ color: RESULT_COLORS.fail }}>F {ps.fail}</span>
                          <span style={{ color: "#64748B" }}>{ps.progress}%</span>
                        </div>
                      </div>
                    )}
                    <div style={s.cardDate}>
                      {(() => {
                        const d = new Date(p.created_at);
                        return isNaN(d.getTime()) ? "-" : d.toLocaleDateString(i18n.language === "ko" ? "ko-KR" : "en-US");
                      })()}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Create Modal */}
      {showModal && (
        <div style={s.overlay} onClick={() => setShowModal(false)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={s.modalTitle}>{t("createProject")}</h2>
            <form onSubmit={handleCreate} style={s.modalForm}>
              <label style={s.label}>{t("projectName")}</label>
              <input
                style={s.input}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t("projectNamePlaceholder")}
                autoFocus
              />
              <label style={s.label}>{t("description")}</label>
              <textarea
                style={{ ...s.input, minHeight: 80, resize: "vertical" as const }}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder={t("descriptionPlaceholder")}
              />
              <label style={s.label}>{t("jiraBaseUrl")}</label>
              <input
                style={s.input}
                value={form.jira_base_url}
                onChange={(e) => setForm({ ...form, jira_base_url: e.target.value })}
                placeholder={t("jiraBaseUrlPlaceholder")}
              />
              <label style={{ ...s.label, display: "flex", alignItems: "center", gap: 8, marginTop: 16 }}>
                <input
                  type="checkbox"
                  checked={form.is_private}
                  onChange={(e) => setForm({ ...form, is_private: e.target.checked })}
                  style={{ width: 16, height: 16 }}
                />
                {t("privateProject")}
              </label>
              <div style={s.modalActions}>
                <button
                  type="button"
                  style={s.cancelBtn}
                  onClick={() => setShowModal(false)}
                >
                  {t("common:cancel")}
                </button>
                <button type="submit" style={s.submitBtn} disabled={creating}>
                  {creating ? t("common:creating") : t("common:create")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { maxWidth: 1200, margin: "0 auto", padding: "24px 24px 48px" },
  section: { marginBottom: 36 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 16px" },

  /* Summary cards */
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 14,
    marginBottom: 16,
  },
  summaryCard: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    padding: "16px 18px",
    boxShadow: "var(--shadow)",
  },
  summaryLabel: { fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 },
  summaryValue: { fontSize: 26, fontWeight: 700, color: "var(--text-primary)" },

  /* Overall bar */
  overallBar: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    padding: "14px 18px",
    boxShadow: "var(--shadow)",
    marginBottom: 16,
  },
  barLabelRow: {
    display: "flex",
    gap: 16,
    marginBottom: 8,
    fontSize: 12,
    fontWeight: 600,
  },
  legend: { fontWeight: 600 },
  barTrack: {
    display: "flex",
    height: 10,
    borderRadius: 5,
    overflow: "hidden",
    backgroundColor: "var(--border-color)",
  },
  barEmpty: { fontSize: 12, color: "#94A3B8" },

  /* Table */
  tableWrap: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    boxShadow: "var(--shadow)",
    overflow: "auto",
  },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    fontSize: 12,
  },
  thNum: {
    textAlign: "right" as const,
    padding: "10px 12px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    fontSize: 12,
    width: 60,
  },
  tr: { cursor: "pointer" },
  td: { padding: "10px 12px", borderBottom: "1px solid var(--border-color)" },
  tdName: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--border-color)",
    fontWeight: 600,
    color: "var(--accent)",
  },
  tdNum: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--border-color)",
    textAlign: "right" as const,
    fontWeight: 600,
    fontVariantNumeric: "tabular-nums",
  },

  /* Project cards */
  topRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  newBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  deleteBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "1px solid #DC2626",
    backgroundColor: "transparent",
    color: "#DC2626",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  loading: { textAlign: "center" as const, color: "var(--text-secondary)", padding: 60, fontSize: 16 },
  empty: { textAlign: "center" as const, color: "var(--text-secondary)", padding: 60, fontSize: 16 },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
    gap: 16,
  },
  card: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    borderTop: "1px solid var(--border-color)",
    borderLeft: "1px solid var(--border-color)",
    borderRight: "1px solid var(--border-color)",
    borderBottom: "1px solid var(--border-color)",
    padding: "0 20px 18px",
    cursor: "pointer",
    transition: "border-color 0.15s",
    overflow: "hidden",
  },
  cardAccent: {
    height: 4,
    backgroundColor: "var(--accent)",
    margin: "0 -20px",
    marginBottom: 16,
  },
  cardTitle: { fontSize: 16, fontWeight: 600, color: "var(--text-primary)", margin: "0 0 4px" },
  cardDesc: { fontSize: 13, color: "var(--text-secondary)", margin: "0 0 12px", lineHeight: 1.5 },
  cardStats: { marginBottom: 10 },
  cardStatRow: {
    display: "flex",
    gap: 10,
    marginTop: 6,
    fontSize: 11,
    fontWeight: 600,
    color: "#94A3B8",
  },
  cardDate: { fontSize: 11, color: "#94A3B8" },

  /* Modal */
  overlay: {
    position: "fixed" as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 200,
  },
  modal: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: "32px",
    width: 460,
    maxWidth: "90vw",
    boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
  },
  modalTitle: { margin: "0 0 24px", fontSize: 20, fontWeight: 700, color: "var(--text-primary)" },
  modalForm: { display: "flex", flexDirection: "column" as const, gap: 8 },
  label: { fontSize: 14, fontWeight: 600, color: "var(--text-primary)", marginTop: 8 },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  modalActions: { display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 20 },
  cancelBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 14,
    cursor: "pointer",
  },
  submitBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
};
