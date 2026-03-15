function TimeWheel({ value, options, onChange }: { value: number; options: number[]; onChange: (v: number) => void }) {
  const idx = options.indexOf(value);
  const prev = () => onChange(options[(idx - 1 + options.length) % options.length]!);
  const next = () => onChange(options[(idx + 1) % options.length]!);
  return (
    <div className="flex items-center leading-none">
      <button type="button" onClick={prev} className="text-gray-400 hover:text-gray-600 text-xs px-1">◀</button>
      <span className="text-base font-semibold text-gray-800 tabular-nums w-7 text-center">
        {String(value).padStart(2, "0")}
      </span>
      <button type="button" onClick={next} className="text-gray-400 hover:text-gray-600 text-xs px-1">▶</button>
    </div>
  );
}

export default function TimeInput({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const [h, m] = value.split(":").map(Number);
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const minutes = [0, 15, 30, 45];
  return (
    <div className={`inline-flex items-center gap-0 rounded-lg border border-gray-200 bg-white px-1 py-0.5 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <TimeWheel
        value={h ?? 0}
        options={hours}
        onChange={(v) => onChange(`${String(v).padStart(2, "0")}:${String(m ?? 0).padStart(2, "0")}`)}
      />
      <span className="text-gray-400 font-bold text-base mx-0.5">:</span>
      <TimeWheel
        value={m ?? 0}
        options={minutes}
        onChange={(v) => onChange(`${String(h ?? 0).padStart(2, "0")}:${String(v).padStart(2, "0")}`)}
      />
    </div>
  );
}
