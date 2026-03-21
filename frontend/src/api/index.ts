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
  AssigneeSummary,
  ReportData,
  SheetNode,
  CustomFieldDef,
  TestPlan,
  SavedFilter,
  FilterCondition,
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
    const res = await client.post<{ created: number; updated: number; imported: number; sheets: { sheet: string; created: number; updated: number }[] }>(
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

  createSheet: async (projectId: number, name: string, parentId?: number | null) => {
    const res = await client.post<SheetNode>(
      `/api/projects/${projectId}/testcases/sheets`,
      { name, parent_id: parentId ?? null }
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

  exportExcel: async (projectId: number) => {
    const res = await client.get(
      `/api/projects/${projectId}/testcases/export`,
      { responseType: "blob" }
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

  clone: async (projectId: number, runId: number) => {
    const res = await client.post<TestRun>(
      `/api/projects/${projectId}/testruns/${runId}/clone`
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
  summary: async (projectId: number, runId?: number) => {
    const res = await client.get<DashboardSummary>(
      `/api/projects/${projectId}/dashboard/summary`,
      { params: runId ? { run_id: runId } : undefined }
    );
    return res.data;
  },

  priority: async (projectId: number, runId?: number) => {
    const res = await client.get<PriorityDistribution[]>(
      `/api/projects/${projectId}/dashboard/priority`,
      { params: runId ? { run_id: runId } : undefined }
    );
    return res.data;
  },

  category: async (projectId: number, runId?: number) => {
    const res = await client.get<CategoryBreakdown[]>(
      `/api/projects/${projectId}/dashboard/category`,
      { params: runId ? { run_id: runId } : undefined }
    );
    return res.data;
  },

  rounds: async (projectId: number) => {
    const res = await client.get<RoundComparison[]>(
      `/api/projects/${projectId}/dashboard/rounds`
    );
    return res.data;
  },

  assignee: async (projectId: number, runId?: number) => {
    const res = await client.get<AssigneeSummary[]>(
      `/api/projects/${projectId}/dashboard/assignee`,
      { params: runId ? { run_id: runId } : undefined }
    );
    return res.data;
  },

  heatmap: async (projectId: number, runId?: number) => {
    const res = await client.get<{ category: string; priority: string; fail_count: number }[]>(
      `/api/projects/${projectId}/dashboard/heatmap`,
      { params: runId ? { run_id: runId } : undefined }
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

  downloadPdf: async (projectId: number, runId: number) => {
    const res = await client.get(
      `/api/projects/${projectId}/reports/pdf`,
      { params: { run_id: runId }, responseType: "blob" }
    );
    return res.data;
  },

  downloadExcel: async (projectId: number, runId: number) => {
    const res = await client.get(
      `/api/projects/${projectId}/reports/excel`,
      { params: { run_id: runId }, responseType: "blob" }
    );
    return res.data;
  },
};

// ─── Attachments ──────────────────────────────────────
export const attachmentsApi = {
  list: async (testResultId: number) => {
    const res = await client.get<Attachment[]>(`/api/attachments/${testResultId}`);
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
