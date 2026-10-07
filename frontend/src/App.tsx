import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  errorMessage,
  fetchCalculators,
  fetchOverview,
  fetchReadiness,
  type CalculatorOverview,
  type CalculatorsResponse,
  type Overview,
  type Result,
} from "./api";
import { ErrorBox, Tag, btn, input } from "./ui";
import CalculatorCard from "./views/CalculatorCard";
import PatientPanel from "./views/PatientPanel";
import SummaryTable, { type LiveResult } from "./views/SummaryTable";

/** 그룹 표시 순서 — 백엔드 레지스트리 순서와 같다. 서버가 새 그룹을 보내면 뒤에 붙는다. */
const GROUP_ORDER = ["신체·신장", "심혈관", "간", "중증도", "영양"];
const SUMMARY_TAB = "요약";

export default function App() {
  const [specs, setSpecs] = useState<CalculatorsResponse | null>(null);
  const [specsErr, setSpecsErr] = useState("");
  const [fhirMode, setFhirMode] = useState<string>("");

  const [draft, setDraft] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  // 카드 초기화 키 — 새 환자를 불러오면 카드 폼을 prefill 로 다시 만든다
  const [epoch, setEpoch] = useState(0);
  const [tab, setTab] = useState<string>(SUMMARY_TAB);
  // 카드가 보고하는 현재 결과 (사용자 수정 반영) — 요약 표·탭 배지가 쓴다
  const [live, setLive] = useState<Record<string, LiveResult>>({});
  // 요약 표 → 카드 이동 요청 (카드 id 별 증가 카운터 — 같은 카드를 다시 눌러도 열리게)
  const [focus, setFocus] = useState<Record<string, number>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  const loadSpecs = useCallback(() => {
    setSpecsErr("");
    fetchCalculators()
      .then(setSpecs)
      .catch((e) => setSpecsErr(errorMessage(e)));
    fetchReadiness()
      .then((r) => setFhirMode(r.fhir ?? ""))
      .catch(() => setFhirMode(""));
  }, []);
  useEffect(loadSpecs, [loadSpecs]);

  const loadPatient = useCallback(async (pid: string) => {
    const id = pid.trim();
    if (!id) return;
    setLoading(true);
    setLoadErr("");
    try {
      const ov = await fetchOverview(id);
      setOverview(ov);
      setLive({});
      setFocus({});
      setEpoch((n) => n + 1);
      setTab(SUMMARY_TAB);
      window.location.hash = `#/p/${encodeURIComponent(id)}`;
    } catch (e) {
      setLoadErr(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // `#/p/{환자번호}` 딥링크 — 새로고침·공유 시 같은 환자를 다시 불러온다
  useEffect(() => {
    const m = /^#\/p\/(.+)$/.exec(window.location.hash);
    if (m) {
      const id = decodeURIComponent(m[1]);
      setDraft(id);
      void loadPatient(id);
    }
  }, [loadPatient]);

  function submit(e: FormEvent) {
    e.preventDefault();
    void loadPatient(draft);
  }

  function clearPatient() {
    setOverview(null);
    setDraft("");
    setLoadErr("");
    setLive({});
    setEpoch((n) => n + 1);
    window.location.hash = "";
    inputRef.current?.focus();
  }

  const onResult = useCallback((id: string, result: Result | null, missing: string[]) => {
    setLive((cur) => {
      const prev = cur[id];
      if (prev && prev.result === result && prev.missing.join() === missing.join()) return cur;
      return { ...cur, [id]: { result, missing } };
    });
  }, []);

  const byId = useMemo(() => {
    const m = new Map<string, CalculatorOverview>();
    overview?.calculators.forEach((c) => m.set(c.id, c));
    return m;
  }, [overview]);

  const groups = useMemo(() => {
    if (!specs) return [];
    const names = [...GROUP_ORDER, ...specs.items.map((s) => s.group).filter((g) => !GROUP_ORDER.includes(g))];
    return [...new Set(names)]
      .map((g) => ({ name: g, items: specs.items.filter((s) => s.group === g) }))
      .filter((g) => g.items.length);
  }, [specs]);

  /** 그룹별 계산 완료 수 — 탭 배지 */
  const groupDone = useMemo(() => {
    const m: Record<string, { done: number; total: number }> = {};
    for (const g of groups) {
      m[g.name] = { done: g.items.filter((s) => live[s.id]?.result).length, total: g.items.length };
    }
    return m;
  }, [groups, live]);

  useEffect(() => {
    document.title = overview ? `${overview.snapshot.patient.id} — 환자 계산기` : "환자 계산기 — SNUH";
  }, [overview]);

  function jumpTo(calcId: string) {
    const spec = specs?.items.find((s) => s.id === calcId);
    if (!spec) return;
    setTab(spec.group);
    setFocus((f) => ({ ...f, [calcId]: (f[calcId] ?? 0) + 1 }));
    // 탭이 그려진 뒤 카드로 스크롤
    window.setTimeout(() => document.getElementById(`calc-${calcId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  const tabCls = (active: boolean) =>
    `rounded px-3 py-1.5 text-sm whitespace-nowrap ${active ? "bg-indigo-50 font-medium text-indigo-700" : "text-gray-600 hover:bg-gray-100"}`;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div>
            <span className="text-sm font-semibold text-gray-900">SNUH 환자 계산기</span>
            <span className="ml-2 text-xs text-gray-400">환자 정보 기반 임상 점수 · 수치</span>
          </div>
          <form onSubmit={submit} className="flex flex-1 flex-wrap items-center gap-2 sm:min-w-[360px]">
            <input
              ref={inputRef}
              className={`${input} max-w-[240px] font-mono`}
              placeholder="환자번호"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
              spellCheck={false}
              aria-label="환자번호"
            />
            <button type="submit" className={btn.primary} disabled={loading || !draft.trim()}>
              {loading ? "불러오는 중…" : "불러오기"}
            </button>
            {overview && (
              <button type="button" className={btn.secondary} onClick={clearPatient}>
                환자 해제
              </button>
            )}
          </form>
          <div className="ml-auto flex items-center gap-2 text-xs text-gray-500">
            {fhirMode === "mock" && (
              <Tag tone="amber" title="APP_FHIR_MODE=mock — fixture 데이터">
                mock 데이터
              </Tag>
            )}
            {fhirMode === "error" && <Tag tone="red">FHIR 연결 불가</Tag>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5">
        {specsErr && (
          <div className="mb-4">
            <ErrorBox message={`계산기 목록을 불러올 수 없습니다 — ${specsErr}`} />
            <button type="button" className={`${btn.ghost} mt-1`} onClick={loadSpecs}>
              다시 시도
            </button>
          </div>
        )}
        {loadErr && (
          <div className="mb-4">
            <ErrorBox message={loadErr} onClose={() => setLoadErr("")} />
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="lg:sticky lg:top-[64px] lg:self-start">
            <PatientPanel overview={overview} variables={specs?.variables ?? {}} loading={loading} />
          </aside>

          <section>
            {!specs && !specsErr && <p className="text-sm text-gray-500">계산기 목록 불러오는 중…</p>}
            {specs && (
              <>
                <nav className="mb-4 flex gap-1 overflow-x-auto border-b border-gray-200 pb-2" aria-label="계산기 그룹">
                  <button type="button" className={tabCls(tab === SUMMARY_TAB)} onClick={() => setTab(SUMMARY_TAB)}>
                    요약
                  </button>
                  {groups.map((g) => {
                    const d = groupDone[g.name];
                    return (
                      <button key={g.name} type="button" className={tabCls(tab === g.name)} onClick={() => setTab(g.name)}>
                        {g.name}
                        <span className={`ml-1.5 text-[11px] ${d.done === d.total ? "text-emerald-600" : "text-gray-400"}`}>
                          {d.done}/{d.total}
                        </span>
                      </button>
                    );
                  })}
                </nav>

                <div hidden={tab !== SUMMARY_TAB}>
                  <SummaryTable specs={specs.items} groups={groups} live={live} hasPatient={!!overview} onJump={jumpTo} />
                </div>

                {groups.map((g) => (
                  <div key={g.name} hidden={tab !== g.name}>
                    <div className="space-y-4">
                      {g.items.map((spec) => (
                        <CalculatorCard
                          key={`${spec.id}:${epoch}`}
                          spec={spec}
                          overview={byId.get(spec.id)}
                          flagLabels={overview?.flag_labels ?? specs.flags}
                          onResult={onResult}
                          focusSeq={focus[spec.id] ?? 0}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </>
            )}
            <p className="pt-4 text-xs text-gray-400">
              임상 판단 보조용 도구입니다. 자동으로 채워진 값은 가장 최근 기록 1건이며, 출처와 기록 시점을 반드시 확인하세요.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
