// 스테이징 업로드: 서버에서 업로드 주소를 받아 파일을 그 주소에 직접 올리고 upload_id 를 받는다.
// 배포(Vercel)는 함수가 요청 본문을 4.5MB 까지만 받아서, 큰 파일은 저장소(Supabase)에 직접 올린다.
// 로컬은 발급 주소가 백엔드 자신이라 흐름이 같다.
import type { TFunction } from "i18next";
import client, { API_BASE_URL } from "./client";
import { translateError } from "../utils/errorMessage";

export type UploadPurpose = "attachment" | "tc_import" | "result_import";

export interface UploadConfig {
  upload_limits: Record<UploadPurpose, number>;
  direct_upload: boolean;
}

export class UploadTooLargeError extends Error {
  readonly limitBytes: number | null;
  constructor(limitBytes: number | null) {
    super("upload too large");
    this.name = "UploadTooLargeError";
    this.limitBytes = limitBytes;
  }
}

let configPromise: Promise<UploadConfig> | null = null;
// 같은 파일을 같은 목적으로 다시 올리지 않는다. 미리보기 뒤 가져오기, dry run 뒤 적용이
// 같은 upload_id 를 쓴다(서버는 커밋하지 않은 처리를 되돌려 같은 id 를 다시 받는다).
let cache = new WeakMap<File, Map<UploadPurpose, Promise<string>>>();

export function resetUploadCache() {
  configPromise = null;
  cache = new WeakMap();
}

export function getUploadConfig(): Promise<UploadConfig> {
  if (!configPromise) {
    configPromise = client.get<UploadConfig>("/api/config").then((r) => r.data);
    configPromise.catch(() => {
      configPromise = null;
    });
  }
  return configPromise;
}

interface UploadTarget {
  upload_id: string;
  method: string;
  url: string;
  headers: Record<string, string>;
}

async function upload(purpose: UploadPurpose, file: File): Promise<string> {
  const config = await getUploadConfig();
  const limit = config.upload_limits[purpose] ?? null;
  if (limit !== null && file.size > limit) throw new UploadTooLargeError(limit);

  const { data: target } = await client.post<UploadTarget>("/api/uploads", {
    purpose,
    filename: file.name,
    size: file.size,
    content_type: file.type || "application/octet-stream",
  });
  // ★axios client 를 쓰지 않는다. client 는 쿠키·CSRF 헤더·401 리다이렉트를 붙이는데,
  //   저장소의 서명 주소에는 필요 없고 교차 출처 요청을 막는다.
  const url = /^https?:\/\//.test(target.url) ? target.url : `${API_BASE_URL}${target.url}`;
  const res = await fetch(url, { method: target.method, body: file, headers: target.headers });
  if (res.status === 413) throw new UploadTooLargeError(limit);
  if (!res.ok) throw new Error(`upload failed: HTTP ${res.status}`);
  return target.upload_id;
}

export function stageUpload(purpose: UploadPurpose, file: File): Promise<string> {
  let byPurpose = cache.get(file);
  if (!byPurpose) {
    byPurpose = new Map();
    cache.set(file, byPurpose);
  }
  const existing = byPurpose.get(purpose);
  if (existing) return existing;
  const p = upload(purpose, file);
  byPurpose.set(purpose, p);
  p.catch(() => byPurpose!.delete(purpose));
  return p;
}

export function forgetUpload(purpose: UploadPurpose, file: File) {
  cache.get(file)?.delete(purpose);
}

// 서버가 이 id 를 더는 받지 않는 응답. 404 는 만료로 지워졌거나 첨부가 가져간 것, 409 는 이미 처리된 것.
const STALE_STATUSES = new Set([404, 409, 410]);

// 파일을 올리고 그 upload_id 로 처리 요청(fn)을 보낸다.
// consumes: 이 요청이 성공하면 서버가 id 를 처리 완료로 표시한다(가져오기 적용, 첨부). 그 뒤에는
// 같은 File 이라도 새로 올려야 하므로 캐시를 지운다. 미리보기와 dry run 은 id 를 남긴다.
// 처리 요청이 실패해도 consumes 면 지운다. 응답만 잃고 서버는 커밋했을 수 있어서다.
export async function withStagedUpload<T>(
  purpose: UploadPurpose,
  file: File,
  consumes: boolean,
  fn: (uploadId: string) => Promise<T>,
): Promise<T> {
  const uploadId = await stageUpload(purpose, file);
  try {
    const result = await fn(uploadId);
    if (consumes) forgetUpload(purpose, file);
    return result;
  } catch (err) {
    const status = (err as { response?: { status?: number } })?.response?.status;
    if (consumes || (status !== undefined && STALE_STATUSES.has(status))) forgetUpload(purpose, file);
    throw err;
  }
}

export function formatLimitMb(bytes: number | null): string {
  return bytes ? String(Math.floor(bytes / (1024 * 1024))) : "";
}

// 업로드 오류가 용량 초과인지. 사전 검사(UploadTooLargeError)와 서버 413(첨부 claim, 프록시)을 같이 본다.
// Vercel 엣지가 내는 413 은 JSON 이 아니므로 상태 코드만 본다.
export function tooLargeMessage(err: unknown, t: TFunction): string | null {
  if (err instanceof UploadTooLargeError) {
    return err.limitBytes ? t("common:uploadTooLarge", { mb: formatLimitMb(err.limitBytes) }) : t("common:uploadTooLargeNoLimit");
  }
  const status = (err as { response?: { status?: number } })?.response?.status;
  return status === 413 ? t("common:uploadTooLargeNoLimit") : null;
}

// 업로드가 끼는 요청의 오류 문구. 용량 초과, 서버 detail, 기본 문구 순서로 고른다.
export function uploadErrorMessage(err: unknown, t: TFunction, fallback: string): string {
  const tooLarge = tooLargeMessage(err, t);
  if (tooLarge) return tooLarge;
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? translateError(detail) : fallback;
}
