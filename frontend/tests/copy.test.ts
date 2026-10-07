import { describe, expect, it } from "vitest";
import type { CalculatorSpec, Result } from "../src/api";
import { resultText, summaryText } from "../src/copy";

const spec = { id: "curb65", name: "CURB-65", group: "중증도", description: "", inputs: [], references: [], scale: null, guide: null } as CalculatorSpec;
const result: Result = {
  value: 4, unit: "점", label: "중증 - 중환자실 평가", severity: "danger", notes: [], extra: {},
  details: [
    { label: "의식 혼미 (C)", text: "아니오", points: 0 },
    { label: "BUN >19 mg/dL (U)", text: "24 mg/dL", points: 1 },
  ],
};
const ctx = { patientId: "20000002", fetchedAt: "2026-10-07T13:35:00" };

describe("resultText", () => {
  it("머리줄 + 점수 구성 + 기준 줄", () => {
    expect(resultText(spec, result, ctx)).toBe(
      "CURB-65 4점 - 중증 - 중환자실 평가\n  의식 혼미 (C): 아니오 (0) · BUN >19 mg/dL (U): 24 mg/dL (+1)\n  기준: 환자 20000002 · 조회 2026-10-07 13:35",
    );
  });
  it("환자가 없으면 기준 줄을 뺀다", () => {
    expect(resultText(spec, result, null).split("\n")).toHaveLength(2);
  });
});

describe("summaryText", () => {
  it("계산기마다 한 줄", () => {
    expect(summaryText([{ spec, result }], ctx)).toBe("CURB-65 4점 - 중증 - 중환자실 평가\n기준: 환자 20000002 · 조회 2026-10-07 13:35");
  });
});
