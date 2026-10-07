/**
 * 계산기 입력 상태 — 자동 채움(prefill)과 사용자 수정을 합치는 순수 로직. 화면 코드와 분리해 테스트한다.
 *
 * 필드 하나의 상태 = 값(문자열 또는 참/거짓) + 출처(origin). 출처는 태그로 그려진다:
 *   fhir(검사·활력징후·심전도) · derived(계산·추정) · condition(진단 코드) · default(스펙 기본값) · manual(사용자 입력) · empty
 */
import type { CalculatorSpec, InputSpec, PrefillEntry, PrefillSource } from "./api";

export type Origin = "fhir" | "patient" | "derived" | "condition" | "default" | "manual" | "empty";

export interface FieldState {
  value: string | boolean;
  origin: Origin;
  source: PrefillSource | null;
}

export type FormState = Record<string, FieldState>;

function originOf(src: PrefillSource): Origin {
  if (src.category === "condition") return "condition";
  if (src.category === "patient") return "patient";
  if (src.derived || src.category === "derived") return "derived";
  return "fhir";
}

function emptyValue(spec: InputSpec): string | boolean {
  return spec.type === "boolean" ? false : "";
}

/** 스펙 + prefill → 초기 폼 상태. prefill 이 없으면 스펙 기본값, 그것도 없으면 빈 값. */
export function initialForm(spec: CalculatorSpec, prefill: Record<string, PrefillEntry> | undefined): FormState {
  const form: FormState = {};
  for (const i of spec.inputs) {
    const p = prefill?.[i.key];
    if (p && p.value !== null && p.value !== undefined) {
      form[i.key] = { value: toFieldValue(i, p.value), origin: originOf(p.source), source: p.source };
    } else if (i.default !== null && i.default !== undefined) {
      form[i.key] = { value: toFieldValue(i, i.default), origin: "default", source: null };
    } else {
      form[i.key] = { value: emptyValue(i), origin: "empty", source: null };
    }
  }
  return form;
}

function toFieldValue(spec: InputSpec, v: unknown): string | boolean {
  if (spec.type === "boolean") return v === true || v === "true" || v === 1;
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : "";
  return v === null || v === undefined ? "" : String(v);
}

/** 사용자 수정 — 출처를 manual 로 바꾼다. 빈 문자열로 지우면 empty. */
export function setField(form: FormState, key: string, value: string | boolean): FormState {
  const origin: Origin = value === "" ? "empty" : "manual";
  return { ...form, [key]: { value, origin, source: null } };
}

/** 폼 → POST /api/calculate 본문. 빈 값은 빼서 서버가 「누락」으로 판정하게 한다. */
export function toPayload(spec: CalculatorSpec, form: FormState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const i of spec.inputs) {
    const f = form[i.key];
    if (!f) continue;
    if (i.type === "boolean") {
      out[i.key] = f.value === true;
    } else if (i.type === "number") {
      const s = String(f.value).trim();
      if (s === "") continue;
      const n = Number(s);
      out[i.key] = Number.isFinite(n) ? n : s; // 숫자가 아니면 그대로 보내 서버 검증 메시지를 받는다
    } else if (String(f.value) !== "") {
      out[i.key] = f.value;
    }
  }
  return out;
}

/** 필수인데 비어 있는 키 — 서버 왕복 전에 「입력 필요」 표시용. */
export function missingRequired(spec: CalculatorSpec, form: FormState): string[] {
  return spec.inputs
    .filter((i) => i.required && i.type !== "boolean")
    .filter((i) => String(form[i.key]?.value ?? "").trim() === "")
    .map((i) => i.key);
}

/** 자동 채움(비수동) 필드 수 — 카드 머리의 「자동 n/m」 표시. */
export function autoCount(form: FormState): { auto: number; total: number } {
  const states = Object.values(form);
  return { auto: states.filter((f) => f.origin === "fhir" || f.origin === "patient" || f.origin === "derived" || f.origin === "condition").length, total: states.length };
}
