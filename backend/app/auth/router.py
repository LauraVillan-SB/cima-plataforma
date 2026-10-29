"""Rutas HTTP de autenticación (`/api/v1/auth`).

Expone el registro, el ingreso, el refresco de sesión y el cierre de sesión
(teléfono + Clave de 4 dígitos). La validación de entrada es estricta en
servidor (DTOs Pydantic) y la lógica reside en el service. Los tokens de sesión
se entregan en cookies Secure/HttpOnly/SameSite; nunca en el cuerpo ni para
almacenarse en localStorage (Req 1.11).
Requisitos: 1.2-1.7, 1.10, 1.11, 1.13.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.cookies import clear_session_cookies, set_session_cookies
from app.auth.dto import IngresoRequest, RegistroRequest, SesionResponse
from app.auth.tokens import (
    TOKEN_TYPE_REFRESH,
    TokenInvalidoError,
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
)
from app.common.database import get_session
from app.common.errors import CredencialesInvalidasError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _emitir_sesion(response: Response, sesion: SesionResponse) -> SesionResponse:
    """Emite access + refresh tokens en cookies seguras para la sesión dada."""
    set_session_cookies(
        response,
        access_token=crear_access_token(sesion.id),
        refresh_token=crear_refresh_token(sesion.id),
    )
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
    """Rota el refresh token y emite un nuevo access token (Req 1.11).

    Lee el refresh token de la cookie `HttpOnly`; si falta o es inválido/expirado
    responde con el error genérico de credenciales inválidas, sin detalle.
    """
    if not cima_refresh:
        raise CredencialesInvalidasError(internal_detail="missing refresh cookie")
    try:
        profile_id = decodificar_token(cima_refresh, TOKEN_TYPE_REFRESH)
    except TokenInvalidoError as exc:
        raise CredencialesInvalidasError(internal_detail="invalid refresh token") from exc

    # Rotación: se emiten nuevos access y refresh (nuevo jti) en cada refresco.
    set_session_cookies(
        response,
        access_token=crear_access_token(profile_id),
        refresh_token=crear_refresh_token(profile_id),
    )
    return SesionResponse(id=profile_id, telefono="")


@router.post("/salir", status_code=status.HTTP_204_NO_CONTENT)
async def salir(response: Response) -> Response:
    """Cierra la sesión eliminando las cookies de sesión (Req 1.13)."""
    clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
