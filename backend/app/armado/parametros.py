"""`ParametrosArmado`: el modelo Pydantic que reemplaza el `argparse` de
`tools/armar_cartera.py:558-580`.

Mapeo 1:1 de los flags del CLI, sacando lo que era de exportación de archivo (`--max-emisor` /
`--max-sector` / `--max-soberano` no se agregan como override: la ficha de F-019 sólo pide
monto/moneda/objetivo/perfil/horizonte como input, y si el perfil ya trae sus topes no hace falta un
override manual acá).

## Los topes de renta variable sí son override, y no se contradicen con lo de arriba (F-078)

Los topes de renta fija viven en el perfil porque el asesor no los toca: son la definición de
"conservador". Los de renta variable (`TopesRv`) sí se tocan desde la UI, porque el eje sobre el
que se acota —rubro, país, región, moneda, mercado— es la pregunta que el asesor le está haciendo
a la cartera, y esa pregunta cambia según el cliente. El perfil sigue dando el número de arranque
(`app.armado.renta_variable.TOPES_RV_DEFAULT`); esto lo pisa.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.universo.segmentacion import MONEDA_SEGMENTO


class TopesRv(BaseModel):
    """Cuánto del bloque de renta variable puede caer en una misma categoría de cada eje — F-078.

    **Cinco ejes, un tope cada uno, y ningún score compuesto.** Es la regla 7 del dominio aplicada
    a renta variable: el riesgo es un vector, no un número. Ponderar "país" contra "rubro" para
    sacar un único índice de diversificación exigiría un juicio que nadie estableció.

    `None` en un eje **apaga ese tope**, y es distinto de `TopesRv` entero en `None`: lo primero
    dice "no acotes por país", lo segundo dice "usá los defaults del perfil". Un `TopesRv` parcial
    —sólo `max_pct_rubro`, digamos— apaga los otros cuatro: lo que el llamador declara es la lista
    completa de lo que quiere acotar, no un parche sobre el default.

    El porcentaje se mide **sobre el bloque de renta variable**, no sobre la cartera entera: es la
    unidad en la que se reparten los cupos (ver `armado/renta_variable.py`), y mezclarla con el
    porcentaje de cartera haría que el mismo tope signifique dos cosas según `pct_rv`.
    """

    max_pct_rubro: float | None = Field(default=None, gt=0, le=100)
    """Sobre `sic_oficina`, el rubro tal como lo agrupa la SEC."""
    max_pct_pais: float | None = Field(default=None, gt=0, le=100)
    """Sobre `pais`, el país curado en ISO 3166-1 alfa-2."""
    max_pct_region: float | None = Field(default=None, gt=0, le=100)
    """Sobre `region`, la subregión ONU M49 derivada del país."""
    max_pct_moneda: float | None = Field(default=None, gt=0, le=100)
    """Sobre `moneda_cotizacion`, la moneda en la que la especie liquida en BYMA."""
    max_pct_mercado: float | None = Field(default=None, gt=0, le=100)
    """Sobre `mercado_origen`, el mercado donde cotiza el subyacente."""


class FiltroRv(BaseModel):
    """Qué subconjunto del universo de renta variable participa del armado — F-078.

    Espejo exacto de `frontend/src/lib/presetsRv.ts::FiltroRv`, para que un preset temático se
    pueda mandar al armador sin reinterpretarlo en el camino. Cada dimensión es una lista de
    valores **de la fuente, sin traducir** (regla 11 del dominio): `rubros` lleva
    `Office of Technology` porque así lo escribe la SEC, no "Tecnología".

    Una dimensión en `None` (o en lista vacía) no declara nada y no filtra. Una dimensión
    declarada sí, y **un dato faltante nunca la cumple**: no se puede afirmar que una especie sin
    rubro pertenece al rubro pedido (regla 1).
    """

    rubros: list[str] | None = None
    """Valores exactos de `sic_oficina`. **Se mantiene por compatibilidad** (F-079): el eje "rubro"
    del armador topea por `sectores`/`sector_codigo` desde F-079, no por `sic_oficina`, pero este
    campo sigue funcionando igual que antes -- filtra, no acota."""
    sectores: list[str] | None = None
    """Códigos de major group SIC de dos dígitos (`sector_codigo`, `"73"`), F-079. Es el eje que
    el armador usa para topar "rubro" desde esta feature -- más específico que `sic_oficina` y
    siempre derivable de `sic_codigo` sin ningún curado adicional."""
    sic_codigos: list[str] | None = None
    """Códigos SIC literales, sin normalizar: son la llave de auditoría contra la SEC."""
    estrategias_etf: list[str] | None = None
    """Claves de `estrategia_etf` (`activo_fisico`, `geografico`, `cripto`…)."""
    paises: list[str] | None = None
    """ISO 3166-1 alfa-2 del país curado."""
    regiones: list[str] | None = None
    """Subregiones ONU M49 derivadas del país."""
    mercados: list[str] | None = None
    """Valores de `mercado_origen`, comparados **sin distinguir mayúsculas**: la fuente escribe el
    mismo mercado de dos maneras, `NYSE Arca` en 81 papeles y `NYSE ARCA` en 12 (medido el
    28/08/2026 sobre los CEDEARs con mercado declarado)."""
    palabras_en_nombre: list[str] | None = None
    """Palabras que `nombre_largo` tiene que contener, **como palabra entera y sin distinguir
    mayúsculas**. Es lo único que rescata a `GDX` (Van Eck Gold Miners ETF) para el preset de
    metales preciosos: la SEC no le asigna SIC y BYMA lo declara sólo como sectorial. Leer el
    nombre es la misma técnica de `app/renta_variable/etfs.py` — no se interpreta, se lee. Por
    palabra entera y no por substring porque `gold` adentro de `Goldman` es el mismo bug que
    `etfs.py` ya tuvo con `ETF` adentro de `NETFLIX`."""

    modo: Literal["interseccion", "union"] = "interseccion"
    """`interseccion`: toda dimensión declarada tiene que cumplirse. `union`: alcanza con una.
    La unión existe para los presets que juntan declaraciones de fuentes distintas —el metal
    físico de un ETF, el SIC de una minera y el nombre de BYMA son tres formas de decir lo mismo
    y ninguna especie las tiene a las tres."""


def normalizar_filtro_rv(filtro_rv: FiltroRv | None, rubro_rv: str | None) -> FiltroRv | None:
    """El filtro efectivo, plegando el `rubro_rv` viejo dentro del `FiltroRv` nuevo — F-078.

    `rubro_rv` es la temática de una sola dimensión que el frontend manda desde F-052 y que se
    mantiene por compatibilidad: es exactamente `filtro_rv.rubros = [rubro_rv]`. Se pliega en un
    solo lugar —acá— y desde ahí lo usan tanto el validador de `ParametrosArmado` (que convierte
    el `ValueError` en 422) como `armar_renta_variable`, para que la regla no se escriba dos veces
    y empiece a significar dos cosas.

    Si los dos vienen y **dicen lo mismo**, no hay conflicto: se acepta. Si dicen cosas distintas
    no se elige ninguno —el mismo criterio que `condiciones_en_conflicto` en la ingesta— porque
    elegir exigiría una precedencia que nadie estableció.
    """
    if rubro_rv is None:
        return filtro_rv
    if filtro_rv is None:
        return FiltroRv(rubros=[rubro_rv])
    if not filtro_rv.rubros:
        return filtro_rv.model_copy(update={"rubros": [rubro_rv]})
    if list(filtro_rv.rubros) != [rubro_rv]:
        raise ValueError(
            f"rubro_rv={rubro_rv!r} contradice filtro_rv.rubros={list(filtro_rv.rubros)!r}: "
            "son la misma dimensión declarada dos veces con valores distintos. Mandá una sola "
            "de las dos (rubro_rv es la forma vieja de decir filtro_rv.rubros con un solo valor)."
        )
    return filtro_rv


class ParametrosArmado(BaseModel):
    """El mandato del cliente, ya validado. Espejo de los argumentos de
    `armar_cartera.py::main()`."""

    monto: float = Field(gt=0)
    moneda: Literal["usd", "ars", "todas"] = "todas"
    horizonte: Literal["corto", "medio", "largo"] = "medio"
    perfil: Literal["conservador", "moderado", "agresivo"] = "moderado"
    cobertura: Literal["devaluacion", "inflacion", "tasa-pesos", "mixta"] | None = None
    mix: dict[str, float] | None = None
    """Ya parseado (no el string `'usd_hard=60,cer=40'` de la CLI): el frontend arma el objeto
    directo, así que no hace falta reimplementar el parseo de texto de `--mix` acá."""

    n_total: int = Field(default=15, gt=0)
    min_rend: float = 0.0
    pago_mensual: bool = True

    pct_rv: float | None = Field(default=None, ge=0, le=100)
    """Qué porción de la cartera va a renta variable. `None` usa el default del perfil
    (`app.armado.renta_variable.PCT_RV_PERFIL`) -- no hay forma de pedir "el default" con un
    número, así que la ausencia es la señal."""

    rubro_rv: str | None = None
    """Temática dentro de renta variable, como valor exacto de `sic_oficina` -- el rubro tal como
    lo nombra la SEC, sin traducir (regla 11 del dominio). `None` es sin temática: participa todo
    el universo de renta variable, no sólo un rubro.

    **Se mantiene por compatibilidad** (F-078): es el campo que el frontend viene mandando desde
    F-052 y sacarlo rompería el armador en producción por un renombre. Es un `filtro_rv` de una
    sola dimensión y un solo valor, así que se pliega ahí -- ver `normalizar_filtro_rv`."""

    topes_rv: TopesRv | None = None
    """Cuánto puede concentrar el bloque de renta variable en cada eje. `None` usa los defaults
    del perfil (`app.armado.renta_variable.TOPES_RV_DEFAULT`), igual que `pct_rv`: no hay forma de
    pedir "el default" con un número, así que la ausencia es la señal.

    **Presente significa exactamente lo que declara: no hay merge parcial contra el default.** Un
    `topes_rv` que sólo trae `max_pct_rubro` apaga los otros cuatro ejes, no los hereda del perfil.
    Es lo único que hace *expresable* apagar un eje —si se mergeara, mandar `null` en un eje sería
    indistinguible de no mandarlo y el default volvería siempre— así que no se "arregla" después
    completando los huecos con el perfil."""

    filtro_rv: FiltroRv | None = None
    """Qué subconjunto del universo de renta variable participa. `None` es todo el universo."""

    @model_validator(mode="after")
    def _validar_mix(self) -> "ParametrosArmado":
        """Equivalente al `sys.exit` del CLI ante un segmento desconocido, acá un 422."""
        if self.mix is not None:
            desconocidos = sorted(set(self.mix) - set(MONEDA_SEGMENTO))
            if desconocidos:
                raise ValueError(
                    f"segmento(s) desconocido(s) en mix: {', '.join(desconocidos)}. "
                    f"Válidos: {', '.join(sorted(MONEDA_SEGMENTO))}"
                )
        return self

    @model_validator(mode="after")
    def _plegar_rubro_rv(self) -> "ParametrosArmado":
        """`rubro_rv` y `filtro_rv.rubros` son la misma dimensión: se pliegan en una, o 422.

        No se asigna el resultado a `self.filtro_rv`: `armar_renta_variable` vuelve a plegar con la
        misma función, y dejar el pliegue hecho acá *y* allá haría que el modelo mienta sobre lo
        que el llamador mandó (la respuesta serializa lo que se pidió). Acá sólo se valida.
        """
        normalizar_filtro_rv(self.filtro_rv, self.rubro_rv)
        return self
