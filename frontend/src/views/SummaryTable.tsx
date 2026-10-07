import type { CalculatorSpec, Result } from "../api";
import { fmtNum } from "../format";
import { SEVERITY_TONE, Tag, td, th } from "../ui";

export interface LiveResult {
  result: Result | null;
  missing: string[];
}

/** 요약 탭 - 12개 계산기의 현재 결과를 한 표로. 행을 누르면 해당 그룹 탭의 카드로 이동. */
export default function SummaryTable({
  specs,
  groups,
  live,
  hasPatient,
  onJump,
}: {
  specs: CalculatorSpec[];
  groups: { name: string; items: CalculatorSpec[] }[];
  live: Record<string, LiveResult>;
  hasPatient: boolean;
  onJump: (calcId: string) => void;
}) {
  const done = specs.filter((s) => live[s.id]?.result).length;
  return (
    <section className="rounded-lg border border-gray-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">전체 결과</h2>
          <p className="text-xs text-gray-500">
            {hasPatient
              ? "자동 채움값으로 계산된 결과입니다. 행을 누르면 입력을 확인·수정할 수 있습니다."
              : "환자를 불러오지 않았습니다. 각 그룹 탭에서 값을 직접 입력하면 여기에도 반영됩니다."}
          </p>
        </div>
        <Tag tone={done === specs.length ? "green" : "gray"}>
          계산 완료 {done}/{specs.length}
        </Tag>
      </div>
      <table className="w-full border-t border-gray-100">
        <thead>
          <tr className="bg-gray-50">
            <th className={th}>그룹</th>
            <th className={th}>계산기</th>
            <th className={`${th} text-right`}>결과</th>
            <th className={th}>해석</th>
            <th className={th}></th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) =>
            g.items.map((s, idx) => {
              const r = live[s.id];
              const res = r?.result ?? null;
              const missing = r?.missing ?? [];
              return (
                <tr
                  key={s.id}
                  className="cursor-pointer border-t border-gray-100 hover:bg-indigo-50/40"
                  onClick={() => onJump(s.id)}
                  title="카드로 이동"
                >
                  <td className={`${td} whitespace-nowrap text-xs text-gray-400`}>{idx === 0 ? g.name : ""}</td>
                  <td className={td}>
                    <div className="font-medium text-gray-900">{s.name}</div>
                    <div className="text-[11px] text-gray-400">{s.description}</div>
                  </td>
                  <td className={`${td} whitespace-nowrap text-right font-mono`}>
                    {res ? (
                      <>
                        <span className="text-base font-semibold text-gray-900">{fmtNum(res.value, 1)}</span>
                        {res.unit && <span className="ml-1 text-xs text-gray-500">{res.unit}</span>}
                      </>
                    ) : (
                      <span className="text-gray-300">-</span>
                    )}
                  </td>
                  <td className={td}>
                    {res ? (
                      <Tag tone={SEVERITY_TONE[res.severity]}>{res.label}</Tag>
                    ) : (
                      <span className="text-xs text-amber-700">
                        입력 필요
                        {missing.length > 0 && (
                          <span className="ml-1 text-gray-500">
                            {missing.map((k) => s.inputs.find((i) => i.key === k)?.label ?? k).join(", ")}
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className={`${td} whitespace-nowrap text-right text-xs text-indigo-600`}>열기 ›</td>
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </section>
  );
}
