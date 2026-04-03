import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the client module
vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import client from "../api/client";
import {
  authApi,
  projectsApi,
  testCasesApi,
  testRunsApi,
  dashboardApi,
  reportsApi,
  overviewApi,
  attachmentsApi,
  searchApi,
  membersApi,
  usersApi,
  customFieldsApi,
  testPlansApi,
  filtersApi,
  historyApi,
} from "../api/index";

const mockGet = vi.mocked(client.get);
const mockPost = vi.mocked(client.post);
const mockPut = vi.mocked(client.put);
const mockDelete = vi.mocked(client.delete);

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Auth ────────────────────────────────────────────
describe("authApi", () => {
  it("login sends POST with form data", async () => {
    const token = { access_token: "abc", token_type: "bearer" };
    mockPost.mockResolvedValueOnce({ data: token });
    const form = { username: "user1", password: "pass123" };
    const result = await authApi.login(form);
    expect(mockPost).toHaveBeenCalledWith("/api/auth/login", form);
    expect(result).toEqual(token);
  });

  it("register sends POST with user data", async () => {
    const user = { id: 1, username: "user1" };
    mockPost.mockResolvedValueOnce({ data: user });
    const form = { username: "user1", password: "pass123", display_name: "User" };
    const result = await authApi.register(form);
    expect(mockPost).toHaveBeenCalledWith("/api/auth/register", form);
    expect(result).toEqual(user);
  });

  it("getMe sends GET to /api/auth/me", async () => {
    const user = { id: 1, username: "user1" };
    mockGet.mockResolvedValueOnce({ data: user });
    const result = await authApi.getMe();
    expect(mockGet).toHaveBeenCalledWith("/api/auth/me");
    expect(result).toEqual(user);
  });

  it("checkUsername sends GET with query param", async () => {
    mockGet.mockResolvedValueOnce({ data: { available: true } });
    const result = await authApi.checkUsername("testuser");
    expect(mockGet).toHaveBeenCalledWith("/api/auth/check-username", {
      params: { username: "testuser" },
    });
    expect(result).toEqual({ available: true });
  });

  it("changePassword sends PUT with passwords", async () => {
    const user = { id: 1, username: "user1" };
    mockPut.mockResolvedValueOnce({ data: user });
    const result = await authApi.changePassword("old", "new");
    expect(mockPut).toHaveBeenCalledWith("/api/auth/change-password", {
      current_password: "old",
      new_password: "new",
    });
    expect(result).toEqual(user);
  });

  it("logout sends POST to /api/auth/logout", async () => {
    mockPost.mockResolvedValueOnce({ data: {} });
    await authApi.logout();
    expect(mockPost).toHaveBeenCalledWith("/api/auth/logout");
  });
});

// ─── Projects ────────────────────────────────────────
describe("projectsApi", () => {
  it("list sends GET to /api/projects", async () => {
    const projects = [{ id: 1, name: "P1" }];
    mockGet.mockResolvedValueOnce({ data: projects });
    const result = await projectsApi.list();
    expect(mockGet).toHaveBeenCalledWith("/api/projects");
    expect(result).toEqual(projects);
  });

  it("getOne sends GET with project id", async () => {
    const project = { id: 5, name: "P5" };
    mockGet.mockResolvedValueOnce({ data: project });
    const result = await projectsApi.getOne(5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/5");
    expect(result).toEqual(project);
  });

  it("create sends POST with data", async () => {
    const project = { id: 1, name: "New" };
    mockPost.mockResolvedValueOnce({ data: project });
    const result = await projectsApi.create({ name: "New" });
    expect(mockPost).toHaveBeenCalledWith("/api/projects", { name: "New" });
    expect(result).toEqual(project);
  });

  it("update sends PUT with data", async () => {
    const project = { id: 1, name: "Updated" };
    mockPut.mockResolvedValueOnce({ data: project });
    const result = await projectsApi.update(1, { name: "Updated" });
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1", { name: "Updated" });
    expect(result).toEqual(project);
  });

  it("delete sends DELETE with project id", async () => {
    mockDelete.mockResolvedValueOnce({ data: {} });
    await projectsApi.delete(3);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/3");
  });
});

// ─── Test Cases ──────────────────────────────────────
describe("testCasesApi", () => {
  it("list sends GET with params", async () => {
    const tcs = [{ id: 1, title: "TC1" }];
    mockGet.mockResolvedValueOnce({ data: tcs });
    const result = await testCasesApi.list(1, { sheet_name: "Sheet1" });
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testcases", {
      params: { sheet_name: "Sheet1" },
    });
    expect(result).toEqual(tcs);
  });

  it("create sends POST with test case data", async () => {
    const tc = { id: 1, title: "New TC" };
    mockPost.mockResolvedValueOnce({ data: tc });
    const result = await testCasesApi.create(2, { depth1: "New TC" });
    expect(mockPost).toHaveBeenCalledWith("/api/projects/2/testcases", { depth1: "New TC" });
    expect(result).toEqual(tc);
  });

  it("update sends PUT with tc id and data", async () => {
    const tc = { id: 10, title: "Updated" };
    mockPut.mockResolvedValueOnce({ data: tc });
    const result = await testCasesApi.update(1, 10, { depth1: "Updated" });
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testcases/10", { depth1: "Updated" });
    expect(result).toEqual(tc);
  });

  it("bulkUpdate sends PUT with items array", async () => {
    const tcs = [{ id: 1 }, { id: 2 }];
    mockPut.mockResolvedValueOnce({ data: tcs });
    const items = [{ id: 1, title: "A" }, { id: 2, title: "B" }];
    const result = await testCasesApi.bulkUpdate(1, items);
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testcases/bulk", { items });
    expect(result).toEqual(tcs);
  });

  it("delete sends DELETE with tc id", async () => {
    mockDelete.mockResolvedValueOnce({ data: {} });
    await testCasesApi.delete(1, 5);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/testcases/5");
  });

  it("bulkDelete sends DELETE with joined ids", async () => {
    mockDelete.mockResolvedValueOnce({ data: { deleted: 3 } });
    const result = await testCasesApi.bulkDelete(1, [10, 20, 30]);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/testcases/bulk", {
      params: { ids: "10,20,30" },
    });
    expect(result).toEqual({ deleted: 3 });
  });

  it("restore sends POST to restore endpoint", async () => {
    const tc = { id: 5, title: "Restored" };
    mockPost.mockResolvedValueOnce({ data: tc });
    const result = await testCasesApi.restore(1, 5);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testcases/5/restore");
    expect(result).toEqual(tc);
  });

  it("importExcel sends FormData with file and sheet_names param", async () => {
    const resp = { created: 5, updated: 2, imported: 7, sheets: [] };
    mockPost.mockResolvedValueOnce({ data: resp });
    const file = new File(["content"], "test.xlsx");
    const result = await testCasesApi.importExcel(1, file, ["Sheet1", "Sheet2"]);
    expect(mockPost).toHaveBeenCalledWith(
      "/api/projects/1/testcases/import",
      expect.any(FormData),
      { headers: { "Content-Type": "multipart/form-data" }, params: { sheet_names: "Sheet1,Sheet2" } }
    );
    expect(result).toEqual(resp);
  });

  it("importExcel without sheetNames sends empty params", async () => {
    const resp = { created: 1, updated: 0, imported: 1, sheets: [] };
    mockPost.mockResolvedValueOnce({ data: resp });
    const file = new File(["content"], "test.xlsx");
    const result = await testCasesApi.importExcel(1, file);
    expect(mockPost).toHaveBeenCalledWith(
      "/api/projects/1/testcases/import",
      expect.any(FormData),
      { headers: { "Content-Type": "multipart/form-data" }, params: {} }
    );
    expect(result).toEqual(resp);
  });

  it("previewImport sends FormData", async () => {
    const resp = { sheets: [{ name: "S1", tc_count: 10, existing: 3 }] };
    mockPost.mockResolvedValueOnce({ data: resp });
    const file = new File(["content"], "test.xlsx");
    const result = await testCasesApi.previewImport(1, file);
    expect(mockPost).toHaveBeenCalledWith(
      "/api/projects/1/testcases/import/preview",
      expect.any(FormData),
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    expect(result).toEqual(resp);
  });

  it("createSheet sends POST with name, parent_id, and is_folder", async () => {
    const sheet = { id: 1, name: "NewSheet" };
    mockPost.mockResolvedValueOnce({ data: sheet });
    const result = await testCasesApi.createSheet(1, "NewSheet", 5, false);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testcases/sheets", {
      name: "NewSheet",
      parent_id: 5,
      is_folder: false,
    });
    expect(result).toEqual(sheet);
  });

  it("createSheet with no parentId sends null", async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 1, name: "S" } });
    await testCasesApi.createSheet(1, "S");
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testcases/sheets", {
      name: "S",
      parent_id: null,
      is_folder: false,
    });
  });

  it("createSheet as folder sends is_folder=true", async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 2, name: "F" } });
    await testCasesApi.createSheet(1, "F", null, true);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testcases/sheets", {
      name: "F",
      parent_id: null,
      is_folder: true,
    });
  });

  it("deleteSheet encodes sheet name in URL", async () => {
    mockDelete.mockResolvedValueOnce({ data: { deleted: 2, sheet: "My Sheet" } });
    const result = await testCasesApi.deleteSheet(1, "My Sheet");
    expect(mockDelete).toHaveBeenCalledWith(
      `/api/projects/1/testcases/sheets/${encodeURIComponent("My Sheet")}`
    );
    expect(result).toEqual({ deleted: 2, sheet: "My Sheet" });
  });

  it("listSheets sends GET", async () => {
    const sheets = [{ id: 1, name: "S1" }];
    mockGet.mockResolvedValueOnce({ data: sheets });
    const result = await testCasesApi.listSheets(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testcases/sheets");
    expect(result).toEqual(sheets);
  });

  it("renameSheet sends PUT with new_name", async () => {
    const resp = { id: 1, name: "New", old_name: "Old" };
    mockPut.mockResolvedValueOnce({ data: resp });
    const result = await testCasesApi.renameSheet(1, 1, "New");
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testcases/sheets/1/rename", {
      new_name: "New",
    });
    expect(result).toEqual(resp);
  });

  it("moveSheet sends PUT with parent_id and sort_order", async () => {
    mockPut.mockResolvedValueOnce({ data: { ok: true } });
    const result = await testCasesApi.moveSheet(1, 3, 2, 5);
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testcases/sheets/3/move", {
      parent_id: 2,
      sort_order: 5,
    });
    expect(result).toEqual({ ok: true });
  });

  it("exportExcel sends GET with blob responseType", async () => {
    const blob = new Blob(["data"]);
    mockGet.mockResolvedValueOnce({ data: blob });
    const result = await testCasesApi.exportExcel(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testcases/export", {
      responseType: "blob",
    });
    expect(result).toBe(blob);
  });
});

// ─── Test Runs ───────────────────────────────────────
describe("testRunsApi", () => {
  it("list sends GET", async () => {
    const runs = [{ id: 1, name: "Run1" }];
    mockGet.mockResolvedValueOnce({ data: runs });
    const result = await testRunsApi.list(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testruns");
    expect(result).toEqual(runs);
  });

  it("create sends POST with data", async () => {
    const run = { id: 1, name: "New Run" };
    mockPost.mockResolvedValueOnce({ data: run });
    const result = await testRunsApi.create(1, { name: "New Run" });
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testruns", { name: "New Run" });
    expect(result).toEqual(run);
  });

  it("getOne sends GET with run id", async () => {
    const run = { id: 5, results: [] };
    mockGet.mockResolvedValueOnce({ data: run });
    const result = await testRunsApi.getOne(1, 5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testruns/5");
    expect(result).toEqual(run);
  });

  it("submitResults sends POST with results array", async () => {
    const results = [{ id: 1, status: "PASS" }];
    mockPost.mockResolvedValueOnce({ data: results });
    const input: Partial<import("../types").TestResult>[] = [{ test_case_id: 1, result: "PASS" }];
    const result = await testRunsApi.submitResults(1, 5, input);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testruns/5/results", input);
    expect(result).toEqual(results);
  });

  it("complete sends PUT to complete endpoint", async () => {
    const run = { id: 5, status: "completed" };
    mockPut.mockResolvedValueOnce({ data: run });
    const result = await testRunsApi.complete(1, 5);
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testruns/5/complete");
    expect(result).toEqual(run);
  });

  it("reopen sends PUT to reopen endpoint", async () => {
    const run = { id: 5, status: "in_progress" };
    mockPut.mockResolvedValueOnce({ data: run });
    const result = await testRunsApi.reopen(1, 5);
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testruns/5/reopen");
    expect(result).toEqual(run);
  });

  it("clone sends POST to clone endpoint", async () => {
    const run = { id: 6, name: "Run1 (copy)" };
    mockPost.mockResolvedValueOnce({ data: run });
    const result = await testRunsApi.clone(1, 5);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testruns/5/clone");
    expect(result).toEqual(run);
  });

  it("delete sends DELETE", async () => {
    mockDelete.mockResolvedValueOnce({ data: {} });
    await testRunsApi.delete(1, 5);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/testruns/5");
  });

  it("exportExcel sends GET with blob responseType", async () => {
    const blob = new Blob(["data"]);
    mockGet.mockResolvedValueOnce({ data: blob });
    const result = await testRunsApi.exportExcel(1, 5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testruns/5/export", {
      responseType: "blob",
    });
    expect(result).toBe(blob);
  });
});

// ─── Dashboard ───────────────────────────────────────
describe("dashboardApi", () => {
  it("summary sends GET without runId", async () => {
    const data = { total: 100 };
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.summary(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/summary", {
      params: undefined,
    });
    expect(result).toEqual(data);
  });

  it("summary sends GET with runId param", async () => {
    const data = { total: 50 };
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.summary(1, 10);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/summary", {
      params: { run_id: 10 },
    });
    expect(result).toEqual(data);
  });

  it("priority sends GET with optional runId", async () => {
    const data = [{ priority: "High", count: 5 }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.priority(1, 3);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/priority", {
      params: { run_id: 3 },
    });
    expect(result).toEqual(data);
  });

  it("category sends GET", async () => {
    const data = [{ category: "Login", count: 10 }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.category(2);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/2/dashboard/category", {
      params: undefined,
    });
    expect(result).toEqual(data);
  });

  it("rounds sends GET", async () => {
    const data = [{ round: 1, pass: 10 }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.rounds(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/rounds", {
      params: undefined,
    });
    expect(result).toEqual(data);
  });

  it("assignee sends GET with optional runId", async () => {
    const data = [{ assignee: "user1", count: 5 }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.assignee(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/assignee", {
      params: undefined,
    });
    expect(result).toEqual(data);
  });

  it("heatmap sends GET with runId", async () => {
    const data = [{ category: "Auth", priority: "High", fail_count: 3 }];
    mockGet.mockResolvedValueOnce({ data });
    const result = await dashboardApi.heatmap(1, 7);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/dashboard/heatmap", {
      params: { run_id: 7 },
    });
    expect(result).toEqual(data);
  });
});

// ─── Reports ─────────────────────────────────────────
describe("reportsApi", () => {
  it("getData sends GET with run_id param", async () => {
    const data = { summary: {} };
    mockGet.mockResolvedValueOnce({ data });
    const result = await reportsApi.getData(1, 5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/reports", {
      params: { run_id: 5 },
    });
    expect(result).toEqual(data);
  });

  it("downloadPdf sends GET with blob responseType", async () => {
    const blob = new Blob(["pdf"]);
    mockGet.mockResolvedValueOnce({ data: blob });
    const result = await reportsApi.downloadPdf(1, 5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/reports/pdf", {
      params: { run_id: 5 },
      responseType: "blob",
    });
    expect(result).toBe(blob);
  });

  it("downloadExcel sends GET with blob responseType", async () => {
    const blob = new Blob(["excel"]);
    mockGet.mockResolvedValueOnce({ data: blob });
    const result = await reportsApi.downloadExcel(1, 5);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/reports/excel", {
      params: { run_id: 5 },
      responseType: "blob",
    });
    expect(result).toBe(blob);
  });
});

// ─── Overview ────────────────────────────────────────
describe("overviewApi", () => {
  it("get sends GET to /api/dashboard/overview", async () => {
    const data = { projects: 5 };
    mockGet.mockResolvedValueOnce({ data });
    const result = await overviewApi.get();
    expect(mockGet).toHaveBeenCalledWith("/api/dashboard/overview");
    expect(result).toEqual(data);
  });
});

// ─── Attachments ─────────────────────────────────────
describe("attachmentsApi", () => {
  it("list sends GET with testResultId", async () => {
    const attachments = [{ id: 1, filename: "f.png" }];
    mockGet.mockResolvedValueOnce({ data: attachments });
    const result = await attachmentsApi.list(10);
    expect(mockGet).toHaveBeenCalledWith("/api/attachments/10");
    expect(result).toEqual(attachments);
  });

  it("upload sends FormData with file", async () => {
    const attachment = { id: 1, filename: "test.png" };
    mockPost.mockResolvedValueOnce({ data: attachment });
    const file = new File(["img"], "test.png");
    const result = await attachmentsApi.upload(10, file);
    expect(mockPost).toHaveBeenCalledWith(
      "/api/attachments/10",
      expect.any(FormData),
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    expect(result).toEqual(attachment);
  });

  it("downloadUrl returns correct URL", () => {
    expect(attachmentsApi.downloadUrl(42)).toBe("/api/attachments/download/42");
  });

  it("delete sends DELETE with attachment id", async () => {
    mockDelete.mockResolvedValueOnce({ data: {} });
    await attachmentsApi.delete(42);
    expect(mockDelete).toHaveBeenCalledWith("/api/attachments/42");
  });
});

// ─── Search ──────────────────────────────────────────
describe("searchApi", () => {
  it("global sends GET with query param", async () => {
    const tcs = [{ id: 1, title: "Login TC" }];
    mockGet.mockResolvedValueOnce({ data: tcs });
    const result = await searchApi.global("login");
    expect(mockGet).toHaveBeenCalledWith("/api/search", { params: { q: "login" } });
    expect(result).toEqual(tcs);
  });
});

// ─── Members ─────────────────────────────────────────
describe("membersApi", () => {
  it("list sends GET", async () => {
    const members = [{ id: 1, user_id: 1, role: "admin" }];
    mockGet.mockResolvedValueOnce({ data: members });
    const result = await membersApi.list(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/members");
    expect(result).toEqual(members);
  });

  it("add sends POST with user_id and role", async () => {
    const member = { id: 1, user_id: 5, role: "tester" };
    mockPost.mockResolvedValueOnce({ data: member });
    const result = await membersApi.add(1, 5, "tester");
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/members", {
      user_id: 5,
      role: "tester",
    });
    expect(result).toEqual(member);
  });

  it("updateRole sends PUT with role", async () => {
    const member = { id: 3, role: "admin" };
    mockPut.mockResolvedValueOnce({ data: member });
    const result = await membersApi.updateRole(1, 3, "admin");
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/members/3", { role: "admin" });
    expect(result).toEqual(member);
  });

  it("remove sends DELETE", async () => {
    mockDelete.mockResolvedValueOnce({ data: {} });
    await membersApi.remove(1, 3);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/members/3");
  });
});

// ─── History ─────────────────────────────────────────
describe("historyApi", () => {
  it("getTestCaseHistory sends GET with tc id", async () => {
    const history = [{ id: 1, action: "create" }];
    mockGet.mockResolvedValueOnce({ data: history });
    const result = await historyApi.getTestCaseHistory(10);
    expect(mockGet).toHaveBeenCalledWith("/api/history/testcase/10");
    expect(result).toEqual(history);
  });

  it("getProjectHistory sends GET with project id", async () => {
    const history = [{ id: 1, action: "update" }];
    mockGet.mockResolvedValueOnce({ data: history });
    const result = await historyApi.getProjectHistory(1);
    expect(mockGet).toHaveBeenCalledWith("/api/history/project/1");
    expect(result).toEqual(history);
  });
});

// ─── Users (admin) ───────────────────────────────────
describe("usersApi", () => {
  it("list sends GET to /api/auth/users", async () => {
    const users = [{ id: 1, username: "admin" }];
    mockGet.mockResolvedValueOnce({ data: users });
    const result = await usersApi.list();
    expect(mockGet).toHaveBeenCalledWith("/api/auth/users");
    expect(result).toEqual(users);
  });

  it("updateRole sends PUT with role", async () => {
    const user = { id: 1, role: "admin" };
    mockPut.mockResolvedValueOnce({ data: user });
    const result = await usersApi.updateRole(1, "admin");
    expect(mockPut).toHaveBeenCalledWith("/api/auth/users/1/role", { role: "admin" });
    expect(result).toEqual(user);
  });

  it("resetPassword sends PUT", async () => {
    mockPut.mockResolvedValueOnce({ data: { temp_password: "abc123" } });
    const result = await usersApi.resetPassword(1);
    expect(mockPut).toHaveBeenCalledWith("/api/auth/users/1/reset-password");
    expect(result).toEqual({ temp_password: "abc123" });
  });

  it("getAllAssignments sends GET", async () => {
    const data = { user1: [{ id: 1, project_id: 1, project_name: "P1", role: "admin" }] };
    mockGet.mockResolvedValueOnce({ data });
    const result = await usersApi.getAllAssignments();
    expect(mockGet).toHaveBeenCalledWith("/api/projects/all-assignments");
    expect(result).toEqual(data);
  });

  it("assignToAllProjects sends POST with user_id and role", async () => {
    const resp = { assigned: 3, total_projects: 3 };
    mockPost.mockResolvedValueOnce({ data: resp });
    const result = await usersApi.assignToAllProjects(5, "tester");
    expect(mockPost).toHaveBeenCalledWith("/api/projects/assign-all", {
      user_id: 5,
      role: "tester",
    });
    expect(result).toEqual(resp);
  });
});

// ─── Custom Fields ───────────────────────────────────
describe("customFieldsApi", () => {
  it("list sends GET", async () => {
    const fields = [{ id: 1, name: "Env" }];
    mockGet.mockResolvedValueOnce({ data: fields });
    const result = await customFieldsApi.list(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/custom-fields");
    expect(result).toEqual(fields);
  });

  it("create sends POST with data", async () => {
    const field = { id: 1, name: "Env", field_type: "text" };
    mockPost.mockResolvedValueOnce({ data: field });
    const result = await customFieldsApi.create(1, { name: "Env", field_type: "text" } as never);
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/custom-fields", {
      name: "Env",
      field_type: "text",
    });
    expect(result).toEqual(field);
  });

  it("update sends PUT with field id and data", async () => {
    const field = { id: 2, name: "Updated" };
    mockPut.mockResolvedValueOnce({ data: field });
    const result = await customFieldsApi.update(1, 2, { field_name: "Updated" });
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/custom-fields/2", { field_name: "Updated" });
    expect(result).toEqual(field);
  });

  it("delete sends DELETE with field id", async () => {
    mockDelete.mockResolvedValueOnce({ data: { deleted: "Env" } });
    const result = await customFieldsApi.delete(1, 2);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/custom-fields/2");
    expect(result).toEqual({ deleted: "Env" });
  });
});

// ─── Test Plans ──────────────────────────────────────
describe("testPlansApi", () => {
  it("list sends GET", async () => {
    const plans = [{ id: 1, name: "Plan1" }];
    mockGet.mockResolvedValueOnce({ data: plans });
    const result = await testPlansApi.list(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testplans");
    expect(result).toEqual(plans);
  });

  it("create sends POST with data", async () => {
    const plan = { id: 1, name: "New Plan" };
    mockPost.mockResolvedValueOnce({ data: plan });
    const result = await testPlansApi.create(1, { name: "New Plan" });
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/testplans", { name: "New Plan" });
    expect(result).toEqual(plan);
  });

  it("getOne sends GET with plan id", async () => {
    const plan = { id: 3, name: "Plan3" };
    mockGet.mockResolvedValueOnce({ data: plan });
    const result = await testPlansApi.getOne(1, 3);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testplans/3");
    expect(result).toEqual(plan);
  });

  it("update sends PUT with plan id and data", async () => {
    const plan = { id: 3, name: "Updated" };
    mockPut.mockResolvedValueOnce({ data: plan });
    const result = await testPlansApi.update(1, 3, { name: "Updated" });
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/testplans/3", { name: "Updated" });
    expect(result).toEqual(plan);
  });

  it("delete sends DELETE with plan id", async () => {
    mockDelete.mockResolvedValueOnce({ data: { deleted: "Plan3" } });
    const result = await testPlansApi.delete(1, 3);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/testplans/3");
    expect(result).toEqual({ deleted: "Plan3" });
  });

  it("listRuns sends GET for plan runs", async () => {
    const runs = [{ id: 1, name: "Run1" }];
    mockGet.mockResolvedValueOnce({ data: runs });
    const result = await testPlansApi.listRuns(1, 3);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/testplans/3/runs");
    expect(result).toEqual(runs);
  });
});

// ─── Saved Filters ───────────────────────────────────
describe("filtersApi", () => {
  it("list sends GET", async () => {
    const filters = [{ id: 1, name: "F1" }];
    mockGet.mockResolvedValueOnce({ data: filters });
    const result = await filtersApi.list(1);
    expect(mockGet).toHaveBeenCalledWith("/api/projects/1/filters");
    expect(result).toEqual(filters);
  });

  it("create sends POST with name, conditions, and logic", async () => {
    const filter = { id: 1, name: "High Priority" };
    mockPost.mockResolvedValueOnce({ data: filter });
    const conditions = [{ field: "priority", operator: "eq", value: "High" }];
    const result = await filtersApi.create(1, {
      name: "High Priority",
      conditions: conditions as never,
      logic: "AND",
    });
    expect(mockPost).toHaveBeenCalledWith("/api/projects/1/filters", {
      name: "High Priority",
      conditions,
      logic: "AND",
    });
    expect(result).toEqual(filter);
  });

  it("update sends PUT with filter id and data", async () => {
    const filter = { id: 2, name: "Updated" };
    mockPut.mockResolvedValueOnce({ data: filter });
    const result = await filtersApi.update(1, 2, { name: "Updated" } as never);
    expect(mockPut).toHaveBeenCalledWith("/api/projects/1/filters/2", { name: "Updated" });
    expect(result).toEqual(filter);
  });

  it("delete sends DELETE with filter id", async () => {
    mockDelete.mockResolvedValueOnce({ data: { deleted: "F1" } });
    const result = await filtersApi.delete(1, 2);
    expect(mockDelete).toHaveBeenCalledWith("/api/projects/1/filters/2");
    expect(result).toEqual({ deleted: "F1" });
  });

  it("apply sends POST with conditions and logic, no sheetName", async () => {
    const tcs = [{ id: 1, title: "TC1" }];
    mockPost.mockResolvedValueOnce({ data: tcs });
    const conditions = [{ field: "status", operator: "eq", value: "PASS" }];
    const result = await filtersApi.apply(1, conditions as never, "AND");
    expect(mockPost).toHaveBeenCalledWith(
      "/api/projects/1/filters/apply",
      { name: "_temp", conditions, logic: "AND" },
      { params: undefined }
    );
    expect(result).toEqual(tcs);
  });

  it("apply sends POST with sheetName param", async () => {
    const tcs = [{ id: 2, title: "TC2" }];
    mockPost.mockResolvedValueOnce({ data: tcs });
    const conditions = [{ field: "priority", operator: "eq", value: "Low" }];
    const result = await filtersApi.apply(1, conditions as never, "OR", "Sheet1");
    expect(mockPost).toHaveBeenCalledWith(
      "/api/projects/1/filters/apply",
      { name: "_temp", conditions, logic: "OR" },
      { params: { sheet_name: "Sheet1" } }
    );
    expect(result).toEqual(tcs);
  });
});
