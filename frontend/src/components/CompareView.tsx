import { useCallback, useEffect, useMemo, useState } from "react";
import { testRunsApi } from "../api";
import type { TestRun, TestResult } from "../types";
import toast from "react-hot-toast";

interface Props {
  projectId: number;
}

const resultColors: Record<string, { bg: string; fg: string }> = {
  PASS: { bg: "rgba(26, 127, 55, 0.15)", fg: "#22C55E" },
  FAIL: { bg: "rgba(207, 34, 46, 0.15)", fg: "#EF4444" },
  BLOCK: { bg: "rgba(191, 135, 0, 0.15)", fg: "#EAB308" },
  "N/A": { bg: "rgba(107, 114, 128, 0.15)", fg: "#9CA3AF" },
};

function displayResult(val: string) {
  if (!val || val === "NS") return "";
  if (val === "NA") return "N/A";
  return val;
}

export default function CompareView({ projectId }: Props) {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [leftRunId, setLeftRunId] = useState<number | null>(null);
  const [rightRunId, setRightRunId] = useState<number | null>(null);
  const [leftResults, setLeftResults] = useState<TestResult[]>([]);
  const [rightResults, setRightResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<"all" | "changed" | "regression">("all");

  useEffect(() => {
    testRunsApi.list(projectId).then(setRuns).catch(() => toast.error("수행 목록 로드 실패"));
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
      toast.error("결과 로드 실패");
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
          <label style={styles.selectorLabel}>기준 수행 (Left)</label>
          <select
            style={styles.selector}
            value={leftRunId || ""}
            onChange={(e) => setLeftRunId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">선택...</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
        <span style={{ fontSize: 20, color: "#94A3B8", fontWeight: 700 }}>vs</span>
        <div style={styles.selectorGroup}>
          <label style={styles.selectorLabel}>비교 수행 (Right)</label>
          <select
            style={styles.selector}
            value={rightRunId || ""}
            onChange={(e) => setRightRunId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">선택...</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} (R{r.round})
              </option>
            ))}
          </select>
        </div>
      </div>

      {(!leftRunId || !rightRunId) && (
        <div style={styles.placeholder}>두 개의 테스트 수행을 선택하면 비교 결과가 표시됩니다.</div>
      )}

      {leftRunId && rightRunId && !loading && comparedRows.length > 0 && (
        <>
          {/* Stats */}
          <div style={styles.statsBar}>
            <span style={styles.statBadge}>전체 {stats.total}</span>
            <span style={{ ...styles.statBadge, backgroundColor: "#FEF3C7", color: "#92400E" }}>
              변경 {stats.changed}
            </span>
            <span style={{ ...styles.statBadge, backgroundColor: "#FEE2E2", color: "#991B1B" }}>
              퇴보 {stats.regression}
            </span>
            <span style={{ ...styles.statBadge, backgroundColor: "#DCFCE7", color: "#166534" }}>
              개선 {stats.improved}
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
                  {mode === "all" ? "전체" : mode === "changed" ? "변경만" : "퇴보만"}
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
                  <th style={{ ...styles.th, width: 60, textAlign: "center" }}>변경</th>
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
        <div style={styles.placeholder}>비교 데이터를 불러오는 중...</div>
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
    backgroundColor: "#2D4A7A",
    color: "#fff",
    borderColor: "#2D4A7A",
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
