"""Modelos ORM del Learning Service.

Define las entidades de micro-aprendizaje:
- `microcapsules`: cápsulas cortas (3–5 min) clasificadas en exactamente un tema
  y asociadas a tipos de cultivo/comercio (Req 4.1, 4.2, 4.3).
- `learning_paths`: secuencia ordenada de microcápsulas con umbral de aprobación
  (Req 4.10, 7.3).
- `path_progress`: progreso de un Usuario sobre una ruta, con las microcápsulas
  finalizadas y la marca de completitud (Req 4.6, 4.10).

La columna `embedding` (PgVector) se añadirá en una iteración posterior para la
recuperación por similitud (Req 17.4) sin cambiar el contrato de API; no se crea
aún para no acoplar este slice a la dimensión del modelo de embeddings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base


class Microcapsule(Base):
    """Microcápsula de aprendizaje: contenido corto de un único tema.

    La duración se acota a 180–300 s a nivel de dominio (Req 4.1) y el tema es
    exactamente uno de la allowlist (Req 4.2). `activity_tags` lista los tipos de
    cultivo o comercio a los que aplica la cápsula (Req 4.3).
    """

    __tablename__ = "microcapsules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tema único de la cápsula (valor de la allowlist de temas, Req 4.2).
    topic: Mapped[str] = mapped_column(String(32), index=True)

    # Tipos de cultivo o comercio asociados a la cápsula (Req 4.3).
    activity_tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)

    # Duración del contenido en segundos; acotada a 180–300 (Req 4.1).
    duration_sec: Mapped[int] = mapped_column(Integer)

    # Relevancia para el orden de selección (mayor = más relevante, Req 4.3).
    relevance: Mapped[float] = mapped_column(Numeric(6, 3), default=0)

    # Nivel de dificultad (0 = base). Permite simplificar la siguiente cápsula
    # en la adaptación por señales de progreso (Req 17.1).
    difficulty: Mapped[int] = mapped_column(Integer, default=0)

    # Contenido que se muestra al Usuario. Es texto plano (el cliente nunca lo
    # interpreta como HTML) y debe poder leerse en voz alta (Req 13.4). Las columnas
    # son opcionales para no invalidar cápsulas creadas antes de existir el contenido.
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    paragraphs: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )
    key_points: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )

    # Video de apoyo opcional de YouTube: solo el identificador de 11 caracteres
    # (validado) más el título y el canal para dar crédito. Nunca se guarda una URL
    # libre; el enlace de incrustación lo construye el backend (SSRF/XSS).
    video_id: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    video_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    video_channel: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Fecha de publicación; desempata el orden ante igual relevancia (Req 4.3).
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LearningPath(Base):
    """Ruta de aprendizaje: secuencia ordenada de microcápsulas."""

    __tablename__ = "learning_paths"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Secuencia ordenada de identificadores de microcápsulas que forman la ruta.
    microcapsule_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid()), default=list
    )

    # Umbral de aprobación de la evaluación asociada (0–100, default 70, Req 7.3).
    pass_threshold: Mapped[int] = mapped_column(Integer, default=70)


class PathProgress(Base):
    """Progreso de un Usuario sobre una ruta de aprendizaje.

    Registra las microcápsulas finalizadas y marca la ruta como completada
    cuando todas tienen finalización (Req 4.10). `last_completed_step` da soporte
    a la resiliencia offline (Req 2.8, 18.4). La unicidad (profile_id, path_id)
    garantiza una sola fila de progreso por Usuario y ruta.
    """

    __tablename__ = "path_progress"
    __table_args__ = (
        # Una sola fila de progreso por Usuario y ruta (ya creada en la migración 0004).
        UniqueConstraint("profile_id", "path_id", name="uq_path_progress_profile_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Titular del progreso; se ancla a la identidad autenticada (anti-BOLA).
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Ruta de aprendizaje a la que pertenece este progreso.
    path_id: Mapped[uuid.UUID] = mapped_column(index=True)

    # Microcápsulas finalizadas por el Usuario en esta ruta (conjunto sin orden).
    completed_microcapsules: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid()), default=list
    )

    # Verdadero cuando todas las microcápsulas de la ruta están finalizadas (Req 4.10).
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Último paso completado (índice en la secuencia); resiliencia offline (Req 18.4).
    last_completed_step: Mapped[int] = mapped_column(Integer, default=0)

    # Señales de progreso para la adaptación (Req 17.1, 17.2). Se capturan de la
    # propia actividad del Usuario; no se le pide ningún dato adicional.
    # Veces que repitió una microcápsula ya finalizada.
    repeat_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Veces que excedió el tiempo esperado al finalizar una microcápsula.
    slow_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Verdadero si la última finalización dio señal (repetición o exceso de tiempo):
    # la microcápsula siguiente se entrega simplificada y a ritmo lento. Una
    # finalización posterior sin señal lo devuelve a falso.
    needs_simplification: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # Último `client_event_id` recibido por microcápsula ({id_cápsula: id_evento}).
    # Distingue un reintento de red de la misma petición (no es repetición) de una
    # repetición real, que llega con otro `client_event_id` (Req 4.7).
    finalization_events: Mapped[dict[str, str]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProfileActivityPrompt(Base):
    """Cuántas veces se le pidió al Usuario su tipo de cultivo o comercio (Req 4.8, 4.9).

    Una fila por Perfil. El contador se incrementa de forma atómica y se detiene en
    `MAX_PROFILE_PROMPTS`; agotadas las solicitudes se entrega el tema general sin
    personalización. No contiene PII: solo el identificador y un entero.
    """

    __tablename__ = "profile_activity_prompts"

    profile_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)

    prompt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningEventOutbox(Base):
    """Evento de dominio pendiente de registro en Metrics (Req 4.7, 8.4).

    Si el registro de `microcapsula_completada` o `ruta_completada` sigue fallando
    tras los reintentos acotados, el evento se conserva aquí para registrarlo después
    sin pérdida de datos. `client_event_id` es único: guardar el mismo evento dos veces
    no lo duplica. Solo lleva identificadores y el tipo de evento, sin PII. La fila se
    borra cuando el evento se registra.
    """

    __tablename__ = "learning_event_outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Clave de idempotencia del evento; la misma que se enviará a Metrics.
    client_event_id: Mapped[uuid.UUID] = mapped_column(unique=True)

    # Titular del evento, tomado de la sesión autenticada.
    profile_id: Mapped[uuid.UUID] = mapped_column(index=True)

    event_type: Mapped[str] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
