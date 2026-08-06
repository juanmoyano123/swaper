import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
// De 'vitest/config' y no de 'vite': es el que conoce el bloque `test` de abajo.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Con tres niveles de carpetas y una feature por pantalla, los imports relativos
    // (../../../lib/api/client) se rompen apenas se mueve un archivo.
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // El único .env del proyecto vive en la raíz del repo, no acá (ver CLAUDE.md: "los secretos van
  // en .env, nunca en otro lado"). Sin esto Vite busca frontend/.env, que no existe, y las claves
  // VITE_SUPABASE_* de F-014 quedarían undefined en build.
  envDir: fileURLToPath(new URL('..', import.meta.url)),
  server: {
    // El frontend habla siempre con rutas relativas /api/v1/...; en desarrollo el proxy las manda
    // al backend. Evita configurar CORS en FastAPI, que sería una superficie de ataque más.
    //
    // El destino se puede cambiar con VITE_PROXY_TARGET para cuando el 8000 está ocupado por otro
    // servicio de la máquina: `VITE_PROXY_TARGET=http://localhost:8001 npm run dev`.
    proxy: { '/api': process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    css: false,
    // Sin `globals`: describe/it/expect se importan de vitest, que es lo que TypeScript en modo
    // estricto resuelve sin configuración extra.
    env: {
      // Valores inventados a propósito (mismo criterio que `ENV_DE_PRUEBA` en
      // `backend/tests/conftest.py`): la suite no depende de que el .env real de la raíz esté
      // completo, y estos nunca llegan a pegarle a una red real porque en jsdom no hay sesión
      // guardada — `supabase.auth.getSession()` resuelve local, sin hacer fetch.
      VITE_SUPABASE_URL: 'https://proyecto-de-prueba.supabase.co',
      VITE_SUPABASE_ANON_KEY: 'anon-key-de-prueba-9f3a',
    },
  },
})
