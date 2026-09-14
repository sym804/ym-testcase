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

export interface Project {
  id: number;
  name: string;
  description: string;
  jira_base_url: string | null;
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
  /** 이 런이 담는 시트. 없거나 null 이면 프로젝트 전체다. */
  sheet_names?: string[] | null;
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
  test_case?: TestCase;
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

export interface RoundComparison {
  round: number;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  pass_rate: number;
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
}

/** 리포트의 실패 항목. TestResult 전체가 아니라 화면에 쓰는 조각만 온다. */
export interface ReportFailure {
  test_case: { tc_id: string };
  result: string;
  actual_result: string | null;
  issue_link: string | null;
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
  category_summary: CategoryBreakdown[];
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
