"""Catálogo de contenido de ejemplo del Learning Service.

Define las microcápsulas, rutas y evaluaciones con las que arranca CIMA. Es contenido de
referencia **pendiente de revisión por la Escuela de Sostenibilidad e Inclusión**: está
escrito en español coloquial colombiano, es texto plano, no promete resultados ni da
cifras que no pueda respaldar, y no ofrece asesoría financiera personalizada. CIMA educa
y mide interés: no vende seguros ni procesa pagos (alcance del proyecto).

El contenido principal es el texto; el video de YouTube es un complemento opcional que
solo se carga con un identificador verificado (ver `VideoSpec`). Sin conexión el texto
sigue funcionando.

Cobertura actual: actividad general (respaldo, Req 4.4), café y tienda de barrio con los
tres temas, el Módulo 1 para el campo y la tienda, y una cápsula de ejemplo con su ruta
para cada una de las demás actividades permitidas (plátano, aguacate, cacao, arroz, maíz,
ganadería, hortalizas, panadería y miscelánea).
Requisitos: 4.1, 4.2, 4.3, 4.4, 7.1, 13.4.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Final

from app.learning.constants import (
    GENERAL_TAG,
    MEDIA_FILE_PATTERN,
    TOPIC_ADAPTACION_CLIMA,
    TOPIC_FINANZAS,
    TOPIC_GESTION_RIESGOS,
    YOUTUBE_VIDEO_ID_PATTERN,
)

# Palabras por segundo de lectura en voz alta, pausada (~132 palabras por minuto). De ahí
# se calcula la duración de cada microcápsula, que debe quedar entre 180 y 300 s (Req 4.1).
WORDS_PER_SECOND: Final = 2.2

# Espacio de nombres fijo: los identificadores salen de `uuid5(slug)`, así que cargar el
# catálogo varias veces actualiza las mismas filas en lugar de duplicarlas.
CATALOG_NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "cima.learning.catalog")


@dataclass(frozen=True)
class VideoSpec:
    """Video de apoyo de YouTube. Solo se carga si un humano verificó que existe.

    `video_id` debe ser el identificador de 11 caracteres. `title` y `channel` dan el
    crédito al autor y deben coincidir con lo que informa YouTube (oEmbed).
    """

    video_id: str
    title: str
    channel: str

    def __post_init__(self) -> None:
        if not re.fullmatch(YOUTUBE_VIDEO_ID_PATTERN, self.video_id):
            raise ValueError("Identificador de video de YouTube inválido.")


@dataclass(frozen=True)
class CapsuleSpec:
    """Definición de una microcápsula del catálogo."""

    slug: str
    topic: str
    tags: tuple[str, ...]
    relevance: float
    title: str
    summary: str
    paragraphs: tuple[str, ...]
    key_points: tuple[str, ...]
    video: VideoSpec | None = None
    # Video propio en la carpeta de medios: solo el nombre del archivo (allowlist).
    video_file: str | None = None

    def __post_init__(self) -> None:
        if self.video_file is not None and not re.fullmatch(MEDIA_FILE_PATTERN, self.video_file):
            raise ValueError("Nombre de archivo de video inválido.")

    @property
    def id(self) -> uuid.UUID:
        """Identificador estable derivado del `slug`."""
        return uuid.uuid5(CATALOG_NAMESPACE, f"capsule:{self.slug}")

    @property
    def word_count(self) -> int:
        """Palabras que se leen en voz alta: párrafos y puntos clave."""
        return sum(len(text.split()) for text in (*self.paragraphs, *self.key_points))

    @property
    def duration_sec(self) -> int:
        """Duración estimada de lectura en segundos."""
        return round(self.word_count / WORDS_PER_SECOND)


@dataclass(frozen=True)
class QuestionSpec:
    """Pregunta de evaluación con una sola opción correcta."""

    prompt: str
    options: tuple[str, str, str]
    correct: int


@dataclass(frozen=True)
class PathSpec:
    """Ruta de aprendizaje: cápsulas en orden y su evaluación."""

    slug: str
    capsule_slugs: tuple[str, ...]
    questions: tuple[QuestionSpec, ...]
    title: str
    summary: str
    pass_threshold: int = 70

    @property
    def id(self) -> uuid.UUID:
        """Identificador estable derivado del `slug`."""
        return uuid.uuid5(CATALOG_NAMESPACE, f"path:{self.slug}")


# --------------------------------------------------------------------------- #
# Tema general (respaldo para quien no tiene actividad o no tiene contenido propio)
# --------------------------------------------------------------------------- #
_GENERAL_CLIMA = CapsuleSpec(
    slug="general-leer-el-clima",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=(GENERAL_TAG,),
    relevance=5.0,
    title="Aprende a leer las señales del clima de tu zona",
    summary="Usa el pronóstico y una libreta sencilla para saber qué viene y prepararte a tiempo.",
    paragraphs=(
        "Antes, mucha gente sabía cuándo sembrar o cuándo esperar la lluvia mirando el "
        "calendario de siempre. Hoy eso ya no alcanza: las lluvias llegan antes o después, "
        "hay semanas de sol fuerte y luego aguaceros que lo arrasan todo. La buena noticia "
        "es que puedes ir un paso adelante si aprendes a leer las señales de tu zona y a "
        "tomar decisiones con tiempo, no cuando el problema ya llegó.",
        "Empieza por lo más simple: una libreta. Anota cada semana si llovió, cuánto "
        "aproximadamente, si hizo mucho calor y si hubo vientos fuertes. Con unos meses de "
        "apuntes vas a ver patrones propios de tu terreno que ningún pronóstico general te "
        "da. Un tarro recto puesto al aire libre te sirve de pluviómetro casero: con una "
        "regla mides cuántos centímetros de agua se juntaron.",
        "Después, mira el pronóstico oficial. En Colombia el IDEAM publica pronósticos y "
        "avisos del tiempo, y también informa cuando se espera un fenómeno de El Niño o de "
        "La Niña. El Niño suele traer menos lluvia y más calor; La Niña, más lluvia y más "
        "riesgo de inundaciones y deslizamientos. No tienes que entender toda la ciencia: "
        "basta con saber cuál viene para ajustar tus decisiones.",
        "Conversa también con tus vecinos y con los técnicos de tu zona. Lo que uno ve, "
        "otro lo confirma, y entre todos se detectan los cambios más rápido. Cuando sabes "
        "qué viene puedes decidir con calma: si adelantas o atrasas una siembra, si guardas "
        "agua, si reparas un techo o un canal antes de las lluvias, o si separas un dinero "
        "para la temporada difícil.",
        "Piensa en tu última temporada difícil. ¿Qué señales hubo antes y no las anotaste? "
        "Si hubieras tenido una libreta, ¿qué habrías hecho distinto? Empieza hoy con la "
        "primera hoja: la fecha y cómo estuvo el tiempo.",
        "Imagina una familia que anota durante un año los días de lluvia fuerte y descubre "
        "que las siembras de cierto mes se le pierden casi siempre. Con esa libreta puede "
        "mover la fecha de siembra unas semanas y proteger su cosecha. No necesitó aparatos "
        "ni estudios, solo constancia. Haz lo mismo con lo que más te importe, tu cultivo, "
        "tu local o tu casa, y revisa tus apuntes una vez al mes.",
    ),
    key_points=(
        "Una libreta con la lluvia y el calor de cada semana te enseña los patrones de tu terreno.",
        "Un tarro recto al aire libre sirve de pluviómetro casero.",
        "El IDEAM avisa cuándo se espera El Niño o La Niña: infórmate antes de decidir.",
        "Decidir con tiempo cuesta menos que arreglar cuando el daño ya pasó.",
    ),
)

_GENERAL_AGUA = CapsuleSpec(
    slug="general-cuidar-el-agua",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=(GENERAL_TAG,),
    relevance=4.5,
    title="Cuida el agua: guarda y usa mejor cada gota",
    summary="Ideas sencillas para juntar agua de lluvia, no desperdiciarla y llegar mejor a los meses secos.",
    paragraphs=(
        "El agua es lo primero que falta en una sequía y lo que más sobra en una "
        "inundación. Por eso aprender a guardarla y a usarla bien es una de las mejores "
        "formas de adaptarse al clima. No hace falta una gran obra: con pequeños cambios "
        "puedes tener más agua cuando más la necesitas y perder menos cuando llueve fuerte.",
        "Una forma fácil es recoger el agua lluvia del techo. Con canales limpios y un "
        "tanque o canecas con tapa para que no se críen zancudos, puedes juntar agua para "
        "el aseo, para los animales o para regar. Antes de usarla para tomar necesita un "
        "tratamiento, así que consulta en el puesto de salud o en la oficina de asistencia "
        "técnica agropecuaria de tu municipio cómo hacerlo de forma segura.",
        "Riega con cabeza. Regar muy temprano en la mañana o al final de la tarde reduce "
        "la evaporación. Si puedes, usa riego por goteo o mangueras con pocos huecos en "
        "lugar de dejar correr el agua; así llega a la raíz y no se pierde. Cubrir el suelo "
        "con hojas secas, pasto cortado o restos de cosecha ayuda a que la tierra guarde la "
        "humedad por más tiempo.",
        "Cuida también de dónde viene el agua. Mantener la vegetación cerca de "
        "nacimientos, quebradas y reservorios protege la fuente y evita que el suelo se "
        "lave con las lluvias fuertes. Evita tirar basura, envases de agroquímicos o "
        "residuos de la finca cerca del agua: contaminarla hoy es quedarte sin ella mañana.",
        "En tu casa o negocio revisa las llaves y las mangueras: una gotera pequeña "
        "desperdicia muchos litros al mes, arreglarla casi no cuesta y se nota en la "
        "cuenta. Piensa de dónde sale el agua que usas y cuántos días aguantarías si "
        "faltara; con esa respuesta sabrás cuánto necesitas guardar.",
        "Imagina una finca pequeña con un techo de zinc de buen tamaño. En cada aguacero, "
        "si los canales están limpios, esa agua puede llenar una o varias canecas en pocos "
        "minutos. Guardada y bien tapada, sirve después para regar unas matas, lavar "
        "herramientas o dar de beber a los animales en una semana seca. Un poco de "
        "organización convierte la lluvia fuerte, que antes era un problema, en una "
        "reserva útil.",
    ),
    key_points=(
        "Recoger agua lluvia en tanques con tapa te da reserva para la época seca.",
        "Riega temprano o al final de la tarde y cubre el suelo para que no se seque.",
        "Protege nacimientos y quebradas: son tu fuente de agua.",
        "Revisar goteras y mangueras ahorra agua y plata.",
    ),
)

_GENERAL_PLAN_B = CapsuleSpec(
    slug="general-plan-b",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=(GENERAL_TAG,),
    relevance=4.0,
    title="Tu plan B para las temporadas difíciles",
    summary="Prepara lo básico antes de una emergencia para no tomar decisiones a la carrera.",
    paragraphs=(
        "Una helada, una inundación, una sequía larga o una plaga fuerte pueden llegar sin "
        "avisar. Cuando pasa, la gente toma decisiones apuradas: vender barato, endeudarse "
        "con quien preste o dejar de pagar lo importante. Tener un plan B, escrito y "
        "sencillo, te permite reaccionar con calma. No es ser pesimista: es cuidar lo que "
        "tanto esfuerzo te costó.",
        "Empieza por responder tres preguntas: ¿qué es lo que más me puede afectar en mi "
        "zona?, ¿qué necesito para seguir adelante las primeras semanas?, ¿a quién puedo "
        "llamar? Escribe las respuestas en una hoja. Incluye teléfonos útiles: familiares, "
        "vecinos, la alcaldía, la oficina de gestión del riesgo de tu municipio y los "
        "organismos de socorro de tu zona.",
        "Guarda lo importante en un lugar seguro: copias de tus documentos, de escrituras "
        "o contratos y de los papeles del negocio o de la finca, de preferencia en una "
        "bolsa plástica sellada y también fotografiados en tu celular. Si hay una "
        "emergencia no tendrás que correr a recuperar lo que no puedes perder.",
        "Define un fondo para imprevistos, aunque empiece con muy poco. Separar una "
        "pequeña parte de cada venta o de cada cosecha, siempre el mismo día, crea el "
        "hábito. Ese dinero no es para los gastos del mes: es para cuando el clima o el "
        "mercado te saquen del camino. Con el tiempo lo ideal es que alcance para cubrir "
        "varias semanas de gastos básicos.",
        "Practica el plan con tu familia o tu equipo: que todos sepan dónde están los "
        "papeles, a quién llamar y qué hacer primero. Un plan que solo conoce una persona "
        "no sirve si esa persona no está. Y pregúntate: ¿qué sería lo primero que perderías "
        "en una emergencia? Empieza el plan protegiendo eso.",
        "Imagina que una creciente te obliga a salir de tu casa en la noche. Si el plan "
        "está escrito, sabes quién lleva los documentos, adónde van los niños y a qué "
        "teléfono llamar. Si no lo está, se pierde tiempo valioso y se olvidan cosas "
        "importantes. Dedica una tarde tranquila a escribirlo con tu familia: es de las "
        "tareas que más tranquilidad dan y que menos cuestan. Cuéntaselo también a un "
        "vecino de confianza: si cada familia tiene su plan, todo el barrio responde mejor.",
    ),
    key_points=(
        "Un plan B escrito evita decisiones apuradas cuando llega la emergencia.",
        "Anota teléfonos de familiares, vecinos, la alcaldía y los organismos de socorro.",
        "Guarda copias de tus documentos y tómales fotos con el celular.",
        "Un fondo para imprevistos se arma poco a poco, siempre el mismo día.",
    ),
    # Short institucional de Seguros Bolívar sobre asumir riesgos con preparación. Se
    # verificó con oEmbed y se revisó su contenido: es educativo y no vende un producto.
    video=VideoSpec(
        video_id="mjJ95UBh0tk",
        title="¿Qué significa asumir un riesgo? Hágalo con preparación",
        channel="Seguros Bolivar",
    ),
)

# --------------------------------------------------------------------------- #
# Café
# --------------------------------------------------------------------------- #
_CAFE_CLIMA = CapsuleSpec(
    slug="cafe-sombrio-y-suelo",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=("cafe",),
    relevance=9.5,
    title="Proteger el cafetal: sombrío, suelo cubierto y lluvias fuertes",
    summary="Cómo el sombrío y el cuidado del suelo ayudan a tu cafetal frente a más calor y aguaceros.",
    paragraphs=(
        "El café es una planta sensible. El calor muy alto, las lluvias fuertes y las "
        "épocas secas largas afectan la floración, el llenado del grano y la calidad. Como "
        "el clima está cambiando, cuidar el cafetal ya no es solo fertilizar y cosechar a "
        "tiempo: también es protegerlo del sol, del agua que arrastra el suelo y de los "
        "cambios bruscos entre temporadas.",
        "El sombrío es una de las ayudas más sencillas. Los árboles bien ubicados, como el "
        "plátano, el guamo u otras especies que recomiende el técnico de tu zona, bajan la "
        "temperatura del cultivo, conservan la humedad del suelo y protegen del golpe "
        "directo de la lluvia. Pero ojo: demasiado sombrío tampoco conviene. Pregunta en el "
        "comité de cafeteros o con tu extensionista cuánta sombra le va bien a tu variedad "
        "y a tu altura.",
        "El suelo es tu bodega de agua y de nutrientes. En las laderas, una lluvia fuerte "
        "se lleva la tierra de arriba, que es la más rica. Para evitarlo, siembra siguiendo "
        "las recomendaciones de tu técnico y deja cobertura viva entre las calles del "
        "cafetal, como arvenses nobles, en lugar de limpiar hasta dejar la tierra pelada. "
        "La cobertura frena el agua, evita la erosión y mantiene el suelo fresco.",
        "Mira también tu cafetal con ojos de renovación. Las plantas muy viejas producen "
        "menos y aguantan peor los cambios del clima. Hablar con tu extensionista sobre "
        "renovar por zoca o por siembra, y sobre variedades adaptadas a tu zona, puede "
        "ayudarte a tener un cultivo más fuerte. Hazlo por lotes y no todo el cafetal a la "
        "vez, para no quedarte sin ingresos de un año para otro.",
        "Lleva el pulso del clima en tu finca: anota cuándo floreó cada lote, cuándo llovió "
        "fuerte y cuándo vino el verano. Con esos datos, cada año sabrás mejor cuándo "
        "fertilizar, cuándo esperar y cuándo prevenir. Pregúntate: ¿qué lote de mi cafetal "
        "sufre más con el sol o con la lluvia? Empieza por ahí.",
        "Imagina dos lotes de la misma finca: uno con sombra bien distribuida y otro a "
        "pleno sol. En una semana de calor fuerte, el segundo se estresa más y su suelo se "
        "seca primero. Pasar un rato mirando qué lote aguanta mejor te da pistas para "
        "decidir dónde conviene mejorar la sombra o la cobertura. Pide a tu extensionista "
        "que te acompañe a revisarlo: una visita puede ahorrarte años de prueba y error.",
    ),
    key_points=(
        "El sombrío bien manejado baja el calor y guarda la humedad, pero demasiado también perjudica.",
        "Dejar cobertura viva en el suelo frena la erosión cuando llueve fuerte.",
        "Renueva el cafetal por lotes y con orientación de tu extensionista.",
        "Anota las floraciones y las lluvias de cada lote para decidir mejor cada año.",
    ),
)

_CAFE_FINANZAS = CapsuleSpec(
    slug="cafe-las-cuentas-de-la-cosecha",
    topic=TOPIC_FINANZAS,
    tags=("cafe",),
    relevance=8.5,
    title="Las cuentas del café: qué entra y qué sale en cada cosecha",
    summary="Un registro sencillo para saber cuánto cuesta producir y cuánto te queda realmente.",
    paragraphs=(
        "Muchos caficultores saben cuánto vendieron, pero no cuánto les costó producir. Y "
        "sin saber el costo es difícil saber si se está ganando, empatando o perdiendo. "
        "Llevar las cuentas no es cosa de contadores: con un cuaderno y unos pocos hábitos "
        "puedes entender tu negocio y tomar mejores decisiones.",
        "Divide tus gastos en dos grupos. Los costos de producción son los de la finca: "
        "abonos, jornales de recolección, control de plagas, transporte, beneficio y "
        "mantenimiento. Los gastos del hogar son los de tu familia: comida, estudio, salud "
        "y servicios. Anótalos por separado desde el primer día, porque mezclarlos es la "
        "razón más común por la que parece que la plata no rinde.",
        "Registra cada venta: la fecha, la cantidad, el precio y a quién se la vendiste. Al "
        "final de la cosecha suma todo lo que entró y todo lo que gastaste en producir. La "
        "diferencia es lo que realmente te quedó. Si puedes, calcula también cuánto te "
        "costó producir cada carga o cada kilo: así sabrás desde qué precio de venta "
        "empiezas a ganar.",
        "El café se cosecha en ciertas épocas, pero los gastos son todo el año. Por eso "
        "conviene repartir lo que entra: separa una parte para los gastos de los meses de "
        "poca cosecha, otra para los insumos de la siguiente temporada y otra para un fondo "
        "de imprevistos. Si la cosecha fue buena, la tentación es gastar de más; si fue "
        "mala, hay que haber guardado antes.",
        "Cuidado con las deudas informales y con el gota a gota. Antes de pedir un crédito "
        "pregunta cuánto vas a pagar en total y a qué tasa, compara por lo menos dos "
        "opciones y no firmes lo que no entiendas. Un crédito debe ayudarte a producir, no "
        "ahogarte. Esta semana anota todo lo que gastes, la finca en una hoja y la casa en "
        "otra: en un mes tendrás una foto real de tu negocio.",
        "Imagina que en una cosecha entra mucha plata y parece que todo va bien. Al sumar, "
        "ves que los jornales, el abono y el transporte se llevaron una buena parte, y que "
        "además se gastó de más en la casa durante los meses buenos. Si lo hubieras "
        "anotado, habrías guardado algo para la temporada flaca. Un cuaderno sencillo, "
        "revisado cada mes, te muestra esas diferencias a tiempo.",
    ),
    key_points=(
        "Separa siempre los gastos de la finca de los gastos de la casa.",
        "Registra cada venta: fecha, cantidad, precio y comprador.",
        "Reparte lo que entra de la cosecha para cubrir también los meses de poca venta.",
        "Antes de un crédito pregunta cuánto pagarás en total y compara opciones.",
    ),
)

_CAFE_RIESGOS = CapsuleSpec(
    slug="cafe-riesgos-del-cafetal",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("cafe",),
    relevance=7.5,
    title="Riesgos del cafetal: prevenir, reducir o trasladar",
    summary="Cómo identificar lo que puede afectar tu cosecha y qué hacer con cada riesgo.",
    paragraphs=(
        "Todo cultivo tiene riesgos. En el café pueden ser el clima, como la sequía, las "
        "lluvias excesivas o el granizo; las plagas y enfermedades como la broca o la roya; "
        "los cambios en el precio; los problemas de salud de quien trabaja la finca; o "
        "incluso el robo. Pensar en ellos antes no los elimina, pero te prepara para que "
        "no te tomen por sorpresa.",
        "Una forma ordenada de verlo es hacerte tres preguntas por cada riesgo: ¿qué tan "
        "probable es que pase?, ¿qué tanto daño me haría?, ¿qué puedo hacer al respecto? "
        "Con eso puedes decidir cuáles atender primero. Un riesgo poco probable pero muy "
        "grave, como perder el cafetal por un deslizamiento, merece tanta atención como uno "
        "frecuente y leve.",
        "Frente a un riesgo tienes cuatro caminos. Prevenir: hacer algo para que no "
        "ocurra, como el control oportuno de la broca o la cobertura del suelo. Reducir: "
        "disminuir el daño si ocurre, como tener sombrío y variedades adecuadas. Aceptar: "
        "asumirlo cuando es pequeño y tienes cómo cubrirlo. Y trasladar: pasarle parte del "
        "riesgo a otro, por ejemplo con un seguro.",
        "Los seguros agropecuarios y los microseguros son una forma de trasladar riesgos. "
        "Funcionan así: pagas un valor y, si ocurre el evento que cubre la póliza, recibes "
        "una compensación. Antes de decidir, pregunta siempre qué cubre y qué no, qué debes "
        "hacer para reclamar y en cuánto tiempo. CIMA no vende seguros: aquí aprendes para "
        "decidir con información y puedes dejar registrado si te interesa saber más.",
        "Un seguro no reemplaza el buen manejo del cultivo ni el ahorro: se complementa con "
        "ellos. Lo más sólido es combinar prevención, un fondo de imprevistos y, si te "
        "conviene, una cobertura. Anota los tres riesgos que más te preocupan en tu "
        "cafetal y escribe al lado qué haces hoy para cada uno.",
        "Imagina una tabla de tres columnas en una hoja: el riesgo, qué tan probable es y "
        "qué tan grave sería. En la primera fila pones la sequía, en la segunda la broca y "
        "en la tercera una caída del precio. Al llenarla ves que algunos riesgos los puedes "
        "prevenir con trabajo en la finca y otros necesitan ahorro o una cobertura. Esa "
        "hoja, repasada cada año con tu familia, se convierte en tu mapa de riesgos.",
    ),
    key_points=(
        "Para cada riesgo pregúntate qué tan probable es y qué tanto daño haría.",
        "Ante un riesgo puedes prevenir, reducir, aceptar o trasladar.",
        "Un seguro traslada parte del riesgo; pregunta siempre qué cubre y qué no.",
        "El mejor resultado sale de combinar prevención, ahorro y, si te conviene, cobertura.",
    ),
)

# --------------------------------------------------------------------------- #
# Tienda de barrio
# --------------------------------------------------------------------------- #
_TIENDA_CLIMA = CapsuleSpec(
    slug="tienda-calor-y-lluvias",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=("tienda_barrio",),
    relevance=9.4,
    title="Tu tienda frente al calor y las lluvias",
    summary="Cómo proteger el inventario, la nevera y el local cuando el clima aprieta.",
    paragraphs=(
        "Una tienda de barrio vive de que haya mercancía en buen estado, clientes que "
        "puedan llegar y servicios que funcionen. El clima cambiante afecta las tres cosas: "
        "con mucho calor se dañan los productos fríos, con aguaceros fuertes entra agua al "
        "local o se complica el reparto, y los cortes de energía pueden pararlo todo. "
        "Prepararte te ahorra pérdidas.",
        "Con el calor, la nevera trabaja más. Ponla lejos del sol directo y de la estufa, "
        "con espacio para que circule el aire por detrás, y límpiale de vez en cuando las "
        "rejillas. No la llenes de más ni abras la puerta sin necesidad. Revisa que el "
        "empaque de la puerta cierre bien; si no, pierde frío, gasta más energía y se "
        "dañan los productos.",
        "Con las lluvias, sube del piso lo que se moje fácil: paquetes de arroz, azúcar, "
        "harinas, papel higiénico y cajas de cartón. Usa estibas o estantes bajos de "
        "plástico o metal. Mira cada cierto tiempo el techo, los canales y los bajantes: "
        "una teja corrida o un canal tapado se arregla barato antes de la temporada de "
        "lluvias, pero cuesta mucho cuando ya entró el agua.",
        "Piensa en un plan para los cortes de energía. Si la nevera se queda sin luz, no la "
        "abras más de lo necesario: así mantiene el frío por más tiempo. Ten a la mano "
        "linternas o lámparas con pilas y anota el teléfono de la empresa de energía. Si "
        "vendes productos perecederos, procura no comprar de más cuando se anuncian lluvias "
        "fuertes o calor extremo.",
        "Ofrece soluciones a tus clientes: en temporada de calor, agua y bebidas frías; en "
        "lluvias, domicilios cortos o productos de uso inmediato. Adaptarte también es una "
        "oportunidad de vender mejor. Da hoy una vuelta por tu tienda como si fuera a "
        "llover mañana: ¿qué se mojaría primero? Empieza por ahí.",
        "Imagina que se anuncia una semana de lluvias fuertes. Antes de que lleguen, subes "
        "los paquetes de abajo a un estante, revisas el canal del techo y avisas a tus "
        "clientes que tienes domicilios. Cuando llueve, tu mercancía está a salvo y tus "
        "vecinos saben que pueden contar contigo. Esa preparación de una tarde puede marcar "
        "la diferencia entre perder mercancía y seguir vendiendo con tranquilidad.",
    ),
    key_points=(
        "La nevera lejos del sol y con espacio para el aire gasta menos y enfría mejor.",
        "Sube del piso lo que se moje fácil, usando estibas o estantes bajos.",
        "Revisa techo, canales y bajantes antes de la temporada de lluvias.",
        "Ante un corte de luz, abre la nevera lo menos posible.",
    ),
)

_TIENDA_FINANZAS = CapsuleSpec(
    slug="tienda-plata-del-negocio-y-de-la-casa",
    topic=TOPIC_FINANZAS,
    tags=("tienda_barrio",),
    relevance=8.4,
    title="Separa la plata de la tienda de la plata de la casa",
    summary="Un orden sencillo para saber si tu tienda realmente está ganando.",
    paragraphs=(
        "En muchas tiendas de barrio la caja es también el bolsillo de la familia. Se saca "
        "para el mercado, para el recibo, para el colegio, y al final del mes nadie sabe si "
        "la tienda dejó ganancia o si solo está entrando y saliendo plata. Separar los dos "
        "dineros es el primer paso para ordenar el negocio.",
        "Una buena costumbre es ponerte un sueldo. Decide cuánto vas a sacar cada semana o "
        "cada mes para tus gastos personales y sácalo siempre el mismo día, anotándolo. "
        "Todo lo demás se queda en el negocio para reponer mercancía, pagar arriendo y "
        "servicios y cubrir imprevistos. Así sabes con claridad qué es del negocio y qué es "
        "tuyo.",
        "Conoce la diferencia entre vender y ganar. Lo que entra por ventas no es ganancia: "
        "de ahí hay que descontar lo que te costó la mercancía, el arriendo, la energía, el "
        "transporte y otros gastos. Calcula el margen de tus productos principales: si "
        "compras algo en 1.000 pesos y lo vendes en 1.300, te quedan 300 por unidad, pero "
        "de ahí todavía salen los gastos del local.",
        "El fiado merece un cuaderno aparte. Anota quién debe, cuánto, desde cuándo y "
        "cuándo prometió pagar, y revísalo cada semana. Fiar a muchos clientes por mucho "
        "tiempo deja la tienda sin plata para reponer mercancía. Ponle un límite a cada "
        "cliente y cobra con respeto pero con constancia.",
        "Si puedes, usa una cuenta o una billetera digital para el negocio y otra para tus "
        "gastos personales. Pregunta por las cuotas de manejo y compara antes de decidir. "
        "Esta semana empieza con tu sueldo: define un valor, sácalo un solo día y anota "
        "todo lo que salga de la caja por otras razones.",
        "Imagina que cada vez que falta plata en la casa sacas de la caja sin anotar. A "
        "fin de mes, la tienda parece no dejar nada, aunque vendió bastante. Si en cambio "
        "te pones un sueldo y anotas todo lo demás, puedes ver cuánto dejó realmente el "
        "negocio y decidir con claridad si hay para surtir más, para ahorrar o para pagar "
        "una deuda. Revisa tus números cada mes: el orden no necesita aparatos, solo "
        "un cuaderno y constancia.",
    ),
    key_points=(
        "Ponte un sueldo fijo y sácalo siempre el mismo día.",
        "Ventas no es lo mismo que ganancia: descuenta la mercancía y los gastos del local.",
        "Lleva el fiado en un cuaderno aparte y revísalo cada semana.",
        "Una cuenta para el negocio y otra personal ayudan a no mezclar el dinero.",
    ),
)

_TIENDA_RIESGOS = CapsuleSpec(
    slug="tienda-riesgos-del-negocio",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("tienda_barrio",),
    relevance=7.4,
    title="Riesgos de la tienda: robo, incendio, inundación y deudas",
    summary="Cómo identificar lo que puede afectar tu negocio y cómo prepararte.",
    paragraphs=(
        "Una tienda pequeña guarda muchas cosas valiosas en poco espacio: mercancía, "
        "equipos, el dinero de la caja y el trabajo de años. Un robo, un incendio, una "
        "inundación o una deuda que se sale de control pueden dejarla en cero. Conocer los "
        "riesgos y tomar medidas básicas puede evitar el golpe o reducirlo.",
        "Haz un recorrido con una hoja en la mano. Anota qué podría pasar: instalación "
        "eléctrica en mal estado, cables sobrecargados, gas mal conectado, rejas débiles, "
        "techo con goteras, mercancía en el piso. Al lado de cada punto escribe qué tan "
        "probable es y qué tanto daño haría. Empieza arreglando lo más grave y fácil de "
        "resolver, como pedir que alguien calificado revise las conexiones eléctricas.",
        "Para el robo, evita acumular mucho efectivo en la caja: consigna o transfiere con "
        "regularidad. Mejora la iluminación, mantén la mercancía valiosa a la vista y no "
        "dejes el local solo. Para el incendio, ten cerca un extintor vigente, no "
        "sobrecargues los tomacorrientes y guarda los líquidos inflamables fuera del "
        "local. Anota el teléfono de los bomberos.",
        "Los seguros y microseguros para negocios pueden ayudar a trasladar parte del "
        "riesgo: pagas un valor periódico a cambio de una compensación si ocurre lo que "
        "cubre la póliza. Antes de decidir, pregunta qué eventos cubre, qué excluye, cuál "
        "es el valor asegurado y qué debes hacer para reclamar. CIMA no vende seguros: aquí "
        "aprendes a decidir con información y puedes dejar registrado tu interés.",
        "Las deudas también son un riesgo. Evita pagar una deuda con otra y los "
        "prestamistas informales de cobro diario. Antes de endeudarte calcula si la tienda "
        "dará para pagar cada cuota aun en un mes flojo de ventas. Elige hoy un riesgo para "
        "reducir esta semana, un cable, una reja o el efectivo de la caja: uno a la vez es "
        "mejor que ninguno.",
        "Imagina que haces el recorrido de riesgos un domingo en la tarde, con calma. "
        "Encuentras un cable pelado cerca de la nevera, una reja que no cierra bien y cajas "
        "de mercancía en el piso por donde entra el agua. En una semana puedes corregir las "
        "tres cosas con poca plata. Hacerlo antes de que pase algo cuesta mucho menos que "
        "arreglarlo después del daño.",
    ),
    key_points=(
        "Recorre tu tienda con una hoja y anota lo que podría salir mal.",
        "No acumules efectivo: consigna o transfiere con regularidad.",
        "Un extintor vigente y buenas conexiones eléctricas previenen incendios.",
        "Antes de un seguro o un crédito pregunta qué cubre, qué excluye y cuánto pagarás.",
    ),
)

# --------------------------------------------------------------------------- #
# Cápsulas de refuerzo: una para quien cultiva café, una para la tienda de barrio y
# una de finanzas que sirve a ambos. Cada una va en su propia ruta corta (ver PATHS)
# porque la audiencia de una ruta es la unión de las etiquetas de sus cápsulas.
# --------------------------------------------------------------------------- #
_CAFE_BROCA = CapsuleSpec(
    slug="cafe-la-broca",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("cafe",),
    relevance=8.0,
    title="La broca: cómo cuidar tu cosecha de la plaga que más daña el café",
    summary="Aprende cómo vive la broca, dónde se esconde y qué hacer antes y después de la cosecha.",
    paragraphs=(
        "La broca del café es un escarabajo diminuto, del tamaño de la cabeza de un "
        "alfiler, y es la plaga que más daño le hace al café en el mundo. La hembra "
        "perfora el grano, entra y pone sus huevos adentro. Por eso el daño casi no se "
        "ve por fuera, pero por dentro el grano se pica, pesa menos y se vende peor.",
        "Para defenderte conviene conocerla. Desde el huevo hasta que es adulta pasan "
        "más o menos de veinticuatro a cuarenta y cinco días, según el clima. Le "
        "gustan los lugares sombríos y húmedos, y suele salir después de la lluvia a "
        "buscar otro cafeto. Y donde ya hubo broca, es más fácil que vuelva.",
        "Los granos que se quedan en la planta o caídos en el suelo después de la "
        "cosecha son la casa donde la broca se refugia hasta la próxima floración. Por "
        "eso lo más importante es recoger bien: coge los frutos maduros a tiempo, haz "
        "un repase al final para sacar los que quedaron en las ramas y levanta los que "
        "están en el suelo. Es un trabajo cansón, pero si se hace con juicio es de lo "
        "más eficaz que puedes hacer.",
        "Revisa tu lote cada cierto tiempo: toma un puñado de frutos, mira si tienen "
        "un huequito pequeño cerca de la punta y ábrelos para ver si hay galerías. Así "
        "sabes qué tan afectado está y no actúas a ciegas. También cuida lo que entra "
        "a tu finca: no lleves frutos ni costales de otras fincas sin revisarlos, "
        "porque con ellos puede llegar la plaga.",
        "La naturaleza también ayuda. Algunas hormigas se comen la broca y hay un "
        "hongo que la ataca y que se ve como un polvillo blanco sobre el fruto. Si "
        "fumigas sin necesidad, los insectos que te ayudan también se mueren. Y "
        "recuerda que los insecticidas son peligrosos para tu salud y para el agua: "
        "antes de usar cualquier producto, pregunta al técnico o al extensionista de "
        "tu comité de cafeteros qué conviene en tu finca y cómo aplicarlo con "
        "seguridad. Este contenido es una guía general y no reemplaza esa asesoría.",
        "Esta semana haz una prueba sencilla en un lote: revisa un puñado de frutos "
        "en tres sitios distintos, cuenta cuántos tienen perforación y anótalo. Repite "
        "la revisión después de la cosecha y compara. Con ese cuaderno sabrás si tu "
        "recolección y tu repase están funcionando.",
    ),
    key_points=(
        "La broca perfora el grano y pone sus huevos adentro: el daño se ve al abrirlo.",
        "Recoge a tiempo y haz el repase: quita los frutos que quedan en la rama y en el suelo.",
        "No muevas frutos ni costales de otras fincas sin revisarlos.",
        "Antes de aplicar cualquier producto, consulta al extensionista de tu comité.",
    ),
)

_TIENDA_INVENTARIO = CapsuleSpec(
    slug="tienda-el-inventario",
    topic=TOPIC_FINANZAS,
    tags=("tienda_barrio",),
    relevance=8.0,
    title="Tu inventario: no dejes la plata parada en el estante",
    summary="Aprende a saber qué se vende, qué se queda quieto y cuánto pedir sin que te falte ni te sobre.",
    paragraphs=(
        "Cada producto que está en tu estante es plata que ya pagaste y todavía no "
        "recuperas. Si se vende rápido, esa plata vuelve y puedes comprar de nuevo. Si "
        "se queda quieto, la plata está parada, ocupa espacio y, si se vence o se daña, "
        "se pierde. Por eso llevar el inventario no es un lujo: es cuidar tu capital.",
        "Una buena administración del inventario busca dos cosas a la vez. Primero, que "
        "cuando el cliente pida un producto lo tengas. Segundo, que no tengas más de lo "
        "necesario, porque tener mucho también cuesta. Hay que encontrar el equilibrio: "
        "si pides poco se te acaba y pierdes la venta; si pides mucho se te empoza la "
        "plata.",
        "Para empezar basta un cuaderno. Una vez por semana anota qué productos se "
        "acabaron, cuáles se vendieron más y cuáles llevan semanas sin moverse. Así "
        "descubres tus productos estrella, que debes tener siempre, y tus productos "
        "dormidos, que quizás no vale la pena volver a comprar. Compra con base en lo "
        "que de verdad vendes, no en lo que te ofrece el vendedor.",
        "Ten cuidado con los descuentos por volumen. Comprar más barato solo sirve si "
        "alcanzas a vender todo antes de que se venza y si no dejas sin plata el resto "
        "del negocio. Haz la cuenta: ¿cuánto vas a vender en un mes? Si la respuesta es "
        "menos de lo que te toca comprar, el descuento no es tal.",
        "En los productos que se vencen, como lácteos, pan o fruta, aplica la regla de "
        "primero en entrar, primero en salir. Pon adelante lo que llegó antes y atrás "
        "lo nuevo, y revisa las fechas cada semana. Y para los días de más venta, como "
        "quincena, fiestas o puentes, guarda un poquito de más de lo que más se vende, "
        "como una reserva de seguridad, pero sin exagerar.",
        "Esta semana haz un conteo rápido de tu estante, anota los cinco productos que "
        "más rotan y los cinco que menos. Con eso ya tienes la base para decidir mejor "
        "tu próximo pedido.",
    ),
    key_points=(
        "Lo que está en el estante es plata que todavía no recuperas.",
        "Busca el equilibrio: que no te falte lo que más se vende ni te sobre lo que no rota.",
        "Cada semana anota qué se acabó, qué se vendió más y qué lleva semanas quieto.",
        "En lo que se vence, pon adelante lo que llegó primero y revisa las fechas.",
    ),
)

_FINANZAS_GOTA_A_GOTA = CapsuleSpec(
    slug="finanzas-gota-a-gota",
    topic=TOPIC_FINANZAS,
    tags=("cafe", "tienda_barrio"),
    relevance=9.0,
    title="El gota a gota: cómo reconocerlo y qué hacer en vez de caer",
    summary="Para quien cultiva y para quien atiende un negocio: señales del préstamo gota a gota y alternativas más seguras.",
    paragraphs=(
        "Cuando la plata no alcanza, el préstamo rápido parece una salvación. Por eso el "
        "gota a gota se ofrece justo ahí: sin papeles, sin preguntas y con la plata en "
        "la mano el mismo día. El problema aparece después. Este tipo de préstamo "
        "informal nació en Medellín en los años noventa y se volvió muy conocido porque "
        "se paga a diario o a la semana y cobra intereses muy altos, mucho más caros "
        "que un microcrédito formal.",
        "Hay señales para reconocerlo. Te prestan sin pedir casi nada. Te cobran cuotas "
        "diarias o semanales que no te dicen cuánto suman al final. No te entregan un "
        "contrato claro ni te explican la tasa. Te piden fotos de tu cédula, de tu "
        "negocio o de tu finca. Y lo más grave: si te atrasas, empiezan las "
        "presiones, las amenazas y las visitas. Por eso muchas veces no se pierde solo "
        "plata, también la tranquilidad.",
        "Ojo con las fachadas. A veces quien presta se hace pasar por una entidad "
        "seria, con carteles, mensajes o llamadas muy amables. Antes de aceptar, "
        "pregunta el nombre completo de la entidad y si está vigilada por la "
        "Superintendencia Financiera. Cobrar intereses por encima del límite legal es "
        "un delito, y quien te lo cobra no puede obligarte con amenazas.",
        "Existen caminos más seguros. Pregunta en cooperativas, fondos de empleados y "
        "entidades que ofrecen microcrédito: compara por lo menos dos opciones y pide "
        "siempre el costo total, es decir, cuánto vas a pagar en cuotas hasta el "
        "final. Si eres cafetero, pregunta en tu comité de cafeteros por las líneas "
        "para el sector. Si tienes tienda, llevar bien tus cuentas te sirve de "
        "respaldo cuando pidas un crédito.",
        "Y la mejor defensa es tener un colchón. Aunque sea poquito, aparta una parte "
        "de cada venta o de cada cosecha en un fondo para imprevistos, así cuando algo "
        "falle no tienes que correr donde un prestamista. Si ya estás en un gota a "
        "gota y te están amenazando, no te quedes callado: cuéntaselo a una persona "
        "de confianza y denuncia ante la Policía o la Fiscalía.",
    ),
    key_points=(
        "Si te prestan sin pedir casi nada y no te dicen el costo total, desconfía.",
        "Pregunta siempre cuánto pagarás en total y si la entidad está vigilada.",
        "Compara por lo menos dos opciones: cooperativas, microcrédito, comité de cafeteros.",
        "Ahorra un poquito de cada venta o cosecha: es tu defensa contra el gota a gota.",
    ),
)

# --------------------------------------------------------------------------- #
# Módulo 1 (videos propios de la Escuela). El texto se escribió a partir de la
# transcripción de cada video; el video es el complemento y se sirve con sesión.
# --------------------------------------------------------------------------- #
# Actividades del campo (allowlist del Perfil) a las que aplica el Módulo 1.
_CAMPO: Final[tuple[str, ...]] = (
    "cafe",
    "platano",
    "aguacate",
    "cacao",
    "arroz",
    "maiz",
    "ganaderia",
    "hortalizas",
)

_AGRO_SOSTENIBLE = CapsuleSpec(
    slug="agro-agricultura-sostenible",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=_CAMPO,
    relevance=8.8,
    title="Agricultura sostenible: producir hoy sin acabar con el mañana",
    summary="Qué es la agricultura sostenible y cómo cuidar el suelo, el agua y la plata de tu finca al mismo tiempo.",
    paragraphs=(
        "La agricultura sostenible es una forma de trabajar el campo que busca tres cosas "
        "al mismo tiempo: que la finca dé comida y plata, que la tierra, el agua y los "
        "animales sigan sanos, y que la familia y la comunidad vivan mejor. No es una moda "
        "ni un lujo de fincas grandes. Es cultivar hoy sin dejar la tierra cansada para los "
        "que vienen después.",
        "Muchos productores ya lo están viviendo. Con el cambio del clima las lluvias "
        "llegan cuando no toca, la flor del café no pega o se cae, y la cosecha merma. "
        "Cuando el suelo está pobre y sin cobertura, cada aguacero se lleva la capa buena "
        "de la tierra y cada verano seca más rápido el cultivo. Una finca bien cuidada "
        "aguanta mejor esos golpes.",
        "El primer cuidado es el suelo, porque de él depende todo. Deja coberturas o "
        "arvenses nobles entre los surcos para que la tierra no quede pelada, devuelve al "
        "lote la pulpa y los residuos bien compostados y siembra en curvas de nivel si tu "
        "terreno es pendiente. Un suelo vivo guarda más agua y necesita menos abono.",
        "El segundo es el agua. Protege los nacimientos y las orillas de las quebradas con "
        "árboles, no laves fumigadoras ni tires empaques cerca de ellas y no desperdicies el "
        "agua del beneficio o del riego. El agua que se contamina arriba la toman abajo tus "
        "vecinos y sus animales.",
        "El tercero es manejar las plagas con cabeza. Antes de fumigar, revisa qué tanto "
        "daño hay de verdad. Muchas veces la naturaleza ayuda: hay hongos, avispitas y "
        "hormigas que se comen las plagas, y si echas veneno sin necesidad también los "
        "matas. Cuando sí haga falta un producto, pregunta al técnico o al extensionista "
        "cuál conviene y cómo aplicarlo con seguridad.",
        "Y no te olvides de la plata. Una finca sostenible también tiene que ser rentable: "
        "anota lo que gastas en insumos y lo que vendes, para saber qué prácticas te "
        "ahorran y cuáles no. Cuidar el suelo y el agua casi siempre baja los costos con el "
        "tiempo, porque necesitas menos abono, menos riego y menos remedios.",
        "Esta semana camina tu finca con una libreta y anota tres cosas: dónde la tierra "
        "queda pelada, por dónde corre el agua cuando llueve y qué tan cerca de la quebrada "
        "fumigas o lavas los equipos. Escoge una sola de esas cosas para mejorar este mes. "
        "Recuerda que la idea es mantener el equilibrio entre la naturaleza, tu familia y tu "
        "bolsillo.",
    ),
    key_points=(
        "Agricultura sostenible es producir comida y plata sin acabar con el suelo, el agua ni la comunidad.",
        "Un suelo cubierto y con materia orgánica aguanta mejor los aguaceros y los veranos.",
        "Protege los nacimientos y no laves equipos ni tires empaques cerca de las quebradas.",
        "Antes de fumigar revisa el daño real y consulta al técnico qué producto usar.",
    ),
    video_file="agro-sostenible.mp4",
)

_AGRO_RIESGOS = CapsuleSpec(
    slug="agro-riesgos-del-campo",
    topic=TOPIC_GESTION_RIESGOS,
    tags=_CAMPO,
    relevance=8.7,
    title="Los riesgos del campo: conócelos para estar preparado",
    summary="Los cuatro riesgos principales de quien cultiva o cría animales, y cómo prevenirlos para que el golpe sea menor.",
    paragraphs=(
        "Riesgo es la posibilidad de sufrir una pérdida o un daño por algo que no está del "
        "todo en tus manos. En el campo hay muchos: el clima que cambia, las plagas y "
        "enfermedades, los precios del producto y de los insumos, y hasta las normas del "
        "país. No se pueden eliminar todos, pero sí se pueden conocer, prevenir y preparar "
        "para que el golpe sea menor.",
        "El primero es el riesgo climático: heladas, vientos fuertes, aguaceros que no "
        "paran, inundaciones, granizadas o sequías que dañan la cosecha. Aquí entran "
        "también los deslizamientos que se forman cuando el exceso de lluvia satura la "
        "tierra. Para prepararte, sigue los avisos del IDEAM, mantén limpios los canales y "
        "desagües y no dejes la tierra pelada en las pendientes.",
        "El segundo es el riesgo biológico: las plagas y enfermedades que atacan los "
        "cultivos o los animales y bajan la cantidad y la calidad de lo que produces. En el "
        "café, por ejemplo, la broca y la roya. La mejor defensa es revisar seguido, "
        "recoger bien, mantener las plantas sanas y pedir asesoría al técnico antes de "
        "aplicar cualquier producto.",
        "El tercero es el riesgo geológico: terremotos, erupciones volcánicas y los "
        "deslizamientos que ellos provocan. Estos no se pueden evitar, pero sí puedes "
        "averiguar si tu finca está en una zona de amenaza, no construir la casa ni el "
        "beneficio al pie de un talud y tener claro con tu familia por dónde salir y a "
        "dónde ir si pasa algo.",
        "El cuarto es el riesgo financiero: cuando el precio de lo que vendes baja o el de "
        "los abonos sube, cuando el dólar cambia o cuando no consigues crédito a tiempo. "
        "Para manejarlo, lleva las cuentas de cada cosecha, ten un ahorro para emergencias, "
        "no dependas de un solo producto si puedes diversificar y desconfía de los "
        "préstamos gota a gota.",
        "Para los riesgos que no puedes controlar existen herramientas que reparten el "
        "golpe, como los seguros agropecuarios: se paga una suma pequeña y, si pasa el daño "
        "cubierto, se recibe una ayuda para recuperarse. Vale la pena entender bien cómo "
        "funcionan y qué cubren antes de decidir. CIMA no vende seguros: aquí solo te "
        "explicamos para que decidas con información.",
        "Esta semana haz tu propio mapa de riesgos: en una hoja escribe los cuatro tipos y "
        "al lado lo que más te ha afectado en los últimos años. Escoge el que más te "
        "preocupa y anota una sola cosa que puedes hacer este mes para prepararte.",
    ),
    key_points=(
        "Los cuatro riesgos principales del campo son climáticos, biológicos, geológicos y financieros.",
        "Los riesgos siempre existen: lo importante es prevenirlos, prepararse y reducir su impacto.",
        "Llevar las cuentas y tener un ahorro de emergencia te protege del riesgo financiero.",
        "Antes de decidir sobre un seguro, entiende bien qué cubre y qué no.",
    ),
    video_file="agro-riesgos.mp4",
)

_TIENDA_VIDEOS = CapsuleSpec(
    slug="tienda-tu-negocio-en-video",
    topic=TOPIC_FINANZAS,
    tags=("tienda_barrio", "fruteria"),
    relevance=8.6,
    title="Muestra tu negocio en video sin miedo a la cámara",
    summary="Cómo grabar videos sencillos con tu celular para que más clientes conozcan tu tienda, sin gastar plata.",
    paragraphs=(
        "Si sabes atender a un cliente en el mostrador, ya sabes hacer un video. Hoy mucha "
        "gente busca en el celular dónde comprar, y prefiere negocios de personas "
        "trabajadoras y honestas que muestren cómo es su trabajo de verdad. Un video corto "
        "en tu estado de WhatsApp o en tus redes puede traerte clientes nuevos sin gastar "
        "un peso en publicidad.",
        "El miedo a la cámara es normal. El truco es no pensar que le hablas a un aparato. "
        "Cuando pongas el celular al frente, imagina que es tu compadre o tu clienta de "
        "toda la vida que vino a preguntarte algo. Háblale con la misma confianza con que "
        "la atiendes en la tienda, y el video sale natural.",
        "No necesitas equipos caros. Limpia el lente del celular, ponte de frente a la luz "
        "de la puerta o de una ventana y apóyalo en algo firme para que no tiemble. Graba en "
        "un lugar sin mucho ruido y habla un poco más despacio de lo normal. Con un minuto "
        "basta: la gente ve completos los videos cortos.",
        "¿De qué hablar? De lo que tú sabes y tus clientes valoran: la fruta que acaba de "
        "llegar y cómo escoger la más madura, la promoción de la semana, cómo guardar el "
        "pan para que dure o el horario de los domingos. Muestra los productos de cerca y "
        "di los precios claros. Tu experiencia vale y le sirve a otros.",
        "Cuida también tu negocio y a tu gente. No grabes a clientes ni a niños sin su "
        "permiso, no muestres la caja, el dinero ni dónde guardas la mercancía, y no digas "
        "a qué hora cierras con la plata del día. Lo que publicas lo puede ver cualquiera.",
        "Y haz cuentas para saber si funciona. Pregunta a los clientes nuevos cómo "
        "supieron de ti y anota cuántos llegaron por un video. Si una idea trae gente, "
        "repítela; si no, prueba otra. Así cada video es una pequeña inversión de tiempo "
        "que puedes medir.",
        "Esta semana graba un video de menos de un minuto mostrando el producto que más se "
        "vende en tu tienda. Míralo, pregúntale a alguien de confianza qué le pareció y "
        "publícalo en tu estado. Pierde el miedo: la confianza que le das a tus clientes en "
        "el mostrador también se nota en la pantalla.",
    ),
    key_points=(
        "Háblale a la cámara como si fuera un cliente de confianza, no un aparato.",
        "Con luz de frente, el celular firme y un minuto de video es suficiente.",
        "No grabes la caja, el dinero ni a personas sin su permiso.",
        "Anota cuántos clientes llegan por tus videos para saber qué funciona.",
    ),
    video_file="tienda-videos.mp4",
)

# --------------------------------------------------------------------------- #
# Cápsulas de ejemplo para las demás actividades. Texto escrito por el equipo como
# EJEMPLO, pendiente de revisión técnica de la Escuela: son pautas generales, sin dosis
# ni productos, que siempre remiten al técnico, al extensionista o al ICA. El video de
# apoyo es de un canal institucional (AGROSAVIA, Fedegán o el Ministerio de
# Agricultura), se verificó con oEmbed y se revisó su contenido: es educativo y no
# promociona productos. Panadería y miscelánea no tienen video: no se encontró uno
# institucional.
# --------------------------------------------------------------------------- #
_PLATANO_LABORES = CapsuleSpec(
    slug="platano-labores-del-platanal",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("platano",),
    relevance=8.0,
    title="Las labores del platanal que cuidan tu cosecha",
    summary="Deshije, deshoje, desbellote y herramientas limpias: lo básico para que el platanal no se enferme y el racimo llene bien.",
    paragraphs=(
        "Un platanal sano no depende de la suerte sino de unas labores sencillas hechas "
        "a tiempo. Cuando se dejan para después, las malezas le roban la comida a la "
        "planta, las hojas enfermas riegan la sigatoka y las herramientas sucias llevan "
        "enfermedades como el moko de una mata a otra. Con un poco de orden se pierde "
        "menos y el racimo sale más pesado.",
        "Los primeros cinco a siete meses son los más delicados, porque las malezas "
        "compiten fuerte con la planta joven. Mantén limpio el plato alrededor de cada "
        "mata y, entre los surcos, deja coberturas nobles que protejan el suelo sin "
        "competir. Así la tierra no queda pelada con los aguaceros ni se seca tan rápido "
        "en verano.",
        "Haz el deshije con criterio: deja en cada sitio la planta madre, un hijo y un "
        "nieto bien ubicados, y quita los demás colinos para que no se peleen la comida. "
        "Con el deshoje retira las hojas secas, dobladas o muy manchadas, porque son la "
        "casa de la sigatoka. Después de cosechar, corta el tallo viejo y pícalo para "
        "que se descomponga en el lote.",
        "Cuida el racimo. Quitar la bellota, la flor que queda colgando al final, cada "
        "quince días evita que los insectos que la visitan lleven el moko a otras "
        "plantas. Quitar las últimas manos pequeñas ayuda a que las demás llenen mejor, "
        "y apuntalar o amarrar la mata evita que el viento la tumbe con el racimo "
        "encima. La bolsa protege la fruta de golpes, plagas y quemaduras del sol.",
        "Lo más importante es la higiene. Lava y desinfecta el machete y las demás "
        "herramientas al pasar de una mata a otra, con el producto y la forma que te "
        "indique el técnico. No traigas colinos ni tierra de otras fincas sin saber de "
        "dónde vienen. Si ves plantas que se marchitan de un momento a otro o con el "
        "tallo manchado por dentro, no las muevas y avisa al ICA o al técnico de tu "
        "zona: hay enfermedades que se riegan muy rápido y su control temprano protege "
        "a toda la vereda.",
        "Esta semana recorre tu platanal con una libreta. Anota cuántas matas tienen "
        "más de tres colinos, cuántas tienen hojas secas colgando y si tus herramientas "
        "se están limpiando entre mata y mata. Escoge la labor más atrasada y ponte al "
        "día con ella antes de fin de mes.",
    ),
    key_points=(
        "Mantén limpio el plato de cada mata en los primeros meses y deja coberturas entre surcos.",
        "Deja madre, hijo y nieto, y quita las hojas secas o muy manchadas.",
        "Quita la bellota a tiempo y desinfecta las herramientas entre mata y mata.",
        "Si una planta se marchita de repente, no la muevas y avisa al ICA o al técnico.",
    ),
    video=VideoSpec(
        video_id="VZ-55j2kOjE",
        title="Prácticas culturales en el cultivo de plátano | Modelo Productivo de Plátano",
        channel="AGROSAVIA TV",
    ),
)

_AGUACATE_SUELO = CapsuleSpec(
    slug="aguacate-suelo-y-agua",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=("aguacate",),
    relevance=8.0,
    title="Aguacate: cuida el suelo y el agua para aguantar el clima",
    summary="El aguacate no tolera el encharcamiento y sufre con la erosión. Aprende a conocer tu terreno y a manejar el agua antes de que llegue el problema.",
    paragraphs=(
        "El aguacate es un árbol exigente con el suelo. Sus raíces necesitan aire, así "
        "que no aguantan quedar encharcadas, y en las laderas un aguacero fuerte puede "
        "llevarse la capa buena de la tierra en pocas horas. Con lluvias cada vez más "
        "fuertes y veranos más largos, cuidar el suelo y el agua es la mejor forma de "
        "proteger tu inversión.",
        "Empieza por conocer tu finca. Camínala después de un aguacero y mira por dónde "
        "corre el agua, dónde se queda empozada, dónde se ven piedras que antes no "
        "estaban y dónde la tierra se está lavando. Esos son tus puntos de riesgo. "
        "Anótalos en un croquis sencillo: te servirán para decidir dónde sembrar, dónde "
        "hacer drenajes y dónde no conviene meter árboles.",
        "Si vas a sembrar o a renovar, hazlo bien desde el principio. Adecúa el terreno, "
        "siembra siguiendo las curvas del terreno y deja listos los canales para sacar el "
        "agua sobrante antes de que llegue el invierno. Un árbol sembrado en un sitio que "
        "se encharca casi siempre termina enfermo de la raíz, y eso no se arregla después "
        "con abono.",
        "Protege la tierra que ya tienes. Mantén el suelo cubierto con hojarasca, "
        "coberturas o la misma poda picada, para que la lluvia no golpee directo y el sol "
        "no lo reseque. Fíjate en las señales: si ves lombrices y otros bichos en la "
        "tierra, es buena señal; si aparecen piedras y raíces al aire, el suelo se está "
        "perdiendo. Cada cierto tiempo vale la pena hacer un análisis de suelo para "
        "saber qué le falta, con la orientación del técnico.",
        "Cuida también el agua de la finca. No siembres ni fumigues pegado a las "
        "quebradas y nacimientos; deja esas orillas con su vegetación, porque frenan la "
        "erosión y evitan crecientes y derrumbes. En verano, si tienes riego, aplica el "
        "agua según lo que pide el árbol en cada etapa y no por costumbre.",
        "Esta semana haz tu croquis: dibuja la finca, marca con una equis dónde se "
        "empoza el agua y con un círculo dónde se lava la tierra. Escoge un punto y "
        "piensa qué arreglo puedes hacer antes de las próximas lluvias: un canal, una "
        "cobertura o dejar de sembrar en ese sitio.",
    ),
    key_points=(
        "El aguacate no aguanta el encharcamiento: saca el agua sobrante con canales.",
        "Recorre la finca después de llover y marca dónde se empoza el agua y dónde se lava la tierra.",
        "Mantén el suelo cubierto con hojarasca o coberturas.",
        "No siembres ni fumigues pegado a quebradas y nacimientos.",
    ),
    video=VideoSpec(
        video_id="Bt1CHdwGqyE",
        title="Estrategias de Manejo y conservación de suelos para aguacate Hass – AGROSAVIA",
        channel="AGROSAVIA TV",
    ),
)

_CACAO_MONILIA = CapsuleSpec(
    slug="cacao-monilia-y-mazorca-negra",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("cacao",),
    relevance=8.0,
    title="Cacao: frena la monilia y la mazorca negra a tiempo",
    summary="Dos enfermedades pueden llevarse más de la mitad de la cosecha. Con revisiones frecuentes, poda y orden en el lote se controlan sin gastar de más.",
    paragraphs=(
        "La monilia y la mazorca negra, también llamada fitóftora, son las enfermedades "
        "que más daño le hacen al cacao. Si no se manejan, pueden llevarse más de la "
        "mitad de la cosecha. La buena noticia es que buena parte del control está en "
        "tus manos y no cuesta mucha plata: consiste en cortarle el paso al hongo antes "
        "de que se riegue.",
        "Aprende a reconocerlas. La monilia empieza con manchas o abultamientos en la "
        "mazorca y, si se deja, la mazorca se cubre de un polvo blanco o crema. Ese polvo "
        "son millones de esporas que el viento y la lluvia llevan a las mazorcas sanas. "
        "La mazorca negra se ve como una mancha oscura que avanza rápido, sobre todo en "
        "épocas de mucha humedad.",
        "La clave es sacar las mazorcas enfermas antes de que hagan el polvo. Recorre el "
        "lote cada semana, de preferencia en la mañana, y retira todas las mazorcas "
        "enfermas que encuentres. No las dejes colgando ni las amontones al aire libre: "
        "déjalas en el suelo y cúbrelas con hojarasca para que se descompongan. Las "
        "cáscaras de la cosecha también deben amontonarse y manejarse, o convertirse en "
        "abono, como te indique el técnico.",
        "El hongo vive feliz donde hay humedad y poca luz. Por eso la poda es tan "
        "importante: quita ramas secas, enfermas o cruzadas, y regula el sombrío para que "
        "entre el sol y circule el aire. Desyerba a tiempo y no dejes que el lote se "
        "vuelva un monte cerrado. Cosecha las mazorcas maduras con frecuencia, cada "
        "quince días más o menos, porque las que se quedan en el árbol se enferman y "
        "contagian.",
        "Una planta bien nutrida se defiende mejor. Antes de abonar, haz un análisis de "
        "suelo y pide al técnico o al extensionista de tu zona un plan según lo que le "
        "falta a tu tierra. Si piensas usar algún producto contra las enfermedades, "
        "pregunta primero cuál conviene y cómo aplicarlo con seguridad.",
        "Esta semana escoge veinte árboles de tu lote y cuenta cuántas mazorcas enfermas "
        "tienen. Retíralas y anota el número. Repite cada semana durante un mes: si el "
        "número baja, el manejo está funcionando; si no, revisa con el técnico la poda y "
        "el sombrío.",
    ),
    key_points=(
        "Recorre el lote cada semana y saca las mazorcas enfermas antes de que hagan el polvo blanco.",
        "Deja las mazorcas enfermas en el suelo cubiertas con hojarasca.",
        "Poda y regula el sombrío para que entre luz y circule el aire.",
        "Abona según el análisis de suelo y consulta al técnico antes de aplicar productos.",
    ),
    video=VideoSpec(
        video_id="SbdpLJJLnNU",
        title="Manejo y control de la Moniliasis y la Phytophthora en cacao",
        channel="AGROSAVIA TV",
    ),
)

_ARROZ_AGUA = CapsuleSpec(
    slug="arroz-ahorra-agua",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=("arroz",),
    relevance=8.0,
    title="Arroz: produce lo mismo gastando menos agua",
    summary="Nivelar el lote, hacer caballones en curva y medir el agua que entra y sale permite ahorrar agua y plata, sobre todo en los veranos largos.",
    paragraphs=(
        "El arroz es de los cultivos que más agua usa, y cada vez hay más veranos largos "
        "y más competencia por el agua de los distritos de riego y las quebradas. Cuando "
        "el agua escasea, el que la desperdicia es el primero en quedarse corto. Por eso "
        "aprender a usarla mejor no es solo cuidar el ambiente: es asegurar la cosecha y "
        "bajar los costos.",
        "El primer paso es nivelar bien el lote. En un terreno desparejo el agua se "
        "acumula en las partes bajas y no llega a las altas, así que toca echar mucha más "
        "para cubrirlo todo. Con una buena nivelación el agua se reparte pareja, la "
        "semilla no se ahoga en los charcos y la maleza no se aprovecha de los sitios "
        "secos. Los técnicos de los programas de los arroceros muestran que, con estas "
        "prácticas, se puede ahorrar una parte importante del agua.",
        "El segundo paso es hacer los caballones siguiendo las curvas del terreno. Así el "
        "agua entra y sale despacio y de forma uniforme, en lugar de correr y llevarse la "
        "tierra. Mantén los canales de entrada y de drenaje bien trazados y limpios: el "
        "agua que se queda estancada donde no debe favorece plagas y enfermedades.",
        "El tercer paso es medir. Lo que no se mide no se puede mejorar. Poner una "
        "regleta o una canaleta sencilla a la entrada y a la salida del lote te permite "
        "saber cuánta agua estás usando y cuánta se te va. Con esos datos puedes ajustar "
        "los riegos y comparar un lote con otro o una cosecha con la siguiente.",
        "Usar menos agua también trae otros ahorros: menos semilla perdida, menos "
        "problemas de plagas y, en muchos casos, menos gasto en productos. Antes de hacer "
        "cambios grandes, como una nivelación, consulta con el técnico de los arroceros "
        "o de tu asociación cómo hacerlo en tu zona y qué apoyo hay disponible.",
        "Esta semana recorre tu lote cuando esté con agua y anota dónde se empoza y dónde "
        "queda seco. Mira por dónde se escapa el agua al drenaje. Con ese recorrido ya "
        "sabes cuáles son los puntos que más necesitan arreglo antes de la próxima "
        "siembra.",
    ),
    key_points=(
        "Un lote bien nivelado reparte el agua pareja y necesita menos riego.",
        "Haz los caballones en curva y mantén limpios los canales de entrada y drenaje.",
        "Mide el agua que entra y sale para saber cuánta estás gastando.",
        "Consulta al técnico de los arroceros antes de hacer cambios grandes en el lote.",
    ),
    video=VideoSpec(
        video_id="7VVK1sfUBlw",
        title="Agricultura al Día - Ahorro de agua en cultivos de arroz",
        channel="Ministerio de Agricultura y Desarrollo Rural",
    ),
)

_MAIZ_SANIDAD = CapsuleSpec(
    slug="maiz-plagas-y-enfermedades",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("maiz",),
    relevance=8.0,
    title="Maíz sano: vigila antes de fumigar",
    summary="Monitorear el lote, sembrar a la distancia correcta, rotar con leguminosas y usar semilla de calidad previene más pérdidas que fumigar a ciegas.",
    paragraphs=(
        "En el maíz, las plagas, los hongos y las malezas pueden quitarte buena parte de "
        "la cosecha. La reacción más común es fumigar por calendario o porque el vecino "
        "lo hizo, pero eso cuesta plata, mata a los insectos que te ayudan y con el "
        "tiempo hace que las plagas se vuelvan más resistentes. Funciona mejor un manejo "
        "integrado: mirar primero y actuar a tiempo, combinando varias prácticas.",
        "Todo empieza con buena semilla. Usa semilla certificada o de calidad conocida, "
        "que cumpla lo que pide el ICA, porque una semilla mala trae problemas desde el "
        "primer día. Siembra a la distancia recomendada para tu variedad: cuando las "
        "plantas quedan muy juntas, la humedad se encierra y los hongos de la mazorca "
        "encuentran el ambiente perfecto.",
        "Monitorea el lote cada semana. Camina en zigzag y revisa plantas en varios "
        "sitios: busca hojas comidas, huequitos en el tallo, manchas en las hojas y "
        "mazorcas dañadas. Anota lo que ves. Si encuentras una plaga al comienzo, todavía "
        "se puede manejar con controladores biológicos o productos de bajo impacto; si "
        "esperas a verla en todo el lote, ya es tarde y sale caro.",
        "Rota los cultivos. Sembrar maíz detrás de maíz en el mismo lote deja que las "
        "plagas y enfermedades se acumulen de una cosecha a la otra. Alternar con una "
        "leguminosa, como el frijol o la soya, corta ese ciclo y además mejora el suelo. "
        "En lotes que tuvieron mucha enfermedad, el manejo de los residuos de la cosecha "
        "también ayuda; pregunta al técnico cuál es la mejor forma en tu zona.",
        "Cuando sí haga falta aplicar algo, que sea con criterio. Pregunta al técnico o al "
        "agrónomo qué producto conviene, en qué momento y cómo aplicarlo con protección. "
        "Los productos mal usados son peligrosos para tu salud, la de tu familia y el "
        "agua.",
        "Esta semana arma tu hoja de monitoreo: en una libreta haz una tabla con la fecha, "
        "el sitio del lote y lo que encontraste. Revisa veinte plantas en cinco puntos "
        "distintos. Después de un mes tendrás una idea clara de qué problema te visita "
        "más y cuándo.",
    ),
    key_points=(
        "Usa semilla certificada o de calidad conocida y siembra a la distancia recomendada.",
        "Revisa el lote cada semana en varios puntos y anota lo que encuentras.",
        "Rota el maíz con leguminosas para cortar el ciclo de plagas y enfermedades.",
        "Antes de aplicar un producto, consulta al técnico cuál, cuándo y cómo.",
    ),
    video=VideoSpec(
        video_id="nzkSsLD3O2I",
        title="Manejo fitosanitario | Modelo Productivo de Maíz y Soya",
        channel="AGROSAVIA TV",
    ),
)

_GANADERIA_SILVOPASTORIL = CapsuleSpec(
    slug="ganaderia-arboles-en-el-potrero",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=("ganaderia",),
    relevance=8.0,
    title="Árboles en el potrero: más sombra, más comida y menos calor",
    summary="Las cercas vivas y los sistemas silvopastoriles le dan sombra y forraje al ganado y protegen el suelo. Se puede empezar en pequeño.",
    paragraphs=(
        "Con días más calientes y veranos más largos, el ganado sufre: come menos, "
        "produce menos leche y gana menos peso. Los potreros sin un solo árbol se secan "
        "rápido y el suelo se compacta. Una salida probada en Colombia es la ganadería "
        "con árboles, conocida como sistema silvopastoril, que combina pasto, arbustos "
        "forrajeros y árboles en el mismo potrero.",
        "No tienes que transformar toda la finca de una vez. Lo más sencillo para empezar "
        "son las cercas vivas: en lugar de postes muertos, sembrar estacas de árboles que "
        "pegan fácil y que con el tiempo dan sombra, forraje y madera. Escoge estacas de "
        "árboles sanos, córtalas en bisel y siémbralas en tierra preparada. El técnico de "
        "tu zona te puede decir qué especies se dan mejor en tu clima.",
        "Lo más importante es proteger lo sembrado. El ganado se come los rebrotes "
        "tiernos y tumba las plantas jóvenes, así que aísla las siembras nuevas con una "
        "cerca eléctrica temporal, separada un buen trecho de las plantas. Ten paciencia: "
        "los arbustos forrajeros necesitan varios meses, por lo general de seis a ocho, "
        "antes de que el ganado los pueda ramonear sin acabarlos.",
        "Cuando ya tengas árboles y forrajeras en el potrero, maneja bien el pastoreo. "
        "Divide en potreros más pequeños y rota el ganado, dejando que cada potrero "
        "descanse el tiempo suficiente para que el pasto y los arbustos se recuperen; en "
        "muchos casos hablamos de mes y medio a dos meses. Así el suelo se cubre mejor, "
        "guarda más agua y el potrero produce más comida por hectárea.",
        "Los beneficios se ven en la cuenta: menos plata en suplementos durante el "
        "verano, animales menos estresados por el calor y un suelo que no se lava con las "
        "lluvias. Además, los árboles cuidan las quebradas y atraen aves y otros animales "
        "que ayudan a controlar plagas.",
        "Esta semana escoge un lindero de tu finca donde haga falta cambiar postes y "
        "planea sembrar ahí tu primera cerca viva. Pregunta al técnico qué especie te "
        "conviene, consigue las estacas y aparta el material para aislarla del ganado. "
        "Empezar con un tramo corto es suficiente para aprender.",
    ),
    key_points=(
        "Los árboles en el potrero dan sombra, forraje y protegen el suelo del calor y la lluvia.",
        "Empieza con cercas vivas y pregunta al técnico qué especie se da en tu clima.",
        "Aísla lo sembrado del ganado y espera varios meses antes del primer ramoneo.",
        "Rota los potreros y deja que cada uno descanse para que se recupere.",
    ),
    video=VideoSpec(
        video_id="4bsW-61E7c4",
        title="Cap 107 - Sistemas silvopastoriles al alcance de todos  #manualpracticoganadero",
        channel="FEDEGAN",
    ),
)

_HORTALIZAS_HUERTA = CapsuleSpec(
    slug="hortalizas-huerta-para-comer-y-vender",
    topic=TOPIC_FINANZAS,
    tags=("hortalizas",),
    relevance=8.0,
    title="Tu huerta para comer y para vender",
    summary="Diversificar las hortalizas, hacer abono con los residuos y llevar las cuentas de lo que vendes ayuda a ahorrar en comida y a ganar con los excedentes.",
    paragraphs=(
        "Una huerta bien llevada da para dos cosas: para la comida de la casa y para "
        "vender lo que sobra. Cuando todo el lote está sembrado de una sola hortaliza, un "
        "mal precio o una plaga te deja sin nada. Cuando siembras varias, siempre hay algo "
        "que comer y algo que vender, y el riesgo se reparte.",
        "Diversifica con cabeza. Combina hortalizas de ciclo corto, que se cosechan en "
        "pocas semanas, con otras de ciclo más largo, para tener cosecha casi todo el "
        "año. Escoge lo que se da bien en tu clima y lo que la gente de tu zona compra. "
        "Pregunta en la plaza o en la tienda qué se vende fácil y qué escasea en ciertas "
        "épocas: esa información vale plata.",
        "Ahorra en abono aprovechando lo que ya tienes. Con los residuos de la cosecha, "
        "las cáscaras de la cocina y el estiércol de los animales puedes hacer compost o "
        "lombriabono. Así devuelves a la tierra lo que le sacaste, gastas menos en abonos "
        "comprados y el suelo guarda mejor el agua. Usa también buena semilla: una semilla "
        "barata pero mala te hace perder todo el trabajo.",
        "Cuida el agua y el suelo. Riega temprano o al final de la tarde, cuando se "
        "evapora menos, y mantén el suelo cubierto entre las plantas. Si tienes plagas, "
        "revisa primero con el técnico qué opciones hay antes de usar cualquier producto, "
        "sobre todo en hortalizas que se comen frescas.",
        "Lleva las cuentas. Anota cuánto gastas en semilla, abono y agua en cada siembra, "
        "y cuánto vendes. Anota también lo que la familia se come, porque es plata que no "
        "tuviste que gastar en el mercado. Al final de cada cosecha sabrás qué hortaliza "
        "te deja más y cuál conviene cambiar.",
        "Esta semana haz una lista de las hortalizas que más compra tu familia y de las "
        "que más se venden en tu vereda o en la plaza. Escoge una que no tengas y que se "
        "dé en tu clima, y planea sembrar un pedacito para probar. Empieza también una "
        "hoja de cuentas solo para la huerta.",
    ),
    key_points=(
        "Sembrar varias hortalizas reparte el riesgo y da cosecha casi todo el año.",
        "Pregunta en la plaza qué se vende fácil antes de decidir qué sembrar.",
        "Haz compost o lombriabono con los residuos para gastar menos en abono.",
        "Anota lo que gastas, lo que vendes y lo que se come la familia.",
    ),
    video=VideoSpec(
        video_id="u_eytQ0Hwxc",
        title="Prácticas sostenibles en el modelo agroalimentario de hortalizas en el Caribe seco colombiano",
        channel="AGROSAVIA TV",
    ),
)

_PANADERIA_COSTOS = CapsuleSpec(
    slug="panaderia-cuanto-cuesta-tu-pan",
    topic=TOPIC_FINANZAS,
    tags=("panaderia",),
    relevance=8.0,
    title="¿Cuánto te cuesta de verdad cada pan?",
    summary="Aprende a sacar el costo de cada producto con la receta, el gas, el empaque y lo que se pierde, para ponerle un precio que sí te deje ganancia.",
    paragraphs=(
        "Muchas panaderías venden bastante y aun así sienten que la plata no alcanza. "
        "Casi siempre el problema es el mismo: no saben cuánto les cuesta de verdad cada "
        "pan. Ponen el precio mirando al vecino y, cuando suben la harina, el azúcar o el "
        "gas, siguen vendiendo igual sin darse cuenta de que ya están perdiendo.",
        "Saca el costo con la receta. Escribe todo lo que lleva una tanda: harina, azúcar, "
        "huevos, mantequilla, levadura y sal, con la cantidad y lo que te costó. Suma "
        "todo y divide por el número de panes que salen de esa tanda. Eso es lo que te "
        "cuestan los ingredientes de cada pan. Repite la cuenta cada vez que te suban un "
        "insumo importante.",
        "No te olvides de los costos que no se ven. El gas o la energía del horno, las "
        "bolsas y el papel, el agua, el arriendo y el pago de quien te ayuda también "
        "salen de la venta del pan. Una forma sencilla es sumar lo que gastas en eso al "
        "mes y repartirlo entre los panes que vendes en el mes. Incluye también tu propio "
        "trabajo: si no te pagas, el negocio parece ganar más de lo que gana.",
        "Cuenta lo que se pierde. El pan que no se vende, el que se quema o se daña "
        "también es costo. Anota cada día cuánto te sobra de cada producto. Si de un pan "
        "siempre sobra, haz menos o cambia la hora en que lo horneas; si de otro siempre "
        "falta, ahí hay una venta que estás dejando ir.",
        "Con el costo completo ya puedes poner un precio con cabeza. El precio debe cubrir "
        "el costo y dejar una ganancia. Si no puedes subirlo sin perder clientes, busca "
        "dónde ahorrar: comprar algunos insumos en mayor cantidad con otros panaderos, "
        "ajustar el tamaño o hacer menos de lo que no se vende.",
        "Esta semana escoge tus tres panes que más vendes y saca el costo de cada uno con "
        "la receta. Compáralo con el precio al que lo vendes. Si la diferencia es muy "
        "pequeña o no alcanza para los demás gastos, ya sabes por dónde empezar a "
        "ajustar.",
    ),
    key_points=(
        "Saca el costo de cada pan con la receta y repítelo cuando suban los insumos.",
        "Suma el gas, el empaque, el arriendo y tu propio trabajo, no solo los ingredientes.",
        "Anota cada día lo que sobra o se daña: también es costo.",
        "El precio debe cubrir el costo completo y dejar una ganancia.",
    ),
)

_MISCELANEA_FIADO = CapsuleSpec(
    slug="miscelanea-el-fiado",
    topic=TOPIC_FINANZAS,
    tags=("miscelanea",),
    relevance=8.0,
    title="El fiado: cómo darlo sin quebrar tu negocio",
    summary="Fiar ayuda a los clientes y a vender más, pero sin control se vuelve plata que nunca vuelve. Aprende a llevarlo con orden y con límites claros.",
    paragraphs=(
        "En muchos negocios de barrio el fiado es parte de la relación con los clientes. "
        "Ayuda a la gente cuando está corta de plata y hace que vuelvan. Pero cada cosa "
        "que fías es mercancía que ya pagaste y todavía no te han pagado. Si el fiado "
        "crece sin control, un día te das cuenta de que tienes el estante vacío, la caja "
        "sin plata y un cuaderno lleno de deudas.",
        "Lleva el fiado por escrito, siempre. Ten un cuaderno solo para eso, con una "
        "página por cliente. Anota la fecha, lo que se llevó, el valor y lo que abona. "
        "Pídele al cliente que revise y que firme o ponga sus iniciales cuando se lleve "
        "algo. Así no hay discusiones después y tú sabes en todo momento cuánto te deben.",
        "Ponle límites. Decide cuánto es lo máximo que le fías a cada cliente y hasta "
        "cuándo tiene para pagar, por ejemplo hasta la quincena. Díselo con claridad y con "
        "respeto desde el principio. Si alguien ya llegó a su límite o no ha pagado lo "
        "anterior, no le fíes más hasta que se ponga al día. No es desconfianza: es "
        "cuidar el negocio que también le sirve a él.",
        "Mira el total cada semana. Suma todo lo que te deben y compáralo con lo que "
        "vendes en una semana. Si el fiado se te está acercando a lo que vendes, estás "
        "financiando a tus clientes con la plata que necesitas para surtir. En ese caso, "
        "frena el fiado nuevo y concéntrate en cobrar lo que ya tienes en la calle.",
        "Cobra con tacto pero cobra. Recuérdale al cliente la fecha acordada, ofrécele "
        "abonar por partes si le queda difícil y agradécele cuando paga. Separa la plata "
        "del negocio de la de la casa, para que lo que te pagan del fiado vuelva al "
        "negocio y no se pierda en otros gastos.",
        "Esta semana suma todo lo que te deben en el cuaderno del fiado y anota el total. "
        "Mira quiénes llevan más de un mes sin pagar y define con cada uno una fecha para "
        "ponerse al día. Decide también cuál va a ser tu límite de fiado por cliente de "
        "aquí en adelante.",
    ),
    key_points=(
        "Lo que fías es mercancía que ya pagaste y todavía no te han pagado.",
        "Anota todo en un cuaderno, con una página por cliente y su firma o iniciales.",
        "Pon un límite y una fecha de pago a cada cliente, y díselo desde el principio.",
        "Suma el fiado cada semana: si se acerca a lo que vendes, frena y cobra.",
    ),
)

CAPSULES: Final[tuple[CapsuleSpec, ...]] = (
    _GENERAL_CLIMA,
    _GENERAL_AGUA,
    _GENERAL_PLAN_B,
    _CAFE_CLIMA,
    _CAFE_FINANZAS,
    _CAFE_RIESGOS,
    _TIENDA_CLIMA,
    _TIENDA_FINANZAS,
    _TIENDA_RIESGOS,
    _CAFE_BROCA,
    _TIENDA_INVENTARIO,
    _FINANZAS_GOTA_A_GOTA,
    _AGRO_SOSTENIBLE,
    _AGRO_RIESGOS,
    _TIENDA_VIDEOS,
    _PLATANO_LABORES,
    _AGUACATE_SUELO,
    _CACAO_MONILIA,
    _ARROZ_AGUA,
    _MAIZ_SANIDAD,
    _GANADERIA_SILVOPASTORIL,
    _HORTALIZAS_HUERTA,
    _PANADERIA_COSTOS,
    _MISCELANEA_FIADO,
)

PATHS: Final[tuple[PathSpec, ...]] = (
    PathSpec(
        slug="ruta-campo-sostenibilidad-y-riesgos",
        title="Ruta del campo: sostenibilidad y riesgos",
        summary="Aprende a cuidar el suelo, el agua y la plata de tu finca, y a conocer los riesgos del campo para estar preparado.",
        capsule_slugs=(_AGRO_SOSTENIBLE.slug, _AGRO_RIESGOS.slug),
        questions=(
            QuestionSpec(
                "¿Qué busca la agricultura sostenible?",
                (
                    "Producir lo más posible sin importar el suelo",
                    "Producir comida y plata cuidando el suelo, el agua y la comunidad",
                    "Dejar de usar la tierra",
                ),
                1,
            ),
            QuestionSpec(
                "¿Cuáles son los cuatro riesgos principales del campo?",
                (
                    "Climáticos, biológicos, geológicos y financieros",
                    "Solo las plagas",
                    "Solo los precios del café",
                ),
                0,
            ),
            QuestionSpec(
                "Antes de fumigar contra una plaga, ¿qué conviene hacer?",
                (
                    "Echar el doble de producto",
                    "Fumigar toda la finca por si acaso",
                    "Revisar el daño real y consultar al técnico",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-tienda-negocio-en-video",
        title="Ruta corta: tu negocio en video",
        summary="Aprende a grabar videos sencillos con tu celular para que más clientes conozcan tu tienda, cuidando tu seguridad.",
        capsule_slugs=(_TIENDA_VIDEOS.slug,),
        questions=(
            QuestionSpec(
                "¿Cuál es el truco para perderle el miedo a la cámara?",
                (
                    "Hablarle como a un cliente de confianza",
                    "Leer un papel sin mirar",
                    "Grabar con los ojos cerrados",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué no se debe mostrar en un video de la tienda?",
                (
                    "Los productos y sus precios",
                    "La caja, el dinero o clientes sin su permiso",
                    "El horario de atención",
                ),
                1,
            ),
            QuestionSpec(
                "¿Cómo sabes si tus videos te traen clientes?",
                (
                    "No hay forma de saberlo",
                    "Contando los me gusta",
                    "Preguntando a los clientes nuevos cómo supieron de ti",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-cafe-broca",
        title="Ruta corta: la broca del café",
        summary="Conoce la plaga que más daña el café y aprende a revisar tu lote y a recoger bien para que no se refugie.",
        capsule_slugs=(_CAFE_BROCA.slug,),
        questions=(
            QuestionSpec(
                "¿Qué ayuda más a que la broca no se refugie después de la cosecha?",
                (
                    "Dejar los frutos en el suelo para que se pudran",
                    "Hacer el repase y levantar los frutos de las ramas y del suelo",
                    "Esperar a que llegue la próxima lluvia",
                ),
                1,
            ),
            QuestionSpec(
                "¿Cómo sabes qué tan afectado está tu lote?",
                (
                    "Mirando los frutos solo por fuera",
                    "Preguntándole al vecino",
                    "Revisando una muestra de frutos para ver si tienen perforación",
                ),
                2,
            ),
            QuestionSpec(
                "Antes de aplicar cualquier producto contra la plaga, ¿qué debes hacer?",
                (
                    "Consultar al técnico o al extensionista de tu comité",
                    "Echarle el doble para estar seguro",
                    "Mezclar varios productos",
                ),
                0,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-tienda-inventario",
        title="Ruta corta: el inventario de tu tienda",
        summary="Aprende a ver qué se vende, qué se queda quieto y cuánto pedir para que la plata de tu tienda no quede parada.",
        capsule_slugs=(_TIENDA_INVENTARIO.slug,),
        questions=(
            QuestionSpec(
                "¿Por qué un producto que no se vende es un problema?",
                (
                    "Porque es plata que ya pagaste y está parada",
                    "Porque ocupa menos espacio",
                    "Porque con el tiempo sube de precio solo",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué significa primero en entrar, primero en salir?",
                (
                    "Vender primero lo que llegó más nuevo",
                    "Vender primero lo que llegó antes, sobre todo si se vence",
                    "Vender solo lo más caro",
                ),
                1,
            ),
            QuestionSpec(
                "Antes de aprovechar un descuento por comprar más, ¿qué debes calcular?",
                (
                    "El color del empaque",
                    "Si el vendedor es amable",
                    "Cuánto alcanzas a vender antes de que se venza",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-finanzas-gota-a-gota",
        title="Ruta corta: cuidado con el gota a gota",
        summary="Para quien cultiva y para quien atiende un negocio: cómo reconocer el gota a gota y qué alternativas más seguras tienes.",
        capsule_slugs=(_FINANZAS_GOTA_A_GOTA.slug,),
        questions=(
            QuestionSpec(
                "¿Cuál es una señal de alerta de un préstamo gota a gota?",
                (
                    "Te prestan sin pedir casi nada y no te dicen el costo total",
                    "Te entregan un contrato claro",
                    "Te explican la tasa y cuánto pagarás en total",
                ),
                0,
            ),
            QuestionSpec(
                "Antes de aceptar un crédito, ¿qué debes preguntar?",
                (
                    "Solo el valor de la primera cuota",
                    "Cuánto pagarás en total y si la entidad está vigilada",
                    "Nada: todos cobran igual",
                ),
                1,
            ),
            QuestionSpec(
                "Si ya te están amenazando por un gota a gota, ¿qué conviene hacer?",
                (
                    "Pagar y quedarte callado",
                    "Esconderte unos días",
                    "Contarlo a alguien de confianza y denunciar",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-general-clima",
        title="Ruta general: clima, agua y plan B",
        summary="Lo básico para cualquier persona: leer el clima, cuidar el agua y tener un plan para las temporadas difíciles.",
        capsule_slugs=(_GENERAL_CLIMA.slug, _GENERAL_AGUA.slug, _GENERAL_PLAN_B.slug),
        questions=(
            QuestionSpec(
                "¿Para qué sirve llevar una libreta con la lluvia y el calor de cada semana?",
                (
                    "Para descubrir los patrones de tu propio terreno y decidir con tiempo",
                    "Para que el IDEAM te pague por los datos",
                    "Para evitar que llueva",
                ),
                0,
            ),
            QuestionSpec(
                "¿Cuál es una buena forma de reducir la evaporación al regar?",
                (
                    "Regar al mediodía con más agua",
                    "Regar temprano en la mañana o al final de la tarde",
                    "Dejar la manguera corriendo todo el día",
                ),
                1,
            ),
            QuestionSpec(
                "¿Qué debe tener un buen plan B para las temporadas difíciles?",
                (
                    "Solo el número de un prestamista",
                    "Teléfonos útiles, copias de documentos y un fondo para imprevistos",
                    "Esperar a que pase y decidir después",
                ),
                1,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-cafe",
        title="Ruta del cafetal",
        summary="Protege tu cafetal del clima, ordena las cuentas de la cosecha y aprende a manejar los riesgos.",
        capsule_slugs=(_CAFE_CLIMA.slug, _CAFE_FINANZAS.slug, _CAFE_RIESGOS.slug),
        questions=(
            QuestionSpec(
                "¿Qué ayuda a frenar la erosión en un cafetal en ladera cuando llueve fuerte?",
                (
                    "Dejar el suelo completamente pelado",
                    "Mantener cobertura viva entre las calles del cafetal",
                    "Quitar todo el sombrío",
                ),
                1,
            ),
            QuestionSpec(
                "¿Por qué conviene separar los gastos de la finca de los de la casa?",
                (
                    "Porque así sabes cuánto cuesta producir y cuánto te queda realmente",
                    "Porque así lo exige la ley",
                    "Para pagar menos intereses",
                ),
                0,
            ),
            QuestionSpec(
                "¿Cuál de estas NO es una forma de manejar un riesgo?",
                (
                    "Prevenirlo",
                    "Trasladarlo, por ejemplo con un seguro",
                    "Ignorarlo y esperar que no pase",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-tienda-barrio",
        title="Ruta de la tienda de barrio",
        summary="Cuida tu negocio del calor y las lluvias, separa la plata del negocio y de la casa, y conoce sus riesgos.",
        capsule_slugs=(_TIENDA_CLIMA.slug, _TIENDA_FINANZAS.slug, _TIENDA_RIESGOS.slug),
        questions=(
            QuestionSpec(
                "¿Qué conviene hacer con los productos que se mojan fácil antes de las lluvias?",
                (
                    "Dejarlos en el piso",
                    "Subirlos a estibas o estantes bajos",
                    "Taparlos con papel periódico",
                ),
                1,
            ),
            QuestionSpec(
                "¿Qué significa ponerte un sueldo en tu tienda?",
                (
                    "Sacar del negocio un valor fijo, siempre el mismo día, para tus gastos personales",
                    "Sacar plata de la caja cada vez que la necesites",
                    "Pagarle a un empleado",
                ),
                0,
            ),
            QuestionSpec(
                "Antes de contratar un seguro o pedir un crédito, ¿qué debes preguntar?",
                (
                    "Qué cubre, qué excluye y cuánto pagarás en total",
                    "Nada: todos son iguales",
                    "Solo el valor de la primera cuota",
                ),
                0,
            ),
        ),
    ),
    # Rutas cortas de ejemplo, una por actividad (pendientes de revisión de la Escuela).
    PathSpec(
        slug="ruta-platano-labores",
        title="Ruta corta: las labores del platanal",
        summary="Aprende las labores que mantienen sano tu platanal y hacen que el racimo llene bien.",
        capsule_slugs=(_PLATANO_LABORES.slug,),
        questions=(
            QuestionSpec(
                "¿Qué plantas conviene dejar en cada sitio al deshijar?",
                (
                    "Todos los colinos que salgan",
                    "La madre, un hijo y un nieto",
                    "Solo la planta madre",
                ),
                1,
            ),
            QuestionSpec(
                "¿Por qué hay que desinfectar las herramientas entre mata y mata?",
                (
                    "Para que no se oxiden",
                    "Porque así cortan más rápido",
                    "Para no llevar enfermedades como el moko a otras plantas",
                ),
                2,
            ),
            QuestionSpec(
                "Si una planta se marchita de un momento a otro, ¿qué debes hacer?",
                (
                    "No moverla y avisar al ICA o al técnico",
                    "Arrancarla y llevarla a otra finca",
                    "Echarle el doble de abono",
                ),
                0,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-aguacate-suelo",
        title="Ruta corta: suelo y agua en el aguacate",
        summary="Conoce tu terreno y maneja el agua para que el aguacate aguante las lluvias fuertes y los veranos largos.",
        capsule_slugs=(_AGUACATE_SUELO.slug,),
        questions=(
            QuestionSpec(
                "¿Qué le pasa al aguacate en un sitio que se encharca?",
                (
                    "Crece más rápido",
                    "Suele enfermarse de la raíz",
                    "Da más fruta",
                ),
                1,
            ),
            QuestionSpec(
                "¿Cuándo conviene recorrer la finca para ver los puntos de riesgo?",
                (
                    "Después de un aguacero",
                    "Solo en verano",
                    "Nunca, no hace falta",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué conviene hacer en las orillas de quebradas y nacimientos?",
                (
                    "Sembrar aguacate hasta el borde",
                    "Fumigar para limpiarlas",
                    "Dejarlas con su vegetación y no fumigar ahí",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-cacao-monilia",
        title="Ruta corta: monilia y mazorca negra en el cacao",
        summary="Reconoce las dos enfermedades que más dañan el cacao y aprende a frenarlas con revisión, poda y orden.",
        capsule_slugs=(_CACAO_MONILIA.slug,),
        questions=(
            QuestionSpec(
                "¿Cuándo hay que sacar las mazorcas con monilia?",
                (
                    "Cuando ya están cubiertas de polvo blanco",
                    "Antes de que hagan el polvo blanco",
                    "Solo al final de la cosecha",
                ),
                1,
            ),
            QuestionSpec(
                "¿Qué se hace con las mazorcas enfermas que se retiran?",
                (
                    "Se dejan en el suelo cubiertas con hojarasca",
                    "Se dejan colgando en el árbol",
                    "Se llevan a otra finca",
                ),
                0,
            ),
            QuestionSpec(
                "¿Por qué ayuda la poda contra estas enfermedades?",
                (
                    "Porque el árbol queda más bonito",
                    "Porque así se usa menos abono",
                    "Porque entra luz y circula el aire, y el hongo prospera con humedad y sombra",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-arroz-agua",
        title="Ruta corta: ahorra agua en el arroz",
        summary="Aprende a nivelar, a hacer caballones en curva y a medir el agua para producir gastando menos.",
        capsule_slugs=(_ARROZ_AGUA.slug,),
        questions=(
            QuestionSpec(
                "¿Para qué sirve nivelar bien el lote de arroz?",
                (
                    "Para que el agua se reparta pareja y se necesite menos",
                    "Para que crezca más maleza",
                    "Para que el agua se acumule en las partes bajas",
                ),
                0,
            ),
            QuestionSpec(
                "¿Cómo conviene hacer los caballones?",
                (
                    "En línea recta, sin importar el terreno",
                    "Siguiendo las curvas del terreno",
                    "No hace falta hacerlos",
                ),
                1,
            ),
            QuestionSpec(
                "¿Por qué es útil medir el agua que entra y sale del lote?",
                (
                    "Porque lo pide el vecino",
                    "No sirve para nada",
                    "Para saber cuánta gastas y cuánta se te va",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-maiz-sanidad",
        title="Ruta corta: maíz sano",
        summary="Aprende a vigilar tu lote de maíz y a combinar prácticas para tener menos plagas y enfermedades.",
        capsule_slugs=(_MAIZ_SANIDAD.slug,),
        questions=(
            QuestionSpec(
                "¿Cada cuánto conviene revisar el lote de maíz?",
                (
                    "Cada semana, en varios puntos",
                    "Solo cuando se ve todo dañado",
                    "Una vez al año",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué ayuda a cortar el ciclo de plagas y enfermedades?",
                (
                    "Sembrar maíz detrás de maíz",
                    "Rotar el maíz con una leguminosa",
                    "Sembrar las plantas muy juntas",
                ),
                1,
            ),
            QuestionSpec(
                "Antes de aplicar un producto, ¿qué debes hacer?",
                (
                    "Usar el que tenga el vecino",
                    "Mezclar varios para estar seguro",
                    "Preguntar al técnico cuál, cuándo y cómo aplicarlo",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-ganaderia-arboles",
        title="Ruta corta: árboles en el potrero",
        summary="Aprende a empezar con cercas vivas y a manejar el pastoreo para tener más sombra y comida para el ganado.",
        capsule_slugs=(_GANADERIA_SILVOPASTORIL.slug,),
        questions=(
            QuestionSpec(
                "¿Cuál es una forma sencilla de empezar con árboles en la finca?",
                (
                    "Sembrar cercas vivas",
                    "Tumbar los árboles que quedan",
                    "Cambiar todo el potrero de una vez",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué hay que hacer con lo recién sembrado?",
                (
                    "Dejar que el ganado lo ramonee de inmediato",
                    "Aislarlo del ganado hasta que crezca",
                    "No regarlo nunca",
                ),
                1,
            ),
            QuestionSpec(
                "¿Para qué sirve rotar los potreros?",
                (
                    "Para que el ganado camine más",
                    "Para gastar más cerca",
                    "Para que cada potrero descanse y se recupere",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-hortalizas-huerta",
        title="Ruta corta: tu huerta para comer y vender",
        summary="Aprende a diversificar tu huerta, a ahorrar en abono y a llevar las cuentas de lo que vendes.",
        capsule_slugs=(_HORTALIZAS_HUERTA.slug,),
        questions=(
            QuestionSpec(
                "¿Por qué conviene sembrar varias hortalizas y no una sola?",
                (
                    "Porque se reparte el riesgo y hay cosecha casi todo el año",
                    "Porque así se gasta más semilla",
                    "No conviene, es mejor una sola",
                ),
                0,
            ),
            QuestionSpec(
                "¿Cómo se puede ahorrar en abono?",
                (
                    "Botando los residuos de la cosecha",
                    "Haciendo compost o lombriabono con los residuos",
                    "Comprando el doble de abono",
                ),
                1,
            ),
            QuestionSpec(
                "¿Qué conviene anotar en las cuentas de la huerta?",
                (
                    "Solo lo que se vende",
                    "Nada, no hace falta",
                    "Lo que gastas, lo que vendes y lo que se come la familia",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-panaderia-costos",
        title="Ruta corta: el costo de tu pan",
        summary="Aprende a sacar el costo real de cada pan para ponerle un precio que sí te deje ganancia.",
        capsule_slugs=(_PANADERIA_COSTOS.slug,),
        questions=(
            QuestionSpec(
                "¿Cómo se saca el costo de los ingredientes de cada pan?",
                (
                    "Sumando lo que lleva una tanda y dividiendo por los panes que salen",
                    "Mirando el precio del vecino",
                    "Adivinando",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué otros costos debes sumar además de los ingredientes?",
                (
                    "Ninguno",
                    "El gas, el empaque, el arriendo y tu propio trabajo",
                    "Solo el arriendo",
                ),
                1,
            ),
            QuestionSpec(
                "¿Qué debe cubrir el precio del pan?",
                (
                    "Solo la harina",
                    "Lo mismo que cobra el vecino",
                    "El costo completo y una ganancia",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-miscelanea-fiado",
        title="Ruta corta: el fiado con orden",
        summary="Aprende a llevar el fiado por escrito y con límites para que no se coma la plata de tu negocio.",
        capsule_slugs=(_MISCELANEA_FIADO.slug,),
        questions=(
            QuestionSpec(
                "¿Qué es, en el fondo, lo que fías?",
                (
                    "Mercancía que ya pagaste y todavía no te han pagado",
                    "Un regalo para el cliente",
                    "Plata que no importa",
                ),
                0,
            ),
            QuestionSpec(
                "¿Qué conviene acordar con cada cliente al fiarle?",
                (
                    "Nada, para no incomodarlo",
                    "Un límite y una fecha de pago",
                    "Que pague cuando quiera",
                ),
                1,
            ),
            QuestionSpec(
                "Si el total del fiado se acerca a lo que vendes en una semana, ¿qué haces?",
                (
                    "Fiar más para vender más",
                    "Cerrar el negocio",
                    "Frenar el fiado nuevo y cobrar lo que ya te deben",
                ),
                2,
            ),
        ),
    ),
)
