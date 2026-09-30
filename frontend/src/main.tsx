import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Filler,
  Title,
} from "chart.js";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./i18n";
// 본문 폰트. 쓰는 글자 범위의 조각만 받는 동적 서브셋이라 처음 로드가 가볍다.
// 앱에 포함해 두므로 외부 CDN 없이 오프라인에서도 같은 폰트가 나온다.
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./index.css";

// Register Chart.js components
ChartJS.register(
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Filler,
  Title
);
// 차트 글자도 본문과 같은 폰트를 쓴다. Chart.js 기본값(Helvetica 계열)에는 한글이 없어
// 범례의 "미수행" 같은 글자가 다른 폰트로 섞여 나왔다.
// index.css 의 --font-sans 와 같은 값이다.
ChartJS.defaults.font.family = "'Pretendard Variable', Pretendard, -apple-system, 'Segoe UI', 'Malgun Gothic', sans-serif";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
      <AuthProvider>
        <ErrorBoundary>
        <App />
        <Toaster
          position="top-center"
          toastOptions={{
            duration: 3000,
            style: {
              fontFamily: "'Malgun Gothic', 'Segoe UI', sans-serif",
              fontSize: "14px",
            },
          }}
        />
      </ErrorBoundary>
      </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
);
