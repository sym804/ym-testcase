import { useCallback, useRef, useState } from "react";
import type { GridApi } from "ag-grid-community";
import { attachmentsApi } from "../api";
import type { Attachment } from "../types";
import toast from "react-hot-toast";
import type { TFunction } from "i18next";

export function useAttachments(
  gridApiRef: React.RefObject<GridApi | null>,
  t: TFunction,
) {
  const [attachmentsMap, setAttachmentsMap] = useState<Record<number, Attachment[]>>({});
  const [previewImage, setPreviewImage] = useState<{ url: string; filename: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadTargetResultId, setUploadTargetResultId] = useState<number | null>(null);

  const resetAttachments = useCallback(() => {
    setAttachmentsMap({});
  }, []);

  const loadAttachmentFor = useCallback(async (resultId: number) => {
    if (attachmentsMap[resultId] !== undefined) return;
    try {
      const atts = await attachmentsApi.list(resultId);
      setAttachmentsMap((prev) => ({ ...prev, [resultId]: atts }));
    } catch { /* ignore */ }
  }, [attachmentsMap]);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !uploadTargetResultId) return;
    if (!file.type.startsWith("image/")) {
      toast.error(t("imageOnly"));
      return;
    }
    try {
      const att = await attachmentsApi.upload(uploadTargetResultId, file);
      setAttachmentsMap((prev) => ({
        ...prev,
        [uploadTargetResultId]: [...(prev[uploadTargetResultId] || []), att],
      }));
      gridApiRef.current?.refreshCells({ force: true });
      toast.success(t("imageAttached"));
    } catch {
      toast.error(t("uploadFailed"));
    }
    e.target.value = "";
    setUploadTargetResultId(null);
  }, [uploadTargetResultId, gridApiRef, t]);

  const handleDeleteAttachment = useCallback(async (attachmentId: number, resultId: number) => {
    if (!confirm(t("deleteAttachmentConfirm"))) return;
    try {
      await attachmentsApi.delete(attachmentId);
      setAttachmentsMap((prev) => ({
        ...prev,
        [resultId]: (prev[resultId] || []).filter((a) => a.id !== attachmentId),
      }));
      gridApiRef.current?.refreshCells({ force: true });
      toast.success(t("attachDeleteDone"));
    } catch {
      toast.error(t("attachDeleteFailed"));
    }
  }, [gridApiRef, t]);

  const triggerUpload = useCallback((resultId: number) => {
    setUploadTargetResultId(resultId);
    fileInputRef.current?.click();
  }, []);

  const handleDropUpload = useCallback(async (resultId: number, files: File[]) => {
    for (const file of files) {
      try {
        const att = await attachmentsApi.upload(resultId, file);
        setAttachmentsMap((prev) => ({ ...prev, [resultId]: [...(prev[resultId] || []), att] }));
        gridApiRef.current?.refreshCells({ force: true });
        toast.success(t("fileAttached", { name: file.name }));
      } catch {
        toast.error(t("fileUploadFailed", { name: file.name }));
      }
    }
  }, [gridApiRef, t]);

  return {
    attachmentsMap,
    previewImage,
    setPreviewImage,
    fileInputRef,
    resetAttachments,
    loadAttachmentFor,
    handleFileUpload,
    handleDeleteAttachment,
    triggerUpload,
    handleDropUpload,
  };
}
