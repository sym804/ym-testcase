import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { reportsApi, testRunsApi } from "../api";
import type { ReportBreakdownRow, ReportData, TestRun } from "../types";
import { resolveIssueUrl } from "../utils/issueLink";
import toast from "react-hot-toast";

const RESULT_COLOR: Record<string, string> = {
  PASS: "var(--color-pass)",
  FAIL: "var(--color-fail)",
  BLOCK: "var(--color-block)",
};

function formatRate(rate: number | null | undefined) {
  return rate == null ? "-" : `${rate.toFixed(1)}%`;
}

function formatDuration(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** 파일을 저장시킨다. revoke 를 바로 부르면 일부 브라우저에서 다운로드가 끊겨 한 박자 미룬다. */
function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

interface Props {
  projectId: number;
}

export default function ReportView({ projectId }: Props) {
  const { t, i18n } = useTranslation("report");
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    testRunsApi
      .list(projectId)
      .then((data) => {
        setRuns(data);
        if (data.length > 0) setSelectedRunId(data[0].id);
      })
      .catch(() => toast.error(t("runLoadFailed")));
  }, [projectId]);

  const loadReport = useCallback(async () => {
    if (!selectedRunId) return;
    setLoading(true);
    try {
      const data = await reportsApi.getData(projectId, selectedRunId);
      setReport(data);
    } catch (err) {
      console.error(err);
      toast.error(t("loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedRunId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const handleDownloadPdf = async () => {
    if (!selectedRunId) return;
    try {
      const { blob, filename } = await reportsApi.downloadPdf(projectId, selectedRunId);
      saveBlob(blob, filename ?? `report_${selectedRunId}.pdf`);
    } catch (err) {
      console.error(err);
      toast.error(t("pdfFailed"));
    }
  };

  const handleDownloadExcel = async () => {
    if (!selectedRunId) return;
    try {
      const { blob, filename } = await reportsApi.downloadExcel(projectId, selectedRunId);
      saveBlob(blob, filename ?? `report_${selectedRunId}.xlsx`);
    } catch (err) {
      console.error(err);
      toast.error(t("excelFailed"));
    }
  };

  const locale = i18n.language === "ko" ? "ko-KR" : "en-US";
  const formatDate = (iso: string | null | undefined) =>
    iso ? new Date(iso).toLocaleDateString(locale) : "-";

  // testid 는 `{kind}-na-{이름}` 모양이다. 기존 테스트가 category-na-인증 으로 찾는다.
  const breakdownCells = (row: ReportBreakdownRow, kind: string, name: string) => (
    <>
      <td style={styles.tdNum}>{row.total}</td>
      <td style={{ ...styles.tdNum, color: "var(--color-pass)" }}>{row.pass}</td>
      <td style={{ ...styles.tdNum, color: "var(--color-fail)" }}>{row.fail}</td>
      <td style={{ ...styles.tdNum, color: "var(--color-block)" }}>{row.block}</td>
      <td data-testid={`${kind}-na-${name}`} style={{ ...styles.tdNum, color: "var(--color-na)" }}>{row.na}</td>
      <td data-testid={`${kind}-ns-${name}`} style={{ ...styles.tdNum, color: "var(--color-ns)" }}>{row.not_started}</td>
      <td data-testid={`${kind}-rate-${name}`} style={styles.tdNum}>{formatRate(row.pass_rate)}</td>
    </>
  );

  const breakdownHeaders = (
    <>
      <th style={styles.thNum}>Total</th>
      <th style={styles.thNum}>PASS</th>
      <th style={styles.thNum}>FAIL</th>
      <th style={styles.thNum}>BLOCK</th>
      <th style={styles.thNum}>N/A</th>
      <th style={styles.thNum}>{t("notStarted")}</th>
      <th style={styles.thNum}>{t("passRate")}</th>
    </>
  );

  return (
    <div>
      {/* Selector & Actions */}
      <div style={styles.topRow}>
        <div style={styles.selectorRow}>
          <label style={styles.selectorLabel}>{t("testRun")}</label>
          <select
            style={styles.select}
            value={selectedRunId ?? ""}
            onChange={(e) =>
              setSelectedRunId(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">{t("selectOption")}</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
        <div style={styles.downloadBtns}>
          <button style={styles.btnPdf} onClick={handleDownloadPdf} disabled={!selectedRunId}>
            {t("pdfDownload")}
          </button>
          <button style={styles.btnExcel} onClick={handleDownloadExcel} disabled={!selectedRunId}>
            {t("excelDownload")}
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          {t("common:loadingData")}
        </div>
      ) : !report ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          {t("selectRun")}
        </div>
      ) : (
        <div style={styles.reportContent}>
          {/* Project Info */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("projectInfo")}</h3>
            <div style={styles.infoGrid}>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("project")}</span>
                <span style={styles.infoValue}>{report.project.name}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("version")}</span>
                <span style={styles.infoValue}>{report.test_run.version || "-"}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("environment")}</span>
                <span style={styles.infoValue}>
                  {report.test_run.environment || "-"}
                </span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("round")}</span>
                <span style={styles.infoValue}>R{report.test_run.round}</span>
              </div>
              {/* 예전에는 "수행일" 한 칸에 생성일을 보여 줬다. 두 날짜를 나눠 싣는다. */}
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("createdDate")}</span>
                <span data-testid="info-created" style={styles.infoValue}>{formatDate(report.test_run.created_at)}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("completedDate")}</span>
                <span data-testid="info-completed" style={styles.infoValue}>{formatDate(report.test_run.completed_at)}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>{t("executors")}</span>
                <span data-testid="info-executors" style={styles.infoValue}>
                  {report.executors?.length
                    ? report.executors.map((e) => `${e.name} ${e.count}`).join(", ")
                    : "-"}
                </span>
              </div>
              {report.total_duration_sec ? (
                <div style={styles.infoItem}>
                  <span style={styles.infoLabel}>{t("totalDuration")}</span>
                  <span style={styles.infoValue}>{formatDuration(report.total_duration_sec)}</span>
                </div>
              ) : null}
            </div>
          </div>

          {/* Overall Stats */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("overallStatus")}</h3>
            <div style={styles.statsGrid}>
              <div data-testid="stat-total" style={{ ...styles.statCard, borderLeftColor: "var(--accent)" }}>
                <div style={styles.statLabel}>{t("totalTC")}</div>
                <div style={styles.statValue}>{report.summary.total}</div>
              </div>
              <div data-testid="stat-pass" style={{ ...styles.statCard, borderLeftColor: "var(--color-pass)" }}>
                <div style={styles.statLabel}>PASS</div>
                <div style={styles.statValue}>{report.summary.pass}</div>
              </div>
              <div data-testid="stat-fail" style={{ ...styles.statCard, borderLeftColor: "var(--color-fail)" }}>
                <div style={styles.statLabel}>FAIL</div>
                <div style={styles.statValue}>{report.summary.fail}</div>
              </div>
              <div data-testid="stat-block" style={{ ...styles.statCard, borderLeftColor: "var(--color-block)" }}>
                <div style={styles.statLabel}>BLOCK</div>
                <div style={styles.statValue}>{report.summary.block}</div>
              </div>
              <div data-testid="stat-na" style={{ ...styles.statCard, borderLeftColor: "var(--color-na)" }}>
                <div style={styles.statLabel}>N/A</div>
                <div style={styles.statValue}>{report.summary.na}</div>
              </div>
              <div data-testid="stat-not-started" style={{ ...styles.statCard, borderLeftColor: "var(--color-ns-accent)" }}>
                <div style={styles.statLabel}>{t("notStarted")}</div>
                <div style={styles.statValue}>{report.summary.not_started}</div>
              </div>
              <div data-testid="stat-pass-rate" style={{ ...styles.statCard, borderLeftColor: "var(--color-pass)" }}>
                <div style={styles.statLabel}>PASS Rate</div>
                <div style={styles.statValue}>{report.summary.pass_rate.toFixed(1)}%</div>
                <div style={styles.statNote}>{t("passRateNote")}</div>
              </div>
            </div>
          </div>

          {/* 직전 수행 대비 */}
          {report.comparison && (
            <div style={styles.section} data-testid="comparison">
              <h3 style={styles.sectionTitle}>{t("comparisonTitle")}</h3>
              <div style={styles.statNote}>
                {t("comparisonBase", {
                  name: report.comparison.previous_run.name,
                  round: report.comparison.previous_run.round,
                  common: report.comparison.common,
                })}
              </div>
              <div style={{ ...styles.statsGrid, marginTop: 12 }}>
                <div style={{ ...styles.statCard, borderLeftColor: "var(--accent)" }}>
                  <div style={styles.statLabel}>{t("changed")}</div>
                  <div style={styles.statValue}>{report.comparison.changed}</div>
                </div>
                <div data-testid="comparison-regressions" style={{ ...styles.statCard, borderLeftColor: "var(--color-fail)" }}>
                  <div style={styles.statLabel}>{t("regressions")}</div>
                  <div style={styles.statValue}>{report.comparison.regressions.length}</div>
                </div>
                <div data-testid="comparison-fixed" style={{ ...styles.statCard, borderLeftColor: "var(--color-pass)" }}>
                  <div style={styles.statLabel}>{t("fixed")}</div>
                  <div style={styles.statValue}>{report.comparison.fixed.length}</div>
                </div>
              </div>
              {[
                { key: "regressions", items: report.comparison.regressions },
                { key: "fixed", items: report.comparison.fixed },
              ].map(({ key, items }) =>
                items.length > 0 ? (
                  <div key={key} style={styles.changeRow}>
                    <span style={styles.changeLabel}>{t(key)}</span>
                    <span>{items.map((i) => i.tc_id).join(", ")}</span>
                  </div>
                ) : null
              )}
            </div>
          )}

          {/* 실패·차단 항목. 예전에는 FAIL 만 실어 BLOCK 만 있는 수행이 "없음" 으로 보였다. */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("topFailures")}</h3>
            {report.top_failures.length === 0 ? (
              <div style={styles.emptyText}>{t("noFailures")}</div>
            ) : (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>{t("tcId")}</th>
                    <th style={styles.th}>{t("priority")}</th>
                    <th style={styles.th}>{t("category")}</th>
                    <th style={styles.th}>{t("result")}</th>
                    <th style={styles.th}>{t("actualResult")}</th>
                    <th style={styles.th}>{t("executor")}</th>
                    <th style={styles.th}>{t("issueLink")}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.top_failures.map((f, i) => {
                    const url = resolveIssueUrl(f.issue_link, report.project.jira_base_url);
                    return (
                      <tr key={i} data-testid={`issue-row-${f.test_case?.tc_id}`}>
                        <td style={styles.td}>{f.test_case?.tc_id || "-"}</td>
                        <td style={styles.td}>{f.test_case?.priority || "-"}</td>
                        <td style={styles.td}>{f.test_case?.category || "-"}</td>
                        <td style={{ ...styles.td, color: RESULT_COLOR[f.result] ?? "var(--text-primary)", fontWeight: 600 }}>
                          {f.result}
                        </td>
                        <td style={styles.td}>{f.actual_result || "-"}</td>
                        <td style={styles.td}>{f.executed_by || "-"}</td>
                        <td style={styles.td}>
                          {!f.issue_link ? (
                            "-"
                          ) : url ? (
                            <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-link)" }}>
                              {f.issue_link}
                            </a>
                          ) : (
                            f.issue_link
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Jira Issues */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("relatedJiraIssues")}</h3>
            {report.jira_issues.length === 0 ? (
              <div style={styles.emptyText}>{t("noRelatedIssues")}</div>
            ) : (
              <div style={styles.issueList}>
                {report.jira_issues.map((issue) => {
                  const url = resolveIssueUrl(issue, report.project.jira_base_url);
                  return url ? (
                    <a key={issue} href={url} target="_blank" rel="noopener noreferrer" style={styles.issueBadge}>
                      {issue}
                    </a>
                  ) : (
                    <span key={issue} style={styles.issueBadge}>{issue}</span>
                  );
                })}
              </div>
            )}
          </div>

          {/* 우선순위별 요약 */}
          {report.priority_summary?.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>{t("prioritySummary")}</h3>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>{t("priority")}</th>
                    {breakdownHeaders}
                  </tr>
                </thead>
                <tbody>
                  {report.priority_summary.map((row) => (
                    <tr key={row.priority ?? "__unset"} data-testid={`priority-row-${row.priority ?? "unset"}`}>
                      <td style={styles.td}>{row.priority ?? t("unsetPriority")}</td>
                      {breakdownCells(row, "priority", row.priority ?? "unset")}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Category Summary */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("categorySummary")}</h3>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>{t("category")}</th>
                  {breakdownHeaders}
                </tr>
              </thead>
              <tbody>
                {report.category_summary.map((row) => (
                  <tr key={row.category} data-testid={`category-row-${row.category}`}>
                    <td style={styles.td}>{row.category}</td>
                    {breakdownCells(row, "category", row.category)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  topRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
    flexWrap: "wrap",
    gap: 12,
  },
  selectorRow: { display: "flex", alignItems: "center", gap: 12 },
  selectorLabel: { fontSize: 14, fontWeight: 600, color: "var(--text-primary)" },
  select: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    minWidth: 240,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  downloadBtns: { display: "flex", gap: 8 },
  btnPdf: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--color-fail)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnExcel: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--color-pass)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  reportContent: {},
  section: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 24,
    marginBottom: 20,
    boxShadow: "var(--shadow)",
  },
  sectionTitle: { margin: "0 0 16px", fontSize: 17, fontWeight: 700, color: "var(--text-primary)" },
  infoGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
    gap: 16,
  },
  infoItem: { display: "flex", flexDirection: "column" as const, gap: 4 },
  infoLabel: { fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 },
  infoValue: { fontSize: 15, color: "var(--text-primary)", fontWeight: 600 },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 16,
  },
  statNote: {
    marginTop: 4,
    fontSize: 11,
    color: "var(--text-secondary)",
  },
  statCard: {
    padding: "16px",
    borderRadius: 8,
    backgroundColor: "var(--bg-page)",
    borderLeft: "4px solid",
  },
  statLabel: { fontSize: 13, color: "var(--text-secondary)", marginBottom: 6 },
  statValue: { fontSize: 24, fontWeight: 700, color: "var(--text-primary)" },
  emptyText: { color: "var(--text-secondary)", fontSize: 14, padding: "12px 0" },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: {
    textAlign: "left" as const,
    padding: "8px 10px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
  },
  thNum: {
    textAlign: "right" as const,
    padding: "8px 10px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
  },
  td: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
  },
  tdNum: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    textAlign: "right" as const,
    fontWeight: 600,
    color: "var(--text-primary)",
  },
  issueList: { display: "flex", flexWrap: "wrap" as const, gap: 8 },
  changeRow: { marginTop: 10, fontSize: 13, color: "var(--text-primary)", display: "flex", gap: 8, flexWrap: "wrap" as const },
  changeLabel: { fontWeight: 600, color: "var(--text-secondary)" },
  issueBadge: {
    textDecoration: "none",
    display: "inline-block",
    padding: "4px 12px",
    borderRadius: 6,
    backgroundColor: "var(--bg-input)",
    color: "var(--color-link)",
    fontSize: 13,
    fontWeight: 600,
  },
};
