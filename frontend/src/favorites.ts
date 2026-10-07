/**
 * 즐겨찾기(별표) 계산기 - 브라우저 localStorage 에 id 목록만 둔다 (개인정보 없음, 기기별 설정).
 * 저장소 접근은 전부 try/catch - 차단된 환경에서는 메모리만으로 동작한다.
 */

const KEY = "snuhcalc.favorites";

let memory: string[] | null = null;

function storage(): Storage | null {
  try {
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch {
    return null;
  }
}

export function getFavorites(): string[] {
  if (memory !== null) return memory;
  try {
    const raw = storage()?.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    memory = Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    memory = [];
  }
  return memory;
}

export function setFavorites(ids: string[]): string[] {
  memory = [...new Set(ids)];
  try {
    storage()?.setItem(KEY, JSON.stringify(memory));
  } catch {
    /* 메모리만 */
  }
  return memory;
}

export function toggleFavorite(id: string): string[] {
  const cur = getFavorites();
  return setFavorites(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
}

/** 그룹 탭 안 정렬 - 별표가 먼저, 그 안에서는 원래 순서 유지. */
export function sortFavoritesFirst<T extends { id: string }>(items: T[], favorites: string[]): T[] {
  const set = new Set(favorites);
  return [...items.filter((i) => set.has(i.id)), ...items.filter((i) => !set.has(i.id))];
}
