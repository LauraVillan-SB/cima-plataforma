"""Rutas HTTP del Certification Service (`/api/v1/certificados`).

Expone la emisión de un Certificado (condicionada e idempotente) y su consulta
con autorización por titular. La autorización es siempre de backend: ambas
operaciones usan la identidad autenticada (`current_user_id`), nunca un id del
cliente (anti-BOLA).
Requisitos: 6.1–6.7.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.certification import service
from app.certification.dto import CertificateResponse, IssueCertificateRequest
from app.common.database import get_session
from app.common.security import get_current_user_id

router = APIRouter(prefix="/api/v1/certificados", tags=["certificados"])


@router.post("", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
async def emitir_certificado(
    data: IssueCertificateRequest,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CertificateResponse:
    """Emite el Certificado de una ruta para el Usuario autenticado.

    Solo procede si la ruta está completa y la evaluación fue aprobada (Req 6.1,
    6.2). Es idempotente por (titular, ruta): reintentar devuelve el mismo
    Certificado (Req 6.4). El titular proviene de la sesión (anti-BOLA, Req 6.5).
    """
    return await service.issue_certificate(db, current_user_id, data.path_id)


@router.get("/{certificado_id}", response_model=CertificateResponse)
async def obtener_certificado(
    certificado_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> CertificateResponse:
    """Devuelve un Certificado solo si el Usuario autenticado es su titular.

    Si no existe, responde "no encontrado" sin filtrar datos de otros Perfiles
    (Req 6.6). Si es de otro titular, rechaza con error de autorización y registra
    el intento sin exponer PII ni el contenido del Certificado (Req 6.7).
    """
    return await service.get_certificate(db, current_user_id, certificado_id)
