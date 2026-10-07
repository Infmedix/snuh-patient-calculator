import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, calculate, errorMessage, type CalculatorOverview, type CalculatorSpec, type InputSpec, type Result } from "../api";
import { CATEGORY_LABEL, daysAgo, fmtDateTime, fmtNum } from "../format";
import { autoCount, initialForm, missingRequired, setField, toPayload, type FieldState, type FormState } from "../inputs";
import { SEVERITY_BAR, SEVERITY_TONE, Tag, btn, input, type Tone } from "../ui";

const ORIGIN_TAG: Record<FieldState["origin"], { label: string; tone: Tone } | null> = {
  fhir: { label: "FHIR", tone: "indigo" },
  patient: { label: "환자정보", tone: "indigo" },
  derived: { label: "계산", tone: "sky" },
  condition: { label: "진단", tone: "indigo" },
  manual: { label: "직접", tone: "gray" },
  default: null,
  empty: null,
};

/**
 * 계산기 카드 — 결과 + 스펙 기반 입력 폼. 입력이 바뀌면 300ms 뒤 서버에 재계산을 요청한다.
 * 환자가 바뀌면 부모가 key 를 바꿔 다시 마운트한다 (폼을 prefill 로 재생성).
 */
export default function CalculatorCard({
  spec,
  overview,
  flagLabels,
}: {
  spec: CalculatorSpec;
  overview: CalculatorOverview | undefined;
  flagLabels: Record<string, string>;
}) {
  const [form, setForm] = useState<FormState>(() => initialForm(spec, overview?.prefill));
  const [result, setResult] = useState<Result | null>(overview?.result ?? null);
  const [serverMissing, setServerMissing] = useState<string[]>(overview?.missing ?? []);
  const [err, setErr] = useState<string>(overview?.error ?? "");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(true);
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

  const missingKeys = result ? [] : (serverMissing.length ? serverMissing : missing);
  const bar = result ? SEVERITY_BAR[result.severity] : "border-l-gray-300";

  return (
    <article className={`flex flex-col rounded-lg border border-gray-200 border-l-4 bg-white ${bar}`}>
      <header className="flex items-start gap-2 px-4 pt-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-gray-900">{spec.name}</h3>
          <p className="truncate text-xs text-gray-500" title={spec.description}>
            {spec.description}
          </p>
        </div>
        <button type="button" className={btn.ghost} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "입력 접기" : "입력 펼치기"}
        </button>
      </header>

      <div className="px-4 pt-2">
        {result ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-mono text-2xl font-semibold text-gray-900">
              {fmtNum(result.value, 1)}
              {result.unit && <span className="ml-1 text-sm font-normal text-gray-500">{result.unit}</span>}
            </span>
            <Tag tone={SEVERITY_TONE[result.severity]}>{result.label}</Tag>
            {busy && <span className="text-[11px] text-gray-400">계산 중…</span>}
          </div>
        ) : (
          <div className="text-sm text-gray-500">
            {busy ? (
              "계산 중…"
            ) : missingKeys.length ? (
              <>
                <span className="font-medium text-amber-700">입력 필요</span>
                <span className="ml-1 text-xs text-gray-500">{missingKeys.map((k) => labelOf(spec, k)).join(", ")}</span>
              </>
            ) : (
              "결과 없음"
            )}
          </div>
        )}
        {err && <p className="mt-1 text-xs text-red-700">{err}</p>}
        <p className="mt-1 text-[11px] text-gray-400">
          자동 채움 {counts.auto}/{counts.total}
          {dirty.current && (
            <>
              {" · "}
              <button type="button" className="underline hover:text-gray-600" onClick={reset}>
                자동 값으로 되돌리기
              </button>
            </>
          )}
        </p>
      </div>

      {open && (
        <div className="mt-3 space-y-1.5 border-t border-gray-100 px-4 py-3">
          {spec.inputs.map((i) => (
            <Field key={i.key} spec={i} state={form[i.key]} onChange={(v) => change(i.key, v)} flagLabels={flagLabels}
                   missing={missingKeys.includes(i.key)} />
          ))}
        </div>
      )}

      {result && (result.details.length > 0 || result.notes.length > 0) && (
        <div className="border-t border-gray-100 px-4 py-3">
          {result.details.length > 0 && (
            <table className="w-full text-xs">
              <tbody>
                {result.details.map((d, idx) => (
                  <tr key={idx} className="align-top">
                    <td className="py-0.5 pr-2 text-gray-500">{d.label}</td>
                    <td className="py-0.5 text-gray-800">{d.text}</td>
                    <td className="py-0.5 pl-2 text-right font-mono text-gray-700">{d.points !== null ? `+${fmtNum(d.points, 0)}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.notes.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-[11px] text-gray-500">
              {result.notes.map((n, idx) => (
                <li key={idx}>· {n}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}

function labelOf(spec: CalculatorSpec, key: string): string {
  return spec.inputs.find((i) => i.key === key)?.label ?? key;
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
  flagLabels: Record<string, string>;
  missing: boolean;
}) {
  const st = state ?? { value: spec.type === "boolean" ? false : "", origin: "empty" as const, source: null };
  const tag = ORIGIN_TAG[st.origin];
  const src = st.source;
  const title = src ? `${CATEGORY_LABEL[src.category] ?? src.category} · ${src.text}${src.observed_at ? `\n${fmtDateTime(src.observed_at)}` : ""}` : spec.help ?? "";

  const meta = (
    <span className="flex shrink-0 items-center gap-1" title={title}>
      {tag && <Tag tone={tag.tone}>{tag.label}</Tag>}
      {src?.observed_at && (
        <span className={`text-[11px] ${src.stale ? "text-amber-700" : "text-gray-400"}`}>{daysAgo(src.observed_at)}</span>
      )}
      {src && !src.observed_at && (src.category === "derived" || src.category === "patient") && (
        <span className="max-w-[140px] truncate text-[11px] text-gray-400">{src.text}</span>
      )}
    </span>
  );

  if (spec.type === "boolean") {
    return (
      <label className="flex items-center gap-2 text-sm text-gray-800" title={title}>
        <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={st.value === true} onChange={(e) => onChange(e.target.checked)} />
        <span className="flex-1">{spec.label}</span>
        {meta}
      </label>
    );
  }

  const labelCls = `text-xs ${missing ? "text-amber-700" : "text-gray-600"}`;
  if (spec.type === "select") {
    return (
      <label className="grid grid-cols-[1fr_auto] items-center gap-x-2 gap-y-0.5" title={title}>
        <span className={labelCls}>
          {spec.label}
          {spec.required && <span className="text-amber-600"> *</span>}
        </span>
        {meta}
        <select className={`${input} col-span-2`} value={String(st.value)} onChange={(e) => onChange(e.target.value)}>
          <option value="">선택…</option>
          {spec.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <label className="grid grid-cols-[1fr_auto] items-center gap-x-2 gap-y-0.5" title={title}>
      <span className={labelCls}>
        {spec.label}
        {spec.required && <span className="text-amber-600"> *</span>}
        {spec.help && !src && <span className="ml-1 text-[11px] text-gray-400">{spec.help}</span>}
      </span>
      {meta}
      <div className="col-span-2 flex items-center gap-1">
        <input
          type="text"
          inputMode="decimal"
          className={`${input} font-mono ${missing ? "border-amber-300" : ""}`}
          value={String(st.value)}
          onChange={(e) => onChange(e.target.value)}
          placeholder={spec.required ? "필수" : "선택"}
        />
        {spec.unit && <span className="w-20 shrink-0 truncate text-xs text-gray-500" title={spec.unit}>{spec.unit}</span>}
      </div>
    </label>
  );
}
