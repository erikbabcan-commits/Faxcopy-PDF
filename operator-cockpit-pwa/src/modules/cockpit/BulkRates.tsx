import { useState, useMemo } from 'react';
import { isBackendConfigured } from '../../services/api';

interface RateRow {
  unitId: string;
  base: number;
  rates: number[];
  selected: boolean;
}

const INITIAL: RateRow[] = [
  { unitId: 'A101', base: 120, rates: [120, 120, 120, 150, 150, 150, 120], selected: false },
  { unitId: 'A102', base: 120, rates: [120, 120, 150, 150, 150, 150, 120], selected: false },
  { unitId: 'A103', base: 200, rates: [200, 200, 200, 220, 220, 220, 200], selected: false },
  { unitId: 'HVR-204', base: 180, rates: [180, 180, 180, 200, 200, 200, 180], selected: false },
  { unitId: 'HVR-308', base: 150, rates: [150, 150, 150, 150, 150, 150, 150], selected: false },
  { unitId: 'B205', base: 130, rates: [130, 130, 150, 150, 150, 150, 130], selected: false },
];

const DAY_LABELS = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne'];

export default function BulkRates() {
  const [rows, setRows] = useState<RateRow[]>(INITIAL);
  const [changeType, setChangeType] = useState<'percent' | 'fixed'>('percent');
  const [value, setValue] = useState(10);
  const [preview, setPreview] = useState<Record<string, number[]>>({});
  const [log, setLog] = useState('');
  const syncNote = isBackendConfigured()
    ? 'Odeslání změn vyžaduje přiřazení jednotek ke skutečným účtům a nabídkám.'
    : 'Odeslání změn vyžaduje připojený backend a přiřazení jednotek ke skutečným účtům a nabídkám.';

  const selectedIds = useMemo(() => rows.filter((row) => row.selected).map((row) => row.unitId), [rows]);

  function resetPreview() {
    setPreview({});
    setLog('');
  }

  function toggle(id: string) {
    setRows((current) => current.map((row) => row.unitId === id ? { ...row, selected: !row.selected } : row));
    resetPreview();
  }

  function toggleAll(checked: boolean) {
    setRows((current) => current.map((row) => ({ ...row, selected: checked })));
    resetPreview();
  }

  function computeNewRates(rates: number[]): number[] {
    return rates.map((rate) => changeType === 'percent' ? Math.round(rate * (1 + value / 100)) : rate + value);
  }

  function doPreview() {
    if (!selectedIds.length) {
      setLog('Vyberte alespoň jednu jednotku.');
      return;
    }
    const next: Record<string, number[]> = {};
    rows.forEach((row) => {
      if (row.selected) next[row.unitId] = computeNewRates(row.rates);
    });
    if (!Number.isFinite(value) || Object.values(next).some((rates) => rates.some((rate) => !Number.isFinite(rate) || rate <= 0))) {
      setPreview({});
      setLog('Výsledné ceny musí být kladná konečná čísla.');
      return;
    }
    setPreview(next);
    setLog('Náhled připraven pro ' + selectedIds.length + ' jednotek. Změny nebyly odeslány.');
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <header className="flex flex-wrap gap-3 items-center justify-between mb-3 shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Hromadné změny cen</h1>
          <p className="text-xs text-[#B8977B]">Náhled sazeb pro ukázkové jednotky</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Typ změny ceny"
            value={changeType}
            onChange={(event) => { setChangeType(event.target.value as 'percent' | 'fixed'); resetPreview(); }}
            className="px-2 py-1.5 rounded-lg border border-[#E2B48A]/40 bg-[#081611] text-xs"
          >
            <option value="percent">Procenta</option>
            <option value="fixed">Pevná částka</option>
          </select>
          <input
            type="number"
            aria-label="Výše změny ceny"
            value={value}
            onChange={(event) => { setValue(Number(event.target.value)); resetPreview(); }}
            className="w-16 px-2 py-1.5 rounded-lg border border-[#E2B48A]/40 bg-[#081611] text-xs"
          />
          <button onClick={doPreview} className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">
            Náhled
          </button>
          <button
            disabled
            title={syncNote}
            aria-describedby="rates-sync-note"
            className="px-4 py-1.5 rounded-lg bg-[#E2B48A] text-[#040C09] text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Odeslání není nastavené
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-auto rounded-xl border border-[#E2B48A]/30 bg-[#081611]/60">
        <table className="w-full text-xs">
          <thead className="text-[#B8977B] border-b border-[#E2B48A]/20 sticky top-0 bg-[#081611]">
            <tr>
              <th className="p-2 text-left">
                <input type="checkbox" aria-label="Vybrat všechny jednotky" checked={selectedIds.length === rows.length} onChange={(event) => toggleAll(event.target.checked)} />
              </th>
              <th className="p-2 text-left">Jednotka</th>
              {DAY_LABELS.map((day) => (
                <th key={day} className="p-2">{day}</th>
              ))}
              <th className="p-2">Základ</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.unitId} className="border-b border-[#E2B48A]/10 hover:bg-white/[0.03]">
                <td className="p-2">
                  <input type="checkbox" aria-label={'Vybrat jednotku ' + row.unitId} checked={row.selected} onChange={() => toggle(row.unitId)} />
                </td>
                <td className="p-2 font-medium">{row.unitId}</td>
                {row.rates.map((rate, index) => {
                  const previewValue = preview[row.unitId]?.[index];
                  const changed = previewValue !== undefined && previewValue !== rate;
                  return (
                    <td key={index} className={'p-2 text-center font-mono ' + (changed ? 'text-amber-300' : 'text-[#F5DEC9]')}>
                      {changed ? previewValue : rate}
                    </td>
                  );
                })}
                <td className="p-2 text-center font-mono text-[#E2B48A]">{row.base}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p role="status" aria-live="polite" className="mt-2 text-xs text-[#B8977B] shrink-0">{log || 'Vyberte jednotky a nastavte změnu pro místní náhled.'}</p>
      <p id="rates-sync-note" className="mt-1 text-xs text-[#B8977B] shrink-0">{syncNote}</p>
    </div>
  );
}
