/** 화면 공통 소품 - snuh-fhir ui.tsx 이식. 외부 UI 라이브러리 없이 Tailwind 만 쓴다. */
import type { ReactNode } from "react";
import type { Severity } from "./api";

export type Tone = "gray" | "red" | "amber" | "indigo" | "green" | "sky";

const TONE: Record<Tone, string> = {
  gray: "bg-gray-100 text-gray-600 ring-gray-200",
  red: "bg-red-100 text-red-700 ring-red-200",
  amber: "bg-amber-100 text-amber-800 ring-amber-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  green: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  sky: "bg-sky-50 text-sky-700 ring-sky-200",
};

export function Tag({ children, tone = "gray", title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return (
    <span title={title} className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export const SEVERITY_TONE: Record<Severity, Tone> = { ok: "green", info: "sky", warn: "amber", danger: "red" };

export const SEVERITY_BAR: Record<Severity, string> = {
  ok: "border-l-emerald-500",
  info: "border-l-sky-500",
  warn: "border-l-amber-500",
  danger: "border-l-red-500",
};

export function ErrorBox({ message, onClose }: { message: string; onClose?: () => void }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      <span className="flex-1 whitespace-pre-wrap">{message}</span>
      {onClose && (
        <button type="button" onClick={onClose} className="text-red-500 hover:text-red-700" aria-label="닫기">
          ×
        </button>
      )}
    </div>
  );
}

export const btn = {
  primary:
    "rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50",
  secondary:
    "rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50",
  ghost: "rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-50",
};

export const input =
  "w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50";

export const th = "px-2 py-1.5 text-left text-xs font-semibold text-gray-500 whitespace-nowrap";
export const td = "px-2 py-1 align-top text-sm text-gray-800";
