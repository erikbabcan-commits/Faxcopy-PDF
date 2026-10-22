import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  // Provider credentials must never be embedded in the browser bundle.
  envPrefix: ['VITE_API_BASE_URL'],
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      strategies: 'generateSW',
      includeAssets: ['favicon.svg', 'favicon.ico', 'apple-touch-icon.png'],
      manifest: {
        name: 'Operator Cockpit — Channel Manager',
        short_name: 'Cockpit',
        description: 'Přehled ubytování, dostupnosti a cen pro Booking.com a Airbnb.',
        lang: 'cs',
        id: '/',
        theme_color: '#040C09',
        background_color: '#040C09',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallbackDenylist: [/^\/api(?:\/|$)/],
        // Cache the app shell only; authenticated API responses stay on the network.
        runtimeCaching: []
      }
    })
  ],
  resolve: { alias: { '@': '/src' } },
  build: { target: 'esnext', sourcemap: false, minify: 'esbuild' }
});
