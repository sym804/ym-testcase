import i18n from "../i18n";

// Map known backend Korean error messages to i18n keys
const ERROR_MAP: Record<string, string> = {
  // Auth
  "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.": "errors.tooManyAttempts",
  "이미 등록된 아이디입니다.": "errors.usernameTaken",
  "아이디 또는 비밀번호가 올바르지 않습니다.": "errors.invalidCredentials",
  "현재 비밀번호가 올바르지 않습니다.": "errors.wrongCurrentPassword",
  "새 비밀번호가 현재와 동일합니다.": "errors.samePassword",
  "사용자를 찾을 수 없습니다.": "errors.userNotFound",
  "관리자 승인을 기다리는 중입니다.": "errors.accountPending",
  "사용이 중지된 계정입니다.": "errors.accountDisabled",
  "이메일로 가입해 주세요.": "errors.emailRequired",
  "이미 가입된 이메일입니다.": "errors.emailTaken",
  "회사 이메일로만 가입할 수 있습니다.": "errors.companyEmailOnly",
  "가입 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.": "errors.tooManyRegistrations",
  "첫 관리자 토큰이 올바르지 않습니다.": "errors.bootstrapTokenInvalid",
  "비밀번호가 없는 계정입니다.": "errors.noPassword",
  "이메일 형식이 올바르지 않습니다.": "errors.emailInvalid",
  // Sheets
  "시트 이름을 입력해 주세요.": "errors.sheetNameRequired",
  "이미 존재하는 시트 이름입니다.": "errors.sheetNameExists",
  "부모 시트를 찾을 수 없습니다.": "errors.parentSheetNotFound",
  "시트를 찾을 수 없습니다.": "errors.sheetNotFound",
  "자기 자신을 부모로 설정할 수 없습니다.": "errors.selfParent",
  "하위 시트를 부모로 설정할 수 없습니다.": "errors.childAsParent",
  "폴더에는 TC를 직접 추가할 수 없습니다. 하위 시트를 사용하세요.": "errors.cannotAddToFolder",
  // Test runs
  "존재하지 않는 테스트 플랜입니다.": "errors.testPlanNotFound",
  "다른 프로젝트의 테스트 플랜은 연결할 수 없습니다.": "errors.testPlanWrongProject",
  "완료된 테스트 런은 수정할 수 없습니다. 재오픈 후 수정하세요.": "errors.completedRunReadonly",
  // Test plans
  "플랜 이름을 입력해 주세요.": "errors.planNameRequired",
  "테스트 플랜을 찾을 수 없습니다.": "errors.testPlanNotFound2",
  // Members
  "유효하지 않은 역할입니다.": "errors.invalidRole",
  // Custom fields
  "필드 이름을 입력해 주세요.": "errors.fieldNameRequired",
  "이미 존재하는 필드 이름입니다.": "errors.fieldNameExists",
  "필드를 찾을 수 없습니다.": "errors.fieldNotFound",
  // Test cases
  "이미 쓰이는 TC ID입니다. 다른 값으로 변경해 주세요.": "errors.tcIdTaken",
  // Filters
  "필터 이름을 입력해 주세요.": "errors.filterNameRequired",
  "logic은 AND 또는 OR이어야 합니다.": "errors.invalidFilterLogic",
  "필터를 찾을 수 없습니다.": "errors.filterNotFound",
  // Uploads, locks, storage
  "업로드를 찾을 수 없습니다.": "errors.uploadNotFound",
  "이미 처리한 업로드입니다.": "errors.uploadAlreadyUsed",
  "같은 업로드를 처리하는 중입니다.": "errors.uploadBusy",
  "파일이 아직 올라오지 않았습니다.": "errors.uploadNotReceived",
  "다른 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.": "errors.busy",
  "파일 저장소에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.": "errors.storageUnavailable",
};

export function translateError(backendDetail: string): string {
  // Check exact match
  const key = ERROR_MAP[backendDetail];
  if (key) {
    return i18n.t(`common:${key}`);
  }

  // Check partial match for messages with dynamic content
  for (const [korean, k] of Object.entries(ERROR_MAP)) {
    if (backendDetail.includes(korean.slice(0, 10))) {
      return i18n.t(`common:${k}`);
    }
  }

  // If unknown, return as-is
  return backendDetail;
}

/**
 * 요청 오류에서 보여 줄 문구를 꺼낸다. FastAPI 의 detail 은 문자열(직접 낸 오류)이거나
 * 배열(pydantic 검증 오류)이다. 배열을 그대로 렌더하면 React 가 객체를 못 그려 깨진다.
 */
export function errorText(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail) return translateError(detail);
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string" && first.msg) return first.msg;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
