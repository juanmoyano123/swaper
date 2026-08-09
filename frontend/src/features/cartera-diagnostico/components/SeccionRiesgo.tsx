/**
 * Vector de riesgo de seis ejes de la cartera cargada — F-031 (tanda 12).
 *
 * Stub de la base común: cuerpo pendiente. Se monta en `DiagnosticoCartera.tsx` después de
 * `SeccionConcentracion`, con las props ya fijadas por el orquestador — F-031 reemplaza el
 * cuerpo entero, nadie más lo toca. El criterio de aceptación (R12, `plan.md:2774`) es que la
 * misma composición cargada acá y armada en `/armador` muestre el mismo vector: por eso recibe
 * `{ticker, peso}[]`, la misma forma con la que el armador arma sus posiciones.
 */
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'

export function SeccionRiesgo(_props: {
  posiciones: { ticker: string; peso: number }[]
  perfil: NombreDePerfil
}) {
  return null
}
