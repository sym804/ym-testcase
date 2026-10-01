import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { testRunsApi } from "../api";
import { translateError } from "../utils/errorMessage";
import type { ResultImportSummary, TestRun } from "../types";

interface ResultImportModalProps {
  projectId: number;
  run: TestRun;
  onClose: () => void;
  /** 적용이 끝나면 부른다. 수행 상세를 다시 읽는 데 쓴다. */
  onApplied: () => void;
}

const errorDetail = (err: unknown) =>
  (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;

/**
 * 자동화 결과 파일(Playwright JSON · JUnit XML)을 이 수행의 결과로 가져온다.
 *
 * 미리보기(dry_run)로 무엇이 기록될지 먼저 보여 주고, 확인한 뒤에만 적용한다.
 * 파일이나 옵션을 바꾸면 미리보기를 지운다. 본 적 없는 계산으로 적용되지 않게 하기 위해서다.
 */
export default function ResultImportModal({ projectId, run, onClose, onApplied }: ResultImportModalProps) {
  const { t } = useTranslation("testrun");
  const [file, setFile] = useState<File | null>(null);
  const [keepExecuted, setKeepExecuted] = useState(true);
  const [label, setLabel] = useState("");
  const [preview, setPreview] = useState<ResultImportSummary | null>(null);
  const [busy, setBusy] = useState(false);

  const resetPreview = () => setPreview(null);

  const call = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    try {
      const res = await testRunsApi.importResults(projectId, run.id, file, { dryRun, keepExecuted, label });
      if (dryRun) {
        setPreview(res);
      } else {
        toast.success(t("importApplied", { count: res.recorded }));
        onApplied();
        onClose();
      }
    } catch (err) {
      const detail = errorDetail(err);
      toast.error(detail ? translateError(detail) : t("importFailed"));
    } finally {
      setBusy(false);
    }
  };

  const formatName = preview?.format === "junit-xml" ? "JUnit XML" : "Playwright JSON";

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="result-import-title">
        <h2 id="result-import-title" style={styles.title}>{t("importResults")}</h2>
        <p style={styles.help}>{t("importHelp")}</p>

        <label style={styles.label} htmlFor="result-import-file">{t("importFile")}</label>
        <input
          id="result-import-file"
          type="file"
          accept=".json,.xml,application/json,text/xml,application/xml"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); resetPreview(); }}
        />

        <label style={styles.checkRow}>
          <input
            type="checkbox"
            checked={keepExecuted}
            onChange={(e) => { setKeepExecuted(e.target.checked); resetPreview(); }}
          />
          {t("importKeepExecuted")}
        </label>

        <label style={styles.label} htmlFor="result-import-label">{t("importLabel")}</label>
        <input
          id="result-import-label"
          style={styles.input}
          value={label}
          maxLength={100}
          placeholder={t("importLabelPlaceholder")}
          onChange={(e) => { setLabel(e.target.value); resetPreview(); }}
        />

        {preview && (
          <div style={styles.preview} data-testid="import-preview">
            <div style={styles.previewHead}>
              {t("importPreviewHead", {
                format: formatName,
                total: preview.total_tests,
                matched: preview.matched_tests,
                tcs: preview.recorded,
              })}
            </div>
            <div style={styles.counts}>
              <span style={{ color: "var(--color-pass)" }}>PASS {preview.counts.PASS}</span>
              <span style={{ color: "var(--color-fail)" }}>FAIL {preview.counts.FAIL}</span>
              <span style={{ color: "var(--text-secondary)" }}>NS {preview.counts.NS}</span>
            </div>
            <ul style={styles.list}>
              {preview.known_failures > 0 && <li>{t("importKnownFailures", { count: preview.known_failures })}</li>}
              <IdLine label={t("importUnexpected")} ids={preview.unexpected_failures} />
              <IdLine label={t("importFixedCandidates")} ids={preview.fixed_candidates} />
              <IdLine label={t("importKept")} ids={preview.kept_executed} />
              <IdLine label={t("importOutOfRun")} ids={preview.out_of_run} />
            </ul>
            {preview.unmatched_count > 0 && (
              <details style={styles.details}>
                <summary>{t("importUnmatched", { count: preview.unmatched_count })}</summary>
                <ul style={styles.unmatchedList}>
                  {preview.unmatched.map((title) => <li key={title}>{title}</li>)}
                </ul>
              </details>
            )}
            <p style={styles.note}>{t("importOverwriteNote")}</p>
          </div>
        )}

        <div style={styles.actions}>
          <button type="button" style={styles.cancelBtn} onClick={onClose}>{t("common:cancel")}</button>
          <button
            type="button"
            style={{ ...styles.secondaryBtn, opacity: !file || busy ? 0.5 : 1 }}
            disabled={!file || busy}
            onClick={() => call(true)}
          >
            {t("importPreview")}
          </button>
          <button
            type="button"
            style={{ ...styles.submitBtn, opacity: !preview || busy || preview.recorded === 0 ? 0.5 : 1 }}
            disabled={!preview || busy || preview.recorded === 0}
            onClick={() => call(false)}
          >
            {t("importApply", { count: preview?.recorded ?? 0 })}
          </button>
        </div>
      </div>
    </div>
  );
}

function IdLine({ label, ids }: { label: string; ids: string[] }) {
  if (ids.length === 0) return null;
  return (
    <li>
      {label} {ids.length}: <span style={{ fontFamily: "monospace" }}>{ids.join(", ")}</span>
    </li>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 200,
  },
  modal: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 32,
    width: 560,
    maxWidth: "90vw",
    maxHeight: "85vh",
    overflowY: "auto",
    boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    color: "var(--text-primary)",
  },
  title: { margin: "0 0 4px", fontSize: 20, fontWeight: 700 },
  help: { margin: "0 0 8px", fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, whiteSpace: "pre-line" },
  label: { fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginTop: 8 },
  checkRow: { display: "flex", alignItems: "center", gap: 8, fontSize: 14, marginTop: 8, cursor: "pointer" },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  preview: {
    marginTop: 12,
    padding: 16,
    borderRadius: 8,
    border: "1px solid var(--border-color)",
    backgroundColor: "var(--bg-input)",
    fontSize: 13,
  },
  previewHead: { fontWeight: 600, marginBottom: 8 },
  counts: { display: "flex", gap: 16, fontWeight: 700, fontSize: 15, marginBottom: 8 },
  list: { margin: 0, paddingLeft: 18, lineHeight: 1.7 },
  details: { marginTop: 8 },
  unmatchedList: { margin: "6px 0 0", paddingLeft: 18, maxHeight: 160, overflowY: "auto", fontSize: 12, color: "var(--text-secondary)" },
  note: { margin: "10px 0 0", fontSize: 12, color: "var(--text-secondary)" },
  actions: { display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 20 },
  cancelBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 14,
    cursor: "pointer",
  },
  secondaryBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid var(--accent)",
    backgroundColor: "var(--bg-card)",
    color: "var(--accent)",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  submitBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
};
