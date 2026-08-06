import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/**
 * Ingreso por invitación, sin registro abierto.
 *
 * En F-003 es solo el lugar reservado: la autenticación real, la sesión y las guardas de ruta las
 * implementa F-014 contra Supabase Auth. Deliberadamente no hay formulario todavía — un campo de
 * contraseña que no autentica es peor que no tener nada.
 */
export function LoginPage() {
  return (
    <Pantalla titulo="Ingresar" bajada="Acceso por invitación. No hay registro abierto.">
      <Panel>
        <EstadoVacio
          titulo="El ingreso todavía no está habilitado."
          detalle="La autenticación con Supabase Auth y el aislamiento por asesor los construye F-014."
        />
      </Panel>
    </Pantalla>
  )
}
