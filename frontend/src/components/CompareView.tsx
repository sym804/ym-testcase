import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { testRunsApi } from "../api";
import type { TestRun, TestResult } from "../types";
import toast from "react-hot-toast";

interface Props {
  projectId: number;
}

const resultColors: Record<string, { bg: string; fg: string }> = {
  PASS: { bg: "rgba(26, 127, 55, 0.15)", fg: "var(--color-pass)" },
  FAIL: { bg: "rgba(207, 34, 46, 0.15)", fg: "var(--color-fail)" },
  BLOCK: { bg: "rgba(191, 135, 0, 0.15)", fg: "var(--color-block)" },
  "N/A": { bg: "rgba(107, 114, 128, 0.15)", fg: "var(--text-secondary)" },
};

function displayResult(val: string) {
  if (!val || val === "NS") return "";
  if (val === "NA") return "N/A";
  return val;
}

export default function CompareView({ projectId }: Props) {
  const { t } = useTranslation("compare");
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [leftRunId, setLeftRunId] = useState<number | null>(null);
  const [rightRunId, setRightRunId] = useState<number | null>(null);
  const [leftResults, setLeftResults] = useState<TestResult[]>([]);
  const [rightResults, setRightResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<"all" | "changed" | "regression">("all");

  useEffect(() => {
    testRunsApi.list(projectId).then(setRuns).catch(() => toast.error(t("runLoadFailed")));
  }, [projectId]);

  const loadResults = useCallback(async () => {
    if (!leftRunId || !rightRunId) return;
    setLoading(true);
    try {
      const [leftDetail, rightDetail] = await Promise.all([
        testRunsApi.getOne(projectId, leftRunId),
        testRunsApi.getOne(projectId, rightRunId),
      ]);
      const mapResult = (r: TestResult) => ({
        ...r,
        result: r.result === "NS" ? "" : r.result === "NA" ? "N/A" : r.result,
      });
      setLeftResults((leftDetail.results || []).map(mapResult));
      setRightResults((rightDetail.results || []).map(mapResult));
    } catch (err) {
      console.error(err);
      toast.error(t("resultLoadFailed"));
    } finally {
      setLoading(false);
    }
  }, [projectId, leftRunId, rightRunId]);

  useEffect(() => {
    if (leftRunId && rightRunId) loadResults();
  }, [leftRunId, rightRunId, loadResults]);

  // Merge by test_case_id
  const comparedRows = useMemo(() => {
    const leftMap = new Map(leftResults.map((r) => [r.test_case_id, r]));
    const rightMap = new Map(rightResults.map((r) => [r.test_case_id, r]));
    const allIds = new Set([...leftMap.keys(), ...rightMap.keys()]);

    const rows = Array.from(allIds).map((tcId) => {
      const left = leftMap.get(tcId);
      const right = rightMap.get(tcId);
      const tc = left?.test_case || right?.test_case;
      const leftVal = displayResult(left?.result || "");
      const rightVal = displayResult(right?.result || "");
      const changed = leftVal !== rightVal;
      const regression = leftVal === "PASS" && rightVal === "FAIL";
      return { tcId, tc, leftVal, rightVal, changed, regression };
    });

    rows.sort((a, b) => (a.tc?.no || 0) - (b.tc?.no || 0));
    return rows;
  }, [leftResults, rightResults]);

  const filteredRows = useMemo(() => {
    if (filterMode === "changed") return comparedRows.filter((r) => r.changed);
    if (filterMode === "regression") return comparedRows.filter((r) => r.regression);
    return comparedRows;
  }, [comparedRows, filterMode]);

  const stats = useMemo(() => {
    const total = comparedRows.length;
    const changed = comparedRows.filter((r) => r.changed).length;
    const regression = comparedRows.filter((r) => r.regression).length;
    const improved = comparedRows.filter((r) => r.leftVal === "FAIL" && r.rightVal === "PASS").length;
    return { total, changed, regression, improved };
  }, [comparedRows]);

  const leftRun = runs.find((r) => r.id === leftRunId);
  const rightRun = runs.find((r) => r.id === rightRunId);

  return (
    <div style={{ padding: 0 }}>
      {/* Run selectors */}
      <div style={styles.selectorBar}>
        <div style={styles.selectorGroup}>
          <label style={styles.selectorLabel}>{t("baseRun")}</label>
          <select
            style={styles.selector}
            value={leftRunId || ""}
            onChange={(e) => setLeftRunId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("selectPlaceholder")}</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
        <span style={{ fontSize: 20, color: "#94A3B8", fontWeight: 700 }}>vs</span>
        <div style={styles.selectorGroup}>
          <label style={styles.selectorLabel}>{t("compareRun")}</label>
          <select
            style={styles.selector}
            value={rightRunId || ""}
            onChange={(e) => setRightRunId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("selectPlaceholder")}</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
      </div>

      {(!leftRunId || !rightRunId) && (
        <div style={styles.placeholder}>{t("selectBothRuns")}</div>
      )}

      {leftRunId && rightRunId && !loading && comparedRows.length > 0 && (
        <>
          {/* Stats */}
          <div style={styles.statsBar}>
            <span style={styles.statBadge}>{t("total", { count: stats.total })}</span>
            <span style={{ ...styles.statBadge, backgroundColor: "var(--bg-warning-light)", color: "var(--text-warning)" }}>
              {t("changed", { count: stats.changed })}
            </span>
            <span style={{ ...styles.statBadge, backgroundColor: "var(--bg-danger-light)", color: "var(--text-danger)" }}>
              {t("regression", { count: stats.regression })}
            </span>
            <span style={{ ...styles.statBadge, backgroundColor: "var(--bg-success-light)", color: "var(--text-success)" }}>
              {t("improved", { count: stats.improved })}
            </span>
            <div style={{ flex: 1 }} />
            <div style={styles.filterGroup}>
              {(["all", "changed", "regression"] as const).map((mode) => (
                <button
                  key={mode}
                  style={{
                    ...styles.filterBtn,
                    ...(filterMode === mode ? styles.filterBtnActive : {}),
                  }}
                  onClick={() => setFilterMode(mode)}
                >
                  {mode === "all" ? t("filterAll") : mode === "changed" ? t("filterChanged") : t("filterRegression")}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={{ ...styles.th, width: 50 }}>No</th>
                  <th style={{ ...styles.th, width: 90 }}>TC ID</th>
                  <th style={{ ...styles.th, width: 100 }}>Category</th>
                  <th style={styles.th}>Test Steps</th>
                  <th style={{ ...styles.th, width: 110, textAlign: "center" }}>
                    {leftRun ? `${leftRun.name}` : "Left"}
                  </th>
                  <th style={{ ...styles.th, width: 110, textAlign: "center" }}>
                    {rightRun ? `${rightRun.name}` : "Right"}
                  </th>
                  <th style={{ ...styles.th, width: 60, textAlign: "center" }}>{t("change")}</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => {
                  const leftColor = resultColors[row.leftVal];
                  const rightColor = resultColors[row.rightVal];
                  return (
                    <tr
                      key={row.tcId}
                      style={{
                        backgroundColor: row.regression
                          ? "rgba(207, 34, 46, 0.08)"
                          : row.changed
                          ? "rgba(191, 135, 0, 0.08)"
                          : undefined,
                      }}
                    >
                      <td style={styles.td}>{row.tc?.no}</td>
                      <td style={{ ...styles.td, fontWeight: 600, fontSize: 12 }}>{row.tc?.tc_id}</td>
                      <td style={styles.td}>{row.tc?.category}</td>
                      <td style={{ ...styles.td, maxWidth: 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {row.tc?.test_steps}
                      </td>
                      <td
                        style={{
                          ...styles.td,
                          textAlign: "center",
                          fontWeight: 600,
                          backgroundColor: leftColor?.bg,
                          color: leftColor?.fg || "#94A3B8",
                        }}
                      >
                        {row.leftVal || "-"}
                      </td>
                      <td
                        style={{
                          ...styles.td,
                          textAlign: "center",
                          fontWeight: 600,
                          backgroundColor: rightColor?.bg,
                          color: rightColor?.fg || "#94A3B8",
                        }}
                      >
                        {row.rightVal || "-"}
                      </td>
                      <td style={{ ...styles.td, textAlign: "center" }}>
                        {row.regression ? (
                          <span style={{ color: "#DC2626", fontWeight: 700 }}>&#9660;</span>
                        ) : row.changed ? (
                          <span style={{ color: "#D97706", fontWeight: 700 }}>&#9679;</span>
                        ) : (
                          ""
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {loading && (
        <div style={styles.placeholder}>{t("loadingCompare")}</div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  selectorBar: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 16,
    padding: "12px 16px",
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    border: "1px solid var(--border-color)",
  },
  selectorGroup: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  selectorLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-secondary)",
  },
  selector: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 13,
    fontFamily: "inherit",
    minWidth: 220,
    cursor: "pointer",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  placeholder: {
    textAlign: "center",
    padding: 60,
    color: "var(--text-secondary)",
    fontSize: 14,
  },
  statsBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 10,
  },
  statBadge: {
    padding: "3px 10px",
    borderRadius: 5,
    fontSize: 12,
    fontWeight: 600,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  filterGroup: {
    display: "flex",
    gap: 4,
  },
  filterBtn: {
    padding: "4px 12px",
    borderRadius: 5,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-secondary)",
    fontSize: 12,
    cursor: "pointer",
  },
  filterBtnActive: {
    backgroundColor: "var(--accent)",
    color: "#fff",
    borderColor: "var(--accent)",
  },
  tableWrapper: {
    maxHeight: "calc(100vh - 320px)",
    overflow: "auto",
    borderRadius: 10,
    border: "1px solid var(--border-color)",
    backgroundColor: "var(--bg-card)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  th: {
    padding: "8px 10px",
    textAlign: "left",
    backgroundColor: "var(--bg-page)",
    borderBottom: "2px solid var(--border-color)",
    fontSize: 12,
    fontWeight: 700,
    color: "var(--text-primary)",
    position: "sticky" as const,
    top: 0,
  },
  td: {
    padding: "6px 10px",
    borderBottom: "1px solid var(--border-color)",
    fontSize: 12,
    color: "var(--text-primary)",
  },
};
