/** 결과 복사 - 경과기록에 붙여 넣을 한 덩어리 텍스트를 만들고 클립보드에 쓴다. */
import type { CalculatorSpec, Result } from "./api";
import { fmtDateTime, fmtNum } from "./format";

export interface CopyContext {
  patientId: string;
  fetchedAt: string;
}

/** 한 계산기의 결과 텍스트. 예:
 *  CURB-65 4점 - 중증 - 중환자실 평가
 *    의식 혼미 (C): 아니오 (0) · BUN >19 mg/dL (U): 24 mg/dL (+1) · …
 *  기준: 환자 20000002 · 조회 2026-10-07 13:35
 */
export function resultText(spec: CalculatorSpec, result: Result, ctx: CopyContext | null, withContext = true): string {
  const head = `${spec.name} ${fmtNum(result.value, 1)}${result.unit ?? ""} - ${result.label}`;
  const parts = result.details.map((d) => {
    const pts = d.points === null ? "" : ` (${d.points > 0 ? "+" : ""}${fmtNum(d.points, 0)})`;
    return `${d.label}: ${d.text}${pts}`;
  });
  const lines = [head];
  if (parts.length) lines.push("  " + parts.join(" · "));
  if (withContext && ctx) lines.push(`  기준: 환자 ${ctx.patientId} · 조회 ${fmtDateTime(ctx.fetchedAt)}`);
  return lines.join("\n");
}

/** 요약 탭 전체 복사 - 계산된 것만, 그룹 순서대로. */
export function summaryText(items: { spec: CalculatorSpec; result: Result }[], ctx: CopyContext | null): string {
  const lines = items.map(({ spec, result }) => `${spec.name} ${fmtNum(result.value, 1)}${result.unit ?? ""} - ${result.label}`);
  if (ctx) lines.push(`기준: 환자 ${ctx.patientId} · 조회 ${fmtDateTime(ctx.fetchedAt)}`);
  return lines.join("\n");
}

/** 클립보드 쓰기 - HTTPS 가 아니거나 권한이 없으면 숨은 textarea + execCommand 로 폴백. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* 폴백 */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
