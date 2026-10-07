import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiUrl, calculate, errorMessage, fetchOverview } from "../src/api";

const UI_BASE = "https://host.example/apps/runtime/calculator/ui/";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("document", { baseURI: UI_BASE });
});

afterEach(() => vi.unstubAllGlobals());

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("apiUrl", () => {
  it("/ui/ 에서 한 단계 위로 올라가 prefix 를 유지한다", () => {
    expect(apiUrl("api/calculators", UI_BASE)).toBe("https://host.example/apps/runtime/calculator/api/calculators");
  });
  it("dev(루트 서빙)에서는 /api 로 수렴한다", () => {
    expect(apiUrl("api/health", "http://localhost:5174/")).toBe("http://localhost:5174/api/health");
  });
});

describe("calculate", () => {
  it("POST 본문에 inputs 를 싣고 결과를 돌려준다", async () => {
    fetchMock.mockResolvedValue(json(200, { value: 22.9, label: "정상" }));
    const r = await calculate("bmi", { weight_kg: 70, height_cm: 175 });
    expect(r.value).toBe(22.9);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("https://host.example/apps/runtime/calculator/api/calculate/bmi");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ inputs: { weight_kg: 70, height_cm: 175 } });
  });

  it("400 의 구조화된 입력 오류를 ApiError.inputError 로 편다", async () => {
    fetchMock.mockResolvedValue(json(400, { detail: { message: "필수 입력 누락: 나이", missing: ["age"], invalid: {} } }));
    await expect(calculate("egfr", {})).rejects.toMatchObject({ status: 400, inputError: { missing: ["age"] } });
  });
});

describe("fetchOverview / errorMessage", () => {
  it("환자번호를 URL 인코딩하고 404 detail 을 메시지로 낸다", async () => {
    fetchMock.mockResolvedValue(json(404, { detail: "환자 x 를 찾을 수 없습니다" }));
    try {
      await fetchOverview(" a b ");
      throw new Error("should fail");
    } catch (e) {
      expect(String(fetchMock.mock.calls[0][0])).toContain("/api/patients/a%20b/overview");
      expect(e).toBeInstanceOf(ApiError);
      expect(errorMessage(e)).toBe("환자 x 를 찾을 수 없습니다");
    }
  });
});
