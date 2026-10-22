import axios, { type AxiosInstance } from 'axios';
import OpenAI from 'openai';

/**
 * SERVER-ONLY REFERENCE retained from the uploaded project's provider layer.
 * This file is not imported by src/, is not a Vercel Function, and is not a
 * deployed/authenticated backend. Provider endpoints and account permissions
 * have not been verified against live accounts.
 *
 * Before using it, implement authentication, authorization, input validation,
 * real property/listing mappings, CSRF protection and provider error handling
 * in a separate backend. Never import this file into a browser application.
 */

const BOOKING_AUTH_URL = 'https://connectivity-authentication.booking.com/token-based-authentication/exchange';
const BOOKING_SUPPLY = 'https://supply-xml.booking.com';
const BOOKING_SECURE = 'https://secure-supply-xml.booking.com';
const AIRBNB_API = 'https://api.airbnb.com/v2';

interface TokenCache {
  token: string;
  expiresAt: number;
}

let bookingToken: TokenCache | null = null;

async function getBookingToken(): Promise<string> {
  if (bookingToken && bookingToken.expiresAt > Date.now() + 60_000) {
    return bookingToken.token;
  }
  const clientId = process.env.BOOKING_CLIENT_ID;
  const clientSecret = process.env.BOOKING_CLIENT_SECRET;
  if (!clientId || !clientSecret) throw new Error('Missing Booking.com credentials');

  const { data } = await axios.post(BOOKING_AUTH_URL, {
    client_id: clientId,
    client_secret: clientSecret,
  });
  bookingToken = {
    token: data.access_token,
    expiresAt: Date.now() + (data.expires_in ?? 3600) * 1000,
  };
  return bookingToken.token;
}

function bookingClient(secure = false): AxiosInstance {
  const instance = axios.create({
    baseURL: secure ? BOOKING_SECURE : BOOKING_SUPPLY,
    timeout: 20000,
    headers: { 'Content-Type': 'application/xml', Accept: 'application/xml' },
  });
  instance.interceptors.request.use(async (config) => {
    const token = await getBookingToken();
    config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
  return instance;
}

/* ---------- Booking.com ---------- */

export async function testBookingConnection() {
  const start = Date.now();
  try {
    await getBookingToken();
    return { ok: true, latency: Date.now() - start };
  } catch {
    return { ok: false, latency: Date.now() - start, error: 'Booking.com connection failed' };
  }
}

/** Reference only: validate/escape the complete payload before using this XML. */
export async function pushBookingAvailability(payload: {
  hotelId: string;
  roomId: string;
  from: string;
  to: string;
  roomsToSell: number;
  price?: number;
}) {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<request>
  <hotel_id>${payload.hotelId}</hotel_id>
  <room id="${payload.roomId}">
    <date from="${payload.from}" to="${payload.to}">
      <roomstosell>${payload.roomsToSell}</roomstosell>
      ${payload.price ? `<price>${payload.price}</price>` : ''}
      <closed>0</closed>
    </date>
  </room>
</request>`;
  const client = bookingClient(false);
  const { data } = await client.post('/hotels/xml/availability', xml);
  return data;
}

/** Pull reservations summary (requires PCI/PII certification). */
export async function pullBookingReservations(hotelId?: string) {
  const client = bookingClient(true);
  const body = hotelId
    ? `<?xml version="1.0"?><request><hotel_id>${hotelId}</hotel_id></request>`
    : `<?xml version="1.0"?><request/>`;
  const { data } = await client.post('/hotels/xml/reservationssummary', body);
  return data;
}

/* ---------- Airbnb ---------- */

function airbnbClient(): AxiosInstance {
  const token = process.env.AIRBNB_ACCESS_TOKEN;
  if (!token) throw new Error('Missing Airbnb access token');
  return axios.create({
    baseURL: AIRBNB_API,
    timeout: 20000,
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function testAirbnbConnection() {
  const start = Date.now();
  try {
    const client = airbnbClient();
    await client.get('/listings', { params: { _limit: 1 } });
    return { ok: true, latency: Date.now() - start };
  } catch {
    return { ok: false, latency: Date.now() - start, error: 'Airbnb connection failed' };
  }
}

export async function getAirbnbCalendar(listingId: string, start: string, end: string) {
  const client = airbnbClient();
  const { data } = await client.get(`/listings/${listingId}/calendar`, {
    params: { start_date: start, end_date: end },
  });
  return data;
}

export async function updateAirbnbCalendar(
  listingId: string,
  days: { date: string; available?: boolean; price?: number; min_nights?: number }[]
) {
  const client = airbnbClient();
  const { data } = await client.put(`/listings/${listingId}/calendar`, { days });
  return data;
}

/* ---------- Shared / AI ---------- */

let openaiClient: OpenAI | null = null;

function getOpenAIClient(): OpenAI {
  if (openaiClient) return openaiClient;
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('Missing optional OpenAI server API key');
  openaiClient = new OpenAI({ apiKey });
  return openaiClient;
}

export async function askAI(prompt: string) {
  const completion = await getOpenAIClient().chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
  });
  return completion.choices[0]?.message?.content ?? '';
}

export default { testBookingConnection, testAirbnbConnection, pushBookingAvailability, pullBookingReservations, getAirbnbCalendar, updateAirbnbCalendar };
