import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// TODO: JWT를 localStorage에 저장하는 방식은 XSS에 취약함.
// httpOnly 쿠키 기반 인증으로 전환 필요. (백엔드 Set-Cookie + withCredentials)
// TODO: CSRF 토큰 미적용 상태. httpOnly 쿠키 전환 시 CSRF 방어도 함께 구현 필요.

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default client;
