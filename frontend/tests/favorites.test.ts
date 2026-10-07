import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getFavorites, setFavorites, sortFavoritesFirst, toggleFavorite } from "../src/favorites";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
  setFavorites([]);
});
afterEach(() => vi.unstubAllGlobals());

describe("favorites", () => {
  it("토글이 localStorage 에 반영된다", () => {
    expect(getFavorites()).toEqual([]);
    toggleFavorite("sofa");
    toggleFavorite("egfr");
    expect(getFavorites()).toEqual(["sofa", "egfr"]);
    expect(JSON.parse(localStorage.getItem("snuhcalc.favorites")!)).toEqual(["sofa", "egfr"]);
    toggleFavorite("sofa");
    expect(getFavorites()).toEqual(["egfr"]);
  });

  it("그룹 안에서는 별표가 먼저, 원래 순서 유지", () => {
    const items = [{ id: "a" }, { id: "b" }, { id: "c" }];
    expect(sortFavoritesFirst(items, ["c", "a"]).map((i) => i.id)).toEqual(["a", "c", "b"]);
  });
});
