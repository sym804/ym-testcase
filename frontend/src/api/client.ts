import axios from "axios";
import { loginPathFor } from "../utils/nextPath";

// 끝 슬래시를 뗀다. 업로드 PUT 과 미리보기 img 는 axios 를 거치지 않고 문자열로 이어 붙인다.
export const API_BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

// Request interceptor: CSRF 토큰 전송 (상태 변경 요청)
client.interceptors.request.use(
  (config) => {
    const method = (config.method || "get").toUpperCase();
    if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      const csrfToken = getCookie("csrf_token");
      if (csrfToken) {
        config.headers["X-CSRF-Token"] = csrfToken;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 비로그인 상태로 쓰는 화면들. 여기서 나는 401 은 세션 만료가 아니라 정상 흐름이다.
// (로그인 여부 확인 실패, 잘못된 재설정 코드 입력 등) 로그인으로 튕기면 안 된다.
const PUBLIC_PATHS = ["/login", "/register", "/account-help", "/reset-password"];

// Response interceptor: handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (!PUBLIC_PATHS.includes(window.location.pathname)) {
        // 원래 주소를 실어 보낸다. 로그인 뒤 같은 화면으로 돌아온다.
        const { pathname, search, hash } = window.location;
        window.location.href = loginPathFor(pathname, search, hash);
      }
    }
    return Promise.reject(error);
  }
);

export default client;
