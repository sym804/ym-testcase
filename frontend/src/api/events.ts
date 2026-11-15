/**
 * 화면 사이에 알리는 window 이벤트 이름.
 * api/index.ts 와 분리해 둔다. 테스트가 "../api" 를 목으로 바꿔도 이 상수는 그대로 쓰인다.
 */

/** 프로젝트 순서를 저장하면 보낸다. Header 의 프로젝트 선택 목록이 다시 받는다(SYM-228). */
export const PROJECT_ORDER_EVENT = "ymtc:project-order";
