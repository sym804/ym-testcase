import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { projectsApi, overviewApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import { UserRole } from "../types";
import toast from "react-hot-toast";
import Header from "../components/Header";

/** 수행 하나의 요약. 수치는 지금 남은 TC 기준이다(SYM-225). */
interface RunSummary {
  project_id: number;
  project_name: string;
  run_id: number;
  name: string;
  round: number;
  version: string | null;
  environment: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  total: number;
  /** NS 가 아닌 결과 행 */
  executed: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  progress: number;
  /** 판정(PASS/FAIL/BLOCK)이 없으면 null (SYM-133) */
  pass_rate: number | null;
}

interface ProjectRow {
  id: number;
  name: string;
  description: string | null;
  is_private: boolean;
  created_at: string;
  active_tc: number;
  in_progress: RunSummary[];
  last_completed: RunSummary | null;
}

interface OverviewData {
  summary: {
    total_projects: number;
    active_tc: number;
    in_progress_runs: number;
    in_progress_fail_block: number;
  };
  active_runs: RunSummary[];
  projects: ProjectRow[];
}

function formatPassRate(rate: number | null) {
  return rate == null ? "-" : `${rate}%`;
}

const RESULT_COLORS = {
  pass: "var(--color-pass)",
  fail: "var(--color-fail)",
  block: "var(--color-block)",
  // 테마 변수. 고정색이면 다크에서 미수행 막대가 하얗게 튀고, N/A 와 미수행이 같은 회색이 된다.
  na: "var(--color-na)",
  not_started: "var(--color-ns-accent)",
};

/** 값이 없을 때는 합격 색을 칠하지 않는다 */
function passRateColor(rate: number | null) {
  return rate == null ? "var(--text-secondary)" : RESULT_COLORS.pass;
}

/** 수행 화면을 그 수행이 열린 채로 연다(TestRunManager 가 ?run= 을 읽는다). */
function runHref(r: Pick<RunSummary, "project_id" | "run_id">) {
  return `/projects/${r.project_id}?tab=run&run=${r.run_id}`;
}

function ProgressBar({ run, noTcLabel }: { run: RunSummary; noTcLabel: string }) {
  if (run.total === 0) return <div style={s.barEmpty}>{noTcLabel}</div>;
  const segments = [
    { key: "pass", val: run.pass, color: RESULT_COLORS.pass },
    { key: "fail", val: run.fail, color: RESULT_COLORS.fail },
    { key: "block", val: run.block, color: RESULT_COLORS.block },
    { key: "na", val: run.na, color: RESULT_COLORS.na },
    { key: "ns", val: run.total - run.executed, color: RESULT_COLORS.not_started },
  ];
  return (
    <div style={s.barTrack}>
      {segments.map((seg) =>
        seg.val > 0 ? (
          <div
            key={seg.key}
            style={{ width: `${(seg.val / run.total) * 100}%`, backgroundColor: seg.color, height: "100%" }}
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
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", jira_base_url: "", is_private: false });
  const [creating, setCreating] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);

  // 프로젝트 목록과 수치를 한 번에 받는다. 따로 받으면 두 응답 사이에 프로젝트가 생기거나
  // 지워졌을 때 표와 수치가 어긋난다.
  const loadData = async () => {
    try {
      setOverview(await overviewApi.get());
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

  const fmtDate = (v: string | null | undefined) => {
    if (!v) return "-";
    const d = new Date(v);
    return isNaN(d.getTime()) ? "-" : d.toLocaleDateString(i18n.language === "ko" ? "ko-KR" : "en-US");
  };
  const runLabel = (r: RunSummary) => `${r.name} · ${t("roundN", { count: r.round })}`;
  // 응답 모양이 어긋나도(옛 서버, 부분 응답) 화면이 렌더 오류로 죽지 않게 빈 목록으로 둔다
  const projects = overview?.projects ?? [];
  const activeRuns = overview?.active_runs ?? [];

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

  const toggleSelect = (id: number) => {
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
    let failed = 0;
    for (const id of selectedIds) {
      try {
        await projectsApi.delete(id);
        deleted++;
      } catch (err) {
        failed++;
        console.error(`Failed to delete project ${id}`, err);
      }
    }
    // ★개별 실패를 로그로만 삼키고 늘 성공 토스트를 띄우면, 하나도 못 지웠는데
    //   지워진 줄 안다. 목록을 다시 받아 오므로 화면은 그대로인데 이유는 없다.
    if (failed > 0 && deleted === 0) {
      toast.error(t("deleteAllFailed", { count: failed }));
    } else if (failed > 0) {
      toast.error(t("deletePartial", { deleted, failed }));
    } else {
      toast.success(t("deleteSuccess", { count: deleted }));
    }
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
        {loading ? (
          <div style={s.loading}>{t("common:loadingData")}</div>
        ) : (
          <>
            {/* ── 요약: 개수만 센다. 서로 다른 수행을 섞어 더한 진행률 · 합격률은 뜻이 없어 뺐다 ── */}
            {sm && (
              <section style={s.section}>
                <h2 style={s.sectionTitle}>{t("overview")}</h2>
                <div style={s.summaryGrid}>
                  <div style={s.summaryCard}>
                    <div style={s.summaryLabel}>{t("totalProjects")}</div>
                    <div style={s.summaryValue}>{sm.total_projects}</div>
                  </div>
                  <div style={s.summaryCard}>
                    <div style={s.summaryLabel}>{t("activeTC")}</div>
                    <div style={s.summaryValue}>{sm.active_tc}</div>
                  </div>
                  <div style={s.summaryCard}>
                    <div style={s.summaryLabel}>{t("inProgressRuns")}</div>
                    <div style={{ ...s.summaryValue, color: "var(--accent)" }}>{sm.in_progress_runs}</div>
                  </div>
                  <div style={s.summaryCard}>
                    <div style={s.summaryLabel}>{t("inProgressFailBlock")}</div>
                    <div style={{ ...s.summaryValue, color: sm.in_progress_fail_block > 0 ? RESULT_COLORS.fail : "var(--text-primary)" }}>
                      {sm.in_progress_fail_block}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* ── 진행 중인 수행: 프로젝트를 가로질러 지금 돌고 있는 것 ── */}
            <section style={s.section}>
              <h2 style={s.sectionTitle}>{t("activeRuns")}</h2>
              {activeRuns.length === 0 ? (
                <div style={s.emptySmall}>{t("noActiveRuns")}</div>
              ) : (
                <div style={s.tableWrap}>
                  <table style={s.table} aria-label={t("activeRuns")}>
                    <thead>
                      <tr>
                        <th style={s.th}>{t("table.project")}</th>
                        <th style={s.th}>{t("table.run")}</th>
                        <th style={s.th}>{t("table.versionEnv")}</th>
                        <th style={{ ...s.th, width: 200 }}>{t("table.progress")}</th>
                        <th style={s.thNum}>{t("table.executed")}</th>
                        <th style={s.thNum}>FAIL</th>
                        <th style={s.thNum}>BLOCK</th>
                        <th style={s.thNum}>{t("table.passRate")}</th>
                        <th style={s.thNum}>{t("table.startedAt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeRuns.map((r) => (
                        <tr key={r.run_id} style={s.tr} onClick={() => navigate(runHref(r))}>
                          <td style={s.td}>{r.project_name}</td>
                          <td style={s.tdName}>
                            {/* 링크라서 키보드로도 연다. 행 클릭은 마우스용 보조 */}
                            <Link to={runHref(r)} style={s.link} onClick={(e) => e.stopPropagation()}>
                              {runLabel(r)}
                            </Link>
                          </td>
                          <td style={s.tdSub}>{[r.version, r.environment].filter(Boolean).join(" · ") || "-"}</td>
                          <td style={s.td}>
                            <div style={s.barCell}>
                              <ProgressBar run={r} noTcLabel={t("noTC")} />
                              <span style={s.barPct}>{r.progress}%</span>
                            </div>
                          </td>
                          <td style={s.tdNum}>{r.executed}/{r.total}</td>
                          <td style={{ ...s.tdNum, color: r.fail ? RESULT_COLORS.fail : undefined }}>{r.fail}</td>
                          <td style={{ ...s.tdNum, color: r.block ? RESULT_COLORS.block : undefined }}>{r.block}</td>
                          <td style={{ ...s.tdNum, color: passRateColor(r.pass_rate) }}>{formatPassRate(r.pass_rate)}</td>
                          <td style={s.tdNumSub}>{fmtDate(r.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ── 프로젝트: 카드 목록과 수치 표를 하나로 합쳤다 ── */}
            <section style={s.section}>
              <h2 style={s.sectionTitle}>{t("projects")}</h2>
              {/* 프로젝트 추가/삭제 버튼은 표 바로 위. 생성은 로그인한 누구나, 일괄 삭제는 관리자만 */}
              {user && (
                <div style={s.actions}>
                  {isAdmin && selectedIds.size > 0 && (
                    <button style={s.deleteBtn} onClick={handleBulkDelete} disabled={deleting}>
                      {deleting ? t("common:deleting") : t("deleteCount", { count: selectedIds.size })}
                    </button>
                  )}
                  <button style={s.newBtn} onClick={() => setShowModal(true)}>
                    {t("newProject")}
                  </button>
                </div>
              )}
              {projects.length === 0 ? (
                <div style={s.empty}>{t("noProjects")}</div>
              ) : (
                <div style={s.tableWrap}>
                  <table style={s.table} aria-label={t("projects")}>
                    <thead>
                      <tr>
                        {isAdmin && (
                          <th style={{ ...s.th, width: 36, textAlign: "center" }}>
                            <input
                              type="checkbox"
                              aria-label={t("common:selectAll")}
                              checked={projects.length > 0 && projects.every((p) => selectedIds.has(p.id))}
                              onChange={(e) => setSelectedIds(e.target.checked ? new Set(projects.map((p) => p.id)) : new Set())}
                              style={s.check}
                            />
                          </th>
                        )}
                        <th style={s.th}>{t("table.project")}</th>
                        <th style={s.thNum}>{t("activeTC")}</th>
                        <th style={{ ...s.th, minWidth: 220 }}>{t("table.inProgress")}</th>
                        <th style={{ ...s.th, minWidth: 220 }}>{t("table.lastCompleted")}</th>
                        <th style={s.thNum}>{t("table.createdAt")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {projects.map((p) => {
                        const cur = p.in_progress[0];
                        const last = p.last_completed;
                        return (
                          <tr
                            key={p.id}
                            style={{ ...s.tr, backgroundColor: selectedIds.has(p.id) ? "rgba(45,74,122,0.08)" : undefined }}
                            onClick={() => navigate(`/projects/${p.id}`)}
                          >
                            {isAdmin && (
                              <td style={{ ...s.td, textAlign: "center" as const }} onClick={(e) => { e.stopPropagation(); toggleSelect(p.id); }}>
                                <input type="checkbox" aria-label={t("common:selectRow")} checked={selectedIds.has(p.id)} onChange={() => {}} style={s.check} />
                              </td>
                            )}
                            <td style={s.td}>
                              <Link to={`/projects/${p.id}`} style={{ ...s.link, fontWeight: 600 }} onClick={(e) => e.stopPropagation()}>
                                {p.name}
                              </Link>
                              <div style={s.desc}>{p.description || t("noDescription")}</div>
                            </td>
                            <td style={s.tdNum}>{p.active_tc}</td>
                            <td style={s.td}>
                              {cur ? (
                                <>
                                  <Link to={runHref(cur)} style={s.runLink} onClick={(e) => e.stopPropagation()}>
                                    {runLabel(cur)}
                                  </Link>
                                  {p.in_progress.length > 1 && (
                                    <span style={s.more}>{t("moreRuns", { count: p.in_progress.length - 1 })}</span>
                                  )}
                                  <div style={s.barCell}>
                                    <ProgressBar run={cur} noTcLabel={t("noTC")} />
                                    <span style={s.barPct}>{cur.progress}%</span>
                                  </div>
                                </>
                              ) : (
                                <span style={s.none}>{t("noRun")}</span>
                              )}
                            </td>
                            <td style={s.td}>
                              {last ? (
                                <>
                                  <Link to={runHref(last)} style={s.runLink} onClick={(e) => e.stopPropagation()}>
                                    {runLabel(last)}
                                  </Link>
                                  <div style={s.lastRow}>
                                    <span style={{ color: passRateColor(last.pass_rate), fontWeight: 700 }}>{formatPassRate(last.pass_rate)}</span>
                                    <span style={{ color: last.fail ? RESULT_COLORS.fail : undefined }}>FAIL {last.fail}</span>
                                    <span>{fmtDate(last.completed_at)}</span>
                                  </div>
                                </>
                              ) : (
                                <span style={s.none}>{t("noRun")}</span>
                              )}
                            </td>
                            <td style={s.tdNumSub}>{fmtDate(p.created_at)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
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

const cell: React.CSSProperties = { padding: "10px 12px", borderBottom: "1px solid var(--border-color)", verticalAlign: "top" };
const head: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: "2px solid var(--border-color)",
  color: "var(--text-secondary)",
  fontWeight: 600,
  whiteSpace: "nowrap",
  fontSize: 12,
};

const s: Record<string, React.CSSProperties> = {
  container: { maxWidth: 1200, margin: "0 auto", padding: "24px 24px 48px" },
  section: { marginBottom: 32 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 16px" },

  /* Summary cards */
  summaryGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 },
  summaryCard: { backgroundColor: "var(--bg-card)", borderRadius: 10, padding: "16px 18px", boxShadow: "var(--shadow)" },
  summaryLabel: { fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 },
  summaryValue: { fontSize: 26, fontWeight: 700, color: "var(--text-primary)" },

  /* Progress bar */
  barTrack: { display: "flex", height: 10, borderRadius: 5, overflow: "hidden", backgroundColor: "var(--border-color)", flex: 1, minWidth: 80 },
  barEmpty: { fontSize: 12, color: "var(--text-secondary)" },
  barCell: { display: "flex", alignItems: "center", gap: 8, marginTop: 4 },
  barPct: { fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" },

  /* Tables */
  tableWrap: { backgroundColor: "var(--bg-card)", borderRadius: 10, boxShadow: "var(--shadow)", overflow: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: head,
  thNum: { ...head, textAlign: "right", width: 60 },
  tr: { cursor: "pointer" },
  td: cell,
  tdName: { ...cell, fontWeight: 600 },
  tdSub: { ...cell, color: "var(--text-secondary)", whiteSpace: "nowrap" },
  tdNum: { ...cell, textAlign: "right", fontWeight: 600, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" },
  tdNumSub: { ...cell, textAlign: "right", color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" },
  link: { color: "var(--accent)", textDecoration: "none" },
  runLink: { color: "var(--text-primary)", textDecoration: "none", fontWeight: 600 },
  desc: { fontSize: 12, color: "var(--text-secondary)", marginTop: 2, maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  more: { fontSize: 12, color: "var(--text-secondary)", marginLeft: 6 },
  none: { color: "var(--text-secondary)" },
  lastRow: { display: "flex", gap: 10, marginTop: 4, fontSize: 12, color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" },
  check: { width: 15, height: 15, cursor: "pointer" },

  actions: { display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 8 },
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
  loading: { textAlign: "center", color: "var(--text-secondary)", padding: 60, fontSize: 16 },
  empty: { textAlign: "center", color: "var(--text-secondary)", padding: 60, fontSize: 16 },
  emptySmall: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    boxShadow: "var(--shadow)",
    color: "var(--text-secondary)",
    padding: "18px 20px",
    fontSize: 14,
  },

  /* Modal */
  overlay: {
    position: "fixed",
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
  modalForm: { display: "flex", flexDirection: "column", gap: 8 },
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
