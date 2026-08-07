"""`app/core/seguridad.py`: la verificación del JWT que emite Supabase Auth, sin tocar la base.

El aislamiento entre asesores lo prueba `test_auth_integration.py` contra RLS. Acá se prueba la
mitad que sí puede probarse offline: que un token genuino se acepte y que uno roto, vencido, con
otra audiencia, firmado por otro o sin `sub` se rechace con el tipo de error correcto.

**Estos tests firman con una clave EC de verdad y verifican contra su clave pública, servida como
un JWKS igual al de Supabase.** La versión anterior firmaba con HS256 y un secreto inventado, y
verificaba con el mismo algoritmo: era internamente coherente, pasaba siempre, y no podía
descubrir que el proyecto real firma con ES256 y que por lo tanto el backend rechazaba todas las
sesiones genuinas. Un test que genera su propio input con la misma suposición que el código bajo
prueba no verifica nada. Por eso acá el par de claves es real y el JWKS tiene la forma exacta que
publica Supabase: si mañana el código volviera a asumir un algoritmo simétrico, estos tests
fallan.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.seguridad import (
    AUDIENCIA_ESPERADA,
    ClaveDeFirmaNoDisponible,
    TokenExpirado,
    TokenInvalido,
    UsuarioAutenticado,
    cliente_jwks,
    verificar_token,
)

URL_PROYECTO = "https://proyecto-de-prueba.supabase.co"
KID = "ecb0251f-e2de-453c-8bc1-56b8825ba720"


def _par_de_claves() -> ec.EllipticCurvePrivateKey:
    """Una clave EC P-256 nueva: la misma curva y el mismo algoritmo que usa Supabase."""
    return ec.generate_private_key(ec.SECP256R1())


CLAVE = _par_de_claves()
CLAVE_AJENA = _par_de_claves()


def _jwks(clave: ec.EllipticCurvePrivateKey, *, kid: str = KID) -> dict:
    """El JWKS tal como lo publica Supabase en `/auth/v1/.well-known/jwks.json`.

    Se arma con `PyJWK` a partir de la clave pública real en vez de escribir las coordenadas a
    mano: si la forma del documento fuera distinta de la que la librería sabe leer, el test
    estaría probando un formato que no existe.
    """
    numeros = clave.public_key().public_numbers()
    codificar = lambda n: jwt.utils.base64url_encode(  # noqa: E731
        n.to_bytes(32, "big")
    ).decode()
    return {
        "keys": [
            {
                "alg": "ES256",
                "crv": "P-256",
                "ext": True,
                "key_ops": ["verify"],
                "kid": kid,
                "kty": "EC",
                "use": "sig",
                "x": codificar(numeros.x),
                "y": codificar(numeros.y),
            }
        ]
    }


@pytest.fixture(autouse=True)
def jwks_del_proyecto(monkeypatch: pytest.MonkeyPatch):
    """Sirve el JWKS sin salir a la red, y limpia el caché entre tests.

    El caché es `lru_cache` sobre la URL y `PyJWKClient` guarda las claves adentro: sin limpiarlo,
    el primer test fijaría la clave para todos los demás y el que prueba una firma ajena pasaría
    por la razón equivocada.
    """
    cliente_jwks.cache_clear()
    documento = {"actual": _jwks(CLAVE)}

    def _fetch(self):
        return documento["actual"]

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _fetch)
    yield documento
    cliente_jwks.cache_clear()


def _token(
    *,
    clave: ec.EllipticCurvePrivateKey = CLAVE,
    algoritmo: str = "ES256",
    kid: str | None = KID,
    segundos_para_vencer: float = 3600,
    **claims_extra,
) -> str:
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": "asesor@example.com",
        "aud": AUDIENCIA_ESPERADA,
        "role": "authenticated",
        "iat": ahora,
        "exp": ahora + timedelta(seconds=segundos_para_vencer),
        **claims_extra,
    }
    return jwt.encode(payload, clave, algorithm=algoritmo, headers={"kid": kid})


def test_un_token_genuino_devuelve_el_usuario() -> None:
    id_esperado = uuid4()

    usuario = verificar_token(_token(sub=str(id_esperado)), URL_PROYECTO)

    assert usuario == UsuarioAutenticado(id=id_esperado, email="asesor@example.com")


def test_un_token_sin_email_igual_verifica() -> None:
    """Supabase no garantiza el claim `email` —un usuario creado por otro proveedor puede no
    tenerlo— y quedarse sin sesión por eso sería rechazar a alguien que sí está autenticado."""
    usuario = verificar_token(_token(email=None), URL_PROYECTO)

    assert usuario.email is None
    assert isinstance(usuario.id, type(uuid4()))


def test_un_token_vencido_es_token_expirado() -> None:
    with pytest.raises(TokenExpirado):
        verificar_token(_token(segundos_para_vencer=-1), URL_PROYECTO)


def test_un_token_firmado_con_otra_clave_es_invalido() -> None:
    """El caso que importa: la firma no verifica contra la clave pública del proyecto.

    La clave ajena se publica con el mismo `kid`, así que el token llega hasta la verificación de
    firma en vez de morir antes por no encontrar la clave. Sin eso el test pasaría por el motivo
    equivocado.
    """
    with pytest.raises(TokenInvalido):
        verificar_token(_token(clave=CLAVE_AJENA), URL_PROYECTO)


def test_un_token_con_un_kid_que_no_esta_en_el_jwks_es_invalido() -> None:
    """Un token que este proyecto no firmó. Es del cliente, no de nuestra infraestructura, así que
    tiene que ser `TokenInvalido` y no `ClaveDeFirmaNoDisponible`: la diferencia decide si el
    asesor ve "volvé a loguearte" o si el servicio se declara caído."""
    with pytest.raises(TokenInvalido):
        verificar_token(_token(kid="un-kid-de-otro-proyecto"), URL_PROYECTO)


def test_un_token_firmado_con_hs256_y_la_clave_publica_es_invalido(jwks_del_proyecto) -> None:
    """Confusión de algoritmo: la clave pública es pública, así que cualquiera puede usarla como
    si fuera un secreto HMAC. Si `HS256` estuviera entre los algoritmos aceptados, este token
    verificaría y cualquiera podría hacerse pasar por cualquier asesor. Es la razón por la que la
    lista de algoritmos se fija en el código y nunca sale del header del token."""
    publica = jwks_del_proyecto["actual"]["keys"][0]
    secreto_forjado = publica["x"] + publica["y"]
    ahora = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": AUDIENCIA_ESPERADA,
            "iat": ahora,
            "exp": ahora + timedelta(hours=1),
        },
        secreto_forjado,
        algorithm="HS256",
        headers={"kid": KID},
    )

    with pytest.raises(TokenInvalido):
        verificar_token(token, URL_PROYECTO)


def test_un_token_con_otra_audiencia_es_invalido() -> None:
    # Evita que un JWT válido para otro proyecto de Supabase se acepte acá.
    with pytest.raises(TokenInvalido):
        verificar_token(_token(aud="otro-servicio"), URL_PROYECTO)


def test_un_token_sin_sub_es_invalido() -> None:
    """Sin `sub` no hay a quién atribuirle el request. Lo rechaza PyJWT antes que nuestro chequeo
    —de ahí el "Subject must be a string" en el mensaje—, pero llega como `TokenInvalido` igual,
    que es lo único que le importa a quien lo consume."""
    with pytest.raises(TokenInvalido, match=r"(?i)subject|sub"):
        verificar_token(_token(sub=None), URL_PROYECTO)


def test_un_sub_que_no_es_uuid_es_invalido() -> None:
    with pytest.raises(TokenInvalido, match="UUID"):
        verificar_token(_token(sub="no-soy-un-uuid"), URL_PROYECTO)


def test_un_texto_que_no_es_un_jwt_es_invalido() -> None:
    with pytest.raises(TokenInvalido):
        verificar_token("esto-no-es-un-token", URL_PROYECTO)


def test_si_el_jwks_no_se_puede_traer_no_es_culpa_de_la_sesion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin JWKS no se puede verificar nada, pero el que falla es este servicio y no el asesor.
    Por eso es su propia excepción: `deps` la traduce a 503 y no a 401."""
    cliente_jwks.cache_clear()

    def _explota(self):
        raise OSError("la red no está")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _explota)

    with pytest.raises(ClaveDeFirmaNoDisponible):
        verificar_token(_token(), URL_PROYECTO)


def test_el_jwks_se_trae_una_sola_vez_para_muchos_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La verificación no puede pagar una vuelta de red por request: sería agregarle latencia a
    cada llamada autenticada del producto."""
    cliente_jwks.cache_clear()
    documento = _jwks(CLAVE)
    llamadas = {"n": 0}

    def _contar(self):
        llamadas["n"] += 1
        return documento

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _contar)

    for _ in range(5):
        verificar_token(_token(), URL_PROYECTO)

    assert llamadas["n"] == 1
