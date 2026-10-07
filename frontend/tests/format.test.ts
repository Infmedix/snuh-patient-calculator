import { describe, expect, it } from "vitest";
import { daysAgo, fmtDate, fmtDateTime, fmtNum } from "../src/format";

describe("fmtNum", () => {
  it("소수 자릿수를 맞추고 불필요한 0 을 뗀다", () => {
    expect(fmtNum(22.94)).toBe("22.9");
    expect(fmtNum(5)).toBe("5");
    expect(fmtNum(0.4, 2)).toBe("0.4");
    expect(fmtNum(null)).toBe("-");
  });
});

describe("fmtDateTime / fmtDate", () => {
  it("naive ISO 를 그대로 로컬로 해석한다", () => {
    expect(fmtDateTime("2026-10-05T08:30:00")).toBe("2026-10-05 08:30");
    expect(fmtDate("2026-10-05T08:30:00")).toBe("2026-10-05");
    expect(fmtDate("2026-09-20")).toBe("2026-09-20");
    expect(fmtDate(null)).toBe("-");
  });
});

describe("daysAgo", () => {
  const now = new Date("2026-10-07T09:00:00");
  it("오늘·일·개월·년 단위로 말한다", () => {
    expect(daysAgo("2026-10-07T08:59:30", now)).toBe("30초 전");
    expect(daysAgo("2026-10-07T08:48:00", now)).toBe("12분 전");
    expect(daysAgo("2026-10-07T06:00:00", now)).toBe("3시간 전");
    expect(daysAgo("2026-10-06T10:00:00", now)).toBe("23시간 전");
    expect(daysAgo("2026-10-07", now)).toBe("오늘");
    expect(daysAgo("2026-10-02T06:00:00", now)).toBe("5일 전");
    expect(daysAgo("2026-07-08T06:00:00", now)).toBe("3개월 전");
    expect(daysAgo("2024-05-30", now)).toBe("2년 전");
    expect(daysAgo(null, now)).toBe("");
  });
});
