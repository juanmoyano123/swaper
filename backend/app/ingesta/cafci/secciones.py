"""Catálogo declarativo de los títulos de sección de la planilla diaria de CAFCI.

Medido contra el archivo real del 21/08/2026 (`20260821_Planilla_Diaria_A.xlsx`, 4.251 filas de
datos, 39 títulos de fila-de-sección — una fila donde sólo la columna A tiene valor). Un título que
no está acá aborta el parseo (`PlanillaInvalida`) en vez de heredar en silencio la clasificación de
la sección anterior.

**No todo título de sección es una sección con datos propios.** La planilla anida categorías —
"Fondos en Proceso de Liquidacion" no tiene filas de fondo directamente debajo; las tiene su hija
"En Proceso de Liquidacion por Pago Total"—. `SECCIONES` mapea los títulos que sí encabezan filas de
fondo a su `tipo_renta`; `DIVISORES` son los títulos que nunca encabezan datos (categorías
intermedias y las notas al pie del final del archivo) y se saltean sin cambiar la sección activa. Si
una fila de datos aparece justo debajo de un divisor, es una sorpresa estructural y aborta — nunca
se le asigna el tipo de renta de la sección anterior a esa fila por descarte.

`en_liquidacion` es un tipo de renta real, no un caso raro: 21 fondos de la planilla medida están en
este estado y tienen su propia fila de datos completa. Omitirlos sería perder fondos que existen.

La **moneda de cada fondo no sale de acá**: viene de la columna B de su propia fila (`normalizacion.
py`), igual que en el resto del proyecto — un dato que ya está en la fila no se re-declara por el
título de la sección.
"""

SECCIONES: dict[str, str] = {
    "Renta Variable Peso Argentina": "renta_variable",
    "Renta Variable Dolar Estadounidense Billete": "renta_variable",
    "Renta Variable Dolar Estadounidense": "renta_variable",
    "Renta Fija Peso Argentina": "renta_fija",
    "Renta Fija Dolar Estadounidense": "renta_fija",
    "Renta Fija Dolar Estadounidense Billete": "renta_fija",
    "Renta Mixta Peso Argentina": "renta_mixta",
    "Renta Mixta Dolar Estadounidense": "renta_mixta",
    "Renta Mixta Dolar Estadounidense Billete": "renta_mixta",
    "PyMes Peso Argentina": "pymes",
    "PyMes Dolar Estadounidense": "pymes",
    "PyMes Dolar Estadounidense Billete": "pymes",
    "Infraestructura Peso Argentina": "infraestructura",
    "Infraestructura Dolar Estadounidense": "infraestructura",
    "Retorno Total Peso Argentina": "retorno_total",
    "Retorno Total Dolar Estadounidense": "retorno_total",
    "ASG Peso Argentina": "asg",
    "RG900 Peso Argentina": "rg900",
    "Mercado de Dinero Peso Argentina": "mercado_dinero",
    "Mercado de Dinero Dolar Estadounidense": "mercado_dinero",
    "Mercado de Dinero Dolar Estadounidense Billete": "mercado_dinero",
    "Fondos Cerrados Peso Argentina": "fondos_cerrados",
    "Fondos Cerrados Dolar Estadounidense": "fondos_cerrados",
    # Anidada bajo "Fondos Iliquidos, con rescate en especies (P/E)" > "Que no Suscriben
    # Cuotapartes": semánticamente sigue siendo mercado de dinero, sólo que sin cuotapartes.
    "Clases en Dolar Estadounidense": "mercado_dinero",
    "En Proceso de Liquidacion por Pago Parcial y Especies": "en_liquidacion",
    "Solicitud en tramite": "en_liquidacion",
    "En Proceso de Liquidacion por Pago Total": "en_liquidacion",
}

# Categorías intermedias y notas al pie: nunca encabezan una fila de datos directamente. Ver el
# docstring del módulo — una fila de datos justo debajo de uno de estos títulos es la sorpresa
# estructural que hace abortar el parseo, no un motivo para heredarle un tipo de renta cualquiera.
DIVISORES: frozenset[str] = frozenset(
    {
        "Fondos Liquidos, con rescate en efectivo",
        "Que no Suscriben Cuotapartes",
        "Fondos Iliquidos, con rescate en especies (P/E)",
        "Fondos en Proceso de Liquidacion",
        "(*) Determinación del valor de la cuotaparte, rescates y/o suscripciones suspendidos.",
        "(**) Liquidez sujeta a reprogramacion BCRA.",
        "(***) Pago en especies previa autorizacion de la CNV.",
        "P/E Pago en especies.",
        'Advertencia: "Los rendimientos atribuidos en el informe a los distintos Fondos han sido '
        'calculados sin tener en consideración los pagos de distribución de utilidades que '
        'pudieran haber ocurrido"',
    }
)
