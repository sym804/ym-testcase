import { useCallback, useEffect, useMemo, useState } from "react";
import { Doughnut, Bar, Line } from "react-chartjs-2";
import { dashboardApi, testRunsApi } from "../api";
import { useTheme } from "../contexts/ThemeContext";
import type {
  DashboardSummary,
  PriorityDistribution,
  CategoryBreakdown,
  RoundComparison,
  AssigneeSummary,
  TestRun,
} from "../types";
import toast from "react-hot-toast";

interface Props {
  projectId: number;
}

const COLORS_LIGHT = {
  total: "#2563EB",
  pass: "#1A7F37",
  fail: "#CF222E",
  block: "#BF8700",
  na: "#6366F1",
  not_started: "#D1D5DB",
};

const COLORS_DARK = {
  total: "#60A5FA",
  pass: "#22C55E",
  fail: "#EF4444",
  block: "#EAB308",
  na: "#818CF8",
  not_started: "#6B7280",
};

export default function Dashboard({ projectId }: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const CARD_COLORS = isDark ? COLORS_DARK : COLORS_LIGHT;
  const chartTextColor = isDark ? "#E2E8F0" : "#334155";
  const chartGridColor = isDark ? "rgba(45, 74, 122, 0.3)" : "rgba(0, 0, 0, 0.1)";
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | undefined>(undefined);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [priority, setPriority] = useState<PriorityDistribution[]>([]);
  const [category, setCategory] = useState<CategoryBreakdown[]>([]);
  const [rounds, setRounds] = useState<RoundComparison[]>([]);
  const [assignee, setAssignee] = useState<AssigneeSummary[]>([]);
  const [heatmap, setHeatmap] = useState<{ category: string; priority: string; fail_count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, p, c, r, a, h, runList] = await Promise.all([
        dashboardApi.summary(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
        dashboardApi.priority(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
        dashboardApi.category(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
        dashboardApi.rounds(projectId, dateFrom || undefined, dateTo || undefined),
        dashboardApi.assignee(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
        dashboardApi.heatmap(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined),
        testRunsApi.list(projectId),
      ]);
      setSummary(s);
      setPriority(p);
      setCategory(c);
      setRounds(r);
      setAssignee(a);
      setHeatmap(h);
      setRuns(runList);
    } catch (err) {
      console.error(err);
      toast.error("대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedRunId, dateFrom, dateTo]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading || !summary) {
    return (
      <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
        불러오는 중...
      </div>
    );
  }

  const doughnutData = {
    labels: ["PASS", "FAIL", "BLOCK", "N/A", "미수행"],
    datasets: [
      {
        data: [summary.pass, summary.fail, summary.block, summary.na, summary.not_started],
        backgroundColor: [
          CARD_COLORS.pass,
          CARD_COLORS.fail,
          CARD_COLORS.block,
          CARD_COLORS.na,
          CARD_COLORS.not_started,
        ],
        borderWidth: 0,
        borderColor: "transparent",
      },
    ],
  };

  const barData = {
    labels: rounds.map((r) => `R${r.round}`),
    datasets: [
      {
        label: "PASS",
        data: rounds.map((r) => r.pass),
        backgroundColor: CARD_COLORS.pass,
      },
      {
        label: "FAIL",
        data: rounds.map((r) => r.fail),
        backgroundColor: CARD_COLORS.fail,
      },
      {
        label: "BLOCK",
        data: rounds.map((r) => r.block),
        backgroundColor: CARD_COLORS.block,
      },
      {
        label: "N/A",
        data: rounds.map((r) => r.na),
        backgroundColor: CARD_COLORS.na,
      },
    ],
  };

  const trendData = {
    labels: rounds.map((r) => `R${r.round}`),
    datasets: [
      {
        label: "Pass Rate (%)",
        data: rounds.map((r) => {
          const total = r.pass + r.fail + r.block + r.na;
          return total > 0 ? Math.round((r.pass / total) * 100 * 10) / 10 : 0;
        }),
        borderColor: CARD_COLORS.pass,
        backgroundColor: "rgba(26, 127, 55, 0.1)",
        tension: 0.3,
        fill: true,
        pointRadius: 5,
        pointHoverRadius: 7,
      },
      {
        label: "Fail Rate (%)",
        data: rounds.map((r) => {
          const total = r.pass + r.fail + r.block + r.na;
          return total > 0 ? Math.round((r.fail / total) * 100 * 10) / 10 : 0;
        }),
        borderColor: CARD_COLORS.fail,
        backgroundColor: "rgba(207, 34, 46, 0.1)",
        tension: 0.3,
        fill: true,
        pointRadius: 5,
        pointHoverRadius: 7,
      },
    ],
  };

  const cards = [
    { label: "전체 TC", value: summary.total, pct: 100, color: CARD_COLORS.total },
    { label: "PASS", value: summary.pass, pct: summary.pass_rate, color: CARD_COLORS.pass },
    { label: "FAIL", value: summary.fail, pct: summary.fail_rate, color: CARD_COLORS.fail },
    { label: "BLOCK", value: summary.block, pct: summary.block_rate, color: CARD_COLORS.block },
    { label: "N/A", value: summary.na, pct: summary.na_rate, color: CARD_COLORS.na },
    {
      label: "미수행",
      value: summary.not_started,
      pct: summary.not_started_rate,
      color: CARD_COLORS.not_started,
    },
  ];

  return (
    <div>
      {/* Run selector */}
      <div style={styles.selectorRow}>
        <label style={styles.selectorLabel}>테스트 수행:</label>
        <select
          style={styles.select}
          value={selectedRunId ?? ""}
          onChange={(e) =>
            setSelectedRunId(e.target.value ? Number(e.target.value) : undefined)
          }
        >
          <option value="">전체</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name} (R{r.round})
            </option>
          ))}
        </select>

        {/* 날짜 필터 */}
        <div style={{ display: "flex", gap: 4, marginLeft: 12, alignItems: "center" }}>
          {[
            { label: "전체", from: "", to: "" },
            { label: "7일", from: new Date(Date.now() - 7 * 86400000).toISOString().split("T")[0], to: "" },
            { label: "30일", from: new Date(Date.now() - 30 * 86400000).toISOString().split("T")[0], to: "" },
            { label: "90일", from: new Date(Date.now() - 90 * 86400000).toISOString().split("T")[0], to: "" },
          ].map((p) => (
            <button
              key={p.label}
              onClick={() => { setDateFrom(p.from); setDateTo(p.to); }}
              style={{
                padding: "4px 10px",
                fontSize: 12,
                borderRadius: 4,
                border: "1px solid var(--border-color)",
                backgroundColor: dateFrom === p.from && dateTo === p.to ? "var(--primary-color)" : "var(--bg-secondary)",
                color: dateFrom === p.from && dateTo === p.to ? "#fff" : "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          style={{
            padding: "4px 8px", fontSize: 12,
            border: "1px solid var(--border-color)", borderRadius: 4,
            backgroundColor: "var(--bg-primary)", color: "var(--text-primary)", marginLeft: 8,
          }}
        />
        <span style={{ color: "var(--text-secondary)", margin: "0 4px" }}>~</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          style={{
            padding: "4px 8px", fontSize: 12,
            border: "1px solid var(--border-color)", borderRadius: 4,
            backgroundColor: "var(--bg-primary)", color: "var(--text-primary)",
          }}
        />
      </div>

      {/* Summary cards */}
      <div style={styles.cardGrid}>
        {cards.map((c) => (
          <div key={c.label} style={styles.card}>
            <div style={styles.cardLabel}>{c.label}</div>
            <div style={styles.cardValue}>{c.value}</div>
            <div style={styles.cardPct}>{c.pct.toFixed(1)}%</div>
            <div style={{ ...styles.cardAccent, backgroundColor: c.color }} />
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={styles.chartsRow}>
        <div style={styles.chartCard}>
          <h4 style={styles.chartTitle}>결과 분포</h4>
          <div style={{ maxWidth: 320, margin: "0 auto" }}>
            <Doughnut
              data={doughnutData}
              options={{ plugins: { legend: { position: "bottom", labels: { color: chartTextColor } } }, maintainAspectRatio: true }}
            />
          </div>
        </div>
        <div style={styles.chartCard}>
          <h4 style={styles.chartTitle}>라운드별 비교</h4>
          <Bar
            data={barData}
            options={{
              plugins: { legend: { position: "top", labels: { color: chartTextColor } } },
              scales: {
                x: { stacked: true, ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
                y: { stacked: true, beginAtZero: true, ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
              },
              maintainAspectRatio: true,
            }}
          />
        </div>
      </div>

      {/* Trend chart */}
      {rounds.length > 1 && (
        <div style={{ ...styles.chartCard, marginBottom: 28 }}>
          <h4 style={styles.chartTitle}>Pass/Fail Rate 추이</h4>
          <Line
            data={trendData}
            options={{
              plugins: { legend: { position: "top", labels: { color: chartTextColor } } },
              scales: {
                x: { ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
                y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%`, color: chartTextColor }, grid: { color: chartGridColor } },
              },
              maintainAspectRatio: true,
            }}
          />
        </div>
      )}

      {/* Tables */}
      <div style={styles.tablesRow}>
        {/* Priority table */}
        <div style={styles.tableCard}>
          <h4 style={styles.tableTitle}>우선순위별 분포</h4>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Priority</th>
                <th style={styles.thNum}>Total</th>
                <th style={styles.thNum}>PASS</th>
                <th style={styles.thNum}>FAIL</th>
                <th style={styles.thNum}>BLOCK</th>
                <th style={styles.thNum}>N/A</th>
                <th style={styles.thNum}>미수행</th>
              </tr>
            </thead>
            <tbody>
              {priority.map((row) => (
                <tr key={row.priority}>
                  <td style={styles.td}>{row.priority}</td>
                  <td style={styles.tdNum}>{row.total}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.pass }}>{row.pass}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.fail }}>{row.fail}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.block }}>{row.block}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.na }}>{row.na}</td>
                  <td style={styles.tdNum}>{row.not_started}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Category table */}
        <div style={styles.tableCard}>
          <h4 style={styles.tableTitle}>카테고리별 분포</h4>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Category</th>
                <th style={styles.thNum}>Total</th>
                <th style={styles.thNum}>PASS</th>
                <th style={styles.thNum}>FAIL</th>
                <th style={styles.thNum}>BLOCK</th>
                <th style={styles.thNum}>N/A</th>
                <th style={styles.thNum}>미수행</th>
              </tr>
            </thead>
            <tbody>
              {category.map((row) => (
                <tr key={row.category}>
                  <td style={styles.td}>{row.category}</td>
                  <td style={styles.tdNum}>{row.total}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.pass }}>{row.pass}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.fail }}>{row.fail}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.block }}>{row.block}</td>
                  <td style={{ ...styles.tdNum, color: CARD_COLORS.na }}>{row.na}</td>
                  <td style={styles.tdNum}>{row.not_started}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assignee table */}
      <div style={{ ...styles.tableCard, marginTop: 20 }}>
        <h4 style={styles.tableTitle}>담당자별 현황</h4>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>담당자</th>
              <th style={styles.thNum}>Total</th>
              <th style={styles.thNum}>PASS</th>
              <th style={styles.thNum}>FAIL</th>
              <th style={styles.thNum}>BLOCK</th>
              <th style={styles.thNum}>N/A</th>
              <th style={styles.thNum}>미수행</th>
              <th style={styles.thNum}>완료율</th>
            </tr>
          </thead>
          <tbody>
            {assignee.map((row) => (
              <tr key={row.assignee}>
                <td style={styles.td}>{row.assignee || "-"}</td>
                <td style={styles.tdNum}>{row.total}</td>
                <td style={{ ...styles.tdNum, color: CARD_COLORS.pass }}>{row.pass}</td>
                <td style={{ ...styles.tdNum, color: CARD_COLORS.fail }}>{row.fail}</td>
                <td style={{ ...styles.tdNum, color: CARD_COLORS.block }}>{row.block}</td>
                <td style={{ ...styles.tdNum, color: CARD_COLORS.na }}>{row.na}</td>
                <td style={styles.tdNum}>{row.not_started}</td>
                <td style={styles.tdNum}>{row.completion_rate.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Heatmap */}
      {heatmap.length > 0 && <HeatmapTable data={heatmap} />}
    </div>
  );
}

function HeatmapTable({ data }: { data: { category: string; priority: string; fail_count: number }[] }) {
  const { categories, priorities, grid, maxVal } = useMemo(() => {
    const catSet = new Set<string>();
    const priSet = new Set<string>();
    const map: Record<string, Record<string, number>> = {};
    let max = 0;
    data.forEach((d) => {
      catSet.add(d.category);
      priSet.add(d.priority);
      if (!map[d.category]) map[d.category] = {};
      map[d.category][d.priority] = d.fail_count;
      if (d.fail_count > max) max = d.fail_count;
    });
    return {
      categories: Array.from(catSet).sort(),
      priorities: Array.from(priSet).sort(),
      grid: map,
      maxVal: max,
    };
  }, [data]);

  const cellColor = (count: number) => {
    if (count === 0 || !maxVal) return "var(--bg-input)";
    const ratio = count / maxVal;
    if (ratio > 0.7) return "#DC2626";
    if (ratio > 0.4) return "#F97316";
    if (ratio > 0.1) return "#FBBF24";
    return "#FEF3C7";
  };

  return (
    <div style={{ marginTop: 20, backgroundColor: "var(--bg-card)", borderRadius: 12, padding: 24, boxShadow: "var(--shadow)" }}>
      <h4 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
        결함 밀집 히트맵 (Category x Priority)
      </h4>
      <div style={{ overflow: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>
          <thead>
            <tr>
              <th style={{ padding: "8px 10px", borderBottom: "2px solid var(--border-color)", textAlign: "left", color: "var(--text-secondary)", fontWeight: 600 }}>
                Category \ Priority
              </th>
              {priorities.map((p) => (
                <th key={p} style={{ padding: "8px 10px", borderBottom: "2px solid var(--border-color)", textAlign: "center", color: "var(--text-secondary)", fontWeight: 600 }}>
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((cat) => (
              <tr key={cat}>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", fontWeight: 600, color: "var(--text-primary)" }}>
                  {cat}
                </td>
                {priorities.map((pri) => {
                  const count = grid[cat]?.[pri] || 0;
                  return (
                    <td
                      key={pri}
                      style={{
                        padding: "8px 10px",
                        borderBottom: "1px solid var(--border-color)",
                        textAlign: "center",
                        fontWeight: 700,
                        color: count > 0 ? "#fff" : "#94A3B8",
                        backgroundColor: cellColor(count),
                        borderRadius: 4,
                      }}
                    >
                      {count || "-"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  selectorRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 20,
  },
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
  cardGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 16,
    marginBottom: 28,
  },
  card: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: "20px 16px 12px",
    position: "relative" as const,
    overflow: "hidden",
    boxShadow: "var(--shadow)",
    border: "1px solid var(--border-color)",
  },
  cardLabel: { fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 },
  cardValue: { fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 },
  cardPct: { fontSize: 14, color: "var(--text-secondary)" },
  cardAccent: {
    position: "absolute" as const,
    bottom: 0,
    left: 0,
    right: 0,
    height: 4,
  },
  chartsRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
    marginBottom: 28,
  },
  chartCard: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 24,
    boxShadow: "var(--shadow)",
    border: "1px solid var(--border-color)",
  },
  chartTitle: { margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "var(--text-primary)" },
  tablesRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
  },
  tableCard: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 24,
    boxShadow: "var(--shadow)",
    border: "1px solid var(--border-color)",
    overflow: "auto",
  },
  tableTitle: { margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "var(--text-primary)" },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: 13,
  },
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
    fontVariantNumeric: "tabular-nums",
  },
};
