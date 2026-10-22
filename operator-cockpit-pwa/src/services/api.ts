/**
 * Browser client for an authenticated backend supplied by the operator.
 * VITE_API_BASE_URL is a public URL. Provider credentials never belong here.
 * The frontend preview intentionally ships without a deployed API backend.
 */

export interface ConnectionResult {
  ok: boolean;
  latency: number;
  error?: string;
}

export interface BookingAvailabilityPayload {
  hotelId: string;
  roomId: string;
  from: string;
  to: string;
  roomsToSell: number;
  price?: number;
}

export interface AirbnbCalendarDay {
  date: string;
  available?: boolean;
  price?: number;
  min_nights?: number;
}

const BACKEND_NOT_CONFIGURED =
  'Připojení ke kanálům není nastavené. Správce musí připojit zabezpečený backend.';

class BackendError extends Error {}

export function isBackendConfigured(): boolean {
  return Boolean(import.meta.env.VITE_API_BASE_URL?.trim());
}

function backendUrl(path: string): string {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!configuredUrl) throw new BackendError(BACKEND_NOT_CONFIGURED);

  try {
    if (!/^https?:\/\//.test(configuredUrl) && !/^\/(?!\/)/.test(configuredUrl)) {
      throw new Error('Invalid URL');
    }
    const base = new URL(configuredUrl, window.location.origin);
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(base.hostname);
    if (
      (base.protocol !== 'https:' && !(local && base.protocol === 'http:')) ||
      base.username || base.password || base.search || base.hash
    ) {
      throw new Error('Invalid URL');
    }
    return `${base.origin}${base.pathname.replace(/\/$/, '')}${path}`;
  } catch {
    throw new BackendError('Adresa backendu není platná. Zkontrolujte nastavení připojení.');
  }
}

async function backendRequest<T>(path: string, method = 'GET', payload?: unknown): Promise<T> {
  // Resolve configuration before starting any request or timer.
  const url = backendUrl(path);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20_000);

  try {
    const response = await fetch(url, {
      method,
      credentials: 'include',
      redirect: 'error',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: controller.signal,
    });

    if (response.status === 401 || response.status === 403) {
      throw new BackendError('Backend vyžaduje přihlášení a oprávnění správce.');
    }
    if (response.status === 404) {
      throw new BackendError('Požadované rozhraní backendu zatím není dostupné.');
    }
    if (!response.ok) {
      throw new BackendError('Backend požadavek nedokončil. Zkuste to později.');
    }
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new BackendError('Backend nevrátil očekávanou odpověď. Zkontrolujte nastavení připojení.');
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof BackendError) throw error;
    if (controller.signal.aborted) {
      throw new BackendError('Backend neodpověděl včas. Zkuste to znovu.');
    }
    // Never display raw network/provider errors that may contain credentials.
    throw new BackendError('Připojení k backendu se nezdařilo. Zkontrolujte dostupnost a přihlášení.');
  } finally {
    window.clearTimeout(timeout);
  }
}

async function testConnection(channel: 'booking' | 'airbnb'): Promise<ConnectionResult> {
  const start = Date.now();
  try {
    const result = await backendRequest<{ ok: boolean }>(`/${channel}/test-connection`, 'POST');
    if (typeof result?.ok !== 'boolean') {
      throw new BackendError('Backend nevrátil platný výsledek testu připojení.');
    }
    return {
      ok: result.ok,
      latency: Date.now() - start,
      ...(result.ok ? {} : { error: 'Připojení ke kanálu se nepodařilo ověřit.' }),
    };
  } catch (error) {
    return {
      ok: false,
      latency: Date.now() - start,
      error: error instanceof BackendError ? error.message : 'Test připojení se nezdařil.',
    };
  }
}

export function testBookingConnection(): Promise<ConnectionResult> {
  return testConnection('booking');
}

export function testAirbnbConnection(): Promise<ConnectionResult> {
  return testConnection('airbnb');
}

export function pushBookingAvailability(payload: BookingAvailabilityPayload): Promise<unknown> {
  return backendRequest('/booking/availability', 'POST', payload);
}

export function pullBookingReservations(hotelId?: string): Promise<unknown> {
  return backendRequest('/booking/reservations-summary', 'POST', hotelId ? { hotelId } : {});
}

export function getAirbnbCalendar(listingId: string, start: string, end: string): Promise<unknown> {
  const query = new URLSearchParams({ start_date: start, end_date: end });
  return backendRequest(`/airbnb/listings/${encodeURIComponent(listingId)}/calendar?${query}`);
}

export function updateAirbnbCalendar(listingId: string, days: AirbnbCalendarDay[]): Promise<unknown> {
  return backendRequest(`/airbnb/listings/${encodeURIComponent(listingId)}/calendar`, 'PUT', { days });
}

export async function askAI(prompt: string): Promise<string> {
  const result = await backendRequest<{ text: string }>('/ai/chat', 'POST', { prompt });
  if (typeof result?.text !== 'string') {
    throw new BackendError('Backend nevrátil platnou odpověď asistenta.');
  }
  return result.text;
}

export default {
  testBookingConnection,
  testAirbnbConnection,
  pushBookingAvailability,
  pullBookingReservations,
  getAirbnbCalendar,
  updateAirbnbCalendar,
};
