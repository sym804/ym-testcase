import { useEffect, useState } from "react";
import { membersApi } from "../api";
import type { ProjectMember, User } from "../types";
import toast from "react-hot-toast";

interface Props {
  projectId: number;
  createdBy: number;
  myRole: string | null | undefined;
}

const ROLES = ["tester", "admin"];
const ROLE_LABELS: Record<string, string> = {
  tester: "테스터",
  admin: "관리자",
};

export default function ProjectMembers({ projectId, createdBy, myRole }: Props) {
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [addUserId, setAddUserId] = useState<number | "">("");
  const [addRole, setAddRole] = useState("tester");

  const isAdmin = myRole === "admin";

  const load = async () => {
    try {
      const m = await membersApi.list(projectId);
      setMembers(m);
      if (isAdmin) {
        const users = await membersApi.availableUsers(projectId);
        setAllUsers(users);
      }
    } catch {
      toast.error("멤버 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleAdd = async () => {
    if (!addUserId) return;
    try {
      await membersApi.add(projectId, Number(addUserId), addRole);
      toast.success("멤버가 추가되었습니다.");
      setAddUserId("");
      setAddRole("tester");
      load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast.error(msg || "멤버 추가에 실패했습니다.");
    }
  };

  const handleRoleChange = async (memberId: number, role: string) => {
    try {
      await membersApi.updateRole(projectId, memberId, role);
      toast.success("역할이 변경되었습니다.");
      load();
    } catch {
      toast.error("역할 변경에 실패했습니다.");
    }
  };

  const handleRemove = async (memberId: number) => {
    if (!confirm("이 멤버를 제거하시겠습니까?")) return;
    try {
      await membersApi.remove(projectId, memberId);
      toast.success("멤버가 제거되었습니다.");
      load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast.error(msg || "멤버 제거에 실패했습니다.");
    }
  };

  const memberUserIds = new Set(members.map((m) => m.user_id));
  const availableUsers = allUsers.filter((u) => !memberUserIds.has(u.id));

  if (loading) return <div style={s.loading}>불러오는 중...</div>;

  return (
    <div style={s.wrap}>
      <h3 style={s.title}>프로젝트 멤버</h3>

      {/* 멤버 추가 (admin만) */}
      {isAdmin && availableUsers.length > 0 && (
        <div style={s.addRow}>
          <select
            style={s.select}
            value={addUserId}
            onChange={(e) => setAddUserId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">사용자 선택...</option>
            {availableUsers.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name} ({u.username})
              </option>
            ))}
          </select>
          <select
            style={s.select}
            value={addRole}
            onChange={(e) => setAddRole(e.target.value)}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
          <button style={s.addBtn} onClick={handleAdd} disabled={!addUserId}>
            추가
          </button>
        </div>
      )}

      {/* 멤버 목록 */}
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>사용자</th>
            <th style={s.th}>아이디</th>
            <th style={{ ...s.th, width: 140 }}>역할</th>
            <th style={{ ...s.th, width: 100 }}>추가일</th>
            {isAdmin && <th style={{ ...s.th, width: 60 }}></th>}
          </tr>
        </thead>
        <tbody>
          {members.map((m) => {
            const isCreator = m.user_id === createdBy;
            return (
              <tr key={m.id}>
                <td style={s.td}>
                  {m.display_name || "-"}
                  {isCreator && <span style={s.badge}>생성자</span>}
                </td>
                <td style={s.td}>{m.username || "-"}</td>
                <td style={s.td}>
                  {isAdmin && !isCreator ? (
                    <select
                      style={s.roleSelect}
                      value={m.role}
                      onChange={(e) => handleRoleChange(m.id, e.target.value)}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABELS[r]}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span style={s.roleBadge}>{ROLE_LABELS[m.role] || m.role}</span>
                  )}
                </td>
                <td style={s.td}>
                  {new Date(m.added_at).toLocaleDateString("ko-KR")}
                </td>
                {isAdmin && (
                  <td style={s.td}>
                    {!isCreator && (
                      <button
                        style={s.removeBtn}
                        onClick={() => handleRemove(m.id)}
                        title="멤버 제거"
                      >
                        X
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
          {members.length === 0 && (
            <tr>
              <td style={s.td} colSpan={isAdmin ? 5 : 4}>
                등록된 멤버가 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  wrap: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    padding: 20,
    boxShadow: "var(--shadow)",
  },
  title: {
    fontSize: 16,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: "0 0 16px",
  },
  loading: {
    textAlign: "center",
    color: "var(--text-secondary)",
    padding: 40,
  },
  addRow: {
    display: "flex",
    gap: 8,
    marginBottom: 16,
    alignItems: "center",
  },
  select: {
    padding: "6px 10px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 13,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  addBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
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
    fontSize: 12,
  },
  td: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
  },
  badge: {
    marginLeft: 6,
    padding: "1px 6px",
    borderRadius: 4,
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 10,
    fontWeight: 600,
  },
  roleSelect: {
    padding: "4px 8px",
    borderRadius: 4,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  roleBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    backgroundColor: "var(--bg-page)",
    fontSize: 12,
    fontWeight: 600,
  },
  removeBtn: {
    padding: "2px 8px",
    borderRadius: 4,
    border: "1px solid #CF222E",
    backgroundColor: "transparent",
    color: "var(--color-fail)",
    fontSize: 12,
    cursor: "pointer",
    fontWeight: 600,
  },
};
