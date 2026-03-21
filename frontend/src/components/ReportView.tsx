import { useCallback, useEffect, useState } from "react";
import { reportsApi, testRunsApi } from "../api";
import type { ReportData, TestRun } from "../types";
import toast from "react-hot-toast";

interface Props {
  projectId: number;
}

export default function ReportView({ projectId }: Props) {
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
      .catch(() => toast.error("테스트 수행 목록을 불러오지 못했습니다."));
  }, [projectId]);

  const loadReport = useCallback(async () => {
    if (!selectedRunId) return;
    setLoading(true);
    try {
      const data = await reportsApi.getData(projectId, selectedRunId);
      setReport(data);
    } catch (err) {
      console.error(err);
      toast.error("리포트 데이터를 불러오지 못했습니다.");
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
      const blob = await reportsApi.downloadPdf(projectId, selectedRunId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${selectedRunId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      toast.error("PDF 다운로드에 실패했습니다.");
    }
  };

  const handleDownloadExcel = async () => {
    if (!selectedRunId) return;
    try {
      const blob = await reportsApi.downloadExcel(projectId, selectedRunId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${selectedRunId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      toast.error("Excel 다운로드에 실패했습니다.");
    }
  };

  return (
    <div>
      {/* Selector & Actions */}
      <div style={styles.topRow}>
        <div style={styles.selectorRow}>
          <label style={styles.selectorLabel}>테스트 수행:</label>
          <select
            style={styles.select}
            value={selectedRunId ?? ""}
            onChange={(e) =>
              setSelectedRunId(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">-- 선택 --</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
        <div style={styles.downloadBtns}>
          <button style={styles.btnPdf} onClick={handleDownloadPdf} disabled={!selectedRunId}>
            PDF 다운로드
          </button>
          <button style={styles.btnExcel} onClick={handleDownloadExcel} disabled={!selectedRunId}>
            Excel 다운로드
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          불러오는 중...
        </div>
      ) : !report ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          테스트 수행을 선택해 주세요.
        </div>
      ) : (
        <div style={styles.reportContent}>
          {/* Project Info */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>프로젝트 정보</h3>
            <div style={styles.infoGrid}>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>프로젝트</span>
                <span style={styles.infoValue}>{report.project.name}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>버전</span>
                <span style={styles.infoValue}>{report.test_run.version || "-"}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>환경</span>
                <span style={styles.infoValue}>
                  {report.test_run.environment || "-"}
                </span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>라운드</span>
                <span style={styles.infoValue}>R{report.test_run.round}</span>
              </div>
              <div style={styles.infoItem}>
                <span style={styles.infoLabel}>수행일</span>
                <span style={styles.infoValue}>
                  {new Date(report.test_run.created_at).toLocaleDateString("ko-KR")}
                </span>
              </div>
            </div>
          </div>

          {/* Overall Stats */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>전체 현황</h3>
            <div style={styles.statsGrid}>
              <div style={{ ...styles.statCard, borderLeftColor: "#2D4A7A" }}>
                <div style={styles.statLabel}>전체 TC</div>
                <div style={styles.statValue}>{report.summary.total}</div>
              </div>
              <div style={{ ...styles.statCard, borderLeftColor: "#1A7F37" }}>
                <div style={styles.statLabel}>PASS Rate</div>
                <div style={styles.statValue}>{report.summary.pass_rate.toFixed(1)}%</div>
              </div>
              <div style={{ ...styles.statCard, borderLeftColor: "#CF222E" }}>
                <div style={styles.statLabel}>FAIL</div>
                <div style={styles.statValue}>{report.summary.fail}</div>
              </div>
              <div style={{ ...styles.statCard, borderLeftColor: "#BF8700" }}>
                <div style={styles.statLabel}>BLOCK</div>
                <div style={styles.statValue}>{report.summary.block}</div>
              </div>
            </div>
          </div>

          {/* Top Failures */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>주요 실패 항목</h3>
            {report.top_failures.length === 0 ? (
              <div style={styles.emptyText}>실패 항목이 없습니다.</div>
            ) : (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>TC ID</th>
                    <th style={styles.th}>결과</th>
                    <th style={styles.th}>실제 결과</th>
                    <th style={styles.th}>Issue Link</th>
                  </tr>
                </thead>
                <tbody>
                  {report.top_failures.map((f, i) => (
                    <tr key={i}>
                      <td style={styles.td}>{f.test_case?.tc_id || "-"}</td>
                      <td style={{ ...styles.td, color: "#CF222E", fontWeight: 600 }}>
                        {f.result}
                      </td>
                      <td style={styles.td}>{f.actual_result || "-"}</td>
                      <td style={styles.td}>
                        {f.issue_link ? (
                          <a
                            href={
                              f.issue_link.startsWith("http")
                                ? f.issue_link
                                : "#"
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: "#2563EB" }}
                          >
                            {f.issue_link}
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Jira Issues */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>연관 Jira 이슈</h3>
            {report.jira_issues.length === 0 ? (
              <div style={styles.emptyText}>연관 이슈가 없습니다.</div>
            ) : (
              <div style={styles.issueList}>
                {report.jira_issues.map((issue, i) => (
                  <span key={i} style={styles.issueBadge}>
                    {issue}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Category Summary */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>카테고리별 요약</h3>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>카테고리</th>
                  <th style={styles.thNum}>Total</th>
                  <th style={styles.thNum}>PASS</th>
                  <th style={styles.thNum}>FAIL</th>
                  <th style={styles.thNum}>BLOCK</th>
                  <th style={styles.thNum}>N/A</th>
                </tr>
              </thead>
              <tbody>
                {report.category_summary.map((row) => (
                  <tr key={row.category}>
                    <td style={styles.td}>{row.category}</td>
                    <td style={styles.tdNum}>{row.total}</td>
                    <td style={{ ...styles.tdNum, color: "#1A7F37" }}>{row.pass}</td>
                    <td style={{ ...styles.tdNum, color: "#CF222E" }}>{row.fail}</td>
                    <td style={{ ...styles.tdNum, color: "#BF8700" }}>{row.block}</td>
                    <td style={{ ...styles.tdNum, color: "#6B7280" }}>{row.na}</td>
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
    backgroundColor: "#CF222E",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnExcel: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "#1A7F37",
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
  issueBadge: {
    display: "inline-block",
    padding: "4px 12px",
    borderRadius: 6,
    backgroundColor: "var(--bg-input)",
    color: "#5B9BD5",
    fontSize: 13,
    fontWeight: 600,
  },
};
