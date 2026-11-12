"""Rutas HTTP de autenticación (`/api/v1/auth`).

Expone el registro, el ingreso, el refresco de sesión y el cierre de sesión
(teléfono + Clave de 4 dígitos). La validación de entrada es estricta en
servidor (DTOs Pydantic) y la lógica reside en el service. Los tokens de sesión
se entregan en cookies Secure/HttpOnly/SameSite; nunca en el cuerpo ni para
almacenarse en localStorage (Req 1.11).
Requisitos: 1.2-1.7, 1.10, 1.11, 1.13.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.cookies import clear_session_cookies, set_session_cookies
from app.auth.dto import (
    CambioClaveRequest,
    IngresoRequest,
    RegistroRequest,
    SesionResponse,
)
from app.auth.tokens import (
    TOKEN_TYPE_REFRESH,
    TokenExpiradoError,
    TokenInvalidoError,
    decodificar_sesion,
    emitir_sesion,
    sesion_vencida,
)
from app.common.database import get_session
from app.common.errors import CredencialesInvalidasError
from app.common.logging import log_event
from app.common.security import get_current_user_id

logger = logging.getLogger("cima.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _fijar_cookies(
    response: Response, profile_id: uuid.UUID, auth_time: datetime | None = None
) -> None:
    """Emite el par access + refresh en cookies seguras (Req 1.10, 1.14).

    Sin `auth_time` es un ingreso nuevo; en un refresco se conserva el original.
    """
    sesion = emitir_sesion(profile_id, auth_time)
    set_session_cookies(
        response,
        access_token=sesion.access_token,
        refresh_token=sesion.refresh_token,
        refresh_max_age=sesion.refresh_max_age,
    )


def _emitir_sesion(response: Response, sesion: SesionResponse) -> SesionResponse:
    """Abre una sesión nueva en cookies seguras para el titular dado."""
    _fijar_cookies(response, sesion.id)
    return sesion


@router.post("/registro", response_model=SesionResponse, status_code=status.HTTP_201_CREATED)
async def registro(
    data: RegistroRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> SesionResponse:
    """Crea una cuenta con teléfono y Clave y abre sesión (Req 1.2-1.5, 1.11)."""
    sesion = await service.registrar(db, data)
    return _emitir_sesion(response, sesion)


@router.post("/ingreso", response_model=SesionResponse)
async def ingreso(
    data: IngresoRequest,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> SesionResponse:
    """Autentica por teléfono + Clave y abre sesión (Req 1.6, 1.7, 1.11)."""
    sesion = await service.ingresar(db, data)
    return _emitir_sesion(response, sesion)


@router.post("/refresco", response_model=SesionResponse)
async def refresco(
    response: Response,
    cima_refresh: str | None = Cookie(default=None),
) -> SesionResponse:
    """Rota el refresh token y emite un nuevo access token (Req 1.11, 1.14).

    Lee el refresh token de la cookie `HttpOnly`. El refresh vence a los 30 min
    de la última actividad: si venció, la sesión expiró por inactividad y hay que
    volver a autenticarse (Req 1.14). También se rechaza si la sesión alcanzó su
    tope absoluto desde el ingreso. En todos los casos la respuesta es el error
    genérico de credenciales inválidas, sin detalle.
    """
    if not cima_refresh:
        raise CredencialesInvalidasError(internal_detail="missing refresh cookie")
    try:
        datos = decodificar_sesion(cima_refresh, TOKEN_TYPE_REFRESH)
    except TokenExpiradoError as exc:
        # Sin PII: el token vencido no se registra ni se decodifica sin verificar.
        log_event(logger, "auth_sesion_expirada_por_inactividad")
        raise CredencialesInvalidasError(internal_detail="refresh token expired") from exc
    except TokenInvalidoError as exc:
        raise CredencialesInvalidasError(internal_detail="invalid refresh token") from exc

    if sesion_vencida(datos.auth_time):
        log_event(logger, "auth_sesion_tope_absoluto", profile_id=str(datos.profile_id))
        raise CredencialesInvalidasError(internal_detail="session absolute lifetime reached")

    # Rotación: nuevos access y refresh (nuevo jti), conservando la hora del ingreso.
    _fijar_cookies(response, datos.profile_id, datos.auth_time)
    return SesionResponse(id=datos.profile_id, telefono="")


@router.get("/sesion", response_model=SesionResponse)
async def sesion(
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> SesionResponse:
    """Restaura la sesión vigente sin volver a pedir la Clave (Req 2.6).

    Valida el access token de la cookie (vía `get_current_user_id`). Si la
    sesión expiró o no existe, la dependencia responde con error de autorización
    para que el cliente redirija al flujo de autenticación conservando el
    destino (Req 2.7, 10.1, 10.2). El teléfono no se incluye aquí: la identidad
    la aporta el token y el Perfil se consulta por su propio endpoint.
    """
    return SesionResponse(id=current_user_id, telefono="")


@router.post("/salir", status_code=status.HTTP_204_NO_CONTENT)
async def salir(response: Response) -> Response:
    """Cierra la sesión eliminando las cookies de sesión (Req 1.13)."""
    clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/clave", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_clave(
    data: CambioClaveRequest,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Cambia la Clave del usuario autenticado; exige la Clave actual (Req 1.15)."""
    await service.cambiar_clave(db, current_user_id, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
