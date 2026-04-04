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
  // Filters
  "필터 이름을 입력해 주세요.": "errors.filterNameRequired",
  "logic은 AND 또는 OR이어야 합니다.": "errors.invalidFilterLogic",
  "필터를 찾을 수 없습니다.": "errors.filterNotFound",
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
