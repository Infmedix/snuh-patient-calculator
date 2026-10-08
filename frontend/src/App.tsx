import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  errorMessage,
  fetchCalculators,
  fetchOverview,
  fetchReadiness,
  fhirTokenPageUrl,
  type CalculatorOverview,
  type CalculatorsResponse,
  type Overview,
  type Result,
} from "./api";
import { getFavorites, sortFavoritesFirst, toggleFavorite } from "./favorites";
import { clearPat, getPat, maskPat, setPat } from "./pat";
import { ErrorBox, Tag, btn, input } from "./ui";
import CalculatorCard from "./views/CalculatorCard";
import PatPanel from "./views/PatPanel";
import PatientPanel from "./views/PatientPanel";
import SummaryTable, { type LiveResult } from "./views/SummaryTable";

/** 그룹 표시 순서 - 백엔드 레지스트리 순서와 같다. 서버가 새 그룹을 보내면 뒤에 붙는다. */
const GROUP_ORDER = ["신체·신장", "심혈관", "간", "조기경고", "중증도", "동반질환", "영양"];
const SUMMARY_TAB = "요약";

export default function App() {
  const [specs, setSpecs] = useState<CalculatorsResponse | null>(null);
  const [specsErr, setSpecsErr] = useState("");
  const [fhirMode, setFhirMode] = useState<string>("");
  // 서버에 서비스 계정 PAT 가 있으면(관리자가 발급한 토큰 하나를 공유) 사용자는 PAT 를 등록하지 않아도 된다.
  const [serviceToken, setServiceToken] = useState(false);

  const [draft, setDraft] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  // 카드 초기화 키 - 새 환자를 불러오면 카드 폼을 prefill 로 다시 만든다
  const [epoch, setEpoch] = useState(0);
  const [tab, setTab] = useState<string>(SUMMARY_TAB);
  // 카드가 보고하는 현재 결과 (사용자 수정 반영) - 요약 표·탭 배지가 쓴다
  const [live, setLive] = useState<Record<string, LiveResult>>({});
  // 요약 표 → 카드 이동 요청 (카드 id 별 증가 카운터 - 같은 카드를 다시 눌러도 열리게)
  const [focus, setFocus] = useState<Record<string, number>>({});
  const [favorites, setFavoritesState] = useState<string[]>(() => getFavorites());
  // 딥링크 `#/p/{환자}/{계산기}` - 환자 로드가 끝난 뒤 그 카드로 이동
  const pendingCalc = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // 경과 시간 표시("12분 전")가 화면에서 흘러가도록 30초마다 다시 그린다
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);
  // PAT (B 방식: 사용자 본인 토큰). mock 모드에서는 필요 없다.
  const [pat, setPatState] = useState<string | null>(() => getPat());
  const [patOpen, setPatOpen] = useState(false);
  const [patNotice, setPatNotice] = useState("");
  // PAT 패널은 서버에 서비스 토큰이 없는 http 배포에서만 의미가 있다
  const patRelevant = fhirMode !== "mock" && !serviceToken;
  const needsPat = patRelevant && !pat;

  const loadSpecs = useCallback(() => {
    setSpecsErr("");
    fetchCalculators()
      .then(setSpecs)
      .catch((e) => setSpecsErr(errorMessage(e)));
    fetchReadiness()
      .then((r) => {
        setFhirMode(r.fhir ?? "");
        setServiceToken(r.token === "service");
      })
      .catch(() => setFhirMode(""));
  }, []);
  useEffect(loadSpecs, [loadSpecs]);

  const loadPatient = useCallback(async (pid: string) => {
    const id = pid.trim();
    if (!id) return;
    setLoading(true);
    setLoadErr("");
    try {
      const ov = await fetchOverview(id, getPat());
      setPatNotice("");
      setOverview(ov);
      setLive({});
      setFocus({});
      setEpoch((n) => n + 1);
      setTab(SUMMARY_TAB);
      window.location.hash = `#/p/${encodeURIComponent(id)}`;
      if (pendingCalc.current) {
        const target = pendingCalc.current;
        pendingCalc.current = null;
        window.setTimeout(() => jumpToRef.current?.(target), 0);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code?.startsWith("pat_")) {
        // 토큰 문제는 일반 오류 상자 대신 PAT 패널에서 안내한다
        setPatNotice(e.detail);
        setPatOpen(true);
        if (e.code === "pat_invalid") {
          clearPat();
          setPatState(null);
        }
      } else {
        setLoadErr(errorMessage(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // `#/p/{환자번호}` 딥링크 - 새로고침·공유 시 같은 환자를 다시 불러온다
  useEffect(() => {
    const m = /^#\/p\/([^/]+)(?:\/([^/]+))?$/.exec(window.location.hash);
    if (m) {
      const id = decodeURIComponent(m[1]);
      if (m[2]) pendingCalc.current = decodeURIComponent(m[2]);
      setDraft(id);
      void loadPatient(id);
    } else {
      // 환자 없이 계산기 하나만: `#/c/{계산기}`
      const c = /^#\/c\/([^/]+)$/.exec(window.location.hash);
      if (c) pendingCalc.current = decodeURIComponent(c[1]);
    }
  }, [loadPatient]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (needsPat) {
      setPatNotice("환자를 조회하려면 먼저 PAT 를 등록하세요.");
      setPatOpen(true);
      return;
    }
    void loadPatient(draft);
  }

  function registerPat(token: string) {
    setPat(token);
    setPatState(getPat());
    setPatNotice("");
  }

  function releasePat() {
    clearPat();
    setPatState(null);
    setPatNotice("");
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

  /** 그룹별 계산 완료 수 - 탭 배지 */
  const groupDone = useMemo(() => {
    const m: Record<string, { done: number; total: number }> = {};
    for (const g of groups) {
      m[g.name] = { done: g.items.filter((s) => live[s.id]?.result).length, total: g.items.length };
    }
    return m;
  }, [groups, live]);

  useEffect(() => {
    document.title = overview ? `${overview.snapshot.patient.id} - 환자 계산기` : "환자 계산기 - SNUH";
  }, [overview]);

  const jumpToRef = useRef<(calcId: string) => void>(() => {});
  function jumpTo(calcId: string) {
    const spec = specs?.items.find((s) => s.id === calcId);
    if (!spec) return;
    setTab(spec.group);
    setFocus((f) => ({ ...f, [calcId]: (f[calcId] ?? 0) + 1 }));
    // 딥링크 유지: 환자가 있으면 #/p/{환자}/{계산기}, 없으면 #/c/{계산기}
    const pid = overview?.snapshot.patient.id;
    window.history.replaceState(null, "", pid ? `#/p/${encodeURIComponent(pid)}/${calcId}` : `#/c/${calcId}`);
    // 탭이 그려진 뒤 카드로 스크롤
    window.setTimeout(() => document.getElementById(`calc-${calcId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }
  jumpToRef.current = jumpTo;

  // 환자 없이 `#/c/{계산기}` 로 들어온 경우 - 스펙이 도착하면 이동
  useEffect(() => {
    if (specs && !overview && pendingCalc.current) {
      const target = pendingCalc.current;
      pendingCalc.current = null;
      window.setTimeout(() => jumpTo(target), 0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specs]);

  function onToggleFavorite(id: string) {
    setFavoritesState(toggleFavorite(id));
  }

  const tabCls = (active: boolean) =>
    `rounded px-3 py-1.5 text-sm whitespace-nowrap ${active ? "bg-indigo-50 font-medium text-indigo-700" : "text-gray-600 hover:bg-gray-100"}`;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:py-3">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold text-gray-900">SNUH 환자 계산기</span>
            <span className="hidden text-xs text-gray-400 sm:inline">환자 정보 기반 임상 점수 · 수치</span>
          </div>
          <form onSubmit={submit} className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-1 sm:min-w-[360px]">
            <input
              ref={inputRef}
              className={`${input} min-w-0 flex-1 sm:max-w-[240px] sm:flex-none`}
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
          <div className="flex items-center gap-2 text-xs text-gray-500 sm:ml-auto">
            {patRelevant && (
              <button
                type="button"
                className={`${btn.secondary} flex items-center gap-1.5`}
                onClick={() => setPatOpen((v) => !v)}
                aria-expanded={patOpen}
                title={pat ? maskPat(pat) : "FHIR 개인 액세스 토큰 등록"}
              >
                PAT
                {pat ? <Tag tone="green">등록됨</Tag> : <Tag tone="amber">미등록</Tag>}
              </button>
            )}
            {serviceToken && fhirMode === "ok" && (
              <Tag tone="green" title="서버에 설정된 서비스 계정 PAT 로 FHIR 를 호출합니다">
                FHIR 연결됨
              </Tag>
            )}
            {fhirMode === "mock" && (
              <Tag tone="amber" title="APP_FHIR_MODE=mock - fixture 데이터">
                mock 데이터
              </Tag>
            )}
            {fhirMode === "error" && <Tag tone="red">FHIR 연결 불가</Tag>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5">
        {(patOpen || (needsPat && !overview)) && patRelevant && (
          <div className="mb-4">
            <PatPanel pat={pat} onRegister={registerPat} onRelease={releasePat} fhirUiUrl={fhirTokenPageUrl()} notice={patNotice} />
          </div>
        )}
        {specsErr && (
          <div className="mb-4">
            <ErrorBox message={`계산기 목록을 불러올 수 없습니다 - ${specsErr}`} />
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

        {/* grid-cols 에 minmax(0,…)·min-w-0 — 표·nowrap 셀의 최소 너비가 폰 화면을 넘어 가로 스크롤을 만들지 않게 */}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="min-w-0 lg:sticky lg:top-[64px] lg:self-start">
            <PatientPanel overview={overview} variables={specs?.variables ?? {}} loading={loading} />
          </aside>

          <section className="min-w-0">
            {!specs && !specsErr && <p className="text-sm text-gray-500">계산기 목록 불러오는 중…</p>}
            {specs && (
              <>
                <nav className="scrollbar-hidden mb-4 flex gap-1 overflow-x-auto border-b border-gray-200 pb-2" aria-label="계산기 그룹">
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
                  <SummaryTable
                    specs={specs.items}
                    groups={groups}
                    live={live}
                    hasPatient={!!overview}
                    onJump={jumpTo}
                    copyContext={overview ? { patientId: overview.snapshot.patient.id, fetchedAt: overview.snapshot.fetched_at } : null}
                    favorites={favorites}
                    onToggleFavorite={onToggleFavorite}
                  />
                </div>

                {groups.map((g) => (
                  <div key={g.name} hidden={tab !== g.name}>
                    <div className="space-y-4">
                      {sortFavoritesFirst(g.items, favorites).map((spec) => (
                        <CalculatorCard
                          key={`${spec.id}:${epoch}`}
                          spec={spec}
                          overview={byId.get(spec.id)}
                          flagLabels={overview?.flag_labels ?? specs.flags}
                          onResult={onResult}
                          focusSeq={focus[spec.id] ?? 0}
                          copyContext={overview ? { patientId: overview.snapshot.patient.id, fetchedAt: overview.snapshot.fetched_at } : null}
                          favorite={favorites.includes(spec.id)}
                          onToggleFavorite={() => onToggleFavorite(spec.id)}
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
