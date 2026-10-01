// Enums
export enum UserRole {
  ADMIN = "admin",
  QA_MANAGER = "qa_manager",
  USER = "user",
}

export enum TestResultValue {
  PASS = "PASS",
  FAIL = "FAIL",
  BLOCK = "BLOCK",
  NA = "NA",
  NS = "NS",
}

export enum TestRunStatus {
  IN_PROGRESS = "in_progress",
  COMPLETED = "completed",
}

// Models
export interface User {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  must_change_password: boolean;
  created_at: string;
}

export type IssueTracker = "jira" | "linear";

/** 이슈의 QA 확인 결과. 해결 · 유지 · 부분 해결 · 미확인. 도구의 상태(status)와 따로 둔다 */
export type IssueVerdict = "resolved" | "open" | "partial" | "unverified";
export const ISSUE_VERDICTS: IssueVerdict[] = ["resolved", "open", "partial", "unverified"];

/** 리포트가 이슈를 나누는 묶음. 해결만 처리 완료, 나머지(유지·부분·미확인·신규)는 미해결 */
export type IssueGroup = "open" | "resolved";
export const ISSUE_GROUP_ORDER: IssueGroup[] = ["open", "resolved"];

/** 수행에 등록한 이슈(제목과 주소). 키는 비우면 서버가 주소에서 뽑는다 */
export interface RunIssue {
  id: number;
  test_run_id?: number;
  issue_key: string | null;
  title: string;
  url: string;
  status: string | null;
  note: string | null;
  /** 연관 TC 의 TC-ID. 없을 수도 여럿일 수도 있다 */
  tc_ids: string[];
  /** 처음 발견한 수행. null 이면 이번 수행에서 처음 발견한 신규 이슈다 */
  origin_run_id?: number | null;
  origin_round?: number | null;
  /** 리포트 JSON 에만 있다. 발견 수행이 지워졌으면 null */
  origin_run_name?: string | null;
  verdict?: IssueVerdict | null;
  /** 리포트 JSON 에만 있다. 서버가 발견 회차와 판정으로 정한 묶음 */
  group?: IssueGroup;
  /** 연관 TC 가 이번 수행에서 전부 PASS 인지. TC 가 없으면 null. 해결 후보 표시에만 쓴다 */
  tcs_all_pass?: boolean | null;
}

export type RunIssueInput = {
  title: string;
  url: string;
  issue_key?: string | null;
  status?: string | null;
  note?: string | null;
  tc_ids?: string[];
  origin_run_id?: number | null;
  verdict?: IssueVerdict | null;
};

export interface RunIssueCarryOverResult {
  from_run_id: number;
  from_run_name: string;
  from_run_round: number;
  added: number;
  skipped: number;
  issues: RunIssue[];
}

/** 결과 칸 issue_link 에 적혔지만 이슈 목록에 없는 이슈. 등록을 돕는 후보다 */
export interface RunIssueCandidate {
  issue_key: string | null;
  url: string | null;
  tc_ids: string[];
}

export interface Project {
  id: number;
  name: string;
  description: string;
  jira_base_url: string | null;
  /** 이슈 관리 도구. null 이면 주소 모양으로 짐작한다 */
  issue_tracker?: IssueTracker | null;
  is_private: boolean;
  field_config?: Record<string, { display_name?: string; visible?: boolean }> | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  my_role?: string | null;
}

export interface ProjectMember {
  id: number;
  project_id: number;
  user_id: number;
  role: string;
  added_at: string;
  username?: string;
  display_name?: string;
}

export interface TestCase {
  id: number;
  project_id: number;
  no: number;
  tc_id: string;
  type: string;
  category: string;
  depth1: string;
  depth2: string;
  priority: string;
  test_type: string;
  precondition: string;
  test_steps: string;
  expected_result: string;
  r1: string;
  r2: string;
  r3: string;
  remarks: string;
  sheet_name: string;
  custom_fields?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: number;
  project_id: number;
  name: string;
  version: string;
  environment: string;
  round: number;
  status: TestRunStatus;
  test_plan_id?: number | null;
  /** 리포트의 비교 대상. null 이면 같은 이름의 이전 회차(자동) */
  compare_run_id?: number | null;
  /** 이 런이 담는 시트. 없거나 null 이면 프로젝트 전체다. */
  sheet_names?: string[] | null;
  /** 목록 조회에서만 온다. 담은 TC 수와 수행한(NS 아닌) 수 */
  tc_total?: number;
  tc_executed?: number;
  created_by: number;
  created_at: string;
  completed_at?: string;
}

export interface TestResult {
  id: number;
  test_run_id: number;
  test_case_id: number;
  result: TestResultValue | string;
  actual_result: string;
  issue_link: string;
  remarks: string;
  executed_by: number | null;
  executed_at: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_sec?: number | null;
  /** 저장 때만 보낸다. 화면이 읽어 둔 executed_at. 서버 값과 다르면 409(다른 사용자가 먼저 저장) */
  expected_executed_at?: string | null;
  test_case?: TestCase;
}

/** 본인 API 키 목록 항목. 원문은 없고, prefix 로 어느 키인지 알아본다. */
export interface ApiKeyItem {
  id: number;
  name: string;
  prefix: string;
  created_at: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  status: "active" | "expired" | "revoked";
}

/** 자동화 결과 파일 가져오기 응답. dry_run 이면 저장하지 않은 계산 결과다. */
export interface ResultImportSummary {
  format: "playwright-json" | "junit-xml";
  dry_run: boolean;
  run_id: number;
  total_tests: number;
  matched_tests: number;
  matched_tcs: number;
  recorded: number;
  counts: { PASS: number; FAIL: number; NS: number };
  items: { tc_id: string; result: "PASS" | "FAIL" | "NS"; kind: string; note: string }[];
  /** 이미 기록된 결과라 NS 로 덮지 않은 TC */
  kept_executed: string[];
  /** 프로젝트에는 있으나 이 수행의 범위 밖이라 기록하지 않은 TC */
  out_of_run: string[];
  /** test.fail 표식인데 통과한 TC. 결함 해소 후보 */
  fixed_candidates: string[];
  unexpected_failures: string[];
  known_failures: number;
  unmatched_count: number;
  unmatched: string[];
}

export interface Attachment {
  id: number;
  test_result_id: number;
  filename: string;
  content_type?: string;
  file_size?: number;
  uploaded_by: number;
  uploaded_at: string;
}

export interface TestCaseHistory {
  id: number;
  test_case_id: number;
  changed_by: number;
  changer_name?: string;
  changed_at: string;
  field_name: string;
  old_value?: string;
  new_value?: string;
  tc_id?: string;
}

// Sheet tree
export interface SheetNode {
  id: number;
  name: string;
  parent_id: number | null;
  sort_order: number;
  is_folder: boolean;
  tc_count: number;
  children: SheetNode[];
}

// Dashboard types
export interface DashboardSummary {
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
  pass_rate: number;
  fail_rate: number;
  block_rate: number;
  na_rate: number;
  not_started_rate: number;
}

export interface PriorityDistribution {
  priority: string;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
}

export interface CategoryBreakdown {
  category: string;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
}

/** 같은 이름의 수행을 회차 순으로 늘어놓은 한 칸. 합격률 분모는 수행분(PASS+FAIL+BLOCK)이고
 *  실행이 0건이면 null 이다(0% 로 찍히면 폭락처럼 보인다). */
export interface RoundComparison {
  round: number;
  run_id?: number;
  name?: string;
  status?: string;
  created_at?: string | null;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started?: number;
  executed?: number;
  pass_rate: number | null;
  fail_rate?: number | null;
}

// Forms
export interface LoginForm {
  username: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterForm {
  username: string;
  password: string;
  confirm_password: string;
  display_name: string;
}

// Report
// 리포트 응답은 전용 모양이다. Project/TestRun/TestResult 를 그대로 쓰면
// 실제로 오지 않는 필드까지 있다고 선언하게 되어, 컴파일러가 아무 보호도 못 한다
// (`is_private`, `project_id`, `created_by` 등이 항상 undefined 였다).

/** 리포트가 싣는 프로젝트 정보 */
export interface ReportProject {
  id: number;
  name: string;
  description: string | null;
  jira_base_url: string | null;
  issue_tracker?: IssueTracker | null;
  created_at: string | null;
  updated_at: string | null;
  created_by: number;
}

/** 리포트가 싣는 수행 정보 */
export interface ReportRun {
  id: number;
  name: string;
  version: string | null;
  environment: string | null;
  round: number;
  status: string;
  created_at: string | null;
  completed_at: string | null;
  /** 저장한 비교 대상. null 이면 자동이다 */
  compare_run_id?: number | null;
}

/** 리포트의 FAIL/BLOCK 항목. TestResult 전체가 아니라 화면에 쓰는 조각만 온다.
 *  이름은 호환 때문에 Failure 지만 BLOCK 도 온다. `result` 가 실제 값이다. */
export interface ReportFailure {
  test_case: { tc_id: string; priority?: string | null; category?: string | null };
  result: string;
  actual_result: string | null;
  issue_link: string | null;
  executed_by?: string | null;
}

/** 분류별/우선순위별 집계 한 줄. `pass_rate` 는 수행분이 없으면 null 이다. */
export interface ReportBreakdownRow {
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
  pass_rate: number | null;
}

/** `category` 가 null 이면 분류를 비워 둔 TC 들이다. */
export interface ReportCategoryRow extends ReportBreakdownRow {
  category: string | null;
}

/** `priority` 가 null 이면 우선순위를 비워 둔 TC 들이다. */
export interface ReportPriorityRow extends ReportBreakdownRow {
  priority: string | null;
}

export interface ReportChangeItem {
  tc_id: string;
  priority: string | null;
  category?: string | null;
  before: string;
  after: string;
  /** 퇴보 · 미수정(FAIL 그대로) · 개선 · 그 밖의 변경 */
  kind?: "regression" | "still" | "fixed" | "other";
  /** 이 수행에 등록한 이슈 가운데 이 TC 에 연결된 것의 키 */
  issue_keys?: string[];
}

/** 비교 대상 수행 대비. 판정 기준은 수행 비교 화면과 같다(회귀 PASS->FAIL, 해결 FAIL->PASS).
 *  대상은 저장한 compare_run_id(manual), 없으면 같은 이름의 이전 회차(auto)다. */
export interface ReportComparison {
  previous_run: { id: number; name: string; round: number };
  mode?: "auto" | "manual";
  common: number;
  changed: number;
  regressions: ReportChangeItem[];
  fixed: ReportChangeItem[];
  /** 이전 수행의 FAIL 이 이번에 어떻게 됐는지. 변경만 세면 FAIL 그대로인 TC 가 안 보인다 */
  prev_fail?: { total: number; fixed: number; still: number; other: number };
  /** 변경 상세 표. 퇴보 -> 미수정 -> 개선 -> 그 밖 차례 */
  changes?: ReportChangeItem[];
}

/** 리포트 요약. `pass_rate` 의 분모는 `executed`(pass+fail+block)이고 나머지는 `total` 이다. */
export interface ReportSummary {
  total: number;
  executed: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
  pass_rate: number;
  fail_rate: number;
  block_rate: number;
  na_rate: number;
  not_started_rate: number;
}

export interface ReportData {
  project: ReportProject;
  test_run: ReportRun;
  summary: ReportSummary;
  top_failures: ReportFailure[];
  jira_issues: string[];
  /** 수행에 등록한 이슈. jira_issues(결과 칸을 모은 것)는 화면에서 더 쓰지 않고 호환으로만 남는다 */
  issues?: RunIssue[];
  /** 묶음별 건수와, 미해결 가운데 아직 판정하지 않은 수(unverified). 이슈 섹션의 요약 줄 */
  issue_summary?: Record<IssueGroup, number> & { unverified?: number };
  issue_candidates?: RunIssueCandidate[];
  category_summary: ReportCategoryRow[];
  priority_summary: ReportPriorityRow[];
  comparison: ReportComparison | null;
  executors: { name: string; count: number }[];
  total_duration_sec: number | null;
}

// Custom Field Definition
export interface CustomFieldDef {
  id: number;
  project_id: number;
  field_name: string;
  field_type: "text" | "number" | "select" | "multiselect" | "checkbox" | "date";
  options?: string[];
  sort_order: number;
  is_required: boolean;
  created_at: string;
}

// Test Plan
export interface TestPlan {
  id: number;
  project_id: number;
  name: string;
  milestone?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  run_count: number;
  progress?: {
    total: number;
    pass: number;
    fail: number;
    block: number;
    na: number;
    ns: number;
    pass_rate: number;
  };
}

// Saved Filter
export interface FilterCondition {
  field: string;
  operator: string;
  value?: unknown;
}

export interface SavedFilter {
  id: number;
  project_id: number;
  name: string;
  conditions: FilterCondition[];
  logic: "AND" | "OR";
  created_by: number;
  created_at: string;
}

// TC Result History
export interface TCResultHistory {
  result_id: number;
  result: string;
  actual_result: string | null;
  issue_link: string | null;
  remarks: string | null;
  executed_at: string | null;
  duration_sec: number | null;
  run_id: number;
  run_name: string;
  version: string | null;
  environment: string | null;
  round: number;
  run_status: string;
  run_created_at: string | null;
}
