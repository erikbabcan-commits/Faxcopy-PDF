import { useState } from 'react';
import { useAppStore, type ChannelStatus } from '../../store/appStore';
import { isBackendConfigured, testBookingConnection, testAirbnbConnection } from '../../services/api';

const STATUS_LABELS: Record<ChannelStatus, string> = {
  connected: 'Ověřeno',
  disconnected: 'Neověřeno',
  testing: 'Testování…',
  error: 'Chyba',
};

export default function Settings() {
  const { bookingStatus, airbnbStatus, setChannelStatus } = useAppStore();
  const [tab, setTab] = useState<'api' | 'guide'>('api');
  const [log, setLog] = useState('');
  const backendConfigured = isBackendConfigured();
  const testing = bookingStatus === 'testing' || airbnbStatus === 'testing';

  async function test(channel: 'booking' | 'airbnb') {
    if (testing || !backendConfigured) return;
    const name = channel === 'booking' ? 'Booking.com' : 'Airbnb';
    setChannelStatus(channel, 'testing');
    setLog('Testuji připojení k ' + name + '…');
    try {
      const result = channel === 'booking' ? await testBookingConnection() : await testAirbnbConnection();
      setChannelStatus(channel, result.ok ? 'connected' : 'error');
      setLog(result.ok
        ? name + ': připojení ověřeno • ' + result.latency + ' ms'
        : name + ': ' + (result.error ?? 'Test připojení se nezdařil.'));
    } catch {
      setChannelStatus(channel, 'error');
      setLog(name + ': test připojení se nezdařil.');
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Nastavení připojení</h1>
      <div className="flex gap-2">
        <button onClick={() => setTab('api')} aria-pressed={tab === 'api'} className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">Připojení API</button>
        <button onClick={() => setTab('guide')} aria-pressed={tab === 'guide'} className="px-3 py-1.5 rounded-lg border border-[#E2B48A]/40 text-xs">Návod pro správce</button>
      </div>

      {tab === 'api' ? (
        <div className="space-y-3">
          {!backendConfigured && (
            <p className="rounded-xl border border-[#E2B48A]/30 bg-[#081611]/80 p-4 text-sm text-[#D7B598]">
              Připojení ke kanálům zatím není nastavené. Ukázku můžete používat bez přístupu k rezervačním účtům.
            </p>
          )}
          <ChannelCard name="Booking.com Connectivity API" status={bookingStatus} disabled={testing || !backendConfigured} onTest={() => { void test('booking'); }} />
          <ChannelCard name="Airbnb Partner API" status={airbnbStatus} disabled={testing || !backendConfigured} onTest={() => { void test('airbnb'); }} />
          <div className="rounded-xl border border-[#E2B48A]/30 p-4 text-sm">
            <div className="font-medium">Ukázkový provoz</div>
            <div className="text-xs text-[#B8977B] mt-1">Přehled a kalendář používají ukázková data. Odesílání změn cen vyžaduje připojený backend a přiřazení jednotek ke skutečným nabídkám.</div>
          </div>
          <p role="status" aria-live="polite" className="text-xs text-[#B8977B] break-words">{log}</p>
        </div>
      ) : (
        <div className="rounded-xl border border-[#E2B48A]/30 p-4 text-xs space-y-2 leading-relaxed">
          <h2 className="text-sm font-semibold">Připojení rezervačních účtů</h2>
          <p>Pro napojení Booking.com a Airbnb je potřeba zabezpečený backend s ověřeným přístupem správce.</p>
          <p>Přístupové údaje k Booking.com, Airbnb a volitelně OpenAI musí zůstat na serveru.</p>
          <p>Hromadné změny cen vyžadují také přiřazení jednotek ke konkrétním pokojům a nabídkám.</p>
          <p>Aktuální nasazení obsahuje ukázku rozhraní. Synchronizace s rezervačními účty není součástí této ukázky.</p>
        </div>
      )}
    </div>
  );
}

function ChannelCard({ name, status, disabled, onTest }: {
  name: string;
  status: ChannelStatus;
  disabled: boolean;
  onTest: () => void;
}) {
  const statusColor = status === 'connected' ? 'text-[#6EE7B7]' : status === 'error' ? 'text-rose-300' : 'text-[#B8977B]';
  return (
    <div className="rounded-xl border border-[#E2B48A]/30 p-4">
      <div className="flex flex-wrap gap-2 justify-between items-center">
        <span className="font-medium">{name}</span>
        <span className={'text-xs ' + statusColor}>{STATUS_LABELS[status]}</span>
      </div>
      <button onClick={onTest} disabled={disabled} className="mt-2 px-3 py-1 rounded-lg border border-[#E2B48A]/40 text-xs disabled:opacity-50 disabled:cursor-not-allowed">
        {status === 'testing' ? 'Testuji připojení…' : 'Otestovat připojení'}
      </button>
    </div>
  );
}
