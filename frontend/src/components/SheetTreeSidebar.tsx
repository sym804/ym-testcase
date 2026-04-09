import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { testCasesApi } from "../api";
import { translateError } from "../utils/errorMessage";
import type { SheetNode } from "../types";

interface FlatSheet {
  name: string;
  tc_count: number;
  id: number;
  depth: number;
  parent_id: number | null;
  hasChildren: boolean;
  is_folder: boolean;
}

interface SheetTreeSidebarProps {
  sheets: SheetNode[];
  flatSheets: FlatSheet[];
  activeSheet: string | null;
  setActiveSheet: (name: string | null) => void;
  expandedSheets: Set<number>;
  setExpandedSheets: React.Dispatch<React.SetStateAction<Set<number>>>;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  canEditTC: boolean;
  projectId: number;
  onSheetChange: () => void;
}

export default function SheetTreeSidebar({
  sheets,
  flatSheets,
  activeSheet,
  setActiveSheet,
  expandedSheets,
  setExpandedSheets,
  sidebarOpen,
  setSidebarOpen,
  canEditTC,
  projectId,
  onSheetChange,
}: SheetTreeSidebarProps) {
  const { t } = useTranslation("testcase");

  // ── 시트/폴더 추가 (내부 상태) ──
  const [showAddSheet, setShowAddSheet] = useState(false);
  const [newSheetName, setNewSheetName] = useState("");
  const [addSheetParentId, setAddSheetParentId] = useState<number | null>(null);
  const [addingFolder, setAddingFolder] = useState(false);

  const handleAddSheet = async () => {
    const name = newSheetName.trim();
    const label = addingFolder ? t("folder") : t("sheet");
    if (!name) { toast.error(t("nameRequired", { label })); return; }
    try {
      await testCasesApi.createSheet(projectId, name, addSheetParentId, addingFolder);
      setShowAddSheet(false);
      setNewSheetName("");
      setAddSheetParentId(null);
      setAddingFolder(false);
      if (!addingFolder) setActiveSheet(name);
      // 부모가 있으면 자동 펼침
      if (addSheetParentId) {
        setExpandedSheets(prev => new Set([...prev, addSheetParentId!]));
      }
      onSheetChange();
      toast.success(t(addingFolder ? "folderAdded" : "sheetAdded", { name }));
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? translateError(detail) : t(addingFolder ? "folderAddFailed" : "sheetAddFailed"));
    }
  };

  if (flatSheets.length <= 1 && flatSheets[0]?.name === "기본") return null;

  const renderNode = (node: SheetNode, depth: number): React.ReactNode => {
    const isExpanded = expandedSheets.has(node.id);
    const hasChildren = (node.children || []).length > 0;
    const isActive = activeSheet === node.name;

    return (
      <div key={node.id || node.name}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "4px 8px",
            paddingLeft: 8 + depth * 16,
            cursor: "pointer",
            backgroundColor: isActive ? "rgba(45,74,122,0.15)" : "transparent",
            borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
            fontSize: 13,
            color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
            fontWeight: isActive ? 600 : 400,
            gap: 4,
            userSelect: "none",
          }}
          onClick={() => {
            if (node.is_folder) {
              setExpandedSheets(prev => {
                const next = new Set(prev);
                if (next.has(node.id)) { next.delete(node.id); } else { next.add(node.id); }
                return next;
              });
            } else {
              setActiveSheet(node.name);
            }
          }}
          onContextMenu={(e) => {
            e.preventDefault();
          }}
        >
          {/* 펼침/접기 */}
          {(node.is_folder || hasChildren) ? (
            <span
              style={{ fontSize: 10, width: 16, textAlign: "center", flexShrink: 0, color: "var(--text-secondary)" }}
              onClick={(e) => {
                e.stopPropagation();
                setExpandedSheets(prev => {
                  const next = new Set(prev);
                  if (next.has(node.id)) { next.delete(node.id); } else { next.add(node.id); }
                  return next;
                });
              }}
            >
              {isExpanded ? "▼" : "▶"}
            </span>
          ) : (
            <span style={{ width: 16, flexShrink: 0 }} />
          )}
          {/* 아이콘 */}
          <span style={{ fontSize: 14, flexShrink: 0 }}>{node.is_folder ? (isExpanded ? "📂" : "📁") : "📄"}</span>
          {/* 이름 */}
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {node.name}
          </span>
          {/* TC 수 (시트만) */}
          {!node.is_folder && (
            <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0 }}>
              {node.tc_count}
            </span>
          )}
          {/* 액션 버튼 */}
          {canEditTC && (
            <span style={{ display: "flex", gap: 2, marginLeft: 4, flexShrink: 0 }}>
              {node.is_folder && (
                <>
                  <span
                    title={t("addSubFolder")}
                    style={{ cursor: "pointer", fontSize: 10, opacity: 0.4, padding: "0 1px" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setAddSheetParentId(node.id);
                      setAddingFolder(true);
                      setShowAddSheet(true);
                      setNewSheetName("");
                    }}
                  >📁+</span>
                  <span
                    title={t("addSubSheet")}
                    style={{ cursor: "pointer", fontSize: 10, opacity: 0.4, padding: "0 1px" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setAddSheetParentId(node.id);
                      setAddingFolder(false);
                      setShowAddSheet(true);
                      setNewSheetName("");
                    }}
                  >📄+</span>
                </>
              )}
              <span
                title={node.is_folder ? t("deleteFolder") : t("deleteSheet")}
                style={{ cursor: "pointer", fontSize: 12, opacity: 0.4, padding: "0 2px" }}
                onClick={(e) => {
                  e.stopPropagation();
                  const label = node.is_folder ? t("folder") : t("sheet");
                  const childInfo = hasChildren ? t("childInfo", { count: (node.children || []).length }) : "";
                  if (!confirm(t("deleteSheetConfirm", { name: node.name, label, childInfo }))) return;
                  testCasesApi.deleteSheet(projectId, node.name).then(() => {
                    toast.success(t("sheetDeleted", { name: node.name, label }));
                    if (activeSheet === node.name) setActiveSheet(null);
                    onSheetChange();
                  }).catch(() => toast.error(t("sheetDeleteFailed", { label })));
                }}
              >×</span>
            </span>
          )}
        </div>
        {/* 하위 노드 */}
        {(node.is_folder || hasChildren) && isExpanded && (node.children || []).map(child => renderNode(child, depth + 1))}
      </div>
    );
  };

  return (
    <div style={{
      width: sidebarOpen ? 220 : 36,
      minWidth: sidebarOpen ? 220 : 36,
      borderRight: "1px solid var(--border-color)",
      backgroundColor: "var(--bg-card)",
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden",
      transition: "width 0.15s, min-width 0.15s",
    }}>
      {/* 헤더 */}
      <div style={{
        padding: sidebarOpen ? "10px 12px" : "10px 8px",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--text-secondary)",
        textTransform: "uppercase",
        letterSpacing: "0.5px",
        borderBottom: "1px solid var(--border-color)",
        display: "flex",
        justifyContent: sidebarOpen ? "space-between" : "center",
        alignItems: "center",
      }}>
        {sidebarOpen && <span>{t("sheets")}</span>}
        <span
          style={{ cursor: "pointer", fontSize: 14, opacity: 0.6, padding: "0 2px" }}
          title={sidebarOpen ? t("sidebarCollapse") : t("sidebarExpand")}
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >{sidebarOpen ? "◀" : "▶"}</span>
        {canEditTC && sidebarOpen && (
          <span style={{ display: "flex", gap: 2 }}>
            <span
              style={{ cursor: "pointer", fontSize: 12, opacity: 0.6, padding: "0 3px" }}
              title={t("addFolder")}
              onClick={() => { setAddSheetParentId(null); setAddingFolder(true); setShowAddSheet(true); setNewSheetName(""); }}
            >📁+</span>
            <span
              style={{ cursor: "pointer", fontSize: 12, opacity: 0.6, padding: "0 3px" }}
              title={t("addSheet")}
              onClick={() => { setAddSheetParentId(null); setAddingFolder(false); setShowAddSheet(true); setNewSheetName(""); }}
            >📄+</span>
          </span>
        )}
      </div>

      {!sidebarOpen ? null : <>
      {/* 시트 추가 입력 */}
      {showAddSheet && (
        <div style={{ padding: "6px 8px", borderBottom: "1px solid var(--border-color)" }}>
          {addSheetParentId && (
            <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>
              {t("subOf", { name: flatSheets.find(s => s.id === addSheetParentId)?.name })}
            </div>
          )}
          <div style={{ fontSize: 10, color: "var(--accent)", marginBottom: 2, fontWeight: 600 }}>
            {addingFolder ? `📁 ${t("folder")}` : `📄 ${t("sheet")}`} {t("addLabel")}
          </div>
          <div style={{ display: "flex", gap: 4 }}>
            <input
              style={{ flex: 1, padding: "4px 6px", fontSize: 12, borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none" }}
              placeholder={addingFolder ? t("folderName") : t("sheetName")}
              value={newSheetName}
              onChange={(e) => setNewSheetName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleAddSheet(); if (e.key === "Escape") { setShowAddSheet(false); setNewSheetName(""); setAddSheetParentId(null); setAddingFolder(false); } }}
              autoFocus
            />
            <button
              style={{ padding: "4px 8px", fontSize: 11, borderRadius: 4, border: "none", backgroundColor: "var(--accent)", color: "#fff", cursor: "pointer" }}
              onClick={handleAddSheet}
            >{t("common:add")}</button>
          </div>
        </div>
      )}

      {/* 트리 */}
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {/* 전체 보기 */}
        {flatSheets.length > 1 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "4px 8px",
              cursor: "pointer",
              backgroundColor: activeSheet === null ? "rgba(45,74,122,0.15)" : "transparent",
              borderLeft: activeSheet === null ? "3px solid var(--accent)" : "3px solid transparent",
              fontSize: 13,
              color: activeSheet === null ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: activeSheet === null ? 600 : 400,
              gap: 4,
            }}
            onClick={() => setActiveSheet(null)}
          >
            <span style={{ width: 16 }} />
            <span style={{ fontSize: 14 }}>📋</span>
            <span style={{ flex: 1 }}>{t("allSheets")}</span>
            <span style={{ fontSize: 10, color: "var(--text-secondary)" }}>
              {flatSheets.reduce((a, s) => a + s.tc_count, 0)}
            </span>
          </div>
        )}
        {sheets.map(node => renderNode(node, 0))}
      </div>
      </>}
    </div>
  );
}
