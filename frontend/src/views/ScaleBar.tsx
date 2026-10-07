import type { Scale, Severity } from "../api";
import { fmtNum } from "../format";

const SEG: Record<Severity, { base: string; active: string }> = {
  ok: { base: "bg-emerald-100", active: "bg-emerald-400" },
  info: { base: "bg-sky-100", active: "bg-sky-400" },
  warn: { base: "bg-amber-100", active: "bg-amber-400" },
  danger: { base: "bg-red-100", active: "bg-red-400" },
};

/**
 * 결과 구간 막대 — min~max 를 bands 로 나눠 그리고 현재 값 위치를 표시한다.
 * 구간 경계·눈금·화살표가 모두 같은 비례 좌표(백분율)를 쓴다 — 눈금을 균등 배치하면 화살표와 어긋나 보인다.
 */
export default function ScaleBar({ scale, value, unit }: { scale: Scale; value: number | null; unit: string | null }) {
  const span = scale.max - scale.min;
  const pct = (v: number) => ((Math.min(Math.max(v, scale.min), scale.max) - scale.min) / span) * 100;

  let prev = scale.min;
  const segs = scale.bands.map((b) => {
    const to = b.upto === null ? scale.max : Math.min(b.upto, scale.max);
    const s = { from: prev, to, left: pct(prev), width: pct(to) - pct(prev), band: b };
    prev = to;
    return s;
  });
  const activeIdx = value === null ? -1 : segs.findIndex((s, i) => value < s.to || i === segs.length - 1);
  const pos = value === null ? null : pct(value);
  const outOfRange = value !== null && (value < scale.min || value > scale.max);

  // 눈금: 양 끝 + 구간 경계. 끝 눈금은 바깥으로 넘치지 않게 정렬을 바꾼다.
  const ticks = [
    { v: scale.min, left: 0, align: "left" as const, text: fmtNum(scale.min, 1) },
    ...segs.slice(0, -1).map((s) => ({ v: s.to, left: pct(s.to), align: "center" as const, text: fmtNum(s.to, 1) })),
    { v: scale.max, left: 100, align: "right" as const, text: `${fmtNum(scale.max, 1)}+` },
  ];

  return (
    <div className="mt-3">
      {/* 화살표 + 값 — 꼭짓점이 정확히 pos 에 오도록 마커 자체를 가운데 정렬 */}
      <div className="relative h-5">
        {pos !== null && (
          <div className="absolute bottom-0 flex -translate-x-1/2 flex-col items-center" style={{ left: `${pos}%` }}>
            <span className="whitespace-nowrap text-[11px] font-semibold leading-none text-gray-800">
              {fmtNum(value, 1)}
              {unit ? ` ${unit}` : ""}
              {outOfRange ? " (범위 밖)" : ""}
            </span>
            <span
              aria-hidden
              className="mt-0.5 block h-0 w-0 border-x-[5px] border-t-[6px] border-x-transparent border-t-gray-800"
            />
          </div>
        )}
      </div>

      {/* 막대 */}
      <div className="relative flex h-3 w-full overflow-hidden rounded">
        {segs.map((s, i) => (
          <div
            key={i}
            className={`${i === activeIdx ? SEG[s.band.severity].active : SEG[s.band.severity].base} border-r border-white last:border-r-0`}
            style={{ width: `${s.width}%` }}
            title={`${s.band.label}: ${fmtNum(s.from, 1)} – ${s.band.upto === null ? "" : fmtNum(s.to, 1)}`}
          />
        ))}
      </div>

      {/* 구간 이름 — 구간 너비에 맞춰 */}
      <div className="mt-1 flex w-full">
        {segs.map((s, i) => (
          <div
            key={i}
            className={`truncate text-center text-[10px] leading-tight ${i === activeIdx ? "font-semibold text-gray-800" : "text-gray-400"}`}
            style={{ width: `${s.width}%` }}
            title={s.band.label}
          >
            {s.width >= 10 ? s.band.label : ""}
          </div>
        ))}
      </div>

      {/* 눈금 — 구간 경계 위치에 정확히 */}
      <div className="relative mt-0.5 h-3.5">
        {ticks.map((t, i) => (
          <span
            key={i}
            className={`absolute top-0 text-[10px] text-gray-400 ${
              t.align === "left" ? "" : t.align === "right" ? "-translate-x-full" : "-translate-x-1/2"
            }`}
            style={{ left: `${t.left}%` }}
          >
            {t.text}
          </span>
        ))}
      </div>
      {scale.note && <p className="mt-1 text-[11px] text-gray-500">{scale.note}</p>}
    </div>
  );
}
