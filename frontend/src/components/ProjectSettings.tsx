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
                backgroundColor: isPrivate ? "var(--color-fail)" : "var(--color-pass)",
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
                backgroundColor: isPrivate ? "var(--bg-danger-light)" : "var(--bg-success-light)",
                color: isPrivate ? "var(--color-fail)" : "var(--color-pass)",
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

      {/* 기본 필드 설정 (admin만) */}
      {isAdmin && <BuiltInFieldSettings project={project} onUpdate={onUpdate} />}

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
    backgroundColor: "var(--accent)",
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
    border: "1px solid var(--color-fail)",
  },
  dangerTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "var(--color-fail)",
    margin: "0 0 16px",
  },
  deleteBtn: {
    padding: "6px 20px",
    borderRadius: 6,
    border: "1px solid var(--color-fail)",
    backgroundColor: "transparent",
    color: "var(--color-fail)",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  },
  confirmBox: {
    marginTop: 16,
    padding: 16,
    borderRadius: 8,
    backgroundColor: "var(--bg-danger-light)",
    border: "1px solid var(--color-fail)",
  },
  confirmText: {
    fontSize: 13,
    color: "var(--text-danger)",
    marginBottom: 10,
    lineHeight: 1.5,
  },
  confirmInput: {
    width: "100%",
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid var(--color-fail)",
    fontSize: 13,
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
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
    backgroundColor: "var(--bg-card)",
    color: "var(--text-secondary)",
    fontSize: 13,
    cursor: "pointer",
  },
  confirmDeleteBtn: {
    padding: "6px 16px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--color-fail)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
};

// ── 기본 필드 설정 컴포넌트 ──
const BUILTIN_FIELDS = [
  { key: "tc_id", defaultName: "TC ID", canHide: false },
  { key: "type", defaultName: "Type", canHide: true },
  { key: "category", defaultName: "Category", canHide: true },
  { key: "depth1", defaultName: "Depth 1", canHide: true },
  { key: "depth2", defaultName: "Depth 2", canHide: true },
  { key: "priority", defaultName: "Priority", canHide: true },
  { key: "test_type", defaultName: "Platform", canHide: true },
  { key: "precondition", defaultName: "Precondition", canHide: true },
  { key: "test_steps", defaultName: "Test Steps", canHide: false },
  { key: "expected_result", defaultName: "Expected Result", canHide: false },
  { key: "issue_link", defaultName: "Issue Link", canHide: true },
  { key: "assignee", defaultName: "Assignee", canHide: true },
  { key: "remarks", defaultName: "Remarks", canHide: true },
];

function BuiltInFieldSettings({ project, onUpdate }: { project: Project; onUpdate: (p: Project) => void }) {
  const [config, setConfig] = useState<Record<string, { display_name: string; visible: boolean }>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const merged: Record<string, { display_name: string; visible: boolean }> = {};
    for (const f of BUILTIN_FIELDS) {
      const saved = project.field_config?.[f.key];
      merged[f.key] = {
        display_name: saved?.display_name ?? f.defaultName,
        visible: saved?.visible !== false,
      };
    }
    setConfig(merged);
  }, [project.field_config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // 기본값과 다른 것만 저장
      const diff: Record<string, { display_name?: string; visible?: boolean }> = {};
      for (const f of BUILTIN_FIELDS) {
        const c = config[f.key];
        if (!c) continue;
        const changed: { display_name?: string; visible?: boolean } = {};
        if (c.display_name !== f.defaultName) changed.display_name = c.display_name;
        if (c.visible === false) changed.visible = false;
        if (Object.keys(changed).length > 0) diff[f.key] = changed;
      }
      const updated = await projectsApi.update(project.id, { field_config: Object.keys(diff).length > 0 ? diff : null });
      onUpdate(updated);
      toast.success("필드 설정이 저장되었습니다.");
    } catch {
      toast.error("필드 설정 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const merged: Record<string, { display_name: string; visible: boolean }> = {};
    for (const f of BUILTIN_FIELDS) {
      merged[f.key] = { display_name: f.defaultName, visible: true };
    }
    setConfig(merged);
  };

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700 }}>기본 필드 설정</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleReset} style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid var(--border-color)", background: "transparent", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>
            초기화
          </button>
          <button onClick={handleSave} disabled={saving} style={{ padding: "4px 12px", borderRadius: 6, border: "none", background: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--border-color)" }}>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>필드 키</th>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>표시 이름</th>
            <th style={{ textAlign: "center", padding: "8px 10px", fontWeight: 600, width: 60 }}>표시</th>
          </tr>
        </thead>
        <tbody>
          {BUILTIN_FIELDS.map((f) => {
            const c = config[f.key];
            if (!c) return null;
            return (
              <tr key={f.key} style={{ borderBottom: "1px solid var(--border-color)", opacity: c.visible ? 1 : 0.5 }}>
                <td style={{ padding: "6px 10px", fontFamily: "monospace", fontSize: 12, color: "var(--text-secondary)" }}>{f.key}</td>
                <td style={{ padding: "6px 10px" }}>
                  <input
                    type="text"
                    value={c.display_name}
                    onChange={(e) => setConfig({ ...config, [f.key]: { ...c, display_name: e.target.value } })}
                    style={{ width: "100%", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--border-color)", background: "var(--bg-primary)", color: "var(--text-primary)", fontSize: 13 }}
                  />
                </td>
                <td style={{ padding: "6px 10px", textAlign: "center" }}>
                  {f.canHide ? (
                    <input
                      type="checkbox"
                      checked={c.visible}
                      onChange={(e) => setConfig({ ...config, [f.key]: { ...c, visible: e.target.checked } })}
                    />
                  ) : (
                    <input type="checkbox" checked disabled title="필수 필드" />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

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
          style={{ padding: "6px 14px", borderRadius: 6, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
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
              style={{ padding: "6px 14px", borderRadius: 6, border: "none", backgroundColor: "var(--color-pass)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
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
                    style={{ cursor: "pointer", color: "var(--color-fail)", fontSize: 16 }}
                    onClick={() => handleDelete(f)}
                  >×</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 시스템 정보 */}
      <div style={{ marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--border-color)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 12 }}>시스템 정보</h3>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.8 }}>
          <div>YM TestCase v1.0.0.0</div>
          <div>License: AGPL-3.0</div>
          <div>
            <a href="https://github.com/sym804/ym-testcase" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
              GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
