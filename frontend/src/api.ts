/**
 * API 클라이언트 — 백엔드 `/api/*`.
 *
 * 경로 규칙 (snuh-fhir 와 동일): 프런트는 `/ui/` 아래에 서빙되고 공개 URL 에는 배포 prefix 가 붙으므로
 * API 는 절대 경로가 아니라 **문서 기준 상대 경로**(`../api/...`)로 부른다. vite dev 는 `/` 에서 서빙되므로
 * `../` 가 루트로 수렴해 같은 코드가 그대로 동작한다 (vite.config.ts proxy).
 */

export function apiUrl(path: string, base?: string): string {
  const b = base ?? (typeof document !== "undefined" ? document.baseURI : "http://localhost/");
  return new URL(`../${path.replace(/^\/+/, "")}`, b).toString();
}

/* ---------- 오류 ---------- */

export interface InputErrorDetail {
  message: string;
  missing: string[];
  invalid: Record<string, string>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly inputError: InputErrorDetail | null;
  constructor(status: number, detail: unknown) {
    const ie = isInputErrorDetail(detail) ? detail : null;
    const text = ie ? ie.message : detailToString(detail, status);
    super(text);
    this.name = "ApiError";
    this.status = status;
    this.detail = text;
    this.inputError = ie;
  }
}

function isInputErrorDetail(d: unknown): d is InputErrorDetail {
  return !!d && typeof d === "object" && "message" in d && "missing" in d;
}

function detailToString(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) =>
      d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d),
    );
    if (parts.length) return parts.join("; ");
  }
  return `HTTP ${status}`;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message || e.name;
  return String(e);
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(res.status, body?.detail);
  }
  return res.json() as Promise<T>;
}

/* ---------- 타입 (백엔드 to_dict / pydantic 과 1:1) ---------- */

export type InputType = "number" | "boolean" | "select";
export type Severity = "ok" | "info" | "warn" | "danger";

export interface InputSpec {
  key: string;
  label: string;
  type: InputType;
  unit: string | null;
  required: boolean;
  default: unknown;
  variable: string | null;
  flag: string | null;
  auto: boolean;
  minimum: number | null;
  maximum: number | null;
  help: string | null;
  options?: { value: string; label: string }[];
}

export interface Band {
  upto: number | null;
  label: string;
  severity: Severity;
}

export interface Scale {
  min: number;
  max: number;
  bands: Band[];
  note: string | null;
}

export interface CalculatorSpec {
  id: string;
  name: string;
  group: string;
  description: string;
  inputs: InputSpec[];
  references: string[];
  scale: Scale | null;
  guide: string | null;
}

export interface Detail {
  label: string;
  text: string;
  points: number | null;
}

export interface Result {
  value: number | null;
  unit: string | null;
  label: string;
  severity: Severity;
  details: Detail[];
  notes: string[];
  extra: Record<string, unknown>;
}

export interface CalculatorsResponse {
  items: CalculatorSpec[];
  variables: Record<string, { label: string; unit: string | null }>;
  flags: Record<string, string>;
}

export interface ObservedValue {
  variable: string;
  value: number;
  unit: string | null;
  observed_at: string | null;
  source: { display: string; category: string; resource_id: string | null };
  derived: boolean;
}

export interface Snapshot {
  patient: { id: string; name: string | null; sex: "M" | "F" | null; birth_date: string | null; age: number | null };
  fetched_at: string;
  values: Record<string, ObservedValue>;
  weight_history: { value: number; observed_at: string }[];
  conditions: { code: string; display: string | null; recorded_date: string | null }[];
  conditions_available: boolean;
  flags: Record<string, { present: boolean; codes: string[]; displays: string[] }>;
  warnings: string[];
}

export interface PrefillSource {
  text: string;
  category: string;
  observed_at: string | null;
  stale: boolean;
  derived: boolean;
}

export interface PrefillEntry {
  value: unknown;
  source: PrefillSource;
}

export interface CalculatorOverview {
  id: string;
  prefill: Record<string, PrefillEntry>;
  result: Result | null;
  missing: string[];
  error: string | null;
}

export interface Overview {
  snapshot: Snapshot;
  flag_labels: Record<string, string>;
  calculators: CalculatorOverview[];
}

export interface Readiness {
  status: string;
  fhir?: string;
  fixtures?: number;
  detail?: string;
}

/* ---------- 호출 ---------- */

export async function fetchCalculators(): Promise<CalculatorsResponse> {
  return unwrap(await fetch(apiUrl("api/calculators"), { cache: "no-store" }));
}

export async function fetchOverview(patientId: string): Promise<Overview> {
  return unwrap(await fetch(apiUrl(`api/patients/${encodeURIComponent(patientId.trim())}/overview`), { cache: "no-store" }));
}

export async function calculate(calcId: string, inputs: Record<string, unknown>): Promise<Result> {
  return unwrap(
    await fetch(apiUrl(`api/calculate/${encodeURIComponent(calcId)}`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs }),
    }),
  );
}

export async function fetchReadiness(): Promise<Readiness> {
  const res = await fetch(apiUrl("api/health/ready"), { cache: "no-store" });
  return (await res.json()) as Readiness;
}
