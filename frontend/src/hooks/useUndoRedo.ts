import { useCallback, useRef, useState } from "react";
import type { GridApi } from "ag-grid-community";

interface UndoEntry {
  rowId: string;
  field: string;
  oldValue: unknown;
  newValue: unknown;
  dataId: number;
}
type UndoGroup = UndoEntry[];

export type { UndoEntry, UndoGroup };

export function useUndoRedo(gridApiRef: React.RefObject<GridApi | null>) {
  const undoStackRef = useRef<UndoGroup[]>([]);
  const redoStackRef = useRef<UndoGroup[]>([]);
  const isUndoRedoRef = useRef(false);
  const [undoCount, setUndoCount] = useState(0);
  const [redoCount, setRedoCount] = useState(0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const autoSaveRowRef = useRef<(data: any) => void>(() => {});

  const pushUndo = useCallback((group: UndoGroup) => {
    if (group.length === 0) return;
    undoStackRef.current.push(group);
    if (undoStackRef.current.length > 200) undoStackRef.current.shift();
    redoStackRef.current = [];
    setUndoCount(undoStackRef.current.length);
    setRedoCount(0);
  }, []);

  const applyUndoRedo = useCallback((entries: UndoGroup, direction: "undo" | "redo") => {
    const api = gridApiRef.current;
    if (!api) return;
    isUndoRedoRef.current = true;

    const reverseGroup: UndoGroup = [];
    const updatedNodes: Set<string> = new Set();

    for (const entry of entries) {
      const value = direction === "undo" ? entry.oldValue : entry.newValue;
      const reverseValue = direction === "undo" ? entry.newValue : entry.oldValue;
      api.forEachNode((node) => {
        const nodeRowId = node.data?.id ? String(node.data.id) : `new_${node.data?.no}`;
        if (nodeRowId === entry.rowId && node.data) {
          node.data[entry.field] = value;
          updatedNodes.add(nodeRowId);
        }
      });
      reverseGroup.push({ ...entry, oldValue: reverseValue, newValue: value });
    }

    if (direction === "undo") {
      redoStackRef.current.push(reverseGroup.map(e => ({
        ...e, oldValue: e.newValue, newValue: e.oldValue,
      })));
    } else {
      undoStackRef.current.push(reverseGroup.map(e => ({
        ...e, oldValue: e.newValue, newValue: e.oldValue,
      })));
    }

    // 변경된 행 자동 저장
    api.forEachNode((node) => {
      const nodeRowId = node.data?.id ? String(node.data.id) : `new_${node.data?.no}`;
      if (updatedNodes.has(nodeRowId) && node.data) {
        autoSaveRowRef.current(node.data);
      }
    });

    api.refreshCells({ force: true });
    isUndoRedoRef.current = false;
    setUndoCount(undoStackRef.current.length);
    setRedoCount(redoStackRef.current.length);
  }, [gridApiRef]);

  const handleUndo = useCallback(() => {
    const group = undoStackRef.current.pop();
    if (!group) return;
    applyUndoRedo(group, "undo");
  }, [applyUndoRedo]);

  const handleRedo = useCallback(() => {
    const group = redoStackRef.current.pop();
    if (!group) return;
    applyUndoRedo(group, "redo");
  }, [applyUndoRedo]);

  return {
    undoStackRef, redoStackRef, isUndoRedoRef,
    undoCount, redoCount, setUndoCount, setRedoCount,
    autoSaveRowRef,
    pushUndo, applyUndoRedo, handleUndo, handleRedo,
  };
}
