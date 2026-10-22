import { useAppStore } from '../../store/appStore';

export default function Dashboard() {
  const { occupancy, arrivalsToday, revenue } = useAppStore();
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Domů</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Obsazenost" value={`${occupancy}%`} />
        <Kpi label="Příjezdy" value={String(arrivalsToday)} />
        <Kpi label="Odjezdy" value="8" />
        <Kpi label="Tržby" value={`£${revenue.toLocaleString('cs-CZ')}`} />
      </div>
      <div className="rounded-xl border border-[#E2B48A]/30 bg-[#081611]/80 p-4">
        <h2 className="text-sm font-semibold mb-2">Detailní příjezdy</h2>
        <p className="text-xs text-[#B8977B]">Přehled používá ukázková data. Synchronizace s rezervačními účty zatím není připojena.</p>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#E2B48A]/30 bg-gradient-to-br from-[#0D211A] to-[#07130F] p-4">
      <div className="text-[10px] tracking-widest text-[#E2B48A]">{label.toUpperCase()}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}
