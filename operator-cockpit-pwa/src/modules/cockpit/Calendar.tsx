import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';

interface Unit {
  id: string;
  name: string;
  type: string;
}

interface DayCell {
  date: string;
  available: boolean;
  booked: boolean;
  blocked: boolean;
  rate: number;
  channel?: 'booking' | 'airbnb' | 'direct';
}

const UNITS: Unit[] = [
  { id: 'A101', name: 'A101', type: 'Studio' },
  { id: 'A102', name: 'A102', type: 'Studio' },
  { id: 'A103', name: 'A103', type: '1 ložnice' },
  { id: 'HVR-204', name: 'HVR-204', type: '2 ložnice' },
  { id: 'HVR-308', name: 'HVR-308', type: '2 ložnice' },
  { id: 'B205', name: 'B205', type: '1 ložnice' },
  { id: 'C112', name: 'C112', type: 'Studio' },
];

function generateDays(start: Date, count: number): Date[] {
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
}

function localDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function mockCell(unit: Unit, date: Date): DayCell {
  const seed = unit.id.length + date.getDate();
  const blocked = seed % 11 === 0;
  const booked = !blocked && seed % 5 === 0;
  return {
    date: localDate(date),
    available: !booked && !blocked,
    booked,
    blocked,
    rate: 120 + (seed % 6) * 10 + (unit.id.startsWith('H') ? 40 : 0),
    channel: booked ? (seed % 2 === 0 ? 'booking' : 'airbnb') : undefined,
  };
}

export default function Calendar() {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<{ unit: string; date: string } | null>(null);

  const start = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + offset);
    return d;
  }, [offset]);

  const days = useMemo(() => generateDays(start, 14), [start]);

  const grid = useMemo(
    () =>
      UNITS.map((u) => ({
        unit: u,
        cells: days.map((d) => mockCell(u, d)),
      })),
    [days]
  );

  function cellClass(c: DayCell) {
    if (c.blocked) return 'bg-rose-900/50 text-rose-200';
    if (c.booked) return 'bg-emerald-900/50 text-emerald-200';
    return 'bg-[#123127]/50 text-[#F5DEC9] hover:bg-[#1a3d32]';
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <header className="flex flex-wrap gap-3 items-center justify-between mb-3 shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Kalendář dostupnosti</h1>
          <p className="text-[11px] text-[#B8977B]">14denní přehled • ukázková dostupnost, sazby a stav</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setOffset((o) => o - 7)} className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">
            ← 7 dní
          </button>
          <span className="text-xs font-mono text-[#E2B48A] px-2">
            {days[0].toLocaleDateString('cs-CZ')} – {days[13].toLocaleDateString('cs-CZ')}
          </span>
          <button onClick={() => setOffset((o) => o + 7)} className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">
            7 dní →
          </button>
          <Link to="/rates" className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">
            Hromadné ceny
          </Link>
        </div>
      </header>

      <div className="flex-1 overflow-auto rounded-xl border border-[#E2B48A]/30 bg-[#081611]/60">
        <div className="min-w-[980px] p-2">
          <div className="grid grid-cols-[160px_repeat(14,minmax(52px,1fr))] gap-px text-[10px] sticky top-0 bg-[#040C09]/95 z-10">
            <div className="p-2 text-[#B8977B]">Jednotka</div>
            {days.map((d) => (
              <div key={d.toISOString()} className="p-1 text-center text-[#E2B48A]">
                {d.toLocaleDateString('cs-CZ', { weekday: 'short', day: 'numeric' })}
              </div>
            ))}
          </div>
          {grid.map(({ unit, cells }) => (
            <div key={unit.id} className="grid grid-cols-[160px_repeat(14,minmax(52px,1fr))] gap-px mt-px">
              <div className="p-2 font-medium text-[#F0D9C4] bg-[#0A1A14]/80 flex flex-col justify-center">
                <span>{unit.name}</span>
                <span className="text-[9px] text-[#B8977B]">{unit.type}</span>
              </div>
              {cells.map((c) => (
                <button
                  key={c.date}
                  onClick={() => setSelected({ unit: unit.id, date: c.date })}
                  className={`p-1 text-center text-[10px] rounded-sm transition ${cellClass(c)} ${
                    selected?.unit === unit.id && selected.date === c.date ? 'ring-1 ring-[#E2B48A]' : ''
                  }`}
                  title={`${unit.id} • ${c.date} • ${c.blocked ? 'Blokováno' : c.booked ? 'Obsazeno' : 'Volné'} • £${c.rate}`}
                >
                  {c.blocked ? 'Blok' : c.booked ? 'Obs' : c.rate}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {selected && (
        <div className="mt-3 p-3 rounded-xl border border-[#E2B48A]/30 bg-[#081611]/80 text-xs flex justify-between items-center">
          <div>
            Vybráno: <strong>{selected.unit}</strong> • {selected.date}
          </div>
          <button onClick={() => setSelected(null)} className="px-2 py-1 rounded border border-[#E2B48A]/40">
            Zavřít
          </button>
        </div>
      )}
    </div>
  );
}
