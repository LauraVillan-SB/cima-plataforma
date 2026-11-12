"""Catálogo de contenido de ejemplo del Learning Service.

Define las microcápsulas, rutas y evaluaciones con las que arranca CIMA. Es contenido de
referencia **pendiente de revisión por la Escuela de Sostenibilidad e Inclusión**: está
escrito en español coloquial colombiano, es texto plano, no promete resultados ni da
cifras que no pueda respaldar, y no ofrece asesoría financiera personalizada. CIMA educa
y mide interés: no vende seguros ni procesa pagos (alcance del proyecto).

El contenido principal es el texto; el video de YouTube es un complemento opcional que
solo se carga con un identificador verificado (ver `VideoSpec`). Sin conexión el texto
sigue funcionando.

Cobertura actual: actividad general (respaldo, Req 4.4), café y tienda de barrio. Las
demás actividades permitidas reciben el tema general hasta que se agregue su contenido.
Requisitos: 4.1, 4.2, 4.3, 4.4, 7.1, 13.4.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Final

from app.learning.constants import (
    GENERAL_TAG,
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
)

PATHS: Final[tuple[PathSpec, ...]] = (
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
)
