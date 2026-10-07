import { describe, expect, it } from "vitest";
import type { CalculatorSpec, PrefillEntry } from "../src/api";
import { autoCount, initialForm, missingRequired, setField, toPayload } from "../src/inputs";

const spec: CalculatorSpec = {
  id: "demo",
  name: "Demo",
  group: "g",
  description: "",
  references: [],
  inputs: [
    { key: "cr", label: "Cr", type: "number", unit: "mg/dL", required: true, default: null, variable: "creatinine", flag: null, auto: true, minimum: 0, maximum: 50, help: null },
    { key: "age", label: "나이", type: "number", unit: "세", required: true, default: null, variable: null, flag: null, auto: true, minimum: 0, maximum: 130, help: null },
    { key: "htn", label: "고혈압", type: "boolean", unit: null, required: true, default: false, variable: null, flag: "hypertension", auto: true, minimum: null, maximum: null, help: null },
    { key: "basis", label: "기준", type: "select", unit: null, required: true, default: "actual", variable: null, flag: null, auto: false, minimum: null, maximum: null, help: null,
      options: [{ value: "actual", label: "실제" }, { value: "ideal", label: "이상" }] },
    { key: "opt", label: "선택", type: "number", unit: null, required: false, default: null, variable: null, flag: null, auto: false, minimum: null, maximum: null, help: null },
  ],
};

const src = (category: string, derived = false) => ({ text: "x", category, observed_at: "2026-10-05T08:30:00", stale: false, derived });

describe("initialForm", () => {
  it("prefill 값을 출처별 origin 으로 채운다", () => {
    const prefill: Record<string, PrefillEntry> = {
      cr: { value: 1.8, source: src("laboratory") },
      age: { value: 68, source: src("derived", true) },
      htn: { value: true, source: src("condition") },
    };
    const f = initialForm(spec, prefill);
    expect(f.cr).toEqual({ value: "1.8", origin: "fhir", source: prefill.cr.source });
    expect(f.age.origin).toBe("derived");
    expect(initialForm(spec, { age: { value: 68, source: src("patient") } }).age.origin).toBe("patient");
    expect(f.htn).toMatchObject({ value: true, origin: "condition" });
  });

  it("prefill 이 없으면 기본값, 그것도 없으면 빈 값", () => {
    const f = initialForm(spec, undefined);
    expect(f.cr).toEqual({ value: "", origin: "empty", source: null });
    expect(f.htn).toEqual({ value: false, origin: "default", source: null });
    expect(f.basis).toEqual({ value: "actual", origin: "default", source: null });
  });
});

describe("setField / toPayload", () => {
  it("수정하면 manual, 지우면 empty 가 되고 payload 에서 빈 값은 빠진다", () => {
    let f = initialForm(spec, { cr: { value: 1.8, source: src("laboratory") } });
    f = setField(f, "cr", "2.0");
    expect(f.cr.origin).toBe("manual");
    f = setField(f, "age", "");
    expect(f.age.origin).toBe("empty");
    const p = toPayload(spec, f);
    expect(p).toEqual({ cr: 2.0, htn: false, basis: "actual" });
  });

  it("숫자가 아닌 입력은 문자열로 보내 서버 검증을 받게 한다", () => {
    const f = setField(initialForm(spec, undefined), "cr", "abc");
    expect(toPayload(spec, f).cr).toBe("abc");
  });
});

describe("missingRequired / autoCount", () => {
  it("필수 숫자·선택 중 빈 것만 돌려준다 (boolean 은 항상 값이 있음)", () => {
    const f = initialForm(spec, { cr: { value: 1.8, source: src("laboratory") } });
    expect(missingRequired(spec, f)).toEqual(["age"]);
  });

  it("자동 채움 수를 센다", () => {
    const f = initialForm(spec, { cr: { value: 1.8, source: src("laboratory") }, htn: { value: false, source: src("condition") } });
    expect(autoCount(f)).toEqual({ auto: 2, total: 5 });
  });
});
