import { useState, type FormEvent } from "react";
import { looksLikePat, maskPat } from "../pat";
import { Tag, btn, input } from "../ui";

/**
 * PAT 등록 패널 - snuh-fhir 「API 테스터」의 PAT 패널과 같은 규칙.
 * 토큰은 이 탭의 메모리·sessionStorage 에만 머물고 요청 헤더(X-Fhir-Token)로만 나간다.
 */
export default function PatPanel({
  pat,
  onRegister,
  onRelease,
  fhirUiUrl,
  notice,
}: {
  pat: string | null;
  onRegister: (token: string) => void;
  onRelease: () => void;
  /** snuh-fhir 「내 토큰」 화면 주소 (알 수 없으면 null) */
  fhirUiUrl: string | null;
  /** 서버가 돌려준 PAT 관련 안내 (pat_missing·pat_invalid·pat_no_access) */
  notice: string;
}) {
  const [draft, setDraft] = useState("");
  const [warn, setWarn] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const v = draft.trim();
    if (!v) return;
    onRegister(v);
    setWarn(looksLikePat(v) ? "" : "형식이 `snuhfhir_<id8>_<secret>` 와 다릅니다 - 그래도 등록했습니다. 조회가 거부되면 값을 확인하세요.");
    setDraft("");
  }

  return (
    <section className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-4">
      <div className="mb-1 flex items-center gap-2">
        <h2 className="text-sm font-semibold text-gray-900">FHIR 개인 액세스 토큰 (PAT)</h2>
        {pat ? <Tag tone="green">등록됨</Tag> : <Tag tone="amber">미등록</Tag>}
      </div>
      <p className="mb-3 text-xs leading-relaxed text-gray-600">
        환자 기록은 snuh-fhir 에서 가져오며, 호출에는 <b>본인 PAT</b> 가 필요합니다. 토큰은{" "}
        {fhirUiUrl ? (
          <a className="text-indigo-700 underline" href={fhirUiUrl} target="_blank" rel="noreferrer">
            snuh-fhir 「내 토큰」
          </a>
        ) : (
          <>snuh-fhir 「내 토큰」</>
        )}{" "}
        에서 발급받고, 관리자가 본인에게 <b>FHIR 접근 허용</b>을 부여해야 조회가 됩니다. 토큰은 이 탭의 메모리와 sessionStorage 에만
        보관되며(서버·localStorage 저장 없음) 탭을 닫으면 사라집니다.
      </p>
      {notice && <p className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">{notice}</p>}
      {pat ? (
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded border border-gray-200 bg-white px-2.5 py-1.5 font-mono text-sm text-gray-800">{maskPat(pat)}</code>
          <button type="button" className={btn.secondary} onClick={onRelease}>
            해제
          </button>
          <span className="text-xs text-gray-500">다른 토큰으로 바꾸려면 해제 후 다시 등록하세요.</span>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <label className="block min-w-[280px] flex-1 text-xs text-gray-600">
            토큰
            <input
              className={`${input} mt-1 font-mono`}
              type="password"
              autoComplete="new-password"
              spellCheck={false}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="snuhfhir_xxxxxxxx_…"
            />
          </label>
          <button type="submit" className={btn.primary} disabled={!draft.trim()}>
            등록
          </button>
        </form>
      )}
      {warn && <p className="mt-2 text-xs text-amber-700">{warn}</p>}
    </section>
  );
}
