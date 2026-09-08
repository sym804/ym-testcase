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

  /** 런 전체의 첨부를 한 번에 채운다.
   *
   * 첨부가 없는 행도 빈 배열로 박아 둔다. 그래야 lazy 로더가 그 행을 다시
   * 부르지 않고, 셀 렌더러도 "아직 모름" 과 "없음" 을 구분하지 않아도 된다.
   *
   * ★맵을 통째로 갈아끼우지 않는다. 이 조회가 도는 동안 사용자가 파일을 올리거나
   *   지울 수 있는데, 그 응답은 서버가 목록을 뜬 시점보다 새롭다. 통째로 바꾸면
   *   방금 올린 첨부가 사라지고 방금 지운 첨부가 되살아난다.
   *   화면에서 이미 손댄 행은 그 값을 남기고, 나머지만 서버 값으로 채운다.
   *   (resetAttachments 가 런을 열 때 맵을 비우므로, 남는 것은 그 뒤에 손댄 행뿐이다.)
   */
  const seedAttachments = useCallback((resultIds: number[], atts: Attachment[]) => {
    setAttachmentsMap((prev) => {
      const next: Record<number, Attachment[]> = {};
      for (const id of resultIds) next[id] = [];
      for (const att of atts) {
        if (!next[att.test_result_id]) next[att.test_result_id] = [];
        next[att.test_result_id].push(att);
      }
      return { ...next, ...prev };
    });
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
    seedAttachments,
    loadAttachmentFor,
    handleFileUpload,
    handleDeleteAttachment,
    triggerUpload,
    handleDropUpload,
  };
}
