import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, calculate, errorMessage, type CalculatorOverview, type CalculatorSpec, type InputSpec, type Result } from "../api";
import { CATEGORY_LABEL, daysAgo, fmtDateTime, fmtNum } from "../format";
import { autoCount, initialForm, missingRequired, setField, toPayload, type FieldState, type FormState } from "../inputs";
import { SEVERITY_BAR, SEVERITY_TONE, Tag, btn, input, type Tone } from "../ui";
import ScaleBar from "./ScaleBar";

const ORIGIN_TAG: Record<FieldState["origin"], { label: string; tone: Tone } | null> = {
  fhir: { label: "FHIR 기록", tone: "indigo" },
  patient: { label: "환자정보", tone: "indigo" },
  derived: { label: "자동 계산", tone: "sky" },
  condition: { label: "진단 코드", tone: "indigo" },
  manual: { label: "직접 입력", tone: "gray" },
  default: { label: "기본값", tone: "gray" },
  empty: null,
};

const RESULT_BG: Record<Result["severity"], string> = {
  ok: "bg-emerald-50 border-emerald-200",
  info: "bg-sky-50 border-sky-200",
  warn: "bg-amber-50 border-amber-200",
  danger: "bg-red-50 border-red-200",
};

/**
 * 계산기 카드 - 위에서 아래로 「결과 → 입력 → 참고」. 입력이 바뀌면 300ms 뒤 서버에 재계산을 요청한다.
 * 환자가 바뀌면 부모가 key 를 바꿔 다시 마운트한다 (폼을 prefill 로 재생성).
 */
export default function CalculatorCard({
  spec,
  overview,
  onResult,
  focusSeq,
}: {
  spec: CalculatorSpec;
  overview: CalculatorOverview | undefined;
  flagLabels?: Record<string, string>;
  /** 현재 결과(사용자 수정 반영)를 부모에 보고 - 요약 표·탭 배지용 */
  onResult?: (id: string, result: Result | null, missing: string[]) => void;
  /** 요약 표에서 이 카드로 이동할 때마다 증가 - 입력 영역을 연다 */
  focusSeq?: number;
}) {
  const [form, setForm] = useState<FormState>(() => initialForm(spec, overview?.prefill));
  const [result, setResult] = useState<Result | null>(overview?.result ?? null);
  const [serverMissing, setServerMissing] = useState<string[]>(overview?.missing ?? []);
  const [err, setErr] = useState<string>(overview?.error ?? "");
  const [busy, setBusy] = useState(false);
  // 입력 영역은 기본 접힘. 자동 채움만으로 계산이 안 되는(입력이 필요한) 카드만 처음부터 연다.
  const [open, setOpen] = useState(() => !overview?.result);
  const dirty = useRef(false);
  const seq = useRef(0);

  const missing = useMemo(() => missingRequired(spec, form), [spec, form]);
  const counts = useMemo(() => autoCount(form), [form]);

  // 사용자 수정 뒤 디바운스 재계산. 첫 렌더(prefill 그대로)는 서버 overview 결과를 쓴다.
  useEffect(() => {
    if (!dirty.current) return;
    if (missing.length) {
      setResult(null);
      setServerMissing(missing);
      setErr("");
      return;
    }
    const my = ++seq.current;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await calculate(spec.id, toPayload(spec, form));
        if (my !== seq.current) return;
        setResult(r);
        setServerMissing([]);
        setErr("");
      } catch (e) {
        if (my !== seq.current) return;
        setResult(null);
        if (e instanceof ApiError && e.inputError) {
          setServerMissing(e.inputError.missing);
          const inv = Object.entries(e.inputError.invalid);
          setErr(inv.length ? inv.map(([k, m]) => `${labelOf(spec, k)}: ${m}`).join(" / ") : "");
          if (!inv.length && !e.inputError.missing.length) setErr(e.inputError.message);
        } else {
          setErr(errorMessage(e));
        }
      } finally {
        if (my === seq.current) setBusy(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [form, missing, spec]);

  function change(key: string, value: string | boolean) {
    dirty.current = true;
    setForm((f) => setField(f, key, value));
  }

  function reset() {
    dirty.current = false;
    setForm(initialForm(spec, overview?.prefill));
    setResult(overview?.result ?? null);
    setServerMissing(overview?.missing ?? []);
    setErr(overview?.error ?? "");
  }

  const missingKeys = result ? [] : serverMissing.length ? serverMissing : missing;
  const bar = result ? SEVERITY_BAR[result.severity] : "border-l-gray-300";

  const missingSig = missingKeys.join(",");
  useEffect(() => {
    onResult?.(spec.id, result, missingSig ? missingSig.split(",") : []);
  }, [onResult, spec.id, result, missingSig]);

  // 요약 표에서 「열기」로 이동해 오면 입력 영역을 펼친다
  useEffect(() => {
    if (focusSeq) setOpen(true);
  }, [focusSeq]);

  const manualCount = Object.values(form).filter((f) => f.origin === "manual").length;
  const emptyCount = Object.values(form).filter((f) => f.origin === "empty").length;
  const hasPoints = !!result && result.details.some((d) => d.points !== null);

  return (
    <article id={`calc-${spec.id}`} className={`scroll-mt-20 rounded-lg border border-gray-200 border-l-4 bg-white ${bar}`}>
      {/* ---------- 머리 ---------- */}
      <header className="flex flex-col gap-3 px-4 pt-4 sm:flex-row sm:items-start sm:gap-4 sm:px-5">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-gray-900">{spec.name}</h3>
          <p className="text-sm text-gray-600">{spec.description}</p>
          {spec.guide && <p className="mt-1 max-w-3xl text-xs leading-relaxed text-gray-500">{spec.guide}</p>}
          <p className="mt-1.5 text-[11px] text-gray-400">
            입력 {counts.total}개 · 자동 채움 {counts.auto} · 직접 입력 {manualCount}
            {emptyCount > 0 && <span className="text-amber-700"> · 비어 있음 {emptyCount}</span>}
          </p>
        </div>
        <div className="flex shrink-0 flex-row items-center gap-2 sm:flex-col sm:items-end sm:gap-1.5">
          <button
            type="button"
            className={`${btn.secondary} w-[120px] whitespace-nowrap`}
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={`inputs-${spec.id}`}
          >
            {open ? "입력값 닫기 ▴" : "입력값 수정 ▾"}
          </button>
          {dirty.current && (
            <button type="button" className={`${btn.ghost} whitespace-nowrap`} onClick={reset}>
              자동 값으로 되돌리기
            </button>
          )}
        </div>
      </header>

      {/* ---------- 결과 ---------- */}
      <section className={`px-4 pt-4 sm:px-5 ${open ? "" : "pb-4"}`}>
        {result ? (
          <div className={`rounded-md border px-4 py-3 ${RESULT_BG[result.severity]}`}>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-mono text-2xl font-semibold text-gray-900 sm:text-3xl">
                {fmtNum(result.value, 1)}
                {result.unit && <span className="ml-1 text-base font-normal text-gray-500">{result.unit}</span>}
              </span>
              <Tag tone={SEVERITY_TONE[result.severity]}>{result.label}</Tag>
              {busy && <span className="text-[11px] text-gray-400">다시 계산 중…</span>}
            </div>
            {spec.scale && <ScaleBar scale={spec.scale} value={result.value} unit={result.unit} />}

            {result.details.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer select-none text-xs font-semibold text-gray-600 hover:text-gray-900">
                  {hasPoints ? "점수 구성 보기" : "계산에 쓴 값 보기"}
                </summary>
                <table className="mt-1 w-full">
                  <tbody>
                    {result.details.map((d, idx) => (
                      <tr key={idx} className="border-t border-black/5 align-top">
                        <td className="py-1 pr-2 text-gray-600">{d.label}</td>
                        <td className="py-1 text-gray-900">{d.text}</td>
                        <td className="py-1 pl-2 text-right font-mono text-gray-800">
                          {d.points !== null ? (d.points > 0 ? `+${fmtNum(d.points, 0)}` : "0") : ""}
                        </td>
                      </tr>
                    ))}
                    {hasPoints && (
                      <tr className="border-t border-black/10 font-semibold">
                        <td className="py-1 pr-2 text-gray-700" colSpan={2}>
                          합계
                        </td>
                        <td className="py-1 pl-2 text-right font-mono text-gray-900">{fmtNum(result.value, 1)}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </details>
            )}
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-amber-300 bg-amber-50/40 px-4 py-3">
            {busy ? (
              <p className="text-sm text-gray-500">계산 중…</p>
            ) : (
              <>
                <p className="text-sm font-medium text-amber-800">아직 계산할 수 없습니다</p>
                {missingKeys.length > 0 && (
                  <p className="mt-1 text-xs text-amber-800">
                    아래에서 다음 값을 채워 주세요: <b>{missingKeys.map((k) => labelOf(spec, k)).join(", ")}</b>
                  </p>
                )}
                {spec.scale && <ScaleBar scale={spec.scale} value={null} unit={null} />}
              </>
            )}
          </div>
        )}
        {err && <p className="mt-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{err}</p>}
      </section>

      {/* ---------- 입력 ---------- */}
      <section id={`inputs-${spec.id}`} className="px-4 py-4 sm:px-5" hidden={!open}>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">입력값</h4>
        <div className="grid gap-2 sm:grid-cols-2">
          {spec.inputs.map((i) => (
            <Field key={i.key} spec={i} state={form[i.key]} onChange={(v) => change(i.key, v)} missing={missingKeys.includes(i.key)} />
          ))}
        </div>
      </section>

      {/* ---------- 참고 ---------- */}
      {(result?.notes.length || spec.references.length) ? (
        <footer className="border-t border-gray-100 px-4 py-3 sm:px-5">
          {result && result.notes.length > 0 && (
            <ul className="space-y-1 text-xs leading-relaxed text-gray-600">
              {result.notes.map((n, idx) => (
                <li key={idx} className="flex gap-1.5">
                  <span className="text-gray-300">•</span>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          )}
          {spec.references.length > 0 && <p className="mt-2 text-[11px] text-gray-400">출전: {spec.references.join(" · ")}</p>}
        </footer>
      ) : null}
    </article>
  );
}

function labelOf(spec: CalculatorSpec, key: string): string {
  return spec.inputs.find((i) => i.key === key)?.label ?? key;
}

/** 출처 한 줄 - 「검사 · Creatinine 1.8 mg/dL · 2026-10-05 08:30 (2일 전)」 */
function sourceLine(spec: InputSpec, st: FieldState): { text: string; stale: boolean } {
  const src = st.source;
  if (src) {
    const cat = CATEGORY_LABEL[src.category] ?? src.category;
    const when = src.observed_at ? ` · ${fmtDateTime(src.observed_at)} (${daysAgo(src.observed_at)})` : "";
    return { text: `${cat} · ${src.text}${when}`, stale: src.stale };
  }
  if (st.origin === "manual") return { text: "직접 입력한 값", stale: false };
  if (st.origin === "default") return { text: spec.help ? `기본값 · ${spec.help}` : "기본값 - 해당하면 바꿔 주세요", stale: false };
  if (spec.help) return { text: spec.help, stale: false };
  return { text: spec.required ? "기록에서 찾지 못했습니다 - 직접 입력해 주세요" : "선택 입력", stale: false };
}

function Field({
  spec,
  state,
  onChange,
  missing,
}: {
  spec: InputSpec;
  state: FieldState | undefined;
  onChange: (v: string | boolean) => void;
  missing: boolean;
}) {
  const st = state ?? { value: spec.type === "boolean" ? false : "", origin: "empty" as const, source: null };
  const tag = ORIGIN_TAG[st.origin];
  const src = sourceLine(spec, st);
  const box = `rounded-md border p-2.5 ${missing ? "border-amber-300 bg-amber-50/50" : "border-gray-200"}`;
  const srcCls = `mt-1 text-[11px] leading-snug ${src.stale ? "text-amber-700" : "text-gray-500"}`;

  if (spec.type === "boolean") {
    return (
      <div className={box}>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 shrink-0 accent-indigo-600"
            checked={st.value === true}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span className="flex-1 text-sm text-gray-800">{spec.label}</span>
          {tag && <Tag tone={tag.tone}>{tag.label}</Tag>}
        </label>
        <p className={`${srcCls} ml-6`}>
          {src.text}
          {src.stale ? " · 오래된 기록" : ""}
        </p>
      </div>
    );
  }

  return (
    <div className={box}>
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium text-gray-800">
          {spec.label}
          {spec.required && <span className="ml-0.5 text-amber-600">*</span>}
        </label>
        {tag && <Tag tone={tag.tone}>{tag.label}</Tag>}
        {!tag && missing && <Tag tone="amber">입력 필요</Tag>}
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        {spec.type === "select" ? (
          <select className={input} value={String(st.value)} onChange={(e) => onChange(e.target.value)}>
            <option value="">선택…</option>
            {spec.options?.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        ) : (
          <>
            <input
              type="text"
              inputMode="decimal"
              className={`${input} max-w-[180px] font-mono`}
              value={String(st.value)}
              onChange={(e) => onChange(e.target.value)}
              placeholder={spec.required ? "필수" : "선택"}
            />
            {spec.unit && <span className="text-sm text-gray-500">{spec.unit}</span>}
          </>
        )}
      </div>
      <p className={srcCls}>
        {src.text}
        {src.stale ? " · 오래된 기록" : ""}
      </p>
    </div>
  );
}
