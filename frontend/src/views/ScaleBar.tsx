import type { Scale, Severity } from "../api";
import { fmtNum } from "../format";

const SEG: Record<Severity, { base: string; active: string }> = {
  ok: { base: "bg-emerald-100", active: "bg-emerald-400" },
  info: { base: "bg-sky-100", active: "bg-sky-400" },
  warn: { base: "bg-amber-100", active: "bg-amber-400" },
  danger: { base: "bg-red-100", active: "bg-red-400" },
};

/** 결과 구간 막대 — min~max 를 bands 로 나눠 그리고 현재 값 위치를 표시한다. */
export default function ScaleBar({ scale, value, unit }: { scale: Scale; value: number | null; unit: string | null }) {
  const span = scale.max - scale.min;
  let prev = scale.min;
  const segs = scale.bands.map((b) => {
    const upto = b.upto === null ? scale.max : Math.min(b.upto, scale.max);
    const s = { from: prev, to: upto, width: Math.max(0, (upto - prev) / span) * 100, band: b };
    prev = upto;
    return s;
  });
  const clamped = value === null ? null : Math.min(Math.max(value, scale.min), scale.max);
  const pos = clamped === null ? null : ((clamped - scale.min) / span) * 100;
  const activeIdx = value === null ? -1 : segs.findIndex((s, i) => value < s.to || i === segs.length - 1);

  return (
    <div className="mt-3">
      <div className="relative pt-4">
        {pos !== null && (
          <div className="absolute top-0 -translate-x-1/2 text-[11px] font-semibold text-gray-800" style={{ left: `${pos}%` }}>
            ▼ {fmtNum(value, 1)}
            {unit ? ` ${unit}` : ""}
          </div>
        )}
        <div className="flex h-3 w-full overflow-hidden rounded">
          {segs.map((s, i) => (
            <div
              key={i}
              className={`${i === activeIdx ? SEG[s.band.severity].active : SEG[s.band.severity].base} border-r border-white last:border-r-0`}
              style={{ width: `${s.width}%` }}
              title={`${s.band.label}: ${fmtNum(s.from, 1)}–${s.band.upto === null ? "" : fmtNum(s.to, 1)}`}
            />
          ))}
        </div>
        <div className="mt-1 flex w-full">
          {segs.map((s, i) => (
            <div
              key={i}
              className={`truncate text-[10px] leading-tight ${i === activeIdx ? "font-semibold text-gray-800" : "text-gray-400"}`}
              style={{ width: `${s.width}%` }}
              title={s.band.label}
            >
              {s.width >= 12 ? s.band.label : ""}
            </div>
          ))}
        </div>
        <div className="mt-0.5 flex justify-between text-[10px] text-gray-400">
          <span>{fmtNum(scale.min, 1)}</span>
          {segs.slice(0, -1).map((s, i) => (
            <span key={i}>{fmtNum(s.to, 1)}</span>
          ))}
          <span>{fmtNum(scale.max, 1)}+</span>
        </div>
      </div>
      {scale.note && <p className="mt-1 text-[11px] text-gray-500">{scale.note}</p>}
    </div>
  );
}
