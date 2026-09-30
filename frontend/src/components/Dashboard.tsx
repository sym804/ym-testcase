import { useCallback, useEffect, useMemo, useState } from "react";
import { daysAgo } from "../utils/localDate";
import { useTranslation } from "react-i18next";
import { Doughnut, Bar, Line } from "react-chartjs-2";
import { dashboardApi, testRunsApi } from "../api";
import { useTheme } from "../contexts/ThemeContext";
import type {
  DashboardSummary,
  PriorityDistribution,
  CategoryBreakdown,
  RoundComparison,
  TestRun,
} from "../types";
import toast from "react-hot-toast";
import { PRIORITY_OPTIONS, priorityDisplayMap } from "../utils/priority";
import { versionGroups, versionKey } from "../utils/version";

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
  const { t } = useTranslation("dashboard");
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
  const [heatmap, setHeatmap] = useState<{ category: string; priority: string; fail_count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  // 라운드별 비교·추이가 묶을 수행 이름. 비우면 위에서 고른 수행의 이름, 그것도 없으면
  // 서버가 가장 최근 수행의 이름을 쓴다.
  const [trendName, setTrendName] = useState<string>("");
  // 버전 묶음. 비우면 전체. 수행 목록 트리와 같은 묶음 규칙이라 v1.5 와 1.5 는 하나다(09-30).
  const [selectedVersion, setSelectedVersion] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // 위에서 수행을 고르면 그 수행의 회차 추이를 본다
      const selectedName = runs.find((x) => x.id === selectedRunId)?.name;
      const ver = selectedVersion || undefined;
      const [s, p, c, r, h, runList] = await Promise.all([
        dashboardApi.summary(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined, ver),
        dashboardApi.priority(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined, ver),
        dashboardApi.category(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined, ver),
        dashboardApi.rounds(projectId, dateFrom || undefined, dateTo || undefined, trendName || selectedName || undefined, ver),
        dashboardApi.heatmap(projectId, selectedRunId, dateFrom || undefined, dateTo || undefined, ver),
        testRunsApi.list(projectId),
      ]);
      setSummary(s);
      setPriority(p);
      setCategory(c);
      setRounds(r);
      setHeatmap(h);
      setRuns(runList);
    } catch (err) {
      console.error(err);
      toast.error(t("loadFailed"));
    } finally {
      setLoading(false);
    }
    // runs 는 목록을 받은 뒤 갱신되므로 의존성에 넣지 않는다(넣으면 다시 불러오기를 되풀이한다)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, selectedRunId, dateFrom, dateTo, trendName, selectedVersion]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading || !summary) {
    return (
      <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
        {t("common:loadingData")}
      </div>
    );
  }

  const doughnutData = {
    labels: ["PASS", "FAIL", "BLOCK", "N/A", t("notStarted")],
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
      {
        // 진행 중인 회차가 빈 막대로 보이지 않게 미수행도 쌓는다
        label: t("notStarted"),
        data: rounds.map((r) => r.not_started ?? 0),
        backgroundColor: CARD_COLORS.not_started,
      },
    ],
  };

  // 합격률은 서버 값(PASS / 수행분)을 그대로 쓴다. 리포트·요약 카드와 같은 숫자다.
  // 실행이 0건인 회차는 null 이라 점을 찍지 않는다. 진행 중인 회차는 속이 빈 점이다.
  const inProgress = rounds.map((r) => r.status === "in_progress");
  const trendPoint = (color: string) => ({
    borderColor: color,
    pointBackgroundColor: inProgress.map((p) => (p ? (isDark ? "#1E2230" : "#FFFFFF") : color)),
    pointBorderColor: color,
    pointBorderWidth: 2,
    tension: 0,
    fill: false,
    spanGaps: false,
    pointRadius: 5,
    pointHoverRadius: 7,
  });
  // x 축은 회차와 날짜. "R1, R2" 만으로는 언제 수행한 것인지 알 수 없었다(09-30 지적).
  const roundLabel = (r: { round: number; created_at?: string | null }) =>
    r.created_at ? `R${r.round} (${r.created_at.slice(5, 10)})` : `R${r.round}`;
  const trendData = {
    labels: rounds.map(roundLabel),
    datasets: [
      { label: t("trendPass"), data: rounds.map((r) => r.pass_rate), ...trendPoint(CARD_COLORS.pass) },
      { label: t("trendFail"), data: rounds.map((r) => r.fail_rate ?? null), ...trendPoint(CARD_COLORS.fail) },
    ],
  };
  const executedRounds = rounds.filter((r) => (r.executed ?? r.pass + r.fail + r.block) > 0).length;
  const roundName = rounds[0]?.name;
  // 버전을 고르면 수행 선택과 회차 차트의 테스트 목록도 그 버전 안에서만 고른다
  const versions = versionGroups(runs);
  const runsInScope = selectedVersion ? runs.filter((r) => versionKey(r.version) === selectedVersion) : runs;
  const runNames = [...new Set(runsInScope.map((r) => r.name))];
  const selectedRun = runs.find((r) => r.id === selectedRunId);
  const scopeText = [
    selectedVersion ? (versions.find((v) => v.key === selectedVersion)?.label || t("versionNone")) : t("versionAll"),
    selectedRun ? `${selectedRun.name} (R${selectedRun.round})` : t("scopeLatest"),
    dateFrom ? `${dateFrom} ~ ${dateTo || t("today")}` : t("periodAll"),
  ].join(" · ");

  // 툴팁에 어떤 수행인지와 실행 건수를 싣는다. x 축의 R1, R2 만으로는 알 수 없다.
  const roundTooltip = {
    callbacks: {
      title: (items: { dataIndex: number }[]) => {
        const r = rounds[items[0]?.dataIndex ?? 0];
        return r ? `${r.name ?? ""} (R${r.round})` : "";
      },
      afterTitle: (items: { dataIndex: number }[]) => {
        const r = rounds[items[0]?.dataIndex ?? 0];
        if (!r) return "";
        const executed = r.executed ?? r.pass + r.fail + r.block;
        const state = r.status === "in_progress" ? t("inProgress") : t("completed");
        // 비율의 근거가 되는 건수를 같이 보여 준다
        return `${state} · ${t("executedOf", { executed, total: r.total })} · PASS ${r.pass} · FAIL ${r.fail} · BLOCK ${r.block}`;
      },
    },
  };

  const cards = [
    { label: t("totalTC"), value: summary.total, pct: 100, color: CARD_COLORS.total },
    { label: "PASS", value: summary.pass, pct: summary.pass_rate, color: CARD_COLORS.pass },
    { label: "FAIL", value: summary.fail, pct: summary.fail_rate, color: CARD_COLORS.fail },
    { label: "BLOCK", value: summary.block, pct: summary.block_rate, color: CARD_COLORS.block },
    { label: "N/A", value: summary.na, pct: summary.na_rate, color: CARD_COLORS.na },
    {
      label: t("notStarted"),
      value: summary.not_started,
      pct: summary.not_started_rate,
      color: CARD_COLORS.not_started,
    },
  ];

  return (
    <div>
      {/* Version + run selector. 버전 묶음 -> 수행 순으로 좁힌다(수행 목록 트리와 같은 층) */}
      <div style={styles.selectorRow}>
        <label style={styles.selectorLabel}>{t("version")}</label>
        <select
          style={styles.select}
          value={selectedVersion}
          aria-label={t("versionFilter")}
          data-testid="version-select"
          onChange={(e) => {
            setSelectedVersion(e.target.value);
            // 버전을 변경하면 그 버전 밖의 수행 · 테스트 선택은 푼다
            setSelectedRunId(undefined);
            setTrendName("");
          }}
        >
          <option value="">{t("versionAll")}</option>
          {versions.map((v) => (
            <option key={v.key || "__none"} value={v.key}>{v.label || t("versionNone")}</option>
          ))}
        </select>
        <label style={{ ...styles.selectorLabel, marginLeft: 12 }}>{t("testRun")}</label>
        <select
          style={styles.select}
          value={selectedRunId ?? ""}
          aria-label={t("runFilter")}
          onChange={(e) => {
            setSelectedRunId(e.target.value ? Number(e.target.value) : undefined);
            // 수행을 변경하면 회차 차트도 그 수행의 테스트로 돌아간다
            setTrendName("");
          }}
        >
          <option value="">{t("all")}</option>
          {selectedVersion
            ? runsInScope.map((r) => (
                <option key={r.id} value={r.id}>{r.name} (R{r.round})</option>
              ))
            : versions.map((v) => (
                <optgroup key={v.key || "__none"} label={v.label || t("versionNone")}>
                  {runs.filter((r) => versionKey(r.version) === v.key).map((r) => (
                    <option key={r.id} value={r.id}>{r.name} (R{r.round})</option>
                  ))}
                </optgroup>
              ))}
        </select>

        {/* 날짜 필터 */}
        <div style={{ display: "flex", gap: 4, marginLeft: 12, alignItems: "center" }}>
          {[
            { label: t("all"), from: "", to: "" },
            { label: t("days7"), from: daysAgo(7), to: "" },
            { label: t("days30"), from: daysAgo(30), to: "" },
            { label: t("days90"), from: daysAgo(90), to: "" },
          ].map((p) => (
            <button
              key={p.label}
              onClick={() => { setDateFrom(p.from); setDateTo(p.to); }}
              style={{
                padding: "4px 10px",
                fontSize: 12,
                borderRadius: 4,
                border: "1px solid var(--border-color)",
                backgroundColor: dateFrom === p.from && dateTo === p.to ? "var(--accent)" : "var(--bg-card)",
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
            backgroundColor: "var(--bg-input)", color: "var(--text-primary)", marginLeft: 8,
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
            backgroundColor: "var(--bg-input)", color: "var(--text-primary)",
          }}
        />
      </div>

      <div style={styles.scopeNote} data-testid="scope-note">{t("scopeNote", { scope: scopeText })}</div>

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
          <h4 style={styles.chartTitle}>{t("resultDistribution")}</h4>
          <div style={{ maxWidth: 320, margin: "0 auto" }}>
            <Doughnut
              data={doughnutData}
              options={{ plugins: { legend: { position: "bottom", labels: { color: chartTextColor } } }, maintainAspectRatio: true }}
            />
          </div>
        </div>
        <div style={styles.chartCard}>
          <div style={styles.chartHeader}>
            <h4 style={{ ...styles.chartTitle, margin: 0 }}>{t("roundComparison")}</h4>
            {runNames.length > 0 && (
              <select
                data-testid="round-group"
                aria-label={t("roundGroup")}
                style={{ ...styles.select, minWidth: 200, fontSize: 12, padding: "4px 8px" }}
                value={trendName || roundName || ""}
                onChange={(e) => setTrendName(e.target.value)}
              >
                {runNames.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            )}
          </div>
          <Bar
            data={barData}
            options={{
              plugins: { legend: { position: "top", labels: { color: chartTextColor } }, tooltip: roundTooltip },
              scales: {
                x: { stacked: true, ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
                y: { stacked: true, beginAtZero: true, ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
              },
              maintainAspectRatio: true,
            }}
          />
        </div>
      </div>

      {/* 회차 추이와 결함 히트맵을 한 줄에 절반씩. 추이는 선 둘이라 전체 폭이 남았다(09-30 지적).
          실행한 회차가 둘 이상일 때만 추이를 그리고, 하나만 있으면 그것이 전체 폭을 쓴다 */}
      {(executedRounds > 1 || heatmap.length > 0) && (
      <div
        style={{ ...styles.chartsRow, gridTemplateColumns: executedRounds > 1 && heatmap.length > 0 ? "1fr 1fr" : "1fr" }}
        data-testid="trend-heatmap-row"
      >
      {executedRounds > 1 && (
        <div style={styles.chartCard} data-testid="pass-fail-trend">
          <h4 style={styles.chartTitle}>
            {t("passFailTrend")}
            {roundName ? <span style={styles.chartSubtitle}> · {roundName}</span> : null}
          </h4>
          {/* 무엇을 나눈 값인지 밝힌다. 제목과 R1 · R2 만으로는 기준을 알 수 없다 */}
          <div style={styles.chartNote} data-testid="trend-basis">
            {t("trendBasis", { first: rounds[0]?.round ?? 1, last: rounds[rounds.length - 1]?.round ?? 1 })}
          </div>
          <Line
            data={trendData}
            options={{
              plugins: {
                legend: { position: "top", labels: { color: chartTextColor } },
                tooltip: {
                  ...roundTooltip,
                  callbacks: {
                    ...roundTooltip.callbacks,
                    label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
                      `${ctx.dataset.label}: ${ctx.parsed.y == null ? "-" : `${ctx.parsed.y}%`}`,
                  },
                },
              },
              scales: {
                x: { ticks: { color: chartTextColor }, grid: { color: chartGridColor } },
                y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%`, color: chartTextColor }, grid: { color: chartGridColor } },
              },
              maintainAspectRatio: true,
            }}
          />
        </div>
      )}
      {heatmap.length > 0 && (
        <HeatmapTable
          data={heatmap}
          scopeLabel={
            selectedRunId
              ? (() => { const r = runs.find((x) => x.id === selectedRunId); return r ? `${r.name} (R${r.round})` : ""; })()
              : t("heatmapScopeLatest")
          }
        />
      )}
      </div>
      )}

      {/* Tables */}
      <div style={styles.tablesRow}>
        {/* Priority table */}
        <div style={styles.tableCard}>
          <h4 style={styles.tableTitle}>{t("priorityDistribution")}</h4>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Priority</th>
                <th style={styles.thNum}>Total</th>
                <th style={styles.thNum}>PASS</th>
                <th style={styles.thNum}>FAIL</th>
                <th style={styles.thNum}>BLOCK</th>
                <th style={styles.thNum}>N/A</th>
                <th style={styles.thNum}>{t("notStarted")}</th>
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
          <h4 style={styles.tableTitle}>{t("categoryDistribution")}</h4>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Category</th>
                <th style={styles.thNum}>Total</th>
                <th style={styles.thNum}>PASS</th>
                <th style={styles.thNum}>FAIL</th>
                <th style={styles.thNum}>BLOCK</th>
                <th style={styles.thNum}>N/A</th>
                <th style={styles.thNum}>{t("notStarted")}</th>
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

    </div>
  );
}

type HeatCell = { category: string; priority: string; fail_count: number };

/**
 * FAIL 건수를 카테고리 x 우선순위로 본다.
 *
 * ★우선순위 열은 심각도 순(매우 높음 -> 낮음)이다. 예전에는 글자순이라 낮음, 높음,
 *   매우 높음, 보통 으로 섞였다.
 * ★색은 FAIL 색 한 가지를 진하기로만 나눈다. 예전 네 색(노랑~빨강)은 최대값이 2 면
 *   1건이 주황, 2건이 빨강 원색이라 요란했고 옅은 칸에도 흰 글자라 읽기 어려웠다.
 * 행은 FAIL 이 많은 카테고리부터 둔다. 어디에 몰렸는지 위에서 바로 보인다.
 */
function HeatmapTable({ data, scopeLabel }: { data: HeatCell[]; scopeLabel: string }) {
  const { t } = useTranslation("dashboard");
  const { t: tcT } = useTranslation("testcase");
  const priorityDisplay = useMemo(() => priorityDisplayMap(tcT), [tcT]);

  const { rows, priorities, colTotals, total, maxVal } = useMemo(() => {
    const grid: Record<string, Record<string, number>> = {};
    const priSet = new Set<string>();
    let max = 0;
    data.forEach((d) => {
      (grid[d.category] ??= {})[d.priority] = d.fail_count;
      priSet.add(d.priority);
      max = Math.max(max, d.fail_count);
    });
    // 아는 우선순위는 심각도 순, 모르는 값은 글자순, 빈 값(미지정)은 맨 끝
    const known = PRIORITY_OPTIONS.filter((p) => priSet.has(p));
    const unknown = [...priSet].filter((p) => p && !PRIORITY_OPTIONS.includes(p)).sort();
    const pris = [...known, ...unknown, ...(priSet.has("") ? [""] : [])];
    const rowList = Object.entries(grid)
      .map(([category, cells]) => ({
        category,
        cells,
        total: Object.values(cells).reduce((a, b) => a + b, 0),
      }))
      .sort((a, b) => b.total - a.total || a.category.localeCompare(b.category, "ko"));
    const cols = pris.map((p) => rowList.reduce((sum, r) => sum + (r.cells[p] ?? 0), 0));
    return {
      rows: rowList,
      priorities: pris,
      colTotals: cols,
      total: cols.reduce((a, b) => a + b, 0),
      maxVal: max,
    };
  }, [data]);

  // 1건도 보이게 최소 18%, 최대값은 85% 진하기
  const intensity = (count: number) => (maxVal ? 18 + Math.round((count / maxVal) * 67) : 0);
  const cellStyle = (count: number): React.CSSProperties => {
    if (!count) return hm.cell;
    const pct = intensity(count);
    return {
      ...hm.cell,
      backgroundColor: `color-mix(in srgb, var(--color-fail) ${pct}%, transparent)`,
      color: pct >= 55 ? "#fff" : "var(--text-primary)",
      fontWeight: 700,
    };
  };
  const priorityLabel = (p: string) => (p ? (priorityDisplay[p] ?? p) : t("unsetPriority"));

  return (
    <div style={hm.card} data-testid="heatmap">
      <div style={hm.header}>
        <div>
          <h4 style={hm.title}>{t("heatmapTitle")}</h4>
          <div style={hm.subtitle}>{t("heatmapSubtitle", { scope: scopeLabel, total })}</div>
        </div>
        {/* 진하기 범례. 칸의 숫자가 곧 FAIL 건수라 눈금은 최소·최대만 둔다 */}
        <div style={hm.legend} aria-hidden="true">
          <span>1</span>
          {[18, 40, 62, 85].map((pct) => (
            <span
              key={pct}
              style={{ ...hm.legendSwatch, backgroundColor: `color-mix(in srgb, var(--color-fail) ${pct}%, transparent)` }}
            />
          ))}
          <span>{maxVal}</span>
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={hm.table}>
          <thead>
            <tr>
              <th style={{ ...hm.th, textAlign: "left" }}>{t("category")}</th>
              {priorities.map((p) => (
                <th key={p || "__unset"} style={hm.th}>{priorityLabel(p)}</th>
              ))}
              <th style={{ ...hm.th, ...hm.totalHead }}>{t("total")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.category || "__unset"} data-testid={`heatmap-row-${row.category || "unset"}`}>
                <td style={hm.rowHead}>{row.category || t("unsetCategory")}</td>
                {priorities.map((p) => {
                  const count = row.cells[p] ?? 0;
                  return (
                    <td key={p || "__unset"} style={cellStyle(count)}>
                      {count || ""}
                    </td>
                  );
                })}
                <td style={{ ...hm.cell, ...hm.totalCell }}>{row.total}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td style={{ ...hm.rowHead, ...hm.totalRow }}>{t("total")}</td>
              {colTotals.map((n, i) => (
                <td key={priorities[i] || "__unset"} style={{ ...hm.cell, ...hm.totalCell, ...hm.totalRow }}>{n}</td>
              ))}
              <td style={{ ...hm.cell, ...hm.totalCell, ...hm.totalRow }}>{total}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

const hm: Record<string, React.CSSProperties> = {
  card: { backgroundColor: "var(--bg-card)", borderRadius: 12, padding: 24, boxShadow: "var(--shadow)", border: "1px solid var(--border-color)", minWidth: 0 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap", marginBottom: 16 },
  title: { margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text-primary)" },
  subtitle: { marginTop: 4, fontSize: 12, color: "var(--text-secondary)" },
  legend: { display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--text-secondary)" },
  legendSwatch: { width: 18, height: 12, borderRadius: 3, display: "inline-block" },
  // 칸 사이를 띄워 격자선 없이 칸만으로 읽히게 한다
  // 칸이 화면 폭만큼 늘어나면 한 칸이 200px 가 넘어 색 덩어리만 보인다. 내용 폭으로 둔다
  table: { borderCollapse: "separate", borderSpacing: 4, fontSize: 13 },
  th: { padding: "6px 8px", textAlign: "center", color: "var(--text-secondary)", fontWeight: 600, fontSize: 12, whiteSpace: "nowrap" },
  rowHead: { padding: "6px 8px", color: "var(--text-primary)", fontWeight: 500, whiteSpace: "nowrap" },
  cell: {
    padding: "6px 8px",
    textAlign: "center",
    borderRadius: 6,
    // 빈 칸도 격자가 보이게 옅게 칠한다. 라이트 테마에서 --bg-input 은 카드와 같은 흰색이다
    backgroundColor: "color-mix(in srgb, var(--text-secondary) 8%, transparent)",
    color: "var(--text-secondary)",
    minWidth: 88,
    fontVariantNumeric: "tabular-nums",
  },
  totalHead: { color: "var(--text-primary)" },
  totalCell: { backgroundColor: "transparent", color: "var(--text-primary)", fontWeight: 700 },
  totalRow: { paddingTop: 10 },
};

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
  chartHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap" as const,
    marginBottom: 12,
  },
  chartSubtitle: { fontWeight: 500, color: "var(--text-secondary)", fontSize: 13 },
  chartNote: { fontSize: 12, color: "var(--text-secondary)", margin: "-6px 0 10px" },
  scopeNote: { fontSize: 12, color: "var(--text-secondary)", margin: "-12px 0 16px" },
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
