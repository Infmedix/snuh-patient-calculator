/** 표시용 포맷 도우미 - 순수 함수. */

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "-";
  const r = Math.round(v * 10 ** digits) / 10 ** digits;
  return Number.isInteger(r) ? String(r) : r.toFixed(digits).replace(/\.?0+$/, "");
}

/** ISO(로컬 naive 또는 UTC) → `YYYY-MM-DD HH:mm`. 날짜만이면 그대로. */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function fmtDate(iso: string | null | undefined): string {
  const s = fmtDateTime(iso);
  return s === "-" ? s : s.slice(0, 10);
}

/** 기록 시각이 `now` 기준 며칠 전인지 - "오늘" · "3일 전" · "2개월 전". */
export function daysAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (days <= 0) return "오늘";
  if (days < 30) return `${days}일 전`;
  if (days < 365) return `${Math.floor(days / 30)}개월 전`;
  return `${Math.floor(days / 365)}년 전`;
}

export const SEX_LABEL: Record<string, string> = { M: "남", F: "여" };

export const CATEGORY_LABEL: Record<string, string> = {
  laboratory: "검사",
  clinical: "간호기록",
  exam: "심전도",
  derived: "계산",
  condition: "진단",
  patient: "환자정보",
};
