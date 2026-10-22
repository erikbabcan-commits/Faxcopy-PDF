import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ChannelStatus = 'connected' | 'disconnected' | 'testing' | 'error';

interface AppState {
  currentView: string;
  occupancy: number;
  arrivalsToday: number;
  revenue: number;
  bookingStatus: ChannelStatus;
  airbnbStatus: ChannelStatus;
  setView: (view: string) => void;
  setChannelStatus: (channel: 'booking' | 'airbnb', status: ChannelStatus) => void;
  incrementArrivals: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentView: 'dashboard',
      occupancy: 78,
      arrivalsToday: 12,
      revenue: 4320,
      bookingStatus: 'disconnected',
      airbnbStatus: 'disconnected',
      setView: (view) => set({ currentView: view }),
      setChannelStatus: (channel, status) =>
        set(channel === 'booking' ? { bookingStatus: status } : { airbnbStatus: status }),
      incrementArrivals: () => set((s) => ({ arrivalsToday: s.arrivalsToday + 1 })),
    }),
    {
      name: 'operator-cockpit-store',
      // Only a display preference survives reload. Connection tests are transient.
      partialize: (state) => ({ currentView: state.currentView }),
      // Ignore connection statuses written by older versions of the application.
      merge: (persistedState, currentState) => {
        const saved = persistedState as { currentView?: unknown } | undefined;
        return {
          ...currentState,
          currentView: typeof saved?.currentView === 'string' ? saved.currentView : currentState.currentView,
        };
      },
    }
  )
);
