import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { projectsApi, customFieldsApi } from "../api";
import type { Project, CustomFieldDef } from "../types";
import ProjectMembers from "./ProjectMembers";
import toast from "react-hot-toast";
import { translateError } from "../utils/errorMessage";

interface Props {
  project: Project;
  onUpdate: (p: Project) => void;
}

export default function ProjectSettings({ project, onUpdate }: Props) {
  const navigate = useNavigate();
  const { t } = useTranslation("settings");
  const isAdmin = project.my_role === "admin";
  const [isPrivate, setIsPrivate] = useState(project.is_private);
  const [projectName, setProjectName] = useState(project.name);
  const [projectDesc, setProjectDesc] = useState(project.description || "");
  const [saving, setSaving] = useState(false);
  const [nameSaving, setNameSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (deleteInput !== project.name) return;
    setDeleting(true);
    try {
      await projectsApi.delete(project.id);
      toast.success(t("deleteSuccess"));
      navigate("/projects");
    } catch {
      toast.error(t("deleteFailed"));
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
          ? t("changedToPrivate")
          : t("changedToPublic")
      );
    } catch {
      toast.error(t("settingChangeFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveName = async () => {
    if (!projectName.trim()) return;
    setNameSaving(true);
    try {
      const updated = await projectsApi.update(project.id, {
        name: projectName.trim(),
        description: projectDesc.trim() || undefined,
      });
      onUpdate(updated);
      toast.success(t("saved") || "저장되었습니다");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? translateError(detail) : t("saveFailed"));
    } finally {
      setNameSaving(false);
    }
  };

  return (
    <div style={s.container}>
      {/* 프로젝트 정보 */}
      {isAdmin && (
        <div style={s.card}>
          <h3 style={s.title}>{t("projectInfo") || "프로젝트 정보"}</h3>
          <div style={{ marginBottom: 12 }}>
            <div style={s.label}>{t("projectName") || "프로젝트 이름"}</div>
            <input
              style={{ ...s.input, width: "100%", marginTop: 4 }}
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <div style={s.label}>{t("projectDescription") || "설명"}</div>
            <input
              style={{ ...s.input, width: "100%", marginTop: 4 }}
              value={projectDesc}
              onChange={(e) => setProjectDesc(e.target.value)}
              placeholder={t("projectDescPlaceholder") || "프로젝트 설명 (선택)"}
            />
          </div>
          <button
            style={{
              padding: "8px 24px",
              borderRadius: 6,
              border: "none",
              backgroundColor: "#3182f6",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              marginTop: 4,
              opacity: nameSaving || !projectName.trim() ? 0.5 : 1,
            }}
            onClick={handleSaveName}
            disabled={nameSaving || !projectName.trim()}
          >
            {nameSaving ? "..." : t("save")}
          </button>
        </div>
      )}

      {/* 접근 제한 설정 */}
      <div style={s.card}>
        <h3 style={s.title}>{t("accessSettings")}</h3>
        <div style={s.row}>
          <div style={s.info}>
            <div style={s.label}>{t("projectVisibility")}</div>
            <div style={s.desc}>
              {isPrivate
                ? t("privateDesc")
                : t("publicDesc")}
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
              {isPrivate ? t("private") : t("public")}
            </button>
          ) : (
            <span
              style={{
                ...s.statusBadge,
                backgroundColor: isPrivate ? "var(--bg-danger-light)" : "var(--bg-success-light)",
                color: isPrivate ? "var(--color-fail)" : "var(--color-pass)",
              }}
            >
              {isPrivate ? t("private") : t("public")}
            </span>
          )}
        </div>

        {/* 내 역할 표시 */}
        <div style={{ ...s.row, marginTop: 12 }}>
          <div style={s.info}>
            <div style={s.label}>{t("myProjectRole")}</div>
          </div>
          <span style={s.myRole}>{project.my_role || t("noRole")}</span>
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
          <h3 style={s.dangerTitle}>{t("dangerZone")}</h3>
          <div style={s.row}>
            <div style={s.info}>
              <div style={s.label}>{t("deleteProject")}</div>
              <div style={s.desc}>
                {t("deleteProjectDesc")}
              </div>
            </div>
            <button
              style={s.deleteBtn}
              onClick={() => setShowDeleteConfirm(true)}
            >
              {t("deleteProject")}
            </button>
          </div>

          {showDeleteConfirm && (
            <div style={s.confirmBox}>
              <div style={s.confirmText}>
                {t("deleteConfirmPrompt")} <strong>{project.name}</strong>
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
                  {t("common:cancel")}
                </button>
                <button
                  style={{
                    ...s.confirmDeleteBtn,
                    opacity: deleteInput === project.name ? 1 : 0.5,
                  }}
                  onClick={handleDelete}
                  disabled={deleteInput !== project.name || deleting}
                >
                  {deleting ? t("common:deleting") : t("permanentDelete")}
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
  input: {
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
    outline: "none",
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
  { key: "remarks", defaultName: "Remarks", canHide: true },
];

function BuiltInFieldSettings({ project, onUpdate }: { project: Project; onUpdate: (p: Project) => void }) {
  const { t } = useTranslation("settings");
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
      toast.success(t("fieldSaveSuccess"));
    } catch {
      toast.error(t("fieldSaveFailed"));
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
        <h3 style={{ fontSize: 15, fontWeight: 700 }}>{t("builtInFields")}</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleReset} style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid var(--border-color)", background: "transparent", fontSize: 12, cursor: "pointer", color: "var(--text-secondary)" }}>
            {t("common:reset")}
          </button>
          <button onClick={handleSave} disabled={saving} style={{ padding: "4px 12px", borderRadius: 6, border: "none", background: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
            {saving ? t("common:saving") : t("common:save")}
          </button>
        </div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--border-color)" }}>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>{t("fieldKey")}</th>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>{t("displayName")}</th>
            <th style={{ textAlign: "center", padding: "8px 10px", fontWeight: 600, width: 60 }}>{t("visible")}</th>
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
                    <input type="checkbox" checked disabled title={t("requiredField")} />
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
const FIELD_TYPE_KEYS = ["text", "number", "select", "multiselect", "checkbox", "date"];

function CustomFieldManager({ projectId }: { projectId: number }) {
  const { t } = useTranslation("settings");
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
    if (!name) { toast.error(t("fieldNameRequired")); return; }
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
      toast.success(t("fieldAdded", { name }));
      setNewName("");
      setNewOptions("");
      setShowAdd(false);
      loadFields();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? translateError(detail) : t("fieldAddFailed"));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (field: CustomFieldDef) => {
    if (!confirm(t("fieldDeleteConfirm", { name: field.field_name }))) return;
    try {
      await customFieldsApi.delete(projectId, field.id);
      toast.success(t("fieldDeleted", { name: field.field_name }));
      loadFields();
    } catch {
      toast.error(t("fieldDeleteFailed"));
    }
  };

  return (
    <div style={s.card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={s.title}>{t("customFields")}</h3>
        <button
          style={{ padding: "6px 14px", borderRadius: 6, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
          onClick={() => setShowAdd(!showAdd)}
        >
          {showAdd ? t("common:cancel") : t("addField")}
        </button>
      </div>

      {showAdd && (
        <div style={{ padding: 12, backgroundColor: "var(--bg-page)", borderRadius: 8, marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>{t("fieldName")}</div>
              <input
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none", width: 150 }}
                placeholder={t("fieldNamePlaceholder")}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>{t("fieldType")}</div>
              <select
                style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none" }}
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
              >
                {FIELD_TYPE_KEYS.map(k => <option key={k} value={k}>{t(`fieldType_${k}`)}</option>)}
              </select>
            </div>
            {(newType === "select" || newType === "multiselect") && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 4 }}>{t("optionsLabel")}</div>
                <input
                  style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border-input)", fontSize: 13, backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none", width: 200 }}
                  placeholder={t("optionsPlaceholder")}
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
              {loading ? t("common:processing") : t("common:add")}
            </button>
          </div>
        </div>
      )}

      {fields.length === 0 ? (
        <div style={{ color: "var(--text-secondary)", fontSize: 13, padding: "12px 0" }}>
          {t("noCustomFields")}
        </div>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>{t("fieldName")}</th>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>{t("fieldType")}</th>
              <th style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600 }}>{t("optionsLabel")}</th>
              <th style={{ textAlign: "center", padding: "8px 10px", borderBottom: "2px solid var(--border-color)", color: "var(--text-secondary)", fontSize: 12, fontWeight: 600, width: 60 }}>{t("common:delete")}</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(f => (
              <tr key={f.id}>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", fontWeight: 600 }}>{f.field_name}</td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)" }}>
                  {t(`fieldType_${f.field_type}`)}
                </td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>
                  {f.options?.join(", ") || "-"}
                </td>
                <td style={{ padding: "8px 10px", borderBottom: "1px solid var(--border-color)", textAlign: "center" }}>
                  <button
                    type="button"
                    aria-label={t("deleteField")}
                    style={{ cursor: "pointer", color: "var(--color-fail)", fontSize: 16, background: "none", border: "none", padding: 0 }}
                    onClick={() => handleDelete(f)}
                  >×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 시스템 정보 */}
      <div style={{ marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--border-color)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 12 }}>{t("systemInfo")}</h3>
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
