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
  issue_link: string;
  assignee: string;
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

export interface AssigneeSummary {
  assignee: string;
  total: number;
  pass: number;
  fail: number;
  block: number;
  na: number;
  not_started: number;
  completion_rate: number;
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
export interface ReportData {
  project: Project;
  test_run: TestRun;
  summary: DashboardSummary;
  top_failures: TestResult[];
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
