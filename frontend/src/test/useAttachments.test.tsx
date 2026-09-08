import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  attachmentsApi: {
    list: vi.fn(),
    listByRun: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
    downloadUrl: vi.fn(),
  },
}));

import { attachmentsApi } from "../api";
import { useAttachments } from "../hooks/useAttachments";

const t = ((k: string) => k) as any;
const gridApiRef = { current: { refreshCells: vi.fn() } } as any;

const uploaded = {
  id: 900,
  test_result_id: 11,
  filename: "방금올린.png",
  content_type: "image/png",
  file_size: 10,
  uploaded_by: 1,
  uploaded_at: "2026-09-08",
};

const fromServer = {
  id: 500,
  test_result_id: 22,
  filename: "서버에있던.png",
  content_type: "image/png",
  file_size: 10,
  uploaded_by: 1,
  uploaded_at: "2026-09-01",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useAttachments", () => {
  it("일괄 조회 응답이 늦게 와도 그 사이 올린 첨부를 지우지 않는다", async () => {
    // ★런 단위 일괄 조회가 도는 동안 사용자가 파일을 올릴 수 있다.
    //   맵을 통째로 갈아끼우면 방금 올린 첨부가 응답 한 번에 사라진다.
    vi.mocked(attachmentsApi.upload).mockResolvedValue(uploaded as any);
    const { result } = renderHook(() => useAttachments(gridApiRef, t));

    await act(async () => {
      await result.current.handleDropUpload(11, [new File(["x"], "방금올린.png")]);
    });
    expect(result.current.attachmentsMap[11]).toHaveLength(1);

    // 서버 응답에는 방금 올린 것이 아직 없다
    act(() => {
      result.current.seedAttachments([11, 22], [fromServer as any]);
    });

    await waitFor(() => {
      expect(result.current.attachmentsMap[22]).toHaveLength(1);
    });
    expect(result.current.attachmentsMap[11]).toHaveLength(1);
    expect(result.current.attachmentsMap[11][0].filename).toBe("방금올린.png");
  });

  it("일괄 조회 응답이 늦게 와도 그 사이 지운 첨부를 되살리지 않는다", async () => {
    vi.mocked(attachmentsApi.upload).mockResolvedValue(uploaded as any);
    vi.mocked(attachmentsApi.delete).mockResolvedValue(undefined as any);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const { result } = renderHook(() => useAttachments(gridApiRef, t));
    await act(async () => {
      await result.current.handleDropUpload(11, [new File(["x"], "방금올린.png")]);
    });
    await act(async () => {
      await result.current.handleDeleteAttachment(900, 11);
    });
    expect(result.current.attachmentsMap[11]).toHaveLength(0);

    // 서버 응답은 삭제 이전 상태라 그 첨부를 아직 들고 있다
    act(() => {
      result.current.seedAttachments([11, 22], [uploaded as any]);
    });

    expect(result.current.attachmentsMap[11]).toHaveLength(0);
  });

  it("건드리지 않은 행은 서버 응답 그대로 채운다", () => {
    const { result } = renderHook(() => useAttachments(gridApiRef, t));
    act(() => {
      result.current.seedAttachments([11, 22, 33], [fromServer as any]);
    });
    expect(result.current.attachmentsMap[11]).toEqual([]);
    expect(result.current.attachmentsMap[22]).toHaveLength(1);
    expect(result.current.attachmentsMap[33]).toEqual([]);
  });

  it("seed 이후에는 행 단위 조회를 다시 하지 않는다", async () => {
    const { result } = renderHook(() => useAttachments(gridApiRef, t));
    act(() => {
      result.current.seedAttachments([11, 22], []);
    });
    await act(async () => {
      await result.current.loadAttachmentFor(11);
      await result.current.loadAttachmentFor(22);
    });
    expect(attachmentsApi.list).not.toHaveBeenCalled();
  });
});
