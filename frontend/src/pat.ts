/**
 * PAT 보관 어댑터 - snuh-fhir 프런트의 pat.ts 와 같은 규칙. **메모리 + sessionStorage 만**.
 *
 * localStorage 금지(영구 저장소), 서버 저장 없음, URL·로그에 싣지 않음. 탭을 닫으면 소멸한다.
 * sessionStorage 접근은 전부 try/catch - 사생활 보호 모드·차단 설정에서는 메모리만으로 동작한다.
 */

const KEY = "snuhcalc.pat";

let memory: string | null = null;

function storage(): Storage | null {
  try {
    return typeof sessionStorage !== "undefined" ? sessionStorage : null;
  } catch {
    return null;
  }
}

export function getPat(): string | null {
  if (memory !== null) return memory;
  try {
    const v = storage()?.getItem(KEY) ?? null;
    memory = v && v.trim() ? v : null;
  } catch {
    memory = null;
  }
  return memory;
}

export function setPat(value: string): void {
  const v = value.trim();
  memory = v || null;
  try {
    if (memory) storage()?.setItem(KEY, memory);
    else storage()?.removeItem(KEY);
  } catch {
    /* 메모리만 */
  }
}

export function clearPat(): void {
  memory = null;
  try {
    storage()?.removeItem(KEY);
  } catch {
    /* 메모리만 */
  }
}

/** 화면 표시용 마스킹 - `snuhfhir_<id8>_••••` (id 조각은 비밀이 아니다). */
export function maskPat(token: string): string {
  const m = /^(snuhfhir_[0-9a-f]{8})_/.exec(token);
  return m ? `${m[1]}_••••••••` : `${token.slice(0, 4)}••••••••`;
}

/** 형식 사전 검사 - 서버가 최종 판정하지만 오타는 미리 잡는다. */
export function looksLikePat(token: string): boolean {
  return /^snuhfhir_[0-9a-f]{8}_[A-Za-z0-9_-]{16,}$/.test(token.trim());
}
