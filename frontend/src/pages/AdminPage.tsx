import { useEffect, useState } from "react";
import { usersApi, projectsApi, membersApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import type { User, Project, ProjectMember } from "../types";
import { UserRole } from "../types";
import Header from "../components/Header";
import toast from "react-hot-toast";

const SYSTEM_ROLES: { value: string; label: string }[] = [
  { value: "user", label: "일반 사용자" },
  { value: "qa_manager", label: "QA 관리자" },
  { value: "admin", label: "시스템 관리자" },
];

const PROJECT_ROLES: { value: string; label: string }[] = [
  { value: "tester", label: "테스터" },
  { value: "admin", label: "관리자" },
];

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [tempPwInfo, setTempPwInfo] = useState<{ username: string; password: string } | null>(null);

  // 프로젝트 배정 모달
  const [assignTarget, setAssignTarget] = useState<User | null>(null);
  const [assignedProjects, setAssignedProjects] = useState<ProjectMember[]>([]);
  const [assignProjectId, setAssignProjectId] = useState<number | "">("");
  const [assignRole, setAssignRole] = useState("tester");
  const [assignLoading, setAssignLoading] = useState(false);

  // 전체 유저별 프로젝트 배정 정보 (한 눈에 보기용)
  const [allAssignments, setAllAssignments] = useState<Record<number, { id: number; project_id: number; project_name: string; role: string }[]>>({});

  const loadUsers = async () => {
    try {
      const data = await usersApi.list();
      setUsers(data);
    } catch (err) {
      console.error(err);
      toast.error("사용자 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const loadProjects = async () => {
    try {
      const data = await projectsApi.list();
      setProjects(data);
    } catch (err) { console.error(err); }
  };

  const loadAllAssignments = async () => {
    try {
      const data = await usersApi.getAllAssignments();
      // API returns string keys, convert to number keys
      const mapped: Record<number, { id: number; project_id: number; project_name: string; role: string }[]> = {};
      for (const [key, val] of Object.entries(data)) {
        mapped[Number(key)] = val;
      }
      setAllAssignments(mapped);
    } catch (err) { console.error(err); }
  };

  useEffect(() => {
    if (currentUser?.role === UserRole.ADMIN) {
      loadUsers();
      loadProjects();
      loadAllAssignments();
    } else {
      setLoading(false);
    }
  }, [currentUser]);

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await usersApi.updateRole(userId, newRole);
      toast.success("역할이 변경되었습니다.");
      loadUsers();
    } catch (err) {
      console.error(err);
      toast.error("역할 변경에 실패했습니다.");
    }
  };

  const handleResetPassword = async (user: User) => {
    if (!confirm(`${user.display_name}(${user.username})의 비밀번호를 초기화하시겠습니까?`)) return;
    try {
      const { temp_password } = await usersApi.resetPassword(user.id);
      setTempPwInfo({ username: user.username, password: temp_password });
    } catch (err) {
      console.error(err);
      toast.error("비밀번호 초기화에 실패했습니다.");
    }
  };

  // 프로젝트 배정 모달 열기
  const openAssignModal = async (user: User) => {
    setAssignTarget(user);
    setAssignProjectId("");
    setAssignRole("tester");
    setAssignedProjects([]);
    // 모든 프로젝트의 멤버를 순회해서 이 사용자가 속한 프로젝트 추출
    try {
      const allMembers: ProjectMember[] = [];
      for (const p of projects) {
        const members = await membersApi.list(p.id);
        const found = members.find((m) => m.user_id === user.id);
        if (found) allMembers.push(found);
      }
      setAssignedProjects(allMembers);
    } catch (err) { console.error(err); }
  };

  const handleAddProject = async () => {
    if (!assignTarget || !assignProjectId) return;
    setAssignLoading(true);
    try {
      await membersApi.add(Number(assignProjectId), assignTarget.id, assignRole);
      toast.success("프로젝트에 배정되었습니다.");
      await openAssignModal(assignTarget);
      loadAllAssignments();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "배정에 실패했습니다.";
      toast.error(msg);
    } finally {
      setAssignLoading(false);
    }
  };

  const handleAssignAll = async () => {
    if (!assignTarget) return;
    if (!confirm(`${assignTarget.display_name}을(를) 모든 프로젝트에 "${PROJECT_ROLES.find(r => r.value === assignRole)?.label}" 역할로 배정하시겠습니까?`)) return;
    setAssignLoading(true);
    try {
      const result = await usersApi.assignToAllProjects(assignTarget.id, assignRole);
      toast.success(`${result.assigned}개 프로젝트에 배정되었습니다.`);
      await openAssignModal(assignTarget);
      loadAllAssignments();
    } catch (err) {
      console.error(err);
      toast.error("일괄 배정에 실패했습니다.");
    } finally {
      setAssignLoading(false);
    }
  };

  const handleRemoveProject = async (member: ProjectMember) => {
    if (!assignTarget) return;
    try {
      await membersApi.remove(member.project_id, member.id);
      toast.success("프로젝트에서 제거되었습니다.");
      await openAssignModal(assignTarget);
      loadAllAssignments();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "제거에 실패했습니다.";
      toast.error(msg);
    }
  };

  const handleChangeProjectRole = async (member: ProjectMember, newRole: string) => {
    try {
      await membersApi.updateRole(member.project_id, member.id, newRole);
      toast.success("프로젝트 역할이 변경되었습니다.");
      if (assignTarget) await openAssignModal(assignTarget);
      loadAllAssignments();
    } catch (err) {
      console.error(err);
      toast.error("역할 변경에 실패했습니다.");
    }
  };

  if (currentUser?.role !== UserRole.ADMIN) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
        <Header />
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
          관리자 권한이 필요합니다.
        </div>
      </div>
    );
  }

  const getProjectName = (projectId: number) => projects.find(p => p.id === projectId)?.name || `#${projectId}`;
  const unassignedProjects = projects.filter(p => !assignedProjects.some(m => m.project_id === p.id));

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
      <Header />
      <div style={s.container}>
        <h2 style={s.title}>사용자 관리</h2>
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>불러오는 중...</div>
        ) : (
          <div style={s.tableWrap}>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>ID</th>
                  <th style={s.th}>사용자명</th>
                  <th style={s.th}>표시명</th>
                  <th style={s.th}>시스템 역할</th>
                  <th style={s.th}>프로젝트 배정</th>
                  <th style={s.th}>가입일</th>
                  <th style={s.th}>비밀번호</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={s.td}>{u.id}</td>
                    <td style={s.td}>{u.username}</td>
                    <td style={s.td}>{u.display_name}</td>
                    <td style={s.td}>
                      <select
                        style={s.select}
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        disabled={u.id === currentUser?.id}
                      >
                        {SYSTEM_ROLES.map((r) => (
                          <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                      </select>
                    </td>
                    <td style={s.td}>
                      {u.role === "user" ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                            {(allAssignments[u.id] || []).length > 0 ? (
                              (allAssignments[u.id] || []).map((a) => (
                                <span
                                  key={a.id}
                                  style={{
                                    ...s.projectTag,
                                    backgroundColor: a.role === "admin" ? "var(--bg-info-light)" : "var(--bg-badge-gray)",
                                    color: a.role === "admin" ? "var(--text-info)" : "var(--text-badge-gray)",
                                    borderColor: a.role === "admin" ? "#93C5FD" : "#D1D5DB",
                                  }}
                                  title={`${a.project_name} (${a.role === "admin" ? "관리자" : "테스터"})`}
                                >
                                  {a.project_name}
                                  <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 2 }}>
                                    {a.role === "admin" ? "관리" : "테스트"}
                                  </span>
                                </span>
                              ))
                            ) : (
                              <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>미배정</span>
                            )}
                          </div>
                          <button style={s.assignBtn} onClick={() => openAssignModal(u)}>
                            관리
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>전체 접근</span>
                      )}
                    </td>
                    <td style={s.td}>{new Date(u.created_at).toLocaleDateString("ko-KR")}</td>
                    <td style={s.td}>
                      {u.id !== currentUser?.id && (
                        <button style={s.resetBtn} onClick={() => handleResetPassword(u)}>
                          초기화
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 비밀번호 초기화 모달 */}
        {tempPwInfo && (
          <div style={s.overlay} onClick={() => setTempPwInfo(null)}>
            <div style={s.modal} onClick={(e) => e.stopPropagation()}>
              <h3 style={s.modalTitle}>비밀번호 초기화 완료</h3>
              <p style={s.modalDesc}>
                <strong>{tempPwInfo.username}</strong>의 임시 비밀번호가 발급되었습니다.<br />
                사용자에게 전달해 주세요. 로그인 시 비밀번호 변경이 강제됩니다.
              </p>
              <div style={s.tempPwBox}>{tempPwInfo.password}</div>
              <button
                style={s.copyBtn}
                onClick={() => {
                  navigator.clipboard.writeText(tempPwInfo.password);
                  toast.success("클립보드에 복사되었습니다.");
                }}
              >
                복사
              </button>
              <button style={s.closeBtn} onClick={() => setTempPwInfo(null)}>닫기</button>
            </div>
          </div>
        )}

        {/* 프로젝트 배정 모달 */}
        {assignTarget && (
          <div style={s.overlay} onClick={() => setAssignTarget(null)}>
            <div style={{ ...s.modal, width: 520, textAlign: "left" as const }} onClick={(e) => e.stopPropagation()}>
              <h3 style={s.modalTitle}>
                {assignTarget.display_name} 프로젝트 배정
              </h3>

              {/* 현재 배정된 프로젝트 */}
              {assignedProjects.length > 0 ? (
                <table style={{ ...s.table, marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th style={s.th}>프로젝트</th>
                      <th style={s.th}>역할</th>
                      <th style={s.th}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {assignedProjects.map((m) => (
                      <tr key={m.id}>
                        <td style={s.td}>{getProjectName(m.project_id)}</td>
                        <td style={s.td}>
                          <select
                            style={s.select}
                            value={m.role}
                            onChange={(e) => handleChangeProjectRole(m, e.target.value)}
                          >
                            {PROJECT_ROLES.map((r) => (
                              <option key={r.value} value={r.value}>{r.label}</option>
                            ))}
                          </select>
                        </td>
                        <td style={s.td}>
                          <button
                            style={{ ...s.resetBtn, fontSize: 11, padding: "2px 8px" }}
                            onClick={() => handleRemoveProject(m)}
                          >
                            제거
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ padding: "12px 0", fontSize: 13, color: "var(--text-secondary)" }}>
                  배정된 프로젝트가 없습니다.
                </div>
              )}

              {/* 프로젝트 추가 */}
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
                <select
                  style={{ ...s.select, flex: 1 }}
                  value={assignProjectId}
                  onChange={(e) => setAssignProjectId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">-- 프로젝트 선택 --</option>
                  {unassignedProjects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                <select style={s.select} value={assignRole} onChange={(e) => setAssignRole(e.target.value)}>
                  {PROJECT_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
                <button
                  style={{ ...s.copyBtn, opacity: !assignProjectId || assignLoading ? 0.4 : 1 }}
                  disabled={!assignProjectId || assignLoading}
                  onClick={handleAddProject}
                >
                  추가
                </button>
              </div>

              {/* 전체 프로젝트 일괄 배정 */}
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
                <button
                  style={{ ...s.assignAllBtn, opacity: assignLoading ? 0.4 : 1 }}
                  disabled={assignLoading}
                  onClick={handleAssignAll}
                >
                  전체 프로젝트 일괄 배정 ({assignRole === "tester" ? "테스터" : "관리자"})
                </button>
              </div>

              <div style={{ textAlign: "right" as const }}>
                <button style={s.closeBtn} onClick={() => setAssignTarget(null)}>닫기</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: { maxWidth: 900, margin: "0 auto", padding: "24px" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--text-primary)", margin: "0 0 20px" },
  tableWrap: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    boxShadow: "var(--shadow)",
    overflow: "auto",
  },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: {
    textAlign: "left" as const,
    padding: "10px 14px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
  },
  td: {
    padding: "10px 14px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
  },
  select: {
    padding: "4px 8px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 13,
    outline: "none",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  assignBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid var(--accent)",
    backgroundColor: "transparent",
    color: "var(--accent)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  resetBtn: {
    padding: "4px 10px",
    borderRadius: 6,
    border: "1px solid #DC2626",
    backgroundColor: "transparent",
    color: "#DC2626",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  overlay: {
    position: "fixed" as const, top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)", display: "flex",
    justifyContent: "center", alignItems: "center", zIndex: 1000,
  },
  modal: {
    backgroundColor: "var(--bg-card)", borderRadius: 12,
    padding: "28px 32px", width: 400, boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
    textAlign: "center" as const, maxHeight: "80vh", overflow: "auto" as const,
  },
  modalTitle: { margin: "0 0 16px", fontSize: 18, fontWeight: 700, color: "var(--text-primary)" },
  modalDesc: { fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: "0 0 16px" },
  tempPwBox: {
    padding: "12px 16px", borderRadius: 8,
    backgroundColor: "var(--bg-input)", border: "1px solid var(--border-input)",
    fontSize: 18, fontWeight: 700, fontFamily: "monospace",
    color: "var(--text-primary)", letterSpacing: 1, marginBottom: 16,
  },
  copyBtn: {
    padding: "8px 20px", borderRadius: 6, border: "none",
    backgroundColor: "var(--accent)", color: "#fff", fontSize: 13,
    fontWeight: 600, cursor: "pointer", marginRight: 8,
  },
  closeBtn: {
    padding: "8px 20px", borderRadius: 6,
    border: "1px solid var(--border-input)", backgroundColor: "transparent",
    color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
  },
  assignAllBtn: {
    padding: "8px 16px", borderRadius: 6, border: "1px solid var(--color-pass)",
    backgroundColor: "transparent", color: "var(--color-pass)",
    fontSize: 12, fontWeight: 600, cursor: "pointer",
  },
  projectTag: {
    display: "inline-flex", alignItems: "center", gap: 2,
    padding: "2px 8px", borderRadius: 4, fontSize: 11,
    fontWeight: 500, border: "1px solid",
    whiteSpace: "nowrap" as const, lineHeight: 1.4,
  },
};
