import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ResultImportSummary, TestRun } from "../types";
import { TestRunStatus } from "../types";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testRunsApi: { importResults: vi.fn() },
}));

import toast from "react-hot-toast";
import { testRunsApi } from "../api";
import ResultImportModal from "../components/ResultImportModal";

const run = {
  id: 7, project_id: 1, name: "e2e", version: "1.6", environment: "prod", round: 1,
  status: TestRunStatus.IN_PROGRESS, created_by: 1, created_at: "2026-10-01",
} as TestRun;

const summary = (over: Partial<ResultImportSummary> = {}): ResultImportSummary => ({
  format: "playwright-json", dry_run: true, run_id: 7, total_tests: 9, matched_tests: 8, matched_tcs: 8,
  recorded: 7, counts: { PASS: 2, FAIL: 4, NS: 1 }, items: [], kept_executed: ["FE-B-02"], out_of_run: [],
  fixed_candidates: ["FE-A-04"], unexpected_failures: ["FE-A-02", "FE-B-01"], known_failures: 1,
  unmatched_count: 1, unmatched: ["묶음 A › 감시 테스트"], ...over,
});

function setup() {
  const onClose = vi.fn();
  const onApplied = vi.fn();
  render(<ResultImportModal projectId={1} run={run} onClose={onClose} onApplied={onApplied} />);
  const file = new File(['{"suites": []}'], "report.json", { type: "application/json" });
  return { onClose, onApplied, file };
}

const previewBtn = () => screen.getByRole("button", { name: /미리보기|Preview/ });
const applyBtn = () => screen.getByRole("button", { name: /적용|Apply/ });

beforeEach(() => vi.clearAllMocks());

describe("결과 가져오기 모달", () => {
  it("파일을 고르기 전에는 미리보기도 적용도 못 한다", () => {
    setup();
    expect(previewBtn()).toBeDisabled();
    expect(applyBtn()).toBeDisabled();
  });

  it("미리보기는 dry_run 으로 부르고 결과 요약을 보여 준다", async () => {
    vi.mocked(testRunsApi.importResults).mockResolvedValue(summary());
    const { file } = setup();
    await userEvent.upload(screen.getByLabelText(/결과 파일|Result file/), file);
    await userEvent.click(previewBtn());

    expect(testRunsApi.importResults).toHaveBeenCalledWith(1, 7, file, { dryRun: true, keepExecuted: true, label: "" });
    const box = await screen.findByTestId("import-preview");
    expect(box).toHaveTextContent("PASS 2");
    expect(box).toHaveTextContent("FAIL 4");
    expect(box).toHaveTextContent("FE-A-04");
    expect(box).toHaveTextContent("FE-B-02");
    expect(applyBtn()).toBeEnabled();
  });

  it("옵션을 바꾸면 미리보기가 지워져 다시 봐야 적용할 수 있다", async () => {
    vi.mocked(testRunsApi.importResults).mockResolvedValue(summary());
    const { file } = setup();
    await userEvent.upload(screen.getByLabelText(/결과 파일|Result file/), file);
    await userEvent.click(previewBtn());
    await screen.findByTestId("import-preview");

    await userEvent.click(screen.getByRole("checkbox"));
    expect(screen.queryByTestId("import-preview")).not.toBeInTheDocument();
    expect(applyBtn()).toBeDisabled();
  });

  it("적용은 dry_run 없이 같은 옵션으로 부르고 수행을 다시 읽게 한다", async () => {
    vi.mocked(testRunsApi.importResults)
      .mockResolvedValueOnce(summary())
      .mockResolvedValueOnce(summary({ dry_run: false }));
    const { file, onApplied, onClose } = setup();
    await userEvent.upload(screen.getByLabelText(/결과 파일|Result file/), file);
    await userEvent.type(screen.getByLabelText(/비고 앞머리|Remarks prefix/), "e2e 회차");
    await userEvent.click(previewBtn());
    await screen.findByTestId("import-preview");
    await userEvent.click(applyBtn());

    await waitFor(() => expect(onApplied).toHaveBeenCalled());
    expect(testRunsApi.importResults).toHaveBeenLastCalledWith(1, 7, file, { dryRun: false, keepExecuted: true, label: "e2e 회차" });
    expect(onClose).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalled();
  });

  it("기록할 TC 가 없으면 적용할 수 없다", async () => {
    vi.mocked(testRunsApi.importResults).mockResolvedValue(summary({ recorded: 0, counts: { PASS: 0, FAIL: 0, NS: 0 } }));
    const { file } = setup();
    await userEvent.upload(screen.getByLabelText(/결과 파일|Result file/), file);
    await userEvent.click(previewBtn());
    await screen.findByTestId("import-preview");
    expect(applyBtn()).toBeDisabled();
  });

  it("서버가 거절하면 그 사유를 보여 준다", async () => {
    vi.mocked(testRunsApi.importResults).mockRejectedValue({ response: { data: { detail: "DTD 가 포함된 XML 은 받지 않습니다." } } });
    const { file } = setup();
    await userEvent.upload(screen.getByLabelText(/결과 파일|Result file/), file);
    await userEvent.click(previewBtn());
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.queryByTestId("import-preview")).not.toBeInTheDocument();
  });
});
