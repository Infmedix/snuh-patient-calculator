import { useMemo, useState } from "react";

/** 넓은 화면(lg)에서는 값 표를 펼쳐 두고, 폰에서는 접어 둬 계산기 카드가 먼저 보이게 한다. */
function wideScreen(): boolean {
  try {
    return typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;
  } catch {
    return true;
  }
}
import type { Overview } from "../api";
import { CATEGORY_LABEL, SEX_LABEL, daysAgo, fmtDate, fmtDateTime, fmtNum } from "../format";
import { Tag, btn, td, th } from "../ui";

/** 좌측 패널 - 환자 요약 · 진단 플래그 · 가져온 값 표 · 경고. */
export default function PatientPanel({
  overview,
  variables,
  loading,
}: {
  overview: Overview | null;
  variables: Record<string, { label: string; unit: string | null }>;
  loading: boolean;
}) {
  const [showConditions, setShowConditions] = useState(false);
  const [showValues, setShowValues] = useState<boolean>(() => wideScreen());

  const rows = useMemo(() => {
    if (!overview) return [];
    const order = Object.keys(variables);
    return Object.values(overview.snapshot.values).sort(
      (a, b) => order.indexOf(a.variable) - order.indexOf(b.variable),
    );
  }, [overview, variables]);

  if (!overview) {
    return (
      <section className="rounded-lg border border-dashed border-gray-300 bg-white p-4 text-sm text-gray-500">
        <h2 className="mb-1 text-sm font-semibold text-gray-700">환자 정보</h2>
        {loading ? (
          <p>FHIR 에서 최근 기록을 가져오는 중…</p>
        ) : (
          <>
            <p>환자번호를 입력하면 최근 검사·활력징후·심전도·진단을 가져와 계산기 입력을 자동으로 채웁니다.</p>
            <p className="mt-2 text-xs text-gray-400">환자 없이도 각 카드에 값을 직접 입력해 계산할 수 있습니다.</p>
          </>
        )}
      </section>
    );
  }

  const s = overview.snapshot;
  const p = s.patient;
  // cci_* 는 Charlson 카드 전용 세부 항목 - 패널 칩은 일반 플래그만
  const presentFlags = Object.entries(s.flags).filter(([name, f]) => f.present && !name.startsWith("cci_"));

  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-mono text-lg font-semibold text-gray-900">{p.id}</p>
            <p className="text-sm text-gray-600">
              {p.name ?? "-"} · {p.sex ? SEX_LABEL[p.sex] : "성별 미상"} · {p.age !== null ? `${p.age}세` : "나이 미상"}
              {p.birth_date && <span className="ml-1 text-xs text-gray-400">({p.birth_date})</span>}
            </p>
          </div>
          <span className="text-[11px] text-gray-400" title={fmtDateTime(s.fetched_at)}>
            조회 {fmtDateTime(s.fetched_at).slice(11)}
          </span>
        </div>

        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold text-gray-500">진단 플래그 (최근 진단 코드 기반)</p>
          {!s.conditions_available ? (
            <p className="text-xs text-amber-700">진단을 가져오지 못해 플래그를 제안할 수 없습니다.</p>
          ) : presentFlags.length === 0 ? (
            <p className="text-xs text-gray-400">해당하는 진단 코드 없음</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {presentFlags.map(([name, f]) => (
                <Tag key={name} tone="indigo" title={`${f.codes.join(", ")}\n${f.displays.join(" / ")}`}>
                  {overview.flag_labels[name] ?? name}
                </Tag>
              ))}
            </div>
          )}
          {s.conditions.length > 0 && (
            <button type="button" className={`${btn.ghost} mt-1 -ml-2`} onClick={() => setShowConditions((v) => !v)}>
              진단 {s.conditions.length}건 {showConditions ? "접기" : "보기"}
            </button>
          )}
          {showConditions && (
            <ul className="mt-1 max-h-48 space-y-0.5 overflow-auto text-xs text-gray-600">
              {s.conditions.map((c) => (
                <li key={c.code} className="flex gap-2">
                  <span className="w-14 shrink-0 font-mono text-gray-800">{c.code}</span>
                  <span className="flex-1 truncate" title={c.display ?? ""}>
                    {c.display ?? "-"}
                  </span>
                  <span className="shrink-0 text-gray-400">{fmtDate(c.recorded_date)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {s.warnings.length > 0 && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1 font-semibold">일부 자료를 가져오지 못했습니다</p>
          <ul className="list-inside list-disc space-y-0.5">
            {s.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg border border-gray-200 bg-white">
        <button
          type="button"
          className="flex w-full items-center justify-between px-4 py-3 text-left"
          onClick={() => setShowValues((v) => !v)}
          aria-expanded={showValues}
        >
          <h2 className="text-xs font-semibold text-gray-500">가져온 값 (변수별 최근 1건)</h2>
          <span className="text-[11px] text-gray-400">
            {rows.length}개 {showValues ? "▴" : "▾"}
          </span>
        </button>
        {!showValues ? null : rows.length === 0 ? (
          <p className="px-4 py-3 text-xs text-gray-400">조회 기간 안에 매칭되는 기록이 없습니다.</p>
        ) : (
          <div className="scroll-stable max-h-[60vh] overflow-y-auto overflow-x-hidden px-2 pb-2">
            <table className="w-full table-fixed">
              <thead>
                <tr>
                  <th className={th}>항목</th>
                  <th className={`${th} w-[88px] text-right`}>값</th>
                  <th className={`${th} w-[60px]`}>기록</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((v) => {
                  const meta = variables[v.variable];
                  const ago = daysAgo(v.observed_at);
                  const stale = /개월|년|([7-9]|[1-9]\d)일/.test(ago);
                  return (
                    <tr key={v.variable} className="border-t border-gray-100">
                      <td className={td}>
                        <div className="text-sm text-gray-800">{meta?.label ?? v.variable}</div>
                        <div className="truncate text-[11px] text-gray-400" title={v.source.display}>
                          {CATEGORY_LABEL[v.source.category] ?? v.source.category} · {v.source.display}
                        </div>
                      </td>
                      <td className={`${td} text-right font-mono`}>
                        {fmtNum(v.value, 2)}
                        <div className="truncate text-[10px] text-gray-400" title={v.unit ?? ""}>{v.unit ?? ""}</div>
                      </td>
                      <td className={`${td} whitespace-nowrap`} title={fmtDateTime(v.observed_at)}>
                        <span className={`text-xs ${stale ? "text-amber-700" : "text-gray-500"}`}>{ago || "-"}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
