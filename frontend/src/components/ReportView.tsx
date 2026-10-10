import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { reportsApi, testRunsApi } from "../api";
import type { Project, ReportBreakdownRow, ReportData, TestRun } from "../types";
import { resolveIssueUrl } from "../utils/issueLink";
import { priorityDisplayMap } from "../utils/priority";
import RunIssuesSection from "./RunIssuesSection";
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
  /** 이슈를 고칠 권한(my_role)을 본다. 없으면 읽기만 한다 */
  project?: Project;
}

export default function ReportView({ projectId, project }: Props) {
  const { t, i18n } = useTranslation("report");
  // 우선순위 표시 이름은 그리드와 같다(testcase 네임스페이스). 요약 표와 목록이 같은 이름을 쓴다.
  const { t: tcT } = useTranslation("testcase");
  const priorityDisplay = useMemo(() => priorityDisplayMap(tcT), [tcT]);
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

  // ★늦게 온 응답이 지금 고른 수행의 리포트를 덮지 않게 세대 번호로 거른다. 수행을 빠르게 바꾸면
  //   선택 상자는 B 인데 화면은 A 의 리포트가 남았다(CompareView 와 같은 방식).
  const reportSeqRef = useRef(0);

  const loadReport = useCallback(async () => {
    if (!selectedRunId) return;
    const seq = ++reportSeqRef.current;
    setLoading(true);
    try {
      const data = await reportsApi.getData(projectId, selectedRunId);
      if (seq !== reportSeqRef.current) return;
      setReport(data);
    } catch (err) {
      if (seq !== reportSeqRef.current) return;
      console.error(err);
      toast.error(t("loadFailed"));
    } finally {
      if (seq === reportSeqRef.current) setLoading(false);
    }
  }, [projectId, selectedRunId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  // 이슈를 고친 뒤 다시 읽는다. loadReport 는 로딩 화면으로 변경해 스크롤이 튀므로 조용히 변경한다.
  // ★조용한 갱신은 세대 번호를 올리지 않는다. 올리면 진행 중인 loadReport 의 응답과 로딩 해제가
  //   버려진다. 대신 응답 시점에 세대와 선택이 그대로인지 본다. 이전 수행에서 시작된 비교 대상
  //   변경이 늦게 끝나 이 함수를 불러도, 이미 다른 수행을 고른 뒤라면 아무것도 하지 않는다.
  const selectedRunIdRef = useRef(selectedRunId);
  selectedRunIdRef.current = selectedRunId;
  // 같은 수행의 갱신이 연달아 나가면 늦게 온 옛 응답이 새 응답을 덮지 않게 갱신끼리도 순번을 둔다.
  const refreshSeqRef = useRef(0);
  const refreshReport = useCallback(async () => {
    const runId = selectedRunId;
    if (!runId || runId !== selectedRunIdRef.current) return;
    const seq = reportSeqRef.current;
    const mine = ++refreshSeqRef.current;
    const current = () =>
      seq === reportSeqRef.current && runId === selectedRunIdRef.current && mine === refreshSeqRef.current;
    try {
      const data = await reportsApi.getData(projectId, runId);
      if (current()) setReport(data);
    } catch {
      if (current()) toast.error(t("loadFailed"));
    }
  }, [projectId, selectedRunId]);

  const canEditReport = !!project?.my_role && project.my_role !== "viewer";

  // 비교 대상을 수행에 저장한다. null 이면 자동(같은 이름의 이전 회차)으로 되돌린다.
  const handleCompareTarget = async (targetId: number | null) => {
    if (!selectedRunId) return;
    try {
      await testRunsApi.update(projectId, selectedRunId, { compare_run_id: targetId });
      setRuns((prev) => prev.map((r) => (r.id === selectedRunId ? { ...r, compare_run_id: targetId } : r)));
      await refreshReport();
    } catch {
      toast.error(t("compareSaveFailed"));
    }
  };

  const handleDownloadPdf = async () => {
    if (!selectedRunId) return;
    try {
      const { blob, filename } = await reportsApi.downloadPdf(projectId, selectedRunId, i18n.language);
      saveBlob(blob, filename ?? `report_${selectedRunId}.pdf`);
    } catch (err) {
      console.error(err);
      toast.error(t("pdfFailed"));
    }
  };

  const handleDownloadExcel = async () => {
    if (!selectedRunId) return;
    try {
      const { blob, filename } = await reportsApi.downloadExcel(projectId, selectedRunId, i18n.language);
      saveBlob(blob, filename ?? `report_${selectedRunId}.xlsx`);
    } catch (err) {
      console.error(err);
      toast.error(t("excelFailed"));
    }
  };

  // PDF 와 같은 모양(YYYY-MM-DD HH:mm)이다. 예전에는 날짜만 로캘 모양으로 보여 PDF 와 달랐다.
  const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

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
          {/* 프로젝트 정보. 항목 | 값 | 항목 | 값 의 표다. PDF 도 같은 표를 그린다 */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>{t("projectInfo")}</h3>
            <table style={styles.infoTable} data-testid="info-table">
              <colgroup>
                <col style={{ width: "13%" }} />
                <col style={{ width: "37%" }} />
                <col style={{ width: "13%" }} />
                <col style={{ width: "37%" }} />
              </colgroup>
              <tbody>
                <tr>
                  <th style={styles.infoTh}>{t("project")}</th>
                  <td style={styles.infoTd}>{report.project.name}</td>
                  <th style={styles.infoTh}>{t("runName")}</th>
                  <td style={styles.infoTd}>{report.test_run.name} (R{report.test_run.round})</td>
                </tr>
                <tr>
                  <th style={styles.infoTh}>{t("version")}</th>
                  <td style={styles.infoTd}>{report.test_run.version || "-"}</td>
                  <th style={styles.infoTh}>{t("environment")}</th>
                  <td style={styles.infoTd}>{report.test_run.environment || "-"}</td>
                </tr>
                <tr>
                  <th style={styles.infoTh}>{t("round")}</th>
                  <td style={styles.infoTd}>R{report.test_run.round}</td>
                  <th style={styles.infoTh}>{t("status")}</th>
                  <td style={styles.infoTd}>
                    <span
                      data-testid="info-status"
                      style={{
                        ...styles.statusPill,
                        ...(report.test_run.status === "completed" ? styles.statusDone : styles.statusRunning),
                      }}
                    >
                      {report.test_run.status === "completed" ? t("statusCompleted") : t("statusInProgress")}
                    </span>
                  </td>
                </tr>
                {/* 예전에는 "수행일" 한 칸에 생성일을 보여 줬다. 두 날짜를 나눠 싣는다. */}
                <tr>
                  <th style={styles.infoTh}>{t("createdDate")}</th>
                  <td data-testid="info-created" style={styles.infoTd}>{formatDate(report.test_run.created_at)}</td>
                  <th style={styles.infoTh}>{t("completedDate")}</th>
                  <td data-testid="info-completed" style={styles.infoTd}>{formatDate(report.test_run.completed_at)}</td>
                </tr>
                <tr>
                  <th style={styles.infoTh}>{t("executors")}</th>
                  <td data-testid="info-executors" style={styles.infoTd} colSpan={3}>
                    {report.executors?.length
                      ? report.executors.map((e) => e.name).join(", ")
                      : "-"}
                  </td>
                </tr>
                {report.total_duration_sec ? (
                  <tr>
                    <th style={styles.infoTh}>{t("totalDuration")}</th>
                    <td style={styles.infoTd} colSpan={3}>{formatDuration(report.total_duration_sec)}</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
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

          {/* 비교 수행 대비. R2 면 같은 이름의 R1 이 자동 대상이고, 없으면(R1) 사람이 고른다.
              고른 값은 수행에 저장해 PDF·엑셀도 같은 대상과 비교한다. */}
          {(report.comparison || canEditReport) && (
            <div style={styles.section} data-testid="comparison">
              <div style={styles.sectionHeader}>
                <h3 style={{ ...styles.sectionTitle, margin: 0 }}>{t("comparisonTitle")}</h3>
                {canEditReport && (
                  <select
                    data-testid="compare-target"
                    style={{ ...styles.select, minWidth: 280, fontSize: 13, padding: "6px 10px" }}
                    value={report.test_run.compare_run_id ?? ""}
                    onChange={(e) => handleCompareTarget(e.target.value ? Number(e.target.value) : null)}
                    aria-label={t("compareTarget")}
                  >
                    <option value="">{t("compareAuto")}</option>
                    {runs
                      .filter((r) => r.id !== report.test_run.id)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} (R{r.round})
                        </option>
                      ))}
                  </select>
                )}
              </div>
              {!report.comparison ? (
                <div style={styles.emptyText}>{t("compareNone")}</div>
              ) : (
                <>
                  <div style={styles.statNote}>
                    {t("comparisonBase", {
                      name: report.comparison.previous_run.name,
                      round: report.comparison.previous_run.round,
                      common: report.comparison.common,
                    })}
                    {report.comparison.mode === "auto" ? ` · ${t("compareAutoNote")}` : ""}
                  </div>
                  {/* 카드 넷: 이전 실패 -> 수정 -> 미수정 -> 퇴보. "8 중 7 고치고 1 남았고 새로 깨진 건 0" 이
                      숫자만으로 읽힌다. 결과가 변경된 TC 카드는 수정 수와 겹쳐 보여 뺐다(09-30). */}
                  {(() => {
                    const c = report.comparison;
                    const pf = c.prev_fail ?? { total: c.fixed.length, fixed: c.fixed.length, still: 0, other: 0 };
                    const cards = [
                      { id: "prev-fail", label: t("prevFailTc"), sub: t("prevFailSub"), value: pf.total, color: "var(--text-secondary)" },
                      { id: "fixed", label: t("fixedTc"), sub: t("fixedSub"), value: pf.fixed, color: "var(--color-pass)" },
                      { id: "still", label: t("stillTc"), sub: t("stillSub"), value: pf.still, color: "var(--color-fail)" },
                      { id: "regressions", label: t("regressedTc"), sub: t("regressedSub"), value: c.regressions.length, color: "var(--color-fail)" },
                    ];
                    return (
                      <div style={{ ...styles.statsGrid, marginTop: 12 }}>
                        {cards.map((card) => (
                          <div key={card.id} data-testid={`comparison-${card.id}`} style={{ ...styles.statCard, borderLeftColor: card.color }}>
                            <div style={styles.statLabel}>{card.label}</div>
                            <div style={{ ...styles.statValue, color: card.value > 0 ? card.color : undefined }}>{card.value}</div>
                            <div style={styles.statSub}>{card.sub}</div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                  {(() => {
                    // 옛 응답(changes 없음)은 퇴보 · 개선 목록으로 표를 만든다
                    const changes = report.comparison.changes ?? [
                      ...report.comparison.regressions.map((c) => ({ ...c, kind: "regression" as const })),
                      ...report.comparison.fixed.map((c) => ({ ...c, kind: "fixed" as const })),
                    ];
                    if (changes.length === 0) return null;
                    return (
                      <div style={{ marginTop: 14 }} data-testid="comparison-changes">
                        <div style={styles.subTitle}>
                          {t("changeList")} <span style={styles.count}>{changes.length}</span>
                        </div>
                        <table style={styles.table}>
                          <thead>
                            <tr>
                              <th style={styles.th}>{t("tcId")}</th>
                              <th style={styles.th}>{t("priority")}</th>
                              <th style={styles.th}>{t("category")}</th>
                              <th style={styles.th}>{t("change")}</th>
                              <th style={styles.th}>{t("kind")}</th>
                              <th style={styles.th}>{t("relatedIssues")}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {changes.map((c) => {
                              const kind = c.kind ?? "other";
                              const color = KIND_COLOR[kind];
                              return (
                                <tr key={c.tc_id} data-testid={`change-row-${c.tc_id}`}>
                                  <td style={styles.tdNowrap}>{c.tc_id || "-"}</td>
                                  <td style={styles.tdNowrap}>{c.priority ? (priorityDisplay[c.priority] ?? c.priority) : t("unsetPriority")}</td>
                                  <td style={styles.td}>{c.category || t("unsetCategory")}</td>
                                  <td style={{ ...styles.tdNowrap, color, fontWeight: 600 }}>{c.before} -&gt; {c.after}</td>
                                  <td style={{ ...styles.tdNowrap, color }}>{t(KIND_KEY[kind])}</td>
                                  <td style={styles.td}>{c.issue_keys?.length ? c.issue_keys.join(", ") : "-"}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    );
                  })()}
                </>
              )}
            </div>
          )}

          {/* 등록한 이슈. 현황 바로 다음에 둔다. PDF·엑셀 요약 시트와 같은 차례다 */}
          <RunIssuesSection
            projectId={projectId}
            runId={report.test_run.id}
            issues={report.issues ?? []}
            summary={report.issue_summary}
            runName={report.test_run.name}
            runs={runs.filter((r) => r.id !== report.test_run.id).map((r) => ({ id: r.id, name: r.name, round: r.round }))}
            tracker={report.project.issue_tracker}
            trackerUrl={report.project.jira_base_url}
            candidates={report.issue_candidates ?? []}
            canEdit={canEditReport}
            onChanged={refreshReport}
          />

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
                    <th style={styles.th}>{t("issueLink")}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.top_failures.map((f, i) => {
                    const url = resolveIssueUrl(f.issue_link, report.project.jira_base_url, report.project.issue_tracker);
                    return (
                      <tr key={i} data-testid={`issue-row-${f.test_case?.tc_id}`}>
                        {/* TC ID·우선순위·결과는 짧은 값이라 줄을 변경하지 않는다. 남는 폭은 실제 결과가 쓴다 */}
                        <td style={styles.tdNowrap}>{f.test_case?.tc_id || "-"}</td>
                        <td style={styles.tdNowrap}>
                          {f.test_case?.priority ? (priorityDisplay[f.test_case.priority] ?? f.test_case.priority) : t("unsetPriority")}
                        </td>
                        <td style={styles.td}>{f.test_case?.category || t("unsetCategory")}</td>
                        <td style={{ ...styles.tdNowrap, color: RESULT_COLOR[f.result] ?? "var(--text-primary)", fontWeight: 600 }}>
                          {f.result}
                        </td>
                        <td style={styles.td}>{f.actual_result || "-"}</td>
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
                      <td style={styles.tdNowrap}>{row.priority ? (priorityDisplay[row.priority] ?? row.priority) : t("unsetPriority")}</td>
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
                  <tr key={row.category === null ? "unset:" : `name:${row.category}`} data-testid={`category-row-${row.category ?? "unset"}`}>
                    <td style={styles.td}>{row.category ?? t("unsetCategory")}</td>
                    {breakdownCells(row, "category", row.category ?? "unset")}
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
  // PDF 버튼은 앱 강조색. 빨강(FAIL 색)은 결과 색과 겹쳐 위험 동작처럼 읽힌다(09-30 지적).
  btnPdf: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  // 엑셀 버튼은 Microsoft Excel 브랜드 초록(#217346). 결과 색(PASS)과 구분된다(09-30 결정).
  btnExcel: {
    padding: "8px 20px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "#217346",
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
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    flexWrap: "wrap" as const,
    marginBottom: 12,
  },
  infoTable: {
    width: "100%",
    borderCollapse: "collapse" as const,
    tableLayout: "fixed" as const,
    fontSize: 13,
    border: "1px solid var(--border-color)",
  },
  // 항목 칸은 옅게 칠해 값과 구분한다
  infoTh: {
    textAlign: "left" as const,
    padding: "9px 12px",
    backgroundColor: "var(--bg-page)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    fontSize: 12,
    border: "1px solid var(--border-color)",
    whiteSpace: "nowrap" as const,
  },
  infoTd: {
    padding: "9px 12px",
    color: "var(--text-primary)",
    fontWeight: 500,
    border: "1px solid var(--border-color)",
    wordBreak: "keep-all" as const,
    overflowWrap: "anywhere" as const,
  },
  statusPill: { display: "inline-block", padding: "1px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600 },
  statusDone: { backgroundColor: "rgba(26, 127, 55, 0.12)", color: "var(--color-pass)" },
  statusRunning: { backgroundColor: "rgba(37, 99, 235, 0.12)", color: "var(--accent)" },
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
    // 한글이 글자 단위로 끊기지 않게 단어 단위로 줄을 변경한다("Opticon 연/동" 방지).
    // 한 단어가 칸보다 길면(주소 등) 그때만 단어 안에서 끊는다.
    wordBreak: "keep-all" as const,
    overflowWrap: "anywhere" as const,
  },
  tdNowrap: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
    whiteSpace: "nowrap" as const,
  },
  tdNum: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    textAlign: "right" as const,
    fontWeight: 600,
    color: "var(--text-primary)",
  },
  statSub: { marginTop: 4, fontSize: 11, color: "var(--text-secondary)" },
  subTitle: { fontSize: 14, fontWeight: 700, color: "var(--text-primary)", marginBottom: 8 },
  count: { fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginLeft: 4 },
};

// 변경 상세의 구분 색. 퇴보 · 미수정은 FAIL 색, 개선은 PASS 색(PDF 와 같다).
const KIND_COLOR: Record<string, string> = {
  regression: "var(--color-fail)", still: "var(--color-fail)", fixed: "var(--color-pass)", other: "var(--text-primary)",
};
const KIND_KEY: Record<string, string> = {
  regression: "kindRegression", still: "kindStill", fixed: "kindFixed", other: "kindOther",
};
