import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { runIssuesApi } from "../api";
import type { IssueGroup, IssueTracker, IssueVerdict, RunIssue, RunIssueCandidate } from "../types";
import { ISSUE_GROUP_ORDER, ISSUE_VERDICTS } from "../types";
import { resolveIssueUrl } from "../utils/issueLink";

/**
 * 리포트의 이슈 섹션. 수행에 등록한 이슈를 보여 주고, 권한이 있으면 추가·수정·삭제한다.
 *
 * 이슈 관리 도구와 연동하지 않는다. 제목과 주소를 사람이 넣거나 MCP 같은 도구가
 * 같은 API(`/testruns/{id}/issues`)로 채운다. 키를 비우면 서버가 주소에서 뽑는다.
 * 연관 TC 는 없을 수도 여럿일 수도 있다.
 *
 * 표의 "상태" 는 QA 판정(verdict)이고, "심각도" 는 note 칸이다. 도구의 상태(status)는
 * API 에는 남아 있지만 화면·PDF·엑셀에 싣지 않는다(09-30 사용자 지시: 판정과 도구 상태가
 * 나란히 있으면 어느 것이 상태인지 헷갈린다).
 *
 * 결과 칸 issue_link 에 적혔지만 목록에 없는 이슈는 "추가 후보" 로 보여 준다.
 * 예전에는 그것을 별도 섹션으로 실었는데, 이슈 목록을 하나로 합치면서 후보로만 둔다.
 *
 * 이전 회차 이슈는 "이전 회차 이슈 가져오기" 로 들어온다. 출처는 옆 선택 목록에서
 * 고르고, 비우면 리포트의 비교 대상이다. 이름이 다른 수행에서 가져온 이슈는 발견 열에
 * 수행 이름을 함께 보여 준다.
 * 가져온 이슈는 발견 회차가 그 회차이고 판정은 미확인이다. QA 가 이번 수행에서
 * 재현해 보고 행의 판정 칸에서 해결 · 유지 · 부분 해결를 고르면 서버가 묶음
 * (미처리 · 신규 · 미확인 · 처리 완료)을 다시 정한다. 묶음은 서버 값(group)을 그대로
 * 쓴다. 여기서 다시 계산하면 PDF · 엑셀과 어긋날 수 있다.
 */
interface Props {
  projectId: number;
  runId: number;
  issues: RunIssue[];
  /** 묶음별 건수. 없으면 요약 줄을 그리지 않는다 */
  summary?: Record<IssueGroup, number> & { unverified?: number };
  /** 현재 수행 이름. 발견 수행의 이름이 다르면 발견 열에 이름을 붙인다 */
  runName?: string;
  /** 가져올 출처 후보(현재 수행 제외). 비우면 선택 목록을 그리지 않고 비교 대상에서 가져온다 */
  runs?: { id: number; name: string; round: number }[];
  tracker?: IssueTracker | null;
  /** 후보의 키를 링크로 변경할 때 쓴다(프로젝트의 이슈 관리 도구 주소) */
  trackerUrl?: string | null;
  candidates?: RunIssueCandidate[];
  canEdit: boolean;
  /** 저장 뒤 리포트를 다시 읽는다. PDF·엑셀과 같은 목록을 보도록 서버 값을 기준으로 한다 */
  onChanged: () => Promise<void> | void;
}

const TRACKER_NAME: Record<IssueTracker, string> = { jira: "Jira", linear: "Linear" };

/** 폼 값. 연관 TC 는 입력칸 그대로 쉼표로 이은 문자열로 들고 있다가 보낼 때 나눈다 */
interface FormState {
  title: string;
  url: string;
  issue_key: string;
  status: string;
  note: string;
  tcs: string;
  /** "" 는 판정 없음 */
  verdict: IssueVerdict | "";
}

const EMPTY: FormState = { title: "", url: "", issue_key: "", status: "", note: "", tcs: "", verdict: "" };

const VERDICT_KEY: Record<IssueVerdict, string> = {
  resolved: "verdictResolved", open: "verdictOpen", partial: "verdictPartial", unverified: "verdictUnverified",
};
const GROUP_KEY: Record<IssueGroup, string> = { open: "groupOpen", resolved: "groupResolved" };
// 묶음 색. 미해결은 FAIL 색, 처리 완료는 PASS 색(PDF·엑셀 소제목과 같다).
const GROUP_COLOR: Record<IssueGroup, string> = { open: "var(--color-fail)", resolved: "var(--color-pass)" };
/** 이전 회차 이슈인데 아직 판정하지 않은 것. 해결 후보 표시 대상. 신규 이슈는 확인 대상이 아니다 */
const isUnverified = (issue: RunIssue) =>
  issue.origin_round != null && (issue.verdict == null || issue.verdict === "unverified");

function splitTcs(text: string): string[] {
  return [...new Set(text.split(",").map((v) => v.trim()).filter(Boolean))];
}

function errorResponse(err: unknown): { status?: number; detail?: string } {
  const r = (err as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  return { status: r?.status, detail: typeof r?.data?.detail === "string" ? r.data.detail : undefined };
}

export default function RunIssuesSection({
  projectId, runId, issues, summary, runName, runs = [], tracker, trackerUrl, candidates = [], canEdit, onChanged,
}: Props) {
  const { t } = useTranslation("report");
  // null 이면 폼이 닫혀 있다. "new" 는 추가, 숫자는 그 이슈를 고치는 중이다.
  const [editing, setEditing] = useState<"new" | number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [carrying, setCarrying] = useState(false);
  // "" 는 비교 대상(자동). 숫자는 그 수행에서 가져온다.
  const [carryFrom, setCarryFrom] = useState<string>("");

  // 서버가 정한 묶음 차례로 나눈다. group 이 없는 옛 응답은 미해결로 둔다.
  const groups = ISSUE_GROUP_ORDER
    .map((g) => ({ group: g, items: issues.filter((i) => (i.group ?? "open") === g) }))
    .filter((g) => g.items.length > 0);
  // 판정이 없을 때: 이번 수행에서 새로 넣은 이슈는 "신규", 이전 회차 이슈는 "-".
  const noVerdictLabel = (issue: RunIssue) => (issue.origin_round == null ? t("verdictNew") : t("issueVerdictNone"));
  const verdictLabel = (issue: RunIssue) => (issue.verdict ? t(VERDICT_KEY[issue.verdict]) : noVerdictLabel(issue));
  const originLabel = (issue: RunIssue) => {
    if (issue.origin_round == null) return t("issueOriginThis");
    const round = t("issueOriginRound", { round: issue.origin_round });
    const name = issue.origin_run_name;
    return name && runName !== undefined && name !== runName ? `${name} ${round}` : round;
  };

  const handleCarryOver = async () => {
    setCarrying(true);
    try {
      const res = await runIssuesApi.carryOver(projectId, runId, carryFrom ? Number(carryFrom) : undefined);
      const msg = t("issueCarryOverDone", { name: res.from_run_name, round: res.from_run_round, added: res.added });
      toast.success(res.skipped > 0 ? `${msg} ${t("issueCarryOverSkipped", { skipped: res.skipped })}` : msg);
      await onChanged();
    } catch (err) {
      const { status } = errorResponse(err);
      toast.error(status === 404 ? t("issueCarryOverNone") : t("issueCarryOverFailed"));
    } finally {
      setCarrying(false);
    }
  };

  // 행에서 바로 판정한다. 이전 회차 이슈를 하나씩 확인하며 찍는 흐름이라 폼을 열지 않는다.
  const handleVerdict = async (issue: RunIssue, value: string) => {
    try {
      await runIssuesApi.update(projectId, runId, issue.id, { verdict: (value || null) as IssueVerdict | null });
      toast.success(t("issueVerdictSaved"));
      await onChanged();
    } catch {
      toast.error(t("issueSaveFailed"));
    }
  };

  const openNew = () => {
    setForm(EMPTY);
    setEditing("new");
  };

  const openEdit = (issue: RunIssue) => {
    setForm({
      title: issue.title,
      url: issue.url,
      issue_key: issue.issue_key ?? "",
      status: issue.status ?? "",
      note: issue.note ?? "",
      tcs: (issue.tc_ids ?? []).join(", "),
      verdict: issue.verdict ?? "",
    });
    setEditing(issue.id);
  };

  // 후보로 폼을 연다. 링크는 칸에 적힌 주소가 있으면 그것을, 없으면 키로 만든다.
  const openCandidate = (c: RunIssueCandidate) => {
    setForm({
      ...EMPTY,
      issue_key: c.issue_key ?? "",
      url: c.url ?? resolveIssueUrl(c.issue_key, trackerUrl, tracker) ?? "",
      tcs: c.tc_ids.join(", "),
    });
    setEditing("new");
  };

  const close = () => {
    setEditing(null);
    setForm(EMPTY);
  };

  const urlValid = /^https?:\/\//i.test(form.url.trim());
  const canSave = !!form.title.trim() && urlValid && !saving;

  const handleSave = async () => {
    if (!canSave || editing === null) return;
    setSaving(true);
    const { tcs, verdict, ...rest } = form;
    const payload = { ...rest, tc_ids: splitTcs(tcs), verdict: verdict || null };
    try {
      if (editing === "new") {
        await runIssuesApi.create(projectId, runId, payload);
        toast.success(t("issueAdded"));
      } else {
        await runIssuesApi.update(projectId, runId, editing, payload);
        toast.success(t("issueUpdated"));
      }
      close();
      await onChanged();
    } catch (err) {
      const { status, detail } = errorResponse(err);
      const notInRun = detail?.match(/^TC not in this run: (.+)$/);
      toast.error(
        status === 409 ? t("issueDuplicate")
          : notInRun ? t("issueTcNotInRun", { ids: notInRun[1] })
          : status === 422 ? t("issueInvalid")
          : t("issueSaveFailed"),
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (issue: RunIssue) => {
    if (!confirm(t("issueDeleteConfirm", { title: issue.title }))) return;
    try {
      await runIssuesApi.delete(projectId, runId, issue.id);
      toast.success(t("issueDeleted"));
      if (editing === issue.id) close();
      await onChanged();
    } catch {
      toast.error(t("issueDeleteFailed"));
    }
  };

  const title = tracker ? t("issuesTitleWithTool", { tool: TRACKER_NAME[tracker] }) : t("issuesTitle");

  return (
    <div style={s.section} data-testid="run-issues">
      <div style={s.header}>
        <h3 style={s.sectionTitle}>
          {title} <span style={s.count}>{issues.length}</span>
        </h3>
        {canEdit && editing === null && (
          <div style={s.headerBtns}>
            {runs.length > 0 && (
              <select
                style={s.carrySelect}
                value={carryFrom}
                onChange={(e) => setCarryFrom(e.target.value)}
                aria-label={t("issueCarryOverFrom")}
                data-testid="issue-carry-from"
              >
                <option value="">{t("issueCarryOverAuto")}</option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>{r.name} (R{r.round})</option>
                ))}
              </select>
            )}
            <button style={s.carryBtn} onClick={handleCarryOver} disabled={carrying} data-testid="issue-carry-over">
              {t("issueCarryOver")}
            </button>
            <button style={s.addBtn} onClick={openNew} data-testid="issue-add">
              {t("issueAdd")}
            </button>
          </div>
        )}
      </div>
      {summary && issues.length > 0 && (
        <div style={s.summaryLine} data-testid="issue-summary">
          {t("issueSummary", summary)}
          {summary.unverified ? t("issueSummaryUnverified", summary) : ""}
        </div>
      )}

      {editing !== null && (
        <div style={s.form} data-testid="issue-form">
          <div style={s.formRow}>
            <label style={{ ...s.field, flex: 3 }}>
              <span style={s.fieldLabel}>{t("issueTitle")} *</span>
              <input
                style={s.input}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder={t("issueTitlePlaceholder")}
                maxLength={500}
                autoFocus
              />
            </label>
            <label style={{ ...s.field, flex: 1 }}>
              <span style={s.fieldLabel}>{t("issueKey")}</span>
              <input
                style={s.input}
                value={form.issue_key}
                onChange={(e) => setForm({ ...form, issue_key: e.target.value })}
                placeholder={t("issueKeyPlaceholder")}
                maxLength={50}
              />
            </label>
          </div>
          <div style={s.formRow}>
            <label style={{ ...s.field, flex: 3 }}>
              <span style={s.fieldLabel}>{t("issueUrl")} *</span>
              <input
                style={{ ...s.input, ...(form.url && !urlValid ? s.inputError : null) }}
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder={tracker === "jira" ? "https://your-domain.atlassian.net/browse/PROJ-123" : "https://linear.app/workspace/issue/ABC-123"}
                maxLength={1000}
              />
            </label>
          </div>
          <div style={s.formRow}>
            <label style={{ ...s.field, flex: 1 }}>
              <span style={s.fieldLabel}>{t("issueTcs")}</span>
              <input
                style={s.input}
                value={form.tcs}
                onChange={(e) => setForm({ ...form, tcs: e.target.value })}
                placeholder={t("issueTcsPlaceholder")}
              />
            </label>
            <label style={{ ...s.field, flex: 1 }}>
              <span style={s.fieldLabel}>{t("issueVerdict")}</span>
              <select
                style={s.input}
                value={form.verdict}
                onChange={(e) => setForm({ ...form, verdict: e.target.value as IssueVerdict | "" })}
                aria-label={t("issueVerdict")}
              >
                <option value="">{t("issueVerdictNone")}</option>
                {ISSUE_VERDICTS.map((v) => (
                  <option key={v} value={v}>{t(VERDICT_KEY[v])}</option>
                ))}
              </select>
            </label>
            <label style={{ ...s.field, flex: 1 }}>
              <span style={s.fieldLabel}>{t("issueNote")}</span>
              <input
                style={s.input}
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                placeholder={t("issueNotePlaceholder")}
              />
            </label>
          </div>
          {form.url && !urlValid && <div style={s.errorText}>{t("issueUrlInvalid")}</div>}
          <div style={s.formActions}>
            <button style={s.cancelBtn} onClick={close} disabled={saving}>
              {t("common:cancel")}
            </button>
            <button
              style={{ ...s.saveBtn, opacity: canSave ? 1 : 0.5 }}
              onClick={handleSave}
              disabled={!canSave}
              data-testid="issue-save"
            >
              {saving ? t("common:saving") : t("common:save")}
            </button>
          </div>
        </div>
      )}

      {issues.length === 0 ? (
        <div style={s.emptyText}>{t("noIssues")}</div>
      ) : (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={{ ...s.th, width: 100 }}>{t("issueKey")}</th>
              <th style={s.th}>{t("issueTitle")}</th>
              <th style={{ ...s.th, width: 72 }}>{t("issueOrigin")}</th>
              <th style={{ ...s.th, width: 120 }}>{t("issueVerdict")}</th>
              <th style={{ ...s.th, width: 130 }}>{t("issueTcs")}</th>
              <th style={{ ...s.th, width: 100 }}>{t("issueNote")}</th>
              {canEdit && <th style={{ ...s.th, width: 96 }} />}
            </tr>
          </thead>
          <tbody>
            {groups.map(({ group, items }, gi) => [
              // 묶음 사이는 빈 행으로 띄우고, 소제목 행은 묶음 색 왼쪽 테두리와 글자색으로 구분한다.
              gi > 0 && (
                <tr key={`gap-${group}`} aria-hidden="true">
                  <td colSpan={canEdit ? 7 : 6} style={s.groupGap} />
                </tr>
              ),
              <tr key={`group-${group}`} data-testid={`issue-group-${group}`}>
                <td colSpan={canEdit ? 7 : 6} style={{ ...s.groupRow, borderLeft: `4px solid ${GROUP_COLOR[group]}`, color: GROUP_COLOR[group] }}>
                  {t(GROUP_KEY[group])} <span style={{ ...s.count, color: GROUP_COLOR[group] }}>{items.length}</span>
                </td>
              </tr>,
              ...items.map((issue) => (
              <tr key={issue.id} data-testid={`run-issue-${issue.id}`}>
                <td style={{ ...s.td, fontWeight: 600, whiteSpace: "nowrap" }}>{issue.issue_key || "-"}</td>
                <td style={s.td}>
                  {/* 서버가 http(s) 만 받지만, DB 를 직접 고친 값이 javascript: 링크가 되지 않게 여기서도 거른다 */}
                  {/^https?:\/\//i.test(issue.url) ? (
                    <a href={issue.url} target="_blank" rel="noopener noreferrer" style={s.link}>
                      {issue.title}
                    </a>
                  ) : (
                    issue.title
                  )}
                </td>
                <td style={{ ...s.td, whiteSpace: "nowrap" }}>{originLabel(issue)}</td>
                <td style={s.td}>
                  {canEdit ? (
                    <select
                      style={s.verdictSelect}
                      value={issue.verdict ?? ""}
                      onChange={(e) => handleVerdict(issue, e.target.value)}
                      aria-label={`${t("issueVerdict")} ${issue.issue_key || issue.title}`}
                      data-testid={`issue-verdict-${issue.id}`}
                    >
                      <option value="">{noVerdictLabel(issue)}</option>
                      {ISSUE_VERDICTS.map((v) => (
                        <option key={v} value={v}>{t(VERDICT_KEY[v])}</option>
                      ))}
                    </select>
                  ) : (
                    verdictLabel(issue)
                  )}
                  {/* 힌트일 뿐이다. TC 통과가 곧 해결는 아니라 판정은 사람이 변경한다 */}
                  {isUnverified(issue) && issue.tcs_all_pass && (
                    <span style={s.candidateBadge} title={t("resolvedCandidateHint")}>{t("resolvedCandidate")}</span>
                  )}
                </td>
                <td style={s.td}>
                  {/* TC-ID 안의 하이픈에서 줄이 변경되지 않게 ID 단위로 묶는다 */}
                  {issue.tc_ids?.length
                    ? issue.tc_ids.map((id, i) => (
                        <span key={id}>
                          <span style={s.nowrap}>{id}</span>
                          {i < issue.tc_ids.length - 1 ? ", " : ""}
                        </span>
                      ))
                    : "-"}
                </td>
                <td style={s.td}>{issue.note || "-"}</td>
                {canEdit && (
                  <td style={{ ...s.td, whiteSpace: "nowrap", textAlign: "right" }}>
                    <button style={s.rowBtn} onClick={() => openEdit(issue)} aria-label={t("issueEdit")}>
                      {t("issueEdit")}
                    </button>
                    <button
                      style={{ ...s.rowBtn, color: "var(--color-fail)" }}
                      onClick={() => handleDelete(issue)}
                      aria-label={t("common:delete")}
                    >
                      {t("common:delete")}
                    </button>
                  </td>
                )}
              </tr>
              )),
            ])}
          </tbody>
        </table>
      )}

      {candidates.length > 0 && (
        <div style={s.candidates} data-testid="issue-candidates">
          <div style={s.candidatesTitle}>{t("issueCandidates", { count: candidates.length })}</div>
          <div style={s.candidateList}>
            {candidates.map((c) => {
              const label = c.issue_key ?? c.url ?? "";
              return (
                <span key={label} style={s.candidate} data-testid={`issue-candidate-${label}`}>
                  <span style={{ fontWeight: 600 }}>{label}</span>
                  {c.tc_ids.length > 0 && <span style={s.candidateTcs}>{c.tc_ids.join(", ")}</span>}
                  {canEdit && editing === null && (
                    <button
                      style={s.candidateBtn}
                      onClick={() => openCandidate(c)}
                      aria-label={t("issueCandidateAdd", { key: label })}
                    >
                      {t("issueAdd")}
                    </button>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  section: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 24,
    marginBottom: 20,
    boxShadow: "var(--shadow)",
  },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, gap: 12 },
  headerBtns: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" },
  carrySelect: {
    padding: "5px 8px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
    maxWidth: 280,
  },
  sectionTitle: { margin: 0, fontSize: 17, fontWeight: 700, color: "var(--text-primary)" },
  count: { fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginLeft: 4 },
  summaryLine: { fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 },
  groupRow: {
    padding: "8px 10px",
    fontSize: 13,
    fontWeight: 700,
    borderBottom: "1px solid var(--border-color)",
    backgroundColor: "var(--bg-page)",
  },
  groupGap: { height: 14, padding: 0, border: "none" },
  carryBtn: {
    padding: "6px 14px",
    borderRadius: 6,
    border: "1px solid var(--border-color)",
    backgroundColor: "transparent",
    color: "var(--text-primary)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  verdictSelect: {
    padding: "3px 6px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  candidateBadge: {
    display: "inline-block",
    marginLeft: 6,
    padding: "1px 6px",
    borderRadius: 4,
    fontSize: 11,
    color: "var(--color-pass)",
    border: "1px solid var(--color-pass)",
    whiteSpace: "nowrap",
  },
  addBtn: {
    padding: "6px 14px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  form: {
    padding: 16,
    borderRadius: 8,
    backgroundColor: "var(--bg-page)",
    marginBottom: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  formRow: { display: "flex", gap: 10, flexWrap: "wrap" },
  field: { display: "flex", flexDirection: "column", gap: 4, minWidth: 160 },
  fieldLabel: { fontSize: 11, fontWeight: 600, color: "var(--text-secondary)" },
  input: {
    padding: "6px 10px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 13,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
    outline: "none",
  },
  inputError: { borderColor: "var(--color-fail)" },
  errorText: { fontSize: 12, color: "var(--color-fail)" },
  formActions: { display: "flex", justifyContent: "flex-end", gap: 8 },
  cancelBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid var(--border-color)",
    backgroundColor: "transparent",
    color: "var(--text-secondary)",
    fontSize: 13,
    cursor: "pointer",
  },
  saveBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  emptyText: { color: "var(--text-secondary)", fontSize: 14, padding: "12px 0" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    textAlign: "left",
    padding: "8px 10px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap",
  },
  td: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
    // 보고서 표와 같다. 한글은 단어 단위로 줄을 변경한다.
    wordBreak: "keep-all",
    overflowWrap: "anywhere",
  },
  link: { color: "var(--color-link)", textDecoration: "none" },
  nowrap: { whiteSpace: "nowrap" },
  candidates: { marginTop: 16, paddingTop: 12, borderTop: "1px dashed var(--border-color)" },
  candidatesTitle: { fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 },
  candidateList: { display: "flex", flexWrap: "wrap", gap: 8 },
  candidate: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "4px 6px 4px 10px",
    borderRadius: 6,
    backgroundColor: "var(--bg-input)",
    fontSize: 12,
    color: "var(--text-primary)",
  },
  candidateTcs: { color: "var(--text-secondary)" },
  candidateBtn: {
    border: "1px solid var(--border-color)",
    background: "var(--bg-card)",
    borderRadius: 4,
    padding: "2px 8px",
    fontSize: 11,
    cursor: "pointer",
    color: "var(--accent)",
  },
  rowBtn: {
    background: "none",
    border: "none",
    padding: "2px 6px",
    fontSize: 12,
    cursor: "pointer",
    color: "var(--text-secondary)",
  },
};
