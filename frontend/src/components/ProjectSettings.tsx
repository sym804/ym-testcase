import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { projectsApi, customFieldsApi } from "../api";
import type { Project, CustomFieldDef } from "../types";
import ProjectMembers from "./ProjectMembers";
import toast from "react-hot-toast";

interface Props {
  project: Project;
  onUpdate: (p: Project) => void;
}

export default function ProjectSettings({ project, onUpdate }: Props) {
  const navigate = useNavigate();
  const isAdmin = project.my_role === "admin";
  const [isPrivate, setIsPrivate] = useState(project.is_private);
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (deleteInput !== project.name) return;
    setDeleting(true);
    try {
      await projectsApi.delete(project.id);
      toast.success("프로젝트가 삭제되었습니다.");
      navigate("/projects");
    } catch {
      toast.error("프로젝트 삭제에 실패했습니다.");
    } finally {
      setDeleting(false);
    }
  };

  const handleTogglePrivate = async () => {
    setSaving(true);
    try {
      const updated = await projectsApi.update(project.id, {
        is_private: !isPrivate,
      });
      setIsPrivate(updated.is_private);
      onUpdate(updated);
      toast.success(
        updated.is_private
          ? "비공개 프로젝트로 변경되었습니다."
          : "공개 프로젝트로 변경되었습니다."
      );
    } catch {
      toast.error("설정 변경에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={s.container}>
      {/* 접근 제한 설정 */}
      <div style={s.card}>
        <h3 style={s.title}>접근 설정</h3>
        <div style={s.row}>
          <div style={s.info}>
            <div style={s.label}>프로젝트 공개 범위</div>
            <div style={s.desc}>
              {isPrivate
                ? "비공개 — 멤버로 등록된 사용자만 접근할 수 있습니다."
                : "공개 — 모든 인증된 사용자가 조회할 수 있습니다. 수정은 역할에 따라 제한됩니다."}
            </div>
          </div>
          {isAdmin ? (
            <button
              style={{
                ...s.toggleBtn,
                backgroundColor: isPrivate ? "#CF222E" : "#1A7F37",
              }}
              onClick={handleTogglePrivate}
              disabled={saving}
            >
              {isPrivate ? "비공개" : "공개"}
            </button>
          ) : (
            <span
              style={{
                ...s.statusBadge,
                backgroundColor: isPrivate ? "#FEE2E2" : "#DCFCE7",
                color: isPrivate ? "#CF222E" : "#1A7F37",
              }}
            >
              {isPrivate ? "비공개" : "공개"}
            </span>
          )}
        </div>

        {/* 내 역할 표시 */}
        <div style={{ ...s.row, marginTop: 12 }}>
          <div style={s.info}>
            <div style={s.label}>내 프로젝트 역할</div>
          </div>
          <span style={s.myRole}>{project.my_role || "없음"}</span>
        </div>
      </div>

      {/* 멤버 관리 */}
      <ProjectMembers
        projectId={project.id}
        createdBy={project.created_by}
        myRole={project.my_role}
      />

      {/* 커스텀 필드 관리 (admin만) */}
      {isAdmin && <CustomFieldManager projectId={project.id} />}

      {/* 프로젝트 삭제 (admin만) */}
      {isAdmin && (
        <div style={s.dangerCard}>
          <h3 style={s.dangerTitle}>위험 영역</h3>
          <div style={s.row}>
            <div style={s.info}>
              <div style={s.label}>프로젝트 삭제</div>
              <div style={s.desc}>
                프로젝트와 모든 TC, 테스트 수행 기록, 첨부파일이 영구 삭제됩니다. 이 작업은 되돌릴 수 없습니다.
              </div>
            </div>
            <button
              style={s.deleteBtn}
              onClick={() => setShowDeleteConfirm(true)}
            >
              프로젝트 삭제
            </button>
          </div>

          {showDeleteConfirm && (
            <div style={s.confirmBox}>
              <div style={s.confirmText}>
                삭제를 확인하려면 프로젝트 이름을 입력하세요: <strong>{project.name}</strong>
              </div>
              <input
                style={s.confirmInput}
                value={deleteInput}
                onChange={(e) => setDeleteInput(e.target.value)}
                placeholder={project.name}
                autoFocus
              />
              <div style={s.confirmActions}>
                <button
                  style={s.cancelBtn}
                  onClick={() => { setShowDeleteConfirm(false); setDeleteInput(""); }}
                >
                  취소
                </button>
                <button
                  style={{
                    ...s.confirmDeleteBtn,
                    opacity: deleteInput === project.name ? 1 : 0.5,
                  }}
                  onClick={handleDelete}
                  disabled={deleteInput !== project.name || deleting}
                >
                  {deleting ? "삭제 중..." : "영구 삭제"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 800,
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  card: {
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
  row: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  info: { flex: 1 },
  label: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 4,
  },
  desc: {
    fontSize: 12,
    color: "var(--text-secondary)",
    lineHeight: 1.5,
  },
  toggleBtn: {
    padding: "6px 20px",
    borderRadius: 6,
    border: "none",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    minWidth: 80,
  },
  statusBadge: {
    padding: "4px 14px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
  },
  myRole: {
    padding: "4px 14px",
    borderRadius: 6,
    backgroundColor: "#2D4A7A",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    textTransform: "capitalize" as const,
  },
  dangerCard: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 10,
    padding: 20,
    boxShadow: "var(--shadow)",
    border: "1px solid #CF222E33",
  },
  dangerTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "#CF222E",
    margin: "0 0 16px",
  },
  deleteBtn: {
    padding: "6px 20px",
    borderRadius: 6,
    border: "1px solid #CF222E",
    backgroundColor: "transparent",
    color: "#CF222E",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  },
  confirmBox: {
    marginTop: 16,
    padding: 16,
    borderRadius: 8,
    backgroundColor: "#FEE2E2",
    border: "1px solid #CF222E44",
  },
  confirmText: {
    fontSize: 13,
    color: "#7F1D1D",
    marginBottom: 10,
    lineHeight: 1.5,
  },
  confirmInput: {
    width: "100%",
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid #CF222E88",
    fontSize: 13,
    backgroundColor: "#fff",
    color: "#1a1a1a",
    boxSizing: "border-box" as const,
  },
  confirmActions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 8,
    marginTop: 12,
  },
  cancelBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "1px solid #ccc",
    backgroundColor: "#fff",
    color: "#333",
    fontSize: 13,
    cursor: "pointer",
  },
  confirmDeleteBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "#CF222E",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
};

// ── 커스텀 필드 관리 컴포넌트 ──
const FIELD_TYPES = [
  { value: "text", label: "텍스트" },
  { value: "number", label: "숫자" },
  { value: "select", label: "단일 선택" },
  { value: "multiselect", label: "복수 선택" },
  { value: "checkbox", label: "체크박스" },
  { value: "date", label: "날짜" },
];

function CustomFieldManager({ projectId }: { projectId: number }) {
  const [fields, setFields] = useState<CustomFieldDef[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("text");
  const [newOptions, setNewOptions] = useState("");
  const [loading, setLoading] = useState(false);

  const loadFields = useCallback(async () => {
    try {
      const data = await customFieldsApi.list(projectId);
      setFields(data);
    } catch {
      // ignore
    }
  }, [projectId]);

  useEffect(() => {
    loadFields();
  }, [loadFields]);

  const handleAdd = async () => {
    const name = newName.trim();
    if (!name) { toast.error("필드 이름을 입력해 주세요."); return; }
    setLoading(true);
    try {
      const opts = (newType === "select" || newType === "multiselect")
        ? newOptions.split(",").map(o => o.trim()).filter(Boolean)
        : undefined;
      await customFieldsApi.create(projectId, {
        field_name: name,
        field_type: newType as CustomFieldDef["field_type"],
        options: opts,
      });
      toast.success(`"${name}" 필드가 추가되었습니다.`);
      setNewName("");
      setNewOptions("");
      setShowAdd(false);
      loadFields();
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "필드 추가에 실패했습니다.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (field: CustomFieldDef) => {
    if (!confirm(`"${field.field_name}" 필드를 삭제하시겠습니까?`)) return;
    try {
      await customFieldsApi.delete(projectId, field.id);
      toast.success(`"${field.field_name}" 필드가 삭제되었습니다.`);
      loadFields();
    } catch {
      toast.error("필드 삭제에 실패했습니다.");
    }
  };

  return (
    <div style={s.card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={s.title}>커스텀 필드</h3>
        <button
          style={{ padding: "6px 14px", borderRadius: 6, border: "none", backgroundColor: "#2D4A7A", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
          onClick={() => setShowAdd(!showAdd)}
        >
          {showAdd ? "취소" : "+ 필드 추가"}
        </button>
      </div>

      {showAdd && (
        <div style={{ padding: 12, backgroundColor: "var(--bg-page)", borderRadius: 8, marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>필드 이름</div>
              <input
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none", width: 150 }}
                placeholder="예: 환경"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>타입</div>
              <select
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none" }}
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
              >
                {FIELD_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            {(newType === "select" || newType === "multiselect") && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>옵션 (쉼표 구분)</div>
                <input
                  style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none", width: 200 }}
                  placeholder="예: Dev, QA, Prod"
                  value={newOptions}
                  onChange={(e) => setNewOptions(e.target.value)}
                />
              </div>
            )}
            <button
              style={{ padding: "6px 14px", borderRadius: 6, border: "none", backgroundColor: "#1A7F37", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
              onClick={handleAdd}
              disabled={loading}
            >
              {loading ? "추가 중..." : "추가"}
            </button>
          </div>
        </div>
      )}

      {fields.length === 0 ? (
        <div style={{ color: "var(--text-secondary)", fontSize: 13, padding: "12px 0" }}>
          등록된 커스텀 필드가 없습니다.
        </div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>필드명</th>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>타입</th>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>옵션</th>
              <th style={{ textAlign: "center", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600, width: 60 }}>삭제</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(f => (
              <tr key={f.id}>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", fontWeight: 600 }}>{f.field_name}</td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)" }}>
                  {FIELD_TYPES.find(t => t.value === f.field_type)?.label || f.field_type}
                </td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>
                  {f.options?.join(", ") || "-"}
                </td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", textAlign: "center" }}>
                  <span
                    style={{ cursor: "pointer", color: "#CF222E", fontSize: 16 }}
                    onClick={() => handleDelete(f)}
                  >×</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
