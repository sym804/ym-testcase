import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TestRunStatus } from "../types";
import type { TestRun } from "../types";
import { versionKey } from "../utils/version";

/**
 * 수행 목록 트리. 버전 -> 수행 이름 -> 회차 세 단계로 묶고, 버전과 이름은 펼치고 접는다.
 *
 * 예전 목록은 생성일 역순 한 줄 목록이라 수행이 늘수록 같은 이름의 회차가 흩어지고,
 * 환경·진행률은 상세를 열어야 보였다(09-30 사용자 지적). 회차 행에 환경 · 상태 · 진행률을
 * 함께 보여 주고, 위에 검색과 상태 · 환경 필터를 둔다.
 *
 * 버전은 "v1.5" 와 "1.5" 를 같은 묶음으로 본다(앞 v 와 대소문자 · 공백 무시). 표시는 그
 * 묶음에서 가장 최근 수행의 표기다. 진행 중인 수행이 하나라도 있는 버전만 처음에 펼친다.
 */
interface Props {
  runs: TestRun[];
  selectedRunId: number | null;
  onSelect: (run: TestRun) => void;
}

/** 환경도 대소문자를 무시해 묶는다("Prod" 와 "prod" 는 하나). 표시는 처음 만난 표기다(09-30 지시) */
function envKey(env: string | null | undefined): string {
  return (env ?? "").trim().toLowerCase();
}

const progressOf = (run: TestRun) =>
  run.tc_total ? Math.round(((run.tc_executed ?? 0) / run.tc_total) * 100) : null;

export default function RunTreePanel({ runs, selectedRunId, onSelect }: Props) {
  const { t } = useTranslation("testrun");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"" | TestRunStatus>("");
  const [env, setEnv] = useState("");
  // 사용자가 손으로 펼치거나 접은 버전. 없으면 기본값(진행 중 수행이 있으면 펼침)을 따른다.
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [seriesToggled, setSeriesToggled] = useState<Record<string, boolean>>({});

  const envs = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of runs) {
      const key = envKey(r.environment);
      if (key && !seen.has(key)) seen.set(key, (r.environment || "").trim());
    }
    return [...seen.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [runs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return runs.filter((r) =>
      (!q || r.name.toLowerCase().includes(q))
      && (!status || r.status === status)
      && (!env || envKey(r.environment) === env));
  }, [runs, query, status, env]);

  // 버전 -> 이름 -> 회차. 버전은 가장 최근 수행 순, 이름도 가장 최근 수행 순, 회차는 큰 것부터.
  const tree = useMemo(() => {
    const byVersion = new Map<string, { label: string; latest: string; series: Map<string, TestRun[]> }>();
    for (const run of filtered) {
      const key = versionKey(run.version);
      let v = byVersion.get(key);
      if (!v) {
        v = { label: (run.version || "").trim(), latest: run.created_at, series: new Map() };
        byVersion.set(key, v);
      }
      if (run.created_at > v.latest) {
        v.latest = run.created_at;
        v.label = (run.version || "").trim();
      }
      const list = v.series.get(run.name) ?? [];
      list.push(run);
      v.series.set(run.name, list);
    }
    return [...byVersion.entries()]
      .sort((a, b) => (a[1].latest < b[1].latest ? 1 : -1))
      .map(([key, v]) => ({
        key,
        label: v.label || t("noVersion"),
        series: [...v.series.entries()]
          .map(([name, list]) => ({
            name,
            runs: [...list].sort((a, b) => b.round - a.round || (a.created_at < b.created_at ? 1 : -1)),
            latest: list.reduce((m, r) => (r.created_at > m ? r.created_at : m), ""),
          }))
          .sort((a, b) => (a.latest < b.latest ? 1 : -1)),
      }));
  }, [filtered, t]);

  const isOpen = (key: string, runsIn: TestRun[]) =>
    key in toggled ? toggled[key] : runsIn.some((r) => r.status !== TestRunStatus.COMPLETED);
  const seriesOpen = (key: string) => (key in seriesToggled ? seriesToggled[key] : true);

  return (
    <div style={s.wrap} data-testid="run-tree">
      <div style={s.filters}>
        <input
          style={s.search}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchRuns")}
          aria-label={t("searchRuns")}
        />
        <div style={s.filterRow}>
          <select style={s.select} value={status} onChange={(e) => setStatus(e.target.value as "" | TestRunStatus)} aria-label={t("statusFilter")}>
            <option value="">{t("statusAll")}</option>
            <option value={TestRunStatus.IN_PROGRESS}>{t("statusInProgressOnly")}</option>
            <option value={TestRunStatus.COMPLETED}>{t("statusCompletedOnly")}</option>
          </select>
          {envs.length > 0 && (
            <select style={s.select} value={env} onChange={(e) => setEnv(e.target.value)} aria-label={t("envFilter")}>
              <option value="">{t("envAll")}</option>
              {envs.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          )}
        </div>
      </div>

      <div style={s.list}>
        {tree.length === 0 ? (
          <div style={s.empty}>{t("noMatchingRuns")}</div>
        ) : tree.map((v) => {
          const all = v.series.flatMap((x) => x.runs);
          const open = isOpen(v.key, all);
          const active = all.filter((r) => r.status !== TestRunStatus.COMPLETED).length;
          return (
            <div key={v.key} data-testid={`version-${v.key || "none"}`}>
              <button
                type="button"
                style={s.versionRow}
                onClick={() => setToggled({ ...toggled, [v.key]: !open })}
                aria-expanded={open}
              >
                <span style={s.caret}>{open ? "▾" : "▸"}</span>
                <span style={s.versionLabel}>{v.label}</span>
                <span style={s.versionCount}>
                  {active > 0 ? t("versionCountActive", { count: all.length, active }) : t("versionCount", { count: all.length })}
                </span>
              </button>
              {open && v.series.map((sr) => {
                const sKey = `${v.key}::${sr.name}`;
                const sOpen = seriesOpen(sKey);
                return (
                  <div key={sr.name} style={s.series} data-testid={`series-${sr.name}`}>
                    <div style={s.seriesRow}>
                      {sr.runs.length > 1 ? (
                        <button
                          type="button"
                          style={s.seriesCaret}
                          onClick={() => setSeriesToggled({ ...seriesToggled, [sKey]: !sOpen })}
                          aria-expanded={sOpen}
                          aria-label={t("toggleSeries", { name: sr.name })}
                        >
                          {sOpen ? "▾" : "▸"}
                        </button>
                      ) : (
                        <span style={s.seriesCaret} />
                      )}
                      {/* 이름을 누르면 가장 최근 회차를 연다 */}
                      <button type="button" style={s.seriesName} onClick={() => onSelect(sr.runs[0])} title={sr.name}>
                        {sr.name}
                      </button>
                      {sr.runs.length > 1 && <span style={s.seriesCount}>{t("roundCount", { count: sr.runs.length })}</span>}
                    </div>
                    {sOpen && sr.runs.map((run) => {
                      const pct = progressOf(run);
                      const done = run.status === TestRunStatus.COMPLETED;
                      return (
                        <button
                          type="button"
                          key={run.id}
                          style={{ ...s.runRow, ...(selectedRunId === run.id ? s.runRowActive : {}) }}
                          onClick={() => onSelect(run)}
                          data-testid={`run-row-${run.id}`}
                        >
                          <span style={s.round}>R{run.round}</span>
                          <span style={s.env}>{run.environment || "-"}</span>
                          <span style={{ ...s.status, color: done ? "var(--color-pass)" : "var(--color-link)" }}>
                            {done ? t("completed") : t("inProgress")}
                          </span>
                          <span style={s.pct}>{pct === null ? "" : `${pct}%`}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", flexDirection: "column", flex: 1, minHeight: 0 },
  filters: { padding: "8px 8px 6px", borderBottom: "1px solid var(--border-color)", display: "flex", flexDirection: "column", gap: 6 },
  search: {
    width: "100%", boxSizing: "border-box", padding: "6px 8px", borderRadius: 6, fontSize: 12,
    border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)",
  },
  filterRow: { display: "flex", gap: 6 },
  select: {
    flex: 1, minWidth: 0, padding: "4px 6px", borderRadius: 6, fontSize: 11,
    border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)",
  },
  list: { flex: 1, overflow: "auto", padding: "6px 8px" },
  empty: { textAlign: "center", color: "var(--text-secondary)", padding: 20, fontSize: 13 },
  versionRow: {
    display: "flex", alignItems: "center", gap: 6, width: "100%", padding: "7px 6px", marginTop: 4,
    border: "none", borderRadius: 6, backgroundColor: "var(--bg-page)", cursor: "pointer", textAlign: "left",
    color: "var(--text-primary)", fontSize: 13, fontWeight: 700,
  },
  caret: { width: 12, color: "var(--text-secondary)", fontSize: 11 },
  versionLabel: { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  versionCount: { fontSize: 11, fontWeight: 500, color: "var(--text-secondary)", whiteSpace: "nowrap" },
  series: { marginLeft: 8, marginTop: 4 },
  seriesRow: { display: "flex", alignItems: "center", gap: 2 },
  seriesCaret: {
    width: 14, minWidth: 14, border: "none", background: "none", padding: 0, cursor: "pointer",
    color: "var(--text-secondary)", fontSize: 11,
  },
  seriesName: {
    flex: 1, minWidth: 0, border: "none", background: "none", padding: "4px 4px", cursor: "pointer", textAlign: "left",
    color: "var(--text-primary)", fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
  },
  seriesCount: { fontSize: 11, color: "var(--text-secondary)", whiteSpace: "nowrap", paddingRight: 4 },
  // ★선택은 테두리 없이 배경색만(09-30 사용자 지적, 그리드 행 호버와 같은 --primary-light).
  //   배경은 축약형(background)이 아니라 backgroundColor 로만 쓴다. 선택 스타일과 같은 속성이어야
  //   React 가 선택 해제 때 값을 되돌린다. 축약형과 섞이면 해제된 행에 회색 배경이 남는다.
  runRow: {
    display: "flex", alignItems: "center", gap: 6, width: "calc(100% - 14px)", marginLeft: 14, padding: "5px 8px",
    borderWidth: 0, borderRadius: 6, backgroundColor: "transparent", cursor: "pointer", textAlign: "left",
    color: "var(--text-primary)", fontSize: 12,
  },
  runRowActive: { backgroundColor: "var(--primary-light)" },
  round: { fontWeight: 700, minWidth: 24 },
  env: { flex: 1, minWidth: 0, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  status: { fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" },
  pct: { minWidth: 34, textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)", fontSize: 11 },
};
