import { useMemo, useState } from "react";
import type { CalculatorSpec, Result } from "../api";
import { copyText, summaryText, type CopyContext } from "../copy";
import { splitByFavorites } from "../favorites";
import { fmtNum } from "../format";
import { SEVERITY_TONE, Tag, btn, input, td, th } from "../ui";

export interface LiveResult {
  result: Result | null;
  missing: string[];
}

type Group = { name: string; items: CalculatorSpec[] };
type Row = { spec: CalculatorSpec; group: string };

/**
 * 요약 탭 - 「내 계산기」(별표) 를 위에, 「그 외」는 접어 둔다. 접힌 쪽에 위험 결과가 있으면 배너로 끌어올린다.
 * 검색어가 있으면 두 층을 무시하고 이름이 맞는 행만 보인다. 행을 누르면 해당 그룹 탭의 카드로 이동.
 */
export default function SummaryTable({
  specs,
  groups,
  live,
  hasPatient,
  onJump,
  copyContext = null,
  favorites,
  onToggleFavorite,
}: {
  specs: CalculatorSpec[];
  groups: Group[];
  live: Record<string, LiveResult>;
  hasPatient: boolean;
  onJump: (calcId: string) => void;
  copyContext?: CopyContext | null;
  favorites: string[];
  onToggleFavorite: (id: string) => void;
}) {
  const done = specs.filter((s) => live[s.id]?.result).length;
  const [copied, setCopied] = useState<"ok" | "fail" | null>(null);
  const [query, setQuery] = useState("");
  const [othersOpen, setOthersOpen] = useState(false);

  const ordered: Row[] = useMemo(() => groups.flatMap((g) => g.items.map((s) => ({ spec: s, group: g.name }))), [groups]);
  const q = query.trim().toLowerCase();
  const searched = q ? ordered.filter(({ spec }) => `${spec.name} ${spec.description} ${spec.id}`.toLowerCase().includes(q)) : null;
  const { mine, others } = useMemo(
    () => splitByFavorites(ordered.map((o) => ({ id: o.spec.id, ...o })), favorites),
    [ordered, favorites],
  );
  const hiddenDanger = others.filter((o) => live[o.spec.id]?.result?.severity === "danger");

  async function copyAll() {
    const items = ordered.flatMap(({ spec }) => (live[spec.id]?.result ? [{ spec, result: live[spec.id]!.result! }] : []));
    const ok = await copyText(summaryText(items, copyContext));
    setCopied(ok ? "ok" : "fail");
    window.setTimeout(() => setCopied(null), 1500);
  }

  function renderRow({ spec, group }: Row) {
    const r = live[spec.id];
    const res = r?.result ?? null;
    const missing = r?.missing ?? [];
    const fav = favorites.includes(spec.id);
    return (
      <tr key={spec.id} className="cursor-pointer border-t border-gray-100 hover:bg-indigo-50/40" onClick={() => onJump(spec.id)} title="카드로 이동">
        <td className={`${td} w-8 pr-0`}>
          <button
            type="button"
            className={`text-lg leading-none ${fav ? "text-amber-500" : "text-gray-300 hover:text-amber-400"}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(spec.id);
            }}
            aria-label={fav ? "내 계산기에서 빼기" : "내 계산기에 추가"}
            aria-pressed={fav}
          >
            {fav ? "★" : "☆"}
          </button>
        </td>
        <td className={td}>
          <div className="font-medium text-gray-900">{spec.name}</div>
          <div className="text-[11px] text-gray-400">{group}</div>
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
                <span className="ml-1 text-gray-500">{missing.map((k) => spec.inputs.find((i) => i.key === k)?.label ?? k).join(", ")}</span>
              )}
            </span>
          )}
        </td>
        <td className={`${td} hidden whitespace-nowrap text-right text-xs text-indigo-600 sm:table-cell`}>열기 ›</td>
      </tr>
    );
  }

  function renderTable(rows: Row[]) {
    return (
      <table className="w-full table-fixed sm:table-auto">
        <thead>
          <tr className="bg-gray-50">
            <th className={`${th} w-8`}></th>
            <th className={th}>계산기</th>
            <th className={`${th} text-right`}>결과</th>
            <th className={th}>해석</th>
            <th className={`${th} hidden sm:table-cell`}></th>
          </tr>
        </thead>
        <tbody>{rows.map(renderRow)}</tbody>
      </table>
    );
  }

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
        <div className="flex items-center gap-2">
          <Tag tone={done === specs.length ? "green" : "gray"}>
            계산 완료 {done}/{specs.length}
          </Tag>
          <button type="button" className={btn.secondary} onClick={copyAll} disabled={done === 0} title="계산된 결과를 한 줄씩 텍스트로 복사">
            {copied === "ok" ? "복사됨 ✓" : copied === "fail" ? "복사 실패" : "전체 복사"}
          </button>
        </div>
      </div>

      <div className="border-t border-gray-100 px-4 py-2">
        <input
          className={`${input} max-w-xs`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="계산기 검색 (예: MELD, 폐렴)"
          aria-label="계산기 검색"
        />
      </div>

      {hiddenDanger.length > 0 && !searched && (
        <div className="border-t border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800">
          <span className="font-semibold">접힌 계산기에 위험 결과가 있습니다: </span>
          {hiddenDanger.map((o, i) => (
            <span key={o.spec.id}>
              {i > 0 && " · "}
              <button type="button" className="underline hover:text-red-900" onClick={() => onJump(o.spec.id)}>
                {o.spec.name} {fmtNum(live[o.spec.id]!.result!.value, 1)}
                {live[o.spec.id]!.result!.unit ?? ""}
              </button>
            </span>
          ))}
        </div>
      )}

      {searched ? (
        searched.length ? (
          renderTable(searched)
        ) : (
          <p className="border-t border-gray-100 px-4 py-3 text-xs text-gray-400">「{query}」에 맞는 계산기가 없습니다.</p>
        )
      ) : (
        <>
          <div className="border-t border-gray-100 px-4 pt-2 text-[11px] text-gray-500">
            {favorites.length ? `내 계산기 ${mine.length}개 (별표)` : "별표(☆)로 자주 쓰는 계산기를 위에 고정할 수 있습니다"}
          </div>
          {renderTable(mine)}
          {others.length > 0 && (
            <div className="border-t border-gray-100">
              <button
                type="button"
                className="flex w-full items-center justify-between px-4 py-2 text-left text-xs text-gray-600 hover:bg-gray-50"
                onClick={() => setOthersOpen((v) => !v)}
                aria-expanded={othersOpen}
              >
                <span>그 외 {others.length}개</span>
                <span>{othersOpen ? "▴" : "▾"}</span>
              </button>
              {othersOpen && renderTable(others)}
            </div>
          )}
        </>
      )}
    </section>
  );
}
