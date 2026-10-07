import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearPat, getPat, looksLikePat, maskPat, setPat } from "../src/pat";

const TOKEN = "snuhfhir_1a2b3c4d_abcdefghijklmnopqrstuvwxyz";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("sessionStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
  clearPat();
});

afterEach(() => vi.unstubAllGlobals());

describe("pat", () => {
  it("등록·조회·해제가 sessionStorage 와 메모리에만 반영된다", () => {
    expect(getPat()).toBeNull();
    setPat(`  ${TOKEN}  `);
    expect(getPat()).toBe(TOKEN);
    expect(sessionStorage.getItem("snuhcalc.pat")).toBe(TOKEN);
    clearPat();
    expect(getPat()).toBeNull();
  });

  it("마스킹은 id 조각만 남긴다", () => {
    expect(maskPat(TOKEN)).toBe("snuhfhir_1a2b3c4d_••••••••");
    expect(maskPat("weird")).toBe("weir••••••••");
  });

  it("형식 검사", () => {
    expect(looksLikePat(TOKEN)).toBe(true);
    expect(looksLikePat("snuhfhir_zz_short")).toBe(false);
  });
});
