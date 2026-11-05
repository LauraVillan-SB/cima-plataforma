"""Modelos ORM del Conversion Service.

`conversion_intents` registra la intención del Usuario de adquirir un
Microseguro (Req 5.5). CIMA no emite pólizas ni cobra: solo guarda el interés
como dato para análisis. Es idempotente por `client_event_id` y tiene una
restricción UNIQUE(profile_id, path_id, option_code) para no duplicar la misma
selección por ruta y Usuario. El contenido registrado no incluye PII.

`no_offer_events` registra la ausencia de oferta para un tipo de actividad
(Req 5.8), con el tipo solicitado pero sin PII, para análisis posterior.
Requisitos: 5.5, 5.6, 5.8.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base
from app.conversion.constants import INCENTIVE_STATUS_PENDIENTE


class ConversionIntent(Base):
    """Intención de conversión a Microseguro, sin PII y sin emisión (Req 5.5)."""

    __tablename__ = "conversion_intents"
    __table_args__ = (
        # Una sola intención por ruta, Usuario y opción seleccionada.
        UniqueConstraint(
            "profile_id",
            "path_id",
            "option_code",
            name="uq_conversion_intent_profile_path_option",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular, verificado contra el Usuario autenticado (anti-BOLA, Req 5.5).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje completada que originó la oferta.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Código de la opción de Microseguro del catálogo estático.
    option_code: Mapped[str] = mapped_column(String(64))

    # Clave de idempotencia; los reintentos reutilizan el valor (Req 5.6).
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NoOfferEvent(Base):
    """Ausencia de oferta de Microseguro para un tipo de actividad (Req 5.8)."""

    __tablename__ = "no_offer_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tipo de cultivo o comercio solicitado para el que no hubo oferta.
    activity_type: Mapped[str] = mapped_column(String(32), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Incentive(Base):
    """Incentivo asociado a una ruta completada y su estado de entrega (Req 5.1–5.3).

    Único por (profile_id, path_id): a cada Usuario le corresponde un único
    incentivo por ruta. `delivery_status` es `entregado` o `pendiente`;
    `retry_count` cuenta los intentos de entrega fallidos (máx. 3 antes de quedar
    pendiente definitivo para resolución posterior). El estado de completitud de
    la ruta vive en el Learning Service (`path_progress`) y nunca se altera aquí
    (Req 5.2, 5.3). No contiene PII: solo identificadores internos y metadatos.
    """

    __tablename__ = "incentives"
    __table_args__ = (
        UniqueConstraint("profile_id", "path_id", name="uq_incentive_profile_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular, verificado contra el Usuario autenticado (anti-BOLA).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje completada que origina el incentivo.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Tipo de incentivo asociado a la ruta (metadato, sin precio ni emisión).
    incentive_type: Mapped[str] = mapped_column(String(64))

    # Estado de entrega: `entregado` o `pendiente` (default pendiente hasta
    # confirmar la entrega observable, Req 5.1).
    delivery_status: Mapped[str] = mapped_column(
        String(16), default=INCENTIVE_STATUS_PENDIENTE
    )

    # Número de intentos de entrega fallidos acumulados (0–3, Req 5.2, 5.3).
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
