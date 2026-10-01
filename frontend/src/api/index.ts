import client from "./client";
import type {
  User,
  Project,
  ProjectMember,
  TestCase,
  TestRun,
  TestResult,
  Attachment,
  TestCaseHistory,
  LoginForm,
  RegisterForm,
  DashboardSummary,
  PriorityDistribution,
  CategoryBreakdown,
  RoundComparison,
  ReportData,
  SheetNode,
  CustomFieldDef,
  TestPlan,
  SavedFilter,
  FilterCondition,
  TCResultHistory,
  RunIssue,
  RunIssueCarryOverResult,
  RunIssueInput,
  ResultImportSummary,
} from "../types";

// ─── Auth ────────────────────────────────────────────
export const authApi = {
  login: async (form: LoginForm) => {
    const res = await client.post<{ access_token: string; token_type: string }>(
      "/api/auth/login",
      form
    );
    return res.data;
  },

  register: async (form: Omit<RegisterForm, "confirm_password">) => {
    const res = await client.post<User>("/api/auth/register", form);
    return res.data;
  },

  getMe: async () => {
    const res = await client.get<User>("/api/auth/me");
    return res.data;
  },

  checkUsername: async (username: string) => {
    const res = await client.get<{ available: boolean }>("/api/auth/check-username", {
      params: { username },
    });
    return res.data;
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const res = await client.put<User>("/api/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return res.data;
  },

  logout: async () => {
    await client.post("/api/auth/logout");
  },
};

// ─── Projects ────────────────────────────────────────
export const projectsApi = {
  list: async () => {
    const res = await client.get<Project[]>("/api/projects");
    return res.data;
  },

  getOne: async (id: number) => {
    const res = await client.get<Project>(`/api/projects/${id}`);
    return res.data;
  },

  create: async (data: Partial<Project>) => {
    const res = await client.post<Project>("/api/projects", data);
    return res.data;
  },

  update: async (id: number, data: Partial<Project>) => {
    const res = await client.put<Project>(`/api/projects/${id}`, data);
    return res.data;
  },

  delete: async (id: number) => {
    await client.delete(`/api/projects/${id}`);
  },
};

// ─── Test Cases ──────────────────────────────────────
export const testCasesApi = {
  list: async (projectId: number, params?: Record<string, string>) => {
    const res = await client.get<TestCase[]>(
      `/api/projects/${projectId}/testcases`,
      { params }
    );
    return res.data;
  },

  create: async (projectId: number, data: Partial<TestCase>) => {
    const res = await client.post<TestCase>(
      `/api/projects/${projectId}/testcases`,
      data
    );
    return res.data;
  },

  update: async (projectId: number, tcId: number, data: Partial<TestCase>) => {
    const res = await client.put<TestCase>(
      `/api/projects/${projectId}/testcases/${tcId}`,
      data
    );
    return res.data;
  },

  bulkUpdate: async (projectId: number, data: Partial<TestCase>[]) => {
    const res = await client.put<TestCase[]>(
      `/api/projects/${projectId}/testcases/bulk`,
      { items: data }
    );
    return res.data;
  },

  delete: async (projectId: number, tcId: number) => {
    await client.delete(`/api/projects/${projectId}/testcases/${tcId}`);
  },

  bulkDelete: async (projectId: number, ids: number[]) => {
    const res = await client.delete<{ deleted: number }>(
      `/api/projects/${projectId}/testcases/bulk`,
      { params: { ids: ids.join(",") } }
    );
    return res.data;
  },

  clone: async (projectId: number, tcId: number) => {
    const res = await client.post<TestCase>(
      `/api/projects/${projectId}/testcases/${tcId}/clone`
    );
    return res.data;
  },

  bulkClone: async (projectId: number, ids: number[]) => {
    const res = await client.post<TestCase[]>(
      `/api/projects/${projectId}/testcases/bulk-clone`,
      { ids }
    );
    return res.data;
  },

  restore: async (projectId: number, tcId: number) => {
    const res = await client.post<TestCase>(
      `/api/projects/${projectId}/testcases/${tcId}/restore`
    );
    return res.data;
  },

  importExcel: async (projectId: number, file: File, sheetNames?: string[]) => {
    const formData = new FormData();
    formData.append("file", file);
    const params = sheetNames?.length ? { sheet_names: sheetNames.join(",") } : {};
    const res = await client.post<{ created: number; updated: number; renamed?: number; imported: number; sheets: { sheet: string; created: number; updated: number; renamed?: number }[] }>(
      `/api/projects/${projectId}/testcases/import`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" }, params }
    );
    return res.data;
  },

  previewImport: async (projectId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await client.post<{ sheets: { name: string; tc_count: number; existing: number }[] }>(
      `/api/projects/${projectId}/testcases/import/preview`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return res.data;
  },

  createSheet: async (projectId: number, name: string, parentId?: number | null, isFolder: boolean = false) => {
    const res = await client.post<SheetNode>(
      `/api/projects/${projectId}/testcases/sheets`,
      { name, parent_id: parentId ?? null, is_folder: isFolder }
    );
    return res.data;
  },

  deleteSheet: async (projectId: number, sheetName: string) => {
    const res = await client.delete<{ deleted: number; sheet: string }>(
      `/api/projects/${projectId}/testcases/sheets/${encodeURIComponent(sheetName)}`
    );
    return res.data;
  },

  listSheets: async (projectId: number) => {
    const res = await client.get<SheetNode[]>(
      `/api/projects/${projectId}/testcases/sheets`
    );
    return res.data;
  },

  renameSheet: async (projectId: number, sheetId: number, newName: string) => {
    const res = await client.put<{ id: number; name: string; old_name: string }>(
      `/api/projects/${projectId}/testcases/sheets/${sheetId}/rename`,
      { new_name: newName }
    );
    return res.data;
  },

  moveSheet: async (projectId: number, sheetId: number, parentId: number | null, sortOrder?: number) => {
    const res = await client.put(
      `/api/projects/${projectId}/testcases/sheets/${sheetId}/move`,
      { parent_id: parentId, sort_order: sortOrder }
    );
    return res.data;
  },

  exportExcel: async (projectId: number, splitSheets = false, expandRefs = false) => {
    const res = await client.get(
      `/api/projects/${projectId}/testcases/export`,
      { params: { split_sheets: splitSheets, expand_refs: expandRefs }, responseType: "blob" }
    );
    return res.data;
  },

  resultHistory: async (projectId: number, tcId: number) => {
    const res = await client.get<TCResultHistory[]>(
      `/api/projects/${projectId}/testcases/${tcId}/result-history`
    );
    return res.data;
  },

  reorder: async (projectId: number, items: { id: number; no: number }[]) => {
    const res = await client.put(
      `/api/projects/${projectId}/testcases/reorder`,
      { items }
    );
    return res.data;
  },
};

// ─── Test Runs ───────────────────────────────────────
export const testRunsApi = {
  list: async (projectId: number) => {
    const res = await client.get<TestRun[]>(
      `/api/projects/${projectId}/testruns`
    );
    return res.data;
  },

  create: async (projectId: number, data: Partial<TestRun>) => {
    const res = await client.post<TestRun>(
      `/api/projects/${projectId}/testruns`,
      data
    );
    return res.data;
  },

  getOne: async (projectId: number, runId: number) => {
    const res = await client.get<TestRun & { results: TestResult[] }>(
      `/api/projects/${projectId}/testruns/${runId}`
    );
    return res.data;
  },

  update: async (projectId: number, runId: number, data: Partial<TestRun>) => {
    const res = await client.put<TestRun>(
      `/api/projects/${projectId}/testruns/${runId}`,
      data
    );
    return res.data;
  },

  submitResults: async (
    projectId: number,
    runId: number,
    results: Partial<TestResult>[]
  ) => {
    const res = await client.post<TestResult[]>(
      `/api/projects/${projectId}/testruns/${runId}/results`,
      results
    );
    return res.data;
  },

  // 자동화 결과 파일(Playwright JSON · JUnit XML)을 회차 결과로. dryRun 이면 계산만 한다.
  importResults: async (
    projectId: number,
    runId: number,
    file: File,
    opts: { dryRun: boolean; keepExecuted: boolean; label?: string }
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    const params: Record<string, string> = {
      dry_run: String(opts.dryRun),
      keep_executed: String(opts.keepExecuted),
    };
    if (opts.label?.trim()) params.label = opts.label.trim();
    const res = await client.post<ResultImportSummary>(
      `/api/projects/${projectId}/testruns/${runId}/results/import`,
      formData,
      { params, headers: { "Content-Type": "multipart/form-data" } }
    );
    return res.data;
  },

  complete: async (projectId: number, runId: number) => {
    const res = await client.put<TestRun>(
      `/api/projects/${projectId}/testruns/${runId}/complete`
    );
    return res.data;
  },

  reopen: async (projectId: number, runId: number) => {
    const res = await client.put<TestRun>(
      `/api/projects/${projectId}/testruns/${runId}/reopen`
    );
    return res.data;
  },

  // next_round: 이름은 그대로, 회차는 같은 이름 가운데 최댓값 + 1. 기본은 예전 복제("(복제)" 이름, 같은 회차).
  clone: async (projectId: number, runId: number, opts?: { next_round?: boolean }) => {
    const res = await client.post<TestRun>(
      `/api/projects/${projectId}/testruns/${runId}/clone${opts?.next_round ? "?next_round=true" : ""}`
    );
    return res.data;
  },

  delete: async (projectId: number, runId: number) => {
    await client.delete(`/api/projects/${projectId}/testruns/${runId}`);
  },

  exportExcel: async (projectId: number, runId: number) => {
    const res = await client.get(
      `/api/projects/${projectId}/testruns/${runId}/export`,
      { responseType: "blob" }
    );
    return res.data;
  },
};

// ─── Dashboard ───────────────────────────────────────
export const dashboardApi = {
  summary: async (projectId: number, runId?: number, dateFrom?: string, dateTo?: string, version?: string) => {
    const params: Record<string, string | number> = {};
    if (runId) params.run_id = runId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (version) params.version = version;
    const res = await client.get<DashboardSummary>(
      `/api/projects/${projectId}/dashboard/summary`,
      { params: Object.keys(params).length ? params : undefined }
    );
    return res.data;
  },

  priority: async (projectId: number, runId?: number, dateFrom?: string, dateTo?: string, version?: string) => {
    const params: Record<string, string | number> = {};
    if (runId) params.run_id = runId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (version) params.version = version;
    const res = await client.get<PriorityDistribution[]>(
      `/api/projects/${projectId}/dashboard/priority`,
      { params: Object.keys(params).length ? params : undefined }
    );
    return res.data;
  },

  category: async (projectId: number, runId?: number, dateFrom?: string, dateTo?: string, version?: string) => {
    const params: Record<string, string | number> = {};
    if (runId) params.run_id = runId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (version) params.version = version;
    const res = await client.get<CategoryBreakdown[]>(
      `/api/projects/${projectId}/dashboard/category`,
      { params: Object.keys(params).length ? params : undefined }
    );
    return res.data;
  },

  // runName: 회차로 묶을 수행 이름. 없으면 서버가 가장 최근 수행의 이름을 쓴다.
  rounds: async (projectId: number, dateFrom?: string, dateTo?: string, runName?: string, version?: string) => {
    const params: Record<string, string | number> = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (runName) params.run_name = runName;
    if (version) params.version = version;
    const res = await client.get<RoundComparison[]>(
      `/api/projects/${projectId}/dashboard/rounds`,
      { params: Object.keys(params).length ? params : undefined }
    );
    return res.data;
  },

  heatmap: async (projectId: number, runId?: number, dateFrom?: string, dateTo?: string, version?: string) => {
    const params: Record<string, string | number> = {};
    if (runId) params.run_id = runId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (version) params.version = version;
    const res = await client.get<{ category: string; priority: string; fail_count: number }[]>(
      `/api/projects/${projectId}/dashboard/heatmap`,
      { params: Object.keys(params).length ? params : undefined }
    );
    return res.data;
  },
};

// ─── Overview (Global Dashboard) ─────────────────────
export const overviewApi = {
  get: async () => {
    const res = await client.get("/api/dashboard/overview");
    return res.data;
  },
};

// ─── Reports ─────────────────────────────────────────
export const reportsApi = {
  getData: async (projectId: number, runId: number) => {
    const res = await client.get<ReportData>(
      `/api/projects/${projectId}/reports`,
      { params: { run_id: runId } }
    );
    return res.data;
  },

  // 파일 이름은 서버가 정한다(`{프로젝트}_Report_R{회차}`). 예전에는 화면이
  // `report_{id}` 로 덮어써서 받은 파일로는 어느 수행인지 알 수 없었다.
  // lang: PDF 문구 언어(ko/en). 화면 언어를 넘긴다. 없으면 서버 기본값(ko)이다.
  downloadPdf: async (projectId: number, runId: number, lang?: string): Promise<ReportFile> => {
    const res = await client.get(
      `/api/projects/${projectId}/reports/pdf`,
      { params: lang ? { run_id: runId, lang } : { run_id: runId }, responseType: "blob" }
    );
    return { blob: res.data, filename: filenameFromDisposition(res.headers?.["content-disposition"]) };
  },

  // lang: 요약 시트 문구 언어(ko/en). PDF 와 같은 규칙이다.
  downloadExcel: async (projectId: number, runId: number, lang?: string): Promise<ReportFile> => {
    const res = await client.get(
      `/api/projects/${projectId}/reports/excel`,
      { params: lang ? { run_id: runId, lang } : { run_id: runId }, responseType: "blob" }
    );
    return { blob: res.data, filename: filenameFromDisposition(res.headers?.["content-disposition"]) };
  },
};

export interface ReportFile {
  blob: Blob;
  /** 헤더가 없거나 읽지 못하면 null. 부르는 쪽이 대신할 이름을 정한다. */
  filename: string | null;
}

/** `attachment; filename*=UTF-8''...` 또는 `filename="..."` 에서 이름을 꺼낸다. */
export function filenameFromDisposition(header: unknown): string | null {
  if (typeof header !== "string") return null;
  const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      return null;
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

// ─── Attachments ──────────────────────────────────────
export const attachmentsApi = {
  list: async (testResultId: number) => {
    const res = await client.get<Attachment[]>(`/api/attachments/${testResultId}`);
    return res.data;
  },

  listByRun: async (runId: number) => {
    const res = await client.get<Attachment[]>(`/api/attachments/by-run/${runId}`);
    return res.data;
  },

  upload: async (testResultId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await client.post<Attachment>(
      `/api/attachments/${testResultId}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return res.data;
  },

  downloadUrl: (attachmentId: number) =>
    `/api/attachments/download/${attachmentId}`,

  delete: async (attachmentId: number) => {
    await client.delete(`/api/attachments/${attachmentId}`);
  },
};

// ─── Project Members ─────────────────────────────────
export const membersApi = {
  list: async (projectId: number) => {
    const res = await client.get<ProjectMember[]>(
      `/api/projects/${projectId}/members`
    );
    return res.data;
  },

  add: async (projectId: number, userId: number, role: string) => {
    const res = await client.post<ProjectMember>(
      `/api/projects/${projectId}/members`,
      { user_id: userId, role }
    );
    return res.data;
  },

  updateRole: async (projectId: number, memberId: number, role: string) => {
    const res = await client.put<ProjectMember>(
      `/api/projects/${projectId}/members/${memberId}`,
      { role }
    );
    return res.data;
  },

  remove: async (projectId: number, memberId: number) => {
    await client.delete(`/api/projects/${projectId}/members/${memberId}`);
  },

  availableUsers: async (projectId: number) => {
    const res = await client.get<User[]>(
      `/api/projects/${projectId}/members/available-users`
    );
    return res.data;
  },
};

// ─── History ──────────────────────────────────────────
export const historyApi = {
  getTestCaseHistory: async (testCaseId: number) => {
    const res = await client.get<TestCaseHistory[]>(`/api/history/testcase/${testCaseId}`);
    return res.data;
  },
  getProjectHistory: async (projectId: number) => {
    const res = await client.get<TestCaseHistory[]>(`/api/history/project/${projectId}`);
    return res.data;
  },
};

// ─── Search ───────────────────────────────────────────
export const searchApi = {
  global: async (q: string) => {
    const res = await client.get<TestCase[]>("/api/search", { params: { q } });
    return res.data;
  },
};

// ─── Users (admin) ────────────────────────────────────
export const usersApi = {
  list: async () => {
    const res = await client.get<User[]>("/api/auth/users");
    return res.data;
  },

  updateRole: async (userId: number, role: string) => {
    const res = await client.put<User>(`/api/auth/users/${userId}/role`, { role });
    return res.data;
  },

  resetPassword: async (userId: number) => {
    const res = await client.put<{ temp_password: string }>(`/api/auth/users/${userId}/reset-password`);
    return res.data;
  },

  getAllAssignments: async () => {
    const res = await client.get<Record<string, { id: number; project_id: number; project_name: string; role: string }[]>>(
      "/api/projects/all-assignments"
    );
    return res.data;
  },

  assignToAllProjects: async (userId: number, role: string) => {
    const res = await client.post<{ assigned: number; total_projects: number }>("/api/projects/assign-all", {
      user_id: userId,
      role,
    });
    return res.data;
  },
};

// ─── Account Recovery ─────────────────────────────────
export interface AccountRequestItem {
  id: number;
  request_type: "find_id" | "reset_password";
  status: "pending" | "approved" | "rejected" | "completed";
  claimed_username: string | null;
  claimed_display_name: string | null;
  contact: string;
  note: string | null;
  user_id: number | null;
  created_at: string;
  resolved_at: string | null;
}

export interface AccountRequestSubmit {
  request_type: "find_id" | "reset_password";
  claimed_username?: string;
  claimed_display_name?: string;
  contact: string;
  note?: string;
}

export interface ApproveResult {
  request_type: "find_id" | "reset_password";
  username: string | null;
  code: string | null;
  code_expires_at: string | null;
}

export const accountRequestsApi = {
  submit: async (data: AccountRequestSubmit) => {
    const res = await client.post<{ message: string }>("/api/auth/account-requests", data);
    return res.data;
  },

  list: async (status: string) => {
    const res = await client.get<AccountRequestItem[]>("/api/auth/account-requests", {
      params: { status },
    });
    return res.data;
  },

  approve: async (requestId: number, userId: number) => {
    const res = await client.post<ApproveResult>(
      `/api/auth/account-requests/${requestId}/approve`,
      { user_id: userId }
    );
    return res.data;
  },

  reject: async (requestId: number, note: string) => {
    const res = await client.post<AccountRequestItem>(
      `/api/auth/account-requests/${requestId}/reject`,
      { note }
    );
    return res.data;
  },

  resetWithCode: async (username: string, code: string, newPassword: string) => {
    const res = await client.post<{ message: string }>("/api/auth/reset-password/verify", {
      username,
      code,
      new_password: newPassword,
    });
    return res.data;
  },
};

// ─── Custom Fields ──────────────────────────────────
export const customFieldsApi = {
  list: async (projectId: number) => {
    const res = await client.get<CustomFieldDef[]>(
      `/api/projects/${projectId}/custom-fields`
    );
    return res.data;
  },

  create: async (projectId: number, data: Partial<CustomFieldDef>) => {
    const res = await client.post<CustomFieldDef>(
      `/api/projects/${projectId}/custom-fields`,
      data
    );
    return res.data;
  },

  update: async (projectId: number, fieldId: number, data: Partial<CustomFieldDef>) => {
    const res = await client.put<CustomFieldDef>(
      `/api/projects/${projectId}/custom-fields/${fieldId}`,
      data
    );
    return res.data;
  },

  delete: async (projectId: number, fieldId: number) => {
    const res = await client.delete<{ deleted: string }>(
      `/api/projects/${projectId}/custom-fields/${fieldId}`
    );
    return res.data;
  },
};

// ─── Test Plans ─────────────────────────────────────
export const testPlansApi = {
  list: async (projectId: number) => {
    const res = await client.get<TestPlan[]>(
      `/api/projects/${projectId}/testplans`
    );
    return res.data;
  },

  create: async (projectId: number, data: Partial<TestPlan>) => {
    const res = await client.post<TestPlan>(
      `/api/projects/${projectId}/testplans`,
      data
    );
    return res.data;
  },

  getOne: async (projectId: number, planId: number) => {
    const res = await client.get<TestPlan>(
      `/api/projects/${projectId}/testplans/${planId}`
    );
    return res.data;
  },

  update: async (projectId: number, planId: number, data: Partial<TestPlan>) => {
    const res = await client.put<TestPlan>(
      `/api/projects/${projectId}/testplans/${planId}`,
      data
    );
    return res.data;
  },

  delete: async (projectId: number, planId: number) => {
    const res = await client.delete<{ deleted: string }>(
      `/api/projects/${projectId}/testplans/${planId}`
    );
    return res.data;
  },

  listRuns: async (projectId: number, planId: number) => {
    const res = await client.get<TestRun[]>(
      `/api/projects/${projectId}/testplans/${planId}/runs`
    );
    return res.data;
  },
};

// ─── Run Issues ─────────────────────────────────────
export const runIssuesApi = {
  list: async (projectId: number, runId: number) => {
    const res = await client.get<RunIssue[]>(
      `/api/projects/${projectId}/testruns/${runId}/issues`
    );
    return res.data;
  },

  create: async (projectId: number, runId: number, data: RunIssueInput) => {
    const res = await client.post<RunIssue>(
      `/api/projects/${projectId}/testruns/${runId}/issues`,
      data
    );
    return res.data;
  },

  update: async (projectId: number, runId: number, issueId: number, data: Partial<RunIssueInput>) => {
    const res = await client.put<RunIssue>(
      `/api/projects/${projectId}/testruns/${runId}/issues/${issueId}`,
      data
    );
    return res.data;
  },

  delete: async (projectId: number, runId: number, issueId: number) => {
    await client.delete(`/api/projects/${projectId}/testruns/${runId}/issues/${issueId}`);
  },

  // 이전 회차 이슈 가져오기. fromRunId 를 비우면 서버가 리포트의 비교 대상을 쓴다.
  // 비교 대상이 없으면 404 다. 같은 링크가 이미 있으면 건너뛴다.
  carryOver: async (projectId: number, runId: number, fromRunId?: number) => {
    const res = await client.post<RunIssueCarryOverResult>(
      `/api/projects/${projectId}/testruns/${runId}/issues/carry-over`,
      fromRunId ? { from_run_id: fromRunId } : {}
    );
    return res.data;
  },
};

// ─── Saved Filters ──────────────────────────────────
export const filtersApi = {
  list: async (projectId: number) => {
    const res = await client.get<SavedFilter[]>(
      `/api/projects/${projectId}/filters`
    );
    return res.data;
  },

  create: async (projectId: number, data: { name: string; conditions: FilterCondition[]; logic: string }) => {
    const res = await client.post<SavedFilter>(
      `/api/projects/${projectId}/filters`,
      data
    );
    return res.data;
  },

  update: async (projectId: number, filterId: number, data: Partial<SavedFilter>) => {
    const res = await client.put<SavedFilter>(
      `/api/projects/${projectId}/filters/${filterId}`,
      data
    );
    return res.data;
  },

  delete: async (projectId: number, filterId: number) => {
    const res = await client.delete<{ deleted: string }>(
      `/api/projects/${projectId}/filters/${filterId}`
    );
    return res.data;
  },

  apply: async (projectId: number, conditions: FilterCondition[], logic: string, sheetName?: string) => {
    const res = await client.post<TestCase[]>(
      `/api/projects/${projectId}/filters/apply`,
      { name: "_temp", conditions, logic },
      { params: sheetName ? { sheet_name: sheetName } : undefined }
    );
    return res.data;
  },
};

