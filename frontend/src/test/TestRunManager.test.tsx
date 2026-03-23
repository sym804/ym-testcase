import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">{JSON.stringify(props.rowData?.length ?? 0)}</div>
  ),
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/MarkdownCell", () => ({
  default: (props: any) => <span>{props.value}</span>,
}));

vi.mock("../components/HighlightCell", () => ({
  default: (props: any) => <span>{props.value}</span>,
}));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(),
    create: vi.fn(),
    getOne: vi.fn(),
    update: vi.fn(),
    submitResults: vi.fn(),
    complete: vi.fn(),
    reopen: vi.fn(),
    clone: vi.fn(),
    delete: vi.fn(),
    exportExcel: vi.fn(),
  },
  testCasesApi: {
    listSheets: vi.fn(),
  },
  attachmentsApi: {
    list: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
    downloadUrl: vi.fn(),
  },
}));

import { testRunsApi, testCasesApi } from "../api";
import { TestRunStatus } from "../types";
import type { TestRun, TestResult } from "../types";
import TestRunManager from "../components/TestRunManager";
import toast from "react-hot-toast";

const adminProject = {
  id: 1,
  name: "TestProject",
  description: "desc",
  jira_base_url: null,
  is_private: false,
  created_by: 1,
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
  my_role: "admin" as string,
};

const viewerProject = {
  ...adminProject,
  my_role: "viewer" as string,
};

const mockTC = {
  id: 1,
  project_id: 1,
  no: 1,
  tc_id: "TC-001",
  type: "기능",
  category: "로그인",
  depth1: "인증",
  depth2: "기본",
  priority: "High",
  test_type: "수동",
  precondition: "",
  test_steps: "1. 로그인 페이지 접근\n2. 아이디/비번 입력",
  expected_result: "로그인 성공",
  r1: "",
  r2: "",
  r3: "",
  issue_link: "",
  assignee: "테스터A",
  remarks: "",
  sheet_name: "기본",
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
};

const mockTC2 = {
  ...mockTC,
  id: 2,
  no: 2,
  tc_id: "TC-002",
  category: "회원가입",
  depth1: "가입",
  priority: "Medium",
  test_steps: "회원가입 테스트",
  expected_result: "가입 완료",
};

const makeRun = (overrides: Partial<TestRun> = {}): TestRun => ({
  id: 1,
  project_id: 1,
  name: "Sprint 1 테스트",
  version: "v1.0",
  environment: "dev",
  round: 1,
  status: TestRunStatus.IN_PROGRESS,
  created_by: 1,
  created_at: "2026-01-01",
  ...overrides,
});

const makeResult = (overrides: Partial<TestResult> = {}): TestResult => ({
  id: 1,
  test_run_id: 1,
  test_case_id: 1,
  result: "PASS",
  actual_result: "",
  issue_link: "",
  remarks: "",
  executed_by: 1,
  executed_at: "2026-01-01",
  test_case: mockTC,
  ...overrides,
});

const mockRuns: TestRun[] = [
  makeRun({ id: 1, name: "Sprint 1 테스트", status: TestRunStatus.IN_PROGRESS }),
  makeRun({ id: 2, name: "Sprint 2 테스트", version: "v2.0", round: 2, status: TestRunStatus.COMPLETED }),
];

const mockRunDetail = {
  ...mockRuns[0],
  results: [
    makeResult({ id: 1, test_case_id: 1, result: "PASS", test_case: mockTC }),
    makeResult({ id: 2, test_case_id: 2, result: "FAIL", test_case: mockTC2 }),
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  // Default: return mock runs
  vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([{ name: "기본", tc_count: 2, id: 1, parent_id: null, sort_order: 0, is_folder: false, children: [] }]);
  vi.mocked(testRunsApi.getOne).mockResolvedValue(mockRunDetail as any);
  vi.mocked(testRunsApi.create).mockResolvedValue(makeRun({ id: 3, name: "새 수행" }));
  vi.mocked(testRunsApi.clone).mockResolvedValue(makeRun({ id: 4, name: "Sprint 1 테스트 (복제)" }));
  vi.mocked(testRunsApi.complete).mockResolvedValue(undefined as any);
  vi.mocked(testRunsApi.reopen).mockResolvedValue(undefined as any);
  vi.mocked(testRunsApi.delete).mockResolvedValue(undefined as any);
});

function renderComponent(project = adminProject) {
  return render(<TestRunManager projectId={project.id} project={project} />);
}

describe("TestRunManager", () => {
  describe("초기 렌더링", () => {
    it("테스트 수행 목록 패널 제목을 표시한다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("테스트 수행 목록")).toBeInTheDocument();
      });
    });

    it("로딩 중 메시지를 표시한다", () => {
      vi.mocked(testRunsApi.list).mockReturnValue(new Promise(() => {})); // never resolves
      renderComponent();
      expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
    });

    it("수행 목록이 비어있으면 안내 메시지를 표시한다", async () => {
      vi.mocked(testRunsApi.list).mockResolvedValue([]);
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("등록된 수행이 없습니다.")).toBeInTheDocument();
      });
    });

    it("수행 목록을 불러와서 표시한다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
        expect(screen.getByText("Sprint 2 테스트")).toBeInTheDocument();
      });
    });

    it("진행 중/완료 상태 배지를 표시한다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("진행 중")).toBeInTheDocument();
        expect(screen.getByText("완료")).toBeInTheDocument();
      });
    });

    it("라운드/버전 정보를 표시한다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("R1 | v1.0")).toBeInTheDocument();
        expect(screen.getByText("R2 | v2.0")).toBeInTheDocument();
      });
    });

    it("선택된 수행이 없으면 안내 메시지를 표시한다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("왼쪽에서 테스트 수행을 선택하세요.")).toBeInTheDocument();
      });
    });

    it("+ New Test Run 버튼이 표시된다", async () => {
      renderComponent();
      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });
    });
  });

  describe("테스트 수행 선택", () => {
    it("수행 클릭 시 상세 정보를 로드한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(testRunsApi.getOne).toHaveBeenCalledWith(1, 1);
      });
    });

    it("선택된 수행의 이름, 버전, 환경, 라운드를 헤더에 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText(/버전: v1.0/)).toBeInTheDocument();
        expect(screen.getByText(/환경: dev/)).toBeInTheDocument();
        expect(screen.getByText(/라운드: R1/)).toBeInTheDocument();
      });
    });

    it("선택된 수행의 결과를 그리드에 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        // ag-grid mock은 rowData length를 JSON으로 표시
        expect(screen.getByTestId("ag-grid")).toHaveTextContent("2");
      });
    });
  });

  describe("새 수행 생성", () => {
    it("+ New Test Run 클릭 시 모달을 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));

      expect(screen.getByText("새 테스트 수행")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("예: Sprint 5 기능 테스트")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("예: v1.2.0")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("예: Staging")).toBeInTheDocument();
    });

    it("이름 없이 생성 시 에러 토스트를 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));
      await user.click(screen.getByText("생성"));

      expect(toast.error).toHaveBeenCalledWith("수행 이름을 입력해 주세요.");
      expect(testRunsApi.create).not.toHaveBeenCalled();
    });

    it("이름 입력 후 생성하면 API를 호출한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));
      await user.type(screen.getByPlaceholderText("예: Sprint 5 기능 테스트"), "새 수행");
      await user.type(screen.getByPlaceholderText("예: v1.2.0"), "v3.0");
      await user.click(screen.getByText("생성"));

      await waitFor(() => {
        expect(testRunsApi.create).toHaveBeenCalledWith(1, {
          name: "새 수행",
          version: "v3.0",
          environment: "",
          round: 1,
        });
      });
    });

    it("생성 성공 시 성공 토스트를 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));
      await user.type(screen.getByPlaceholderText("예: Sprint 5 기능 테스트"), "새 수행");
      await user.click(screen.getByText("생성"));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith("테스트 수행이 생성되었습니다.");
      });
    });

    it("취소 버튼 클릭 시 모달을 닫는다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));
      expect(screen.getByText("새 테스트 수행")).toBeInTheDocument();

      await user.click(screen.getByText("취소"));

      await waitFor(() => {
        expect(screen.queryByText("새 테스트 수행")).not.toBeInTheDocument();
      });
    });

    it("생성 실패 시 에러 토스트를 표시한다", async () => {
      vi.mocked(testRunsApi.create).mockRejectedValue(new Error("fail"));
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("+ New Test Run")).toBeInTheDocument();
      });

      await user.click(screen.getByText("+ New Test Run"));
      await user.type(screen.getByPlaceholderText("예: Sprint 5 기능 테스트"), "새 수행");
      await user.click(screen.getByText("생성"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("생성에 실패했습니다.");
      });
    });
  });

  describe("수행 액션 버튼", () => {
    it("admin 역할일 때 삭제 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent(adminProject);

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("삭제")).toBeInTheDocument();
      });
    });

    it("viewer 역할일 때 삭제 버튼이 표시되지 않는다", async () => {
      const user = userEvent.setup();
      renderComponent(viewerProject);

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("복제")).toBeInTheDocument();
      });
      expect(screen.queryByText("삭제")).not.toBeInTheDocument();
    });

    it("진행 중인 수행에 '수행 완료' 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("수행 완료")).toBeInTheDocument();
      });
    });

    it("완료된 수행에 '다시 수행' 버튼이 표시된다", async () => {
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[1],
        results: [],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 2 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 2 테스트"));

      await waitFor(() => {
        expect(screen.getByText("다시 수행")).toBeInTheDocument();
      });
    });

    it("복제 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("복제")).toBeInTheDocument();
      });
    });

    it("Excel 내보내기 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("Excel")).toBeInTheDocument();
      });
    });
  });

  describe("결과 카운트 & 진행률", () => {
    it("수행 선택 시 결과 카운트 배지를 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        // 결과 카운트 배지들
        expect(screen.getByText(/진행률/)).toBeInTheDocument();
      });
    });
  });

  describe("필터 UI", () => {
    it("수행 선택 시 필터 바를 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByPlaceholderText("검색 (TC ID, Steps, Expected...)")).toBeInTheDocument();
      });
    });

    it("Result, Category, Priority 필터 드롭다운이 있다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        const selects = screen.getAllByRole("combobox");
        // Result, Category, Priority + Round (modal is closed)
        expect(selects.length).toBeGreaterThanOrEqual(3);
      });
    });
  });

  describe("패널 접기/펼치기", () => {
    it("패널 숨기기 버튼 클릭 시 목록이 숨겨진다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("테스트 수행 목록")).toBeInTheDocument();
      });

      // ◀ 버튼으로 패널 숨기기
      await user.click(screen.getByTitle("패널 숨기기"));

      await waitFor(() => {
        expect(screen.queryByText("테스트 수행 목록")).not.toBeInTheDocument();
      });
    });
  });

  describe("완료된 수행 접기/펼치기", () => {
    it("완료된 수행이 5개 넘으면 더보기 링크를 표시한다", async () => {
      const manyRuns = [
        makeRun({ id: 1, name: "진행 중 수행", status: TestRunStatus.IN_PROGRESS }),
        ...Array.from({ length: 8 }, (_, i) =>
          makeRun({ id: i + 10, name: `완료 수행 ${i + 1}`, status: TestRunStatus.COMPLETED })
        ),
      ];
      vi.mocked(testRunsApi.list).mockResolvedValue(manyRuns);
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("진행 중 수행")).toBeInTheDocument();
      });

      // 처음 5개 완료 + 1개 진행 중만 보여야 함
      expect(screen.getByText("완료 수행 1")).toBeInTheDocument();
      expect(screen.getByText("완료 수행 5")).toBeInTheDocument();
      // 6번째는 숨겨져야 함
      expect(screen.queryByText("완료 수행 6")).not.toBeInTheDocument();

      // "더보기" 링크
      expect(screen.getByText(/이전 런 3개 더보기/)).toBeInTheDocument();
    });

    it("더보기 클릭 시 모든 완료 수행을 표시한다", async () => {
      const manyRuns = [
        makeRun({ id: 1, name: "진행 중 수행", status: TestRunStatus.IN_PROGRESS }),
        ...Array.from({ length: 8 }, (_, i) =>
          makeRun({ id: i + 10, name: `완료 수행 ${i + 1}`, status: TestRunStatus.COMPLETED })
        ),
      ];
      vi.mocked(testRunsApi.list).mockResolvedValue(manyRuns);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/이전 런 3개 더보기/)).toBeInTheDocument();
      });

      await user.click(screen.getByText(/이전 런 3개 더보기/));

      await waitFor(() => {
        expect(screen.getByText("완료 수행 6")).toBeInTheDocument();
        expect(screen.getByText("완료 수행 8")).toBeInTheDocument();
        expect(screen.getByText(/접기/)).toBeInTheDocument();
      });
    });
  });

  describe("목록 로드 실패", () => {
    it("수행 목록 로드 실패 시 에러 토스트를 표시한다", async () => {
      vi.mocked(testRunsApi.list).mockRejectedValue(new Error("network"));
      renderComponent();

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("테스트 수행 목록을 불러오지 못했습니다.");
      });
    });

    it("수행 상세 로드 실패 시 에러 토스트를 표시한다", async () => {
      vi.mocked(testRunsApi.getOne).mockRejectedValue(new Error("network"));
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("테스트 결과를 불러오지 못했습니다.");
      });
    });
  });

  describe("결과 일괄입력 메뉴", () => {
    it("결과 일괄입력 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText(/결과 일괄입력/)).toBeInTheDocument();
      });
    });

    it("결과 일괄입력 클릭 시 옵션 메뉴가 열린다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText(/결과 일괄입력/)).toBeInTheDocument();
      });

      await user.click(screen.getByText(/결과 일괄입력/));

      await waitFor(() => {
        // PASS appears both in the bulk menu button and the filter dropdown, so use getAllByText
        const passElements = screen.getAllByText("PASS");
        expect(passElements.length).toBeGreaterThanOrEqual(2); // filter option + bulk menu button
        const failElements = screen.getAllByText("FAIL");
        expect(failElements.length).toBeGreaterThanOrEqual(2);
        expect(screen.getAllByText("BLOCK").length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe("단축키 안내", () => {
    it("단축키 안내 텍스트가 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText(/P\/F\/B\/N: 빠른 결과 입력/)).toBeInTheDocument();
      });
    });
  });

  describe("타이머 토글", () => {
    it("타이머 토글 버튼이 표시된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByTitle("타이머 켜기")).toBeInTheDocument();
      });
    });

    it("타이머 토글 버튼 클릭 시 localStorage에 저장한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByTitle("타이머 켜기")).toBeInTheDocument();
      });

      await user.click(screen.getByTitle("타이머 켜기"));

      expect(localStorage.getItem("tc_timer_enabled")).toBe("true");
    });
  });

  describe("삭제 액션", () => {
    it("삭제 확인 후 API를 호출한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("삭제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("삭제"));

      await waitFor(() => {
        expect(testRunsApi.delete).toHaveBeenCalledWith(1, 1);
        expect(toast.success).toHaveBeenCalledWith("테스트 수행이 삭제되었습니다.");
      });
    });

    it("삭제 취소 시 API를 호출하지 않는다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("삭제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("삭제"));

      expect(testRunsApi.delete).not.toHaveBeenCalled();
    });

    it("삭제 실패 시 에러 토스트를 표시한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(testRunsApi.delete).mockRejectedValue(new Error("fail"));
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("삭제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("삭제"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("삭제에 실패했습니다.");
      });
    });
  });

  describe("복제 액션", () => {
    it("복제 확인 후 API를 호출한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("복제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("복제"));

      await waitFor(() => {
        expect(testRunsApi.clone).toHaveBeenCalledWith(1, 1);
        expect(toast.success).toHaveBeenCalledWith("테스트 수행이 복제되었습니다.");
      });
    });

    it("복제 취소 시 API를 호출하지 않는다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("복제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("복제"));

      expect(testRunsApi.clone).not.toHaveBeenCalled();
    });

    it("복제 실패 시 에러 토스트를 표시한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(testRunsApi.clone).mockRejectedValue(new Error("fail"));
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("복제")).toBeInTheDocument();
      });

      await user.click(screen.getByText("복제"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("복제에 실패했습니다.");
      });
    });
  });

  describe("완료/다시 수행 액션", () => {
    it("수행 완료 시 확인 후 API를 호출한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("수행 완료")).toBeInTheDocument();
      });

      await user.click(screen.getByText("수행 완료"));

      await waitFor(() => {
        expect(testRunsApi.complete).toHaveBeenCalledWith(1, 1);
        expect(toast.success).toHaveBeenCalledWith("테스트 수행이 완료되었습니다.");
      });
    });

    it("수행 완료 취소 시 API를 호출하지 않는다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(false);
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("수행 완료")).toBeInTheDocument();
      });

      await user.click(screen.getByText("수행 완료"));

      expect(testRunsApi.complete).not.toHaveBeenCalled();
    });

    it("다시 수행 클릭 시 API를 호출한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[1],
        results: [],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 2 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 2 테스트"));

      await waitFor(() => {
        expect(screen.getByText("다시 수행")).toBeInTheDocument();
      });

      await user.click(screen.getByText("다시 수행"));

      await waitFor(() => {
        expect(testRunsApi.reopen).toHaveBeenCalledWith(1, 2);
        expect(toast.success).toHaveBeenCalledWith("테스트 수행이 다시 진행 중으로 변경되었습니다.");
      });
    });

    it("다시 수행 실패 시 에러 토스트를 표시한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(testRunsApi.reopen).mockRejectedValue(new Error("fail"));
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[1],
        results: [],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 2 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 2 테스트"));

      await waitFor(() => {
        expect(screen.getByText("다시 수행")).toBeInTheDocument();
      });

      await user.click(screen.getByText("다시 수행"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("상태 변경에 실패했습니다.");
      });
    });

    it("완료 실패 시 에러 토스트를 표시한다", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(testRunsApi.complete).mockRejectedValue(new Error("fail"));
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("수행 완료")).toBeInTheDocument();
      });

      await user.click(screen.getByText("수행 완료"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("완료 처리에 실패했습니다.");
      });
    });
  });

  describe("필터 초기화", () => {
    it("필터 입력 후 초기화 버튼이 나타나고 클릭 시 필터가 초기화된다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByPlaceholderText("검색 (TC ID, Steps, Expected...)")).toBeInTheDocument();
      });

      await user.type(screen.getByPlaceholderText("검색 (TC ID, Steps, Expected...)"), "TC-001");

      await waitFor(() => {
        expect(screen.getByText("초기화")).toBeInTheDocument();
      });

      await user.click(screen.getByText("초기화"));

      await waitFor(() => {
        expect(screen.queryByText("초기화")).not.toBeInTheDocument();
      });
    });
  });

  describe("시트 탭", () => {
    it("시트가 2개 이상이면 시트 탭을 표시한다", async () => {
      vi.mocked(testCasesApi.listSheets).mockResolvedValue([
        { name: "기능", tc_count: 5, id: 1, parent_id: null, sort_order: 0, children: [] },
        { name: "UI", tc_count: 3, id: 2, parent_id: null, sort_order: 1, children: [] },
      ] as any);
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[0],
        results: [
          makeResult({ id: 1, test_case: { ...mockTC, sheet_name: "기능" } }),
        ],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("기능")).toBeInTheDocument();
        expect(screen.getByText("UI")).toBeInTheDocument();
      });
    });
  });

  describe("NS→빈값 변환", () => {
    it("NS 결과를 빈값으로 변환하여 표시한다", async () => {
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[0],
        results: [
          makeResult({ id: 1, result: "NS", test_case: mockTC }),
          makeResult({ id: 2, result: "NA", test_case: mockTC2 }),
        ],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      // ag-grid mock shows rowData length
      await waitFor(() => {
        expect(screen.getByTestId("ag-grid")).toHaveTextContent("2");
      });

      // Verify the API was called
      expect(testRunsApi.getOne).toHaveBeenCalledWith(1, 1);
    });
  });

  describe("프로그레스 바", () => {
    it("수행 선택 시 진행률 프로그레스 바를 표시한다", async () => {
      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        // 100% completion (both results have values: PASS and FAIL)
        expect(screen.getByText("진행률 100%")).toBeInTheDocument();
      });
    });

    it("미입력 결과가 있으면 진행률이 100% 미만이다", async () => {
      vi.mocked(testRunsApi.getOne).mockResolvedValue({
        ...mockRuns[0],
        results: [
          makeResult({ id: 1, result: "PASS", test_case: mockTC }),
          makeResult({ id: 2, result: "NS", test_case: mockTC2 }),
        ],
      } as any);

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("진행률 50%")).toBeInTheDocument();
      });
    });
  });

  describe("Excel 내보내기", () => {
    it("Excel 버튼 클릭 시 exportExcel API를 호출한다", async () => {
      vi.mocked(testRunsApi.exportExcel).mockResolvedValue(new Blob(["test"]));
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-url");
      vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("Excel")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Excel"));

      await waitFor(() => {
        expect(testRunsApi.exportExcel).toHaveBeenCalledWith(1, 1);
      });
    });

    it("Excel 내보내기 실패 시 에러 토스트를 표시한다", async () => {
      vi.mocked(testRunsApi.exportExcel).mockRejectedValue(new Error("fail"));

      const user = userEvent.setup();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Sprint 1 테스트"));

      await waitFor(() => {
        expect(screen.getByText("Excel")).toBeInTheDocument();
      });

      await user.click(screen.getByText("Excel"));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith("Excel 내보내기 실패");
      });
    });
  });
});
