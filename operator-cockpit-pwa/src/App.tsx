import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useAppStore } from './store/appStore';
import Dashboard from './modules/cockpit/Dashboard';
import Calendar from './modules/cockpit/Calendar';
import BulkRates from './modules/cockpit/BulkRates';
import Settings from './modules/cockpit/Settings';

const nav = [
  { to: '/', label: 'Domů' },
  { to: '/calendar', label: 'Kalendář' },
  { to: '/rates', label: 'Ceny' },
  { to: '/channels', label: 'Kanály' },
  { to: '/settings', label: 'Nastavení' },
];

export default function App() {
  const { occupancy, arrivalsToday } = useAppStore();

  return (
    <BrowserRouter>
      <div className="flex flex-col md:flex-row h-[100dvh] overflow-hidden bg-[#040C09] text-[#F5DEC9] font-sans">
        <aside className="w-full md:w-56 border-b md:border-b-0 md:border-r border-[#E2B48A]/20 p-3 md:p-4 flex flex-row md:flex-col gap-1 shrink-0 overflow-x-auto">
          <div className="hidden md:block text-xs font-bold tracking-widest text-[#E2B48A] mb-4">OPERATOR COCKPIT</div>
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm whitespace-nowrap transition ${isActive ? 'bg-[#E2B48A]/20 text-white' : 'text-[#D7B598] hover:bg-white/5'}`
              }
            >
              {n.label}
            </NavLink>
          ))}
          <div className="hidden md:block mt-auto text-[10px] text-[#B8977B]">
            Obsazenost {occupancy}% • Příjezdy {arrivalsToday}
          </div>
        </aside>
        <main className="flex-1 min-h-0 overflow-auto p-3 md:p-4 min-w-0">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/rates" element={<BulkRates />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<div className="text-sm text-[#B8977B]">Modul v přípravě</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
