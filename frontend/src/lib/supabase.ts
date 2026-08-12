/**
 * El único cliente de Supabase del frontend (F-014): login, sesión y —desde acá en adelante—
 * lectura/escritura directa de las tablas de usuario con Row Level Security.
 *
 * Usa la anon key, no la service role: es la que está pensada para viajar al navegador. El
 * aislamiento entre asesores no depende de que esta key sea secreta —no lo es, cualquiera puede
 * verla en el bundle— sino de las policies de RLS en PostgreSQL, que se aplican igual sin
 * importar qué mande el cliente. Ver `docs/esquema-datos.md`, sección "Precedencia por campo" y
 * "Sobre RLS y quién puede escribir".
 */

import { createClient } from '@supabase/supabase-js'

import type { Database } from '@/types/database.types'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !anonKey) {
  // Mismo criterio que `backend/app/core/config.py`: el servicio no arranca a medias. Un cliente
  // de Supabase mal armado no falla acá, falla en el primer click del asesor, con un mensaje que
  // ya no dice qué faltó configurar.
  throw new Error(
    'Faltan VITE_SUPABASE_URL y/o VITE_SUPABASE_ANON_KEY. Completalas en el .env de la raíz ' +
      '(ver .env.example) y reiniciá el servidor de desarrollo.',
  )
}

export const supabase = createClient<Database>(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
})
