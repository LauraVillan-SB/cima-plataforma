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
    title="Aprenda a leer las señales del clima de su zona",
    summary="Use el pronóstico y una libreta sencilla para saber qué viene y prepararse a tiempo.",
    paragraphs=(
        "¿Sabe usted cómo leer las señales del clima de su zona? Antes, mucha gente sabía "
        "cuándo sembrar o cuándo esperar la lluvia mirando el calendario de siempre. Hoy eso "
        "ya no alcanza: las lluvias llegan antes o después, hay semanas de sol fuerte y luego "
        "aguaceros que lo arrasan todo. La buena noticia es que usted puede ir un paso "
        "adelante si aprende a leer las señales de su zona y a tomar decisiones con tiempo, "
        "no cuando el problema ya llegó.",
        "Empiece por lo más simple: una libreta. Anote cada semana si llovió, cuánto "
        "aproximadamente, si hizo mucho calor y si hubo vientos fuertes. Con unos meses de "
        "apuntes va a ver patrones propios de su terreno que ningún pronóstico general le "
        "da. Un tarro recto puesto al aire libre le sirve de pluviómetro casero: con una "
        "regla mide cuántos centímetros de agua se juntaron.",
        "Después, mire el pronóstico oficial. En Colombia el IDEAM publica pronósticos y "
        "avisos del tiempo, y también informa cuando se espera un fenómeno de El Niño o de "
        "La Niña. El Niño suele traer menos lluvia y más calor; La Niña, más lluvia y más "
        "riesgo de inundaciones y deslizamientos. No tiene que entender toda la ciencia: "
        "basta con saber cuál viene para ajustar sus decisiones.",
        "Converse también con sus vecinos y con los técnicos de su zona. Lo que uno ve, "
        "otro lo confirma, y entre todos se detectan los cambios más rápido. Cuando sabe "
        "qué viene puede decidir con calma: si adelanta o atrasa una siembra, si guarda "
        "agua, si repara un techo o un canal antes de las lluvias, o si separa un dinero "
        "para la temporada difícil.",
        "Piense en su última temporada difícil. ¿Qué señales hubo antes y no las anotó? "
        "Si hubiera tenido una libreta, ¿qué habría hecho distinto? Empiece hoy con la "
        "primera hoja: la fecha y cómo estuvo el tiempo.",
        "Imagine una familia que anota durante un año los días de lluvia fuerte y descubre "
        "que las siembras de cierto mes se le pierden casi siempre. Con esa libreta puede "
        "mover la fecha de siembra unas semanas y proteger su cosecha. No necesitó aparatos "
        "ni estudios, solo constancia. Haga lo mismo con lo que más le importe, su cultivo, "
        "su local o su casa, y revise sus apuntes una vez al mes. Recuerde: una libreta "
        "con el clima de cada semana le ayuda a decidir a tiempo.",
    ),
    key_points=(
        "Una libreta con la lluvia y el calor de cada semana le enseña los patrones de su terreno.",
        "Un tarro recto al aire libre sirve de pluviómetro casero.",
        "El IDEAM avisa cuándo se espera El Niño o La Niña: infórmese antes de decidir.",
        "Decidir con tiempo cuesta menos que arreglar cuando el daño ya pasó.",
    ),
)

_GENERAL_AGUA = CapsuleSpec(
    slug="general-cuidar-el-agua",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=(GENERAL_TAG,),
    relevance=4.5,
    title="Cuide el agua: guarde y use mejor cada gota",
    summary="Ideas sencillas para juntar agua de lluvia, no desperdiciarla y llegar mejor a los meses secos.",
    paragraphs=(
        "¿Le ha pasado que el agua falta justo cuando más la necesita? El agua es lo "
        "primero que falta en una sequía y lo que más sobra en una inundación. Por eso "
        "aprender a guardarla y a usarla bien es una de las mejores formas de adaptarse al "
        "clima. No hace falta una gran obra: con pequeños cambios puede tener más agua "
        "cuando más la necesita y perder menos cuando llueve fuerte.",
        "Una forma fácil es recoger el agua lluvia del techo. Con canales limpios y un "
        "tanque o canecas con tapa para que no se críen zancudos, puede juntar agua para "
        "el aseo, para los animales o para regar. Antes de usarla para tomar necesita un "
        "tratamiento, así que consulte en el puesto de salud o en la oficina de asistencia "
        "técnica agropecuaria de su municipio cómo hacerlo de forma segura.",
        "Riegue con cabeza. Regar muy temprano en la mañana o al final de la tarde reduce "
        "la evaporación. Si puede, use riego por goteo o mangueras con pocos huecos en "
        "lugar de dejar correr el agua; así llega a la raíz y no se pierde. Cubrir el suelo "
        "con hojas secas, pasto cortado o restos de cosecha ayuda a que la tierra guarde la "
        "humedad por más tiempo.",
        "Cuide también de dónde viene el agua. Mantener la vegetación cerca de "
        "nacimientos, quebradas y reservorios protege la fuente y evita que el suelo se "
        "lave con las lluvias fuertes. Evite tirar basura, envases de agroquímicos o "
        "residuos de la finca cerca del agua: contaminarla hoy es quedarse sin ella mañana.",
        "En su casa o negocio revise las llaves y las mangueras: una gotera pequeña "
        "desperdicia muchos litros al mes, arreglarla casi no cuesta y se nota en la "
        "cuenta. Piense de dónde sale el agua que usa y cuántos días aguantaría si "
        "faltara; con esa respuesta sabrá cuánto necesita guardar.",
        "Imagine una finca pequeña con un techo de zinc de buen tamaño. En cada aguacero, "
        "si los canales están limpios, esa agua puede llenar una o varias canecas en pocos "
        "minutos. Guardada y bien tapada, sirve después para regar unas matas, lavar "
        "herramientas o dar de beber a los animales en una semana seca. Un poco de "
        "organización convierte la lluvia fuerte, que antes era un problema, en una "
        "reserva útil. Recuerde: guardar agua cuando sobra le ayuda a tenerla cuando falta.",
    ),
    key_points=(
        "Recoger agua lluvia en tanques con tapa le da reserva para la época seca.",
        "Riegue temprano o al final de la tarde y cubra el suelo para que no se seque.",
        "Proteja nacimientos y quebradas: son su fuente de agua.",
        "Revisar goteras y mangueras ahorra agua y plata.",
    ),
)

_GENERAL_PLAN_B = CapsuleSpec(
    slug="general-plan-b",
    topic=TOPIC_ADAPTACION_CLIMA,
    tags=(GENERAL_TAG,),
    relevance=4.0,
    title="Su plan B para las temporadas difíciles",
    summary="Prepare lo básico antes de una emergencia para no tomar decisiones a la carrera.",
    paragraphs=(
        "¿Sabe usted qué haría si mañana llega una emergencia? Una helada, una inundación, "
        "una sequía larga o una plaga fuerte pueden llegar sin avisar. Cuando pasa, la gente "
        "toma decisiones apuradas: vender barato, endeudarse con quien preste o dejar de "
        "pagar lo importante. Tener un plan B, escrito y sencillo, le permite reaccionar "
        "con calma. No es ser pesimista: es cuidar lo que tanto esfuerzo le costó.",
        "Empiece por responder tres preguntas: ¿qué es lo que más me puede afectar en mi "
        "zona?, ¿qué necesito para seguir adelante las primeras semanas?, ¿a quién puedo "
        "llamar? Escriba las respuestas en una hoja. Incluya teléfonos útiles: familiares, "
        "vecinos, la alcaldía, la oficina de gestión del riesgo de su municipio y los "
        "organismos de socorro de su zona.",
        "Guarde lo importante en un lugar seguro: copias de sus documentos, de escrituras "
        "o contratos y de los papeles del negocio o de la finca, de preferencia en una "
        "bolsa plástica sellada y también fotografiados en su celular. Si hay una "
        "emergencia no tendrá que correr a recuperar lo que no puede perder.",
        "Defina un fondo para imprevistos, aunque empiece con muy poco. Separar una "
        "pequeña parte de cada venta o de cada cosecha, siempre el mismo día, crea el "
        "hábito. Ese dinero no es para los gastos del mes: es para cuando el clima o el "
        "mercado lo saquen del camino. Con el tiempo lo ideal es que alcance para cubrir "
        "varias semanas de gastos básicos.",
        "Practique el plan con su familia o su equipo: que todos sepan dónde están los "
        "papeles, a quién llamar y qué hacer primero. Un plan que solo conoce una persona "
        "no sirve si esa persona no está. Y pregúntese: ¿qué sería lo primero que perdería "
        "en una emergencia? Empiece el plan protegiendo eso.",
        "Imagine que una creciente lo obliga a salir de su casa en la noche. Si el plan "
        "está escrito, sabe quién lleva los documentos, adónde van los niños y a qué "
        "teléfono llamar. Si no lo está, se pierde tiempo valioso y se olvidan cosas "
        "importantes. Dedique una tarde con calma a escribirlo con su familia: es de las "
        "tareas que más seguridad dan y que menos cuestan. Cuénteselo también a un "
        "vecino de confianza: si cada familia tiene su plan, todo el barrio responde "
        "mejor. Recuerde: un plan B escrito hoy le evita decidir a la carrera mañana.",
    ),
    key_points=(
        "Un plan B escrito evita decisiones apuradas cuando llega la emergencia.",
        "Anote teléfonos de familiares, vecinos, la alcaldía y los organismos de socorro.",
        "Guarde copias de sus documentos y tómeles fotos con el celular.",
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
    summary=(
        "Cómo el sombrío y el cuidado del suelo ayudan a su cafetal frente a más calor y "
        "aguaceros."
    ),
    paragraphs=(
        "¿Sabe usted por qué el café sufre tanto con el calor y los aguaceros? El café es "
        "una planta sensible. El calor muy alto, las lluvias fuertes y las épocas secas "
        "largas afectan la floración, el llenado del grano y la calidad. Como el clima "
        "está cambiando, cuidar el cafetal ya no es solo fertilizar y cosechar a tiempo: "
        "también es protegerlo del sol, del agua que arrastra el suelo y de los cambios "
        "bruscos entre temporadas.",
        "El sombrío es una de las ayudas más sencillas. Los árboles bien ubicados, como el "
        "plátano, el guamo u otras especies que recomiende el técnico de su zona, bajan la "
        "temperatura del cultivo, conservan la humedad del suelo y protegen del golpe "
        "directo de la lluvia. Pero ojo: demasiado sombrío tampoco conviene. Pregunte en "
        "el comité de cafeteros o a su extensionista cuánta sombra le va bien a su "
        "variedad y a su altura.",
        "El suelo es su bodega de agua y de nutrientes. En las laderas, una lluvia fuerte "
        "se lleva la tierra de arriba, que es la más rica. Para evitarlo, siembre siguiendo "
        "las recomendaciones de su técnico y deje cobertura viva entre las calles del "
        "cafetal, como arvenses nobles, en lugar de limpiar hasta dejar la tierra pelada. "
        "La cobertura frena el agua, evita la erosión y mantiene el suelo fresco.",
        "Mire también su cafetal con ojos de renovación. Las plantas muy viejas producen "
        "menos y aguantan peor los cambios del clima. Hablar con su extensionista sobre "
        "renovar por zoca o por siembra, y sobre variedades adaptadas a su zona, puede "
        "ayudarle a tener un cultivo más fuerte. Hágalo por lotes y no todo el cafetal a "
        "la vez, para no quedarse sin ingresos de un año para otro.",
        "Lleve el pulso del clima en su finca: anote cuándo floreó cada lote, cuándo llovió "
        "fuerte y cuándo vino el verano. Con esos datos, cada año sabrá mejor cuándo "
        "fertilizar, cuándo esperar y cuándo prevenir. Pregúntese: ¿qué lote de mi cafetal "
        "sufre más con el sol o con la lluvia? Empiece por ahí.",
        "Imagine dos lotes de la misma finca: uno con sombra bien distribuida y otro a "
        "pleno sol. En una semana de calor fuerte, el segundo se estresa más y su suelo se "
        "seca primero. Pasar un rato mirando qué lote aguanta mejor le da pistas para "
        "decidir dónde conviene mejorar la sombra o la cobertura. Pida a su extensionista "
        "que lo acompañe a revisarlo: una visita puede ahorrarle años de prueba y error. "
        "Recuerde: un cafetal con sombra bien manejada y el suelo cubierto aguanta mejor "
        "el calor y la lluvia fuerte.",
    ),
    key_points=(
        "El sombrío bien manejado baja el calor y guarda la humedad, "
        "pero demasiado también perjudica.",
        "Dejar cobertura viva en el suelo frena la erosión cuando llueve fuerte.",
        "Renueve el cafetal por lotes y con orientación de su extensionista.",
        "Anote las floraciones y las lluvias de cada lote para decidir mejor cada año.",
    ),
)

_CAFE_FINANZAS = CapsuleSpec(
    slug="cafe-las-cuentas-de-la-cosecha",
    topic=TOPIC_FINANZAS,
    tags=("cafe",),
    relevance=8.5,
    title="Las cuentas del café: qué entra y qué sale en cada cosecha",
    summary=(
        "Un registro sencillo para saber cuánto cuesta producir y cuánto le queda "
        "realmente."
    ),
    paragraphs=(
        "¿Sabe usted cuánto le costó producir su última cosecha? Muchos caficultores saben "
        "cuánto vendieron, pero no cuánto les costó producir. Y sin saber el costo es "
        "difícil saber si se está ganando, empatando o perdiendo. Llevar las cuentas no es "
        "cosa de contadores: con un cuaderno y unos pocos hábitos puede entender su "
        "negocio y tomar mejores decisiones.",
        "Divida sus gastos en dos grupos. Los costos de producción son los de la finca: "
        "abonos, jornales de recolección, control de plagas, transporte, beneficio y "
        "mantenimiento. Los gastos del hogar son los de su familia: comida, estudio, salud "
        "y servicios. Anótelos por separado desde el primer día, porque mezclarlos es la "
        "razón más común por la que parece que la plata no rinde.",
        "Registre cada venta: la fecha, la cantidad, el precio y a quién se la vendió. Al "
        "final de la cosecha sume todo lo que entró y todo lo que gastó en producir. La "
        "diferencia es lo que realmente le quedó. Si puede, calcule también cuánto le "
        "costó producir cada carga o cada kilo: así sabrá desde qué precio de venta "
        "empieza a ganar.",
        "El café se cosecha en ciertas épocas, pero los gastos son todo el año. Por eso "
        "conviene repartir lo que entra: separe una parte para los gastos de los meses de "
        "poca cosecha, otra para los insumos de la siguiente temporada y otra para un "
        "fondo de imprevistos. Si la cosecha fue buena, la tentación es gastar de más; si "
        "fue mala, hay que haber guardado antes.",
        "Cuidado con las deudas informales y con el gota a gota. Antes de pedir un crédito "
        "pregunte cuánto va a pagar en total y a qué tasa, compare por lo menos dos "
        "opciones y no firme lo que no entienda. Un crédito debe ayudarle a producir, no "
        "ahogarle. Esta semana anote todo lo que gaste, la finca en una hoja y la casa en "
        "otra: en un mes tendrá una foto real de su negocio.",
        "Imagine que en una cosecha entra mucha plata y parece que todo va bien. Al sumar, "
        "ve que los jornales, el abono y el transporte se llevaron una buena parte, y que "
        "además se gastó de más en la casa durante los meses buenos. Si lo hubiera "
        "anotado, habría guardado algo para la temporada flaca. Un cuaderno sencillo, "
        "revisado cada mes, le muestra esas diferencias a tiempo. Recuerde: anote cada "
        "mes lo que entra y lo que sale, la finca por un lado y la casa por otro.",
    ),
    key_points=(
        "Separe siempre los gastos de la finca de los gastos de la casa.",
        "Registre cada venta: fecha, cantidad, precio y comprador.",
        "Reparta lo que entra de la cosecha para cubrir también los meses de poca venta.",
        "Antes de un crédito pregunte cuánto pagará en total y compare opciones.",
    ),
)

_CAFE_RIESGOS = CapsuleSpec(
    slug="cafe-riesgos-del-cafetal",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("cafe",),
    relevance=7.5,
    title="Riesgos del cafetal: prevenir, reducir o trasladar",
    summary="Cómo identificar lo que puede afectar su cosecha y qué hacer con cada riesgo.",
    paragraphs=(
        "¿Ha pensado qué pasaría con su finca si mañana llega una sequía o una plaga? "
        "Todo cultivo tiene riesgos. En el café pueden ser el clima, como la sequía, las "
        "lluvias excesivas o el granizo; las plagas y enfermedades como la broca o la "
        "roya; los cambios en el precio; los problemas de salud de quien trabaja la finca; "
        "o incluso el robo. Pensar en ellos antes no los elimina, pero lo prepara para que "
        "no lo tomen por sorpresa.",
        "Una forma ordenada de verlo es hacerse tres preguntas por cada riesgo: ¿qué tan "
        "probable es que pase?, ¿qué tanto daño me haría?, ¿qué puedo hacer al respecto? "
        "Con eso puede decidir cuáles atender primero. Un riesgo poco probable pero muy "
        "grave, como perder el cafetal por un deslizamiento, merece tanta atención como "
        "uno frecuente y leve.",
        "Frente a un riesgo usted tiene cuatro caminos. Prevenir: hacer algo para que no "
        "ocurra, como el control oportuno de la broca o la cobertura del suelo. Reducir: "
        "disminuir el daño si ocurre, como tener sombrío y variedades adecuadas. Aceptar: "
        "asumirlo cuando es pequeño y tiene cómo cubrirlo. Y trasladar: pasarle parte del "
        "riesgo a otro, por ejemplo con un seguro.",
        "Los seguros agropecuarios y los microseguros son una forma de trasladar riesgos. "
        "Funcionan así: usted paga un valor y, si ocurre el evento que cubre la póliza, "
        "recibe una compensación. Antes de decidir, pregunte siempre qué cubre y qué no, "
        "qué debe hacer para reclamar y en cuánto tiempo. CIMA no vende seguros: aquí "
        "aprende para decidir con información y puede dejar registrado si le interesa "
        "saber más.",
        "Un seguro no reemplaza el buen manejo del cultivo ni el ahorro: se complementa "
        "con ellos. Lo más sólido es combinar prevención, un fondo de imprevistos y, si le "
        "conviene, una cobertura. Anote los tres riesgos que más le preocupan en su "
        "cafetal y escriba al lado qué hace hoy para cada uno.",
        "Imagine una tabla de tres columnas en una hoja: el riesgo, qué tan probable es y "
        "qué tan grave sería. En la primera fila pone la sequía, en la segunda la broca y "
        "en la tercera una caída del precio. Al llenarla ve que algunos riesgos los puede "
        "prevenir con trabajo en la finca y otros necesitan ahorro o una cobertura. Esa "
        "hoja, repasada cada año con su familia, se convierte en su mapa de riesgos. "
        "Recuerde: para cada riesgo de su cafetal, decida si lo previene, lo reduce, lo "
        "acepta o lo traslada.",
    ),
    key_points=(
        "Para cada riesgo pregúntese qué tan probable es y qué tanto daño haría.",
        "Ante un riesgo puede prevenir, reducir, aceptar o trasladar.",
        "Un seguro traslada parte del riesgo; pregunte siempre qué cubre y qué no.",
        "El mejor resultado sale de combinar prevención, ahorro y, si le conviene, cobertura.",
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
    title="Su tienda frente al calor y las lluvias",
    summary="Cómo proteger el inventario, la nevera y el local cuando el clima aprieta.",
    paragraphs=(
        "¿Le ha pasado que el calor o un aguacero le daña la mercancía de la tienda? Una "
        "tienda de barrio vive de que haya mercancía en buen estado, clientes que puedan "
        "llegar y servicios que funcionen. El clima cambiante afecta las tres cosas: con "
        "mucho calor se dañan los productos fríos, con aguaceros fuertes entra agua al "
        "local o se complica el reparto, y los cortes de energía pueden pararlo todo. "
        "Prepararse le ahorra pérdidas.",
        "Con el calor, la nevera trabaja más. Póngala lejos del sol directo y de la "
        "estufa, con espacio para que circule el aire por detrás, y límpiele de vez en "
        "cuando las rejillas. No la llene de más ni abra la puerta sin necesidad. Revise "
        "que el empaque de la puerta cierre bien; si no, pierde frío, gasta más energía "
        "y se dañan los productos.",
        "Con las lluvias, suba del piso lo que se moje fácil: paquetes de arroz, azúcar, "
        "harinas, papel higiénico y cajas de cartón. Use estibas o estantes bajos de "
        "plástico o metal. Mire cada cierto tiempo el techo, los canales y los bajantes: "
        "una teja corrida o un canal tapado se arregla barato antes de la temporada de "
        "lluvias, pero cuesta mucho cuando ya entró el agua.",
        "Piense en un plan para los cortes de energía. Si la nevera se queda sin luz, no "
        "la abra más de lo necesario: así mantiene el frío por más tiempo. Tenga a la "
        "mano linternas o lámparas con pilas y anote el teléfono de la empresa de "
        "energía. Si vende productos perecederos, procure no comprar de más cuando se "
        "anuncian lluvias fuertes o calor extremo.",
        "Ofrezca soluciones a sus clientes: en temporada de calor, agua y bebidas frías; "
        "en lluvias, domicilios cortos o productos de uso inmediato. Adaptarse también es "
        "una oportunidad de vender mejor. Dé hoy una vuelta por su tienda como si fuera a "
        "llover mañana: ¿qué se mojaría primero? Empiece por ahí.",
        "Imagine que se anuncia una semana de lluvias fuertes. Antes de que lleguen, sube "
        "los paquetes de abajo a un estante, revisa el canal del techo y avisa a sus "
        "clientes que tiene domicilios. Cuando llueve, su mercancía está a salvo y sus "
        "vecinos saben que pueden contar con usted. Esa preparación de una tarde puede "
        "marcar la diferencia entre perder mercancía y seguir vendiendo con calma. "
        "Recuerde: antes de la temporada, suba del piso lo que se moje, revise el techo "
        "y cuide la nevera.",
    ),
    key_points=(
        "La nevera lejos del sol y con espacio para el aire gasta menos y enfría mejor.",
        "Suba del piso lo que se moje fácil, usando estibas o estantes bajos.",
        "Revise techo, canales y bajantes antes de la temporada de lluvias.",
        "Ante un corte de luz, abra la nevera lo menos posible.",
    ),
)

_TIENDA_FINANZAS = CapsuleSpec(
    slug="tienda-plata-del-negocio-y-de-la-casa",
    topic=TOPIC_FINANZAS,
    tags=("tienda_barrio",),
    relevance=8.4,
    title="Separe la plata de la tienda de la plata de la casa",
    summary="Un orden sencillo para saber si su tienda realmente está ganando.",
    paragraphs=(
        "¿Sabe usted si su tienda dejó ganancia el mes pasado? En muchas tiendas de "
        "barrio la caja es también el bolsillo de la familia. Se saca para el mercado, "
        "para el recibo, para el colegio, y al final del mes nadie sabe si la tienda "
        "dejó ganancia o si solo está entrando y saliendo plata. Separar los dos dineros "
        "es el primer paso para ordenar el negocio.",
        "Una buena costumbre es ponerse un sueldo. Decida cuánto va a sacar cada semana "
        "o cada mes para sus gastos personales y sáquelo siempre el mismo día, "
        "anotándolo. Todo lo demás se queda en el negocio para reponer mercancía, pagar "
        "arriendo y servicios y cubrir imprevistos. Así sabe con claridad qué es del "
        "negocio y qué es suyo.",
        "Conozca la diferencia entre vender y ganar. Lo que entra por ventas no es "
        "ganancia: de ahí hay que descontar lo que le costó la mercancía, el arriendo, "
        "la energía, el transporte y otros gastos. Calcule el margen de sus productos "
        "principales: si compra algo en 1.000 pesos y lo vende en 1.300, le quedan 300 "
        "por unidad, pero de ahí todavía salen los gastos del local.",
        "El fiado merece un cuaderno aparte. Anote quién debe, cuánto, desde cuándo y "
        "cuándo prometió pagar, y revíselo cada semana. Fiar a muchos clientes por mucho "
        "tiempo deja la tienda sin plata para reponer mercancía. Póngale un límite a "
        "cada cliente y cobre con respeto pero con constancia.",
        "Si puede, use una cuenta o una billetera digital para el negocio y otra para "
        "sus gastos personales. Pregunte por las cuotas de manejo y compare antes de "
        "decidir. Esta semana empiece con su sueldo: defina un valor, sáquelo un solo "
        "día y anote todo lo que salga de la caja por otras razones.",
        "Imagine que cada vez que falta plata en la casa saca de la caja sin anotar. A "
        "fin de mes, la tienda parece no dejar nada, aunque vendió bastante. Si en "
        "cambio se pone un sueldo y anota todo lo demás, puede ver cuánto dejó "
        "realmente el negocio y decidir con claridad si hay para surtir más, para "
        "ahorrar o para pagar una deuda. Revise sus números cada mes: el orden no "
        "necesita aparatos, solo un cuaderno y constancia. Recuerde: póngase un sueldo, "
        "sáquelo siempre el mismo día y anote todo lo demás.",
    ),
    key_points=(
        "Póngase un sueldo fijo y sáquelo siempre el mismo día.",
        "Ventas no es lo mismo que ganancia: descuente la mercancía y los gastos del "
        "local.",
        "Lleve el fiado en un cuaderno aparte y revíselo cada semana.",
        "Una cuenta para el negocio y otra personal ayudan a no mezclar el dinero.",
    ),
)

_TIENDA_RIESGOS = CapsuleSpec(
    slug="tienda-riesgos-del-negocio",
    topic=TOPIC_GESTION_RIESGOS,
    tags=("tienda_barrio",),
    relevance=7.4,
    title="Riesgos de la tienda: robo, incendio, inundación y deudas",
    summary="Cómo identificar lo que puede afectar su negocio y cómo prepararse.",
    paragraphs=(
        "¿Ha pensado qué pasaría con su tienda si hoy hubiera un robo, un incendio o una "
        "inundación? Una tienda pequeña guarda muchas cosas valiosas en poco espacio: "
        "mercancía, equipos, el dinero de la caja y el trabajo de años. Un robo, un "
        "incendio, una inundación o una deuda que se sale de control pueden dejarla en "
        "cero. Conocer los riesgos y tomar medidas básicas puede evitar el golpe o "
        "reducirlo.",
        "Haga un recorrido con una hoja en la mano. Anote qué podría pasar: instalación "
        "eléctrica en mal estado, cables sobrecargados, gas mal conectado, rejas débiles, "
        "techo con goteras, mercancía en el piso. Al lado de cada punto escriba qué tan "
        "probable es y qué tanto daño haría. Empiece arreglando lo más grave y fácil de "
        "resolver, como pedir que alguien calificado revise las conexiones eléctricas.",
        "Para el robo, evite acumular mucho efectivo en la caja: consigne o transfiera "
        "con regularidad. Mejore la iluminación, mantenga la mercancía valiosa a la "
        "vista y no deje el local solo. Para el incendio, tenga cerca un extintor "
        "vigente, no sobrecargue los tomacorrientes y guarde los líquidos inflamables "
        "fuera del local. Anote el teléfono de los bomberos.",
        "Los seguros y microseguros para negocios pueden ayudar a trasladar parte del "
        "riesgo: se paga un valor periódico a cambio de una compensación si ocurre lo "
        "que cubre la póliza. Antes de decidir, pregunte qué eventos cubre, qué excluye, "
        "cuál es el valor asegurado y qué debe hacer para reclamar. CIMA no vende "
        "seguros: aquí aprende a decidir con información y puede dejar registrado su "
        "interés.",
        "Las deudas también son un riesgo. Evite pagar una deuda con otra y los "
        "prestamistas informales de cobro diario. Antes de endeudarse calcule si la "
        "tienda dará para pagar cada cuota aun en un mes flojo de ventas. Elija hoy un "
        "riesgo para reducir esta semana, un cable, una reja o el efectivo de la caja: "
        "uno a la vez es mejor que ninguno.",
        "Imagine que hace el recorrido de riesgos un domingo en la tarde, con calma. "
        "Encuentra un cable pelado cerca de la nevera, una reja que no cierra bien y "
        "cajas de mercancía en el piso por donde entra el agua. En una semana puede "
        "corregir las tres cosas con poca plata. Hacerlo antes de que pase algo cuesta "
        "mucho menos que arreglarlo después del daño. Recuerde: recorra su tienda con "
        "una hoja, anote lo que podría salir mal y arregle un riesgo a la vez.",
    ),
    key_points=(
        "Recorra su tienda con una hoja y anote lo que podría salir mal.",
        "No acumule efectivo: consigne o transfiera con regularidad.",
        "Un extintor vigente y buenas conexiones eléctricas previenen incendios.",
        "Antes de un seguro o un crédito pregunte qué cubre, qué excluye y cuánto "
        "pagará.",
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
    title="La broca: cómo cuidar su cosecha de la plaga que más daña el café",
    summary=(
        "Aprenda cómo vive la broca, dónde se esconde y qué hacer antes y después de la "
        "cosecha."
    ),
    paragraphs=(
        "¿Sabe usted dónde se esconde la broca después de la cosecha? La broca del café es "
        "un escarabajo diminuto, del tamaño de la cabeza de un alfiler, y es la plaga que "
        "más daño le hace al café en el mundo. La hembra perfora el grano, entra y pone "
        "sus huevos adentro. Por eso el daño casi no se ve por fuera, pero por dentro el "
        "grano se pica, pesa menos y se vende peor.",
        "Para defenderse conviene conocerla. Desde el huevo hasta que es adulta pasan "
        "más o menos de veinticuatro a cuarenta y cinco días, según el clima. Le "
        "gustan los lugares sombríos y húmedos, y suele salir después de la lluvia a "
        "buscar otro cafeto. Y donde ya hubo broca, es más fácil que vuelva.",
        "Los granos que se quedan en la planta o caídos en el suelo después de la "
        "cosecha son la casa donde la broca se refugia hasta la próxima floración. Por "
        "eso lo más importante es recoger bien: coja los frutos maduros a tiempo, haga "
        "un repase al final para sacar los que quedaron en las ramas y levante los que "
        "están en el suelo. Es un trabajo cansón, pero si se hace con juicio es de lo "
        "más eficaz que puede hacer.",
        "Revise su lote cada cierto tiempo: tome un puñado de frutos, mire si tienen "
        "un huequito pequeño cerca de la punta y ábralos para ver si hay galerías. Así "
        "sabe qué tan afectado está y no actúa a ciegas. También cuide lo que entra "
        "a su finca: no lleve frutos ni costales de otras fincas sin revisarlos, "
        "porque con ellos puede llegar la plaga.",
        "La naturaleza también ayuda. Algunas hormigas se comen la broca y hay un "
        "hongo que la ataca y que se ve como un polvillo blanco sobre el fruto. Si "
        "fumiga sin necesidad, los insectos que le ayudan también se mueren. Y "
        "recuerde que los insecticidas son peligrosos para su salud y para el agua: "
        "antes de usar cualquier producto, pregunte al técnico o al extensionista de "
        "su comité de cafeteros qué conviene en su finca y cómo aplicarlo con "
        "seguridad. Este contenido es una guía general y no reemplaza esa asesoría.",
        "Esta semana haga una prueba sencilla en un lote: revise un puñado de frutos "
        "en tres sitios distintos, cuente cuántos tienen perforación y anótelo. Repita "
        "la revisión después de la cosecha y compare. Con ese cuaderno sabrá si su "
        "recolección y su repase están funcionando. Recuerde: recoja a tiempo, haga el "
        "repase y no deje frutos en la rama ni en el suelo.",
    ),
    key_points=(
        "La broca perfora el grano y pone sus huevos adentro: el daño se ve al abrirlo.",
        "Recoja a tiempo y haga el repase: quite los frutos que quedan en la rama y "
        "en el suelo.",
        "No mueva frutos ni costales de otras fincas sin revisarlos.",
        "Antes de aplicar cualquier producto, consulte al extensionista de su comité.",
    ),
)

_TIENDA_INVENTARIO = CapsuleSpec(
    slug="tienda-el-inventario",
    topic=TOPIC_FINANZAS,
    tags=("tienda_barrio",),
    relevance=8.0,
    title="Su inventario: no deje la plata parada en el estante",
    summary="Aprenda a saber qué se vende, qué se queda quieto y cuánto pedir sin que "
    "le falte ni le sobre.",
    paragraphs=(
        "¿Sabe usted cuánta plata tiene parada en el estante de su tienda? Cada producto "
        "que está en su estante es plata que ya pagó y todavía no recupera. Si se vende "
        "rápido, esa plata vuelve y puede comprar de nuevo. Si se queda quieto, la plata "
        "está parada, ocupa espacio y, si se vence o se daña, se pierde. Por eso llevar "
        "el inventario no es un lujo: es cuidar su capital.",
        "Una buena administración del inventario busca dos cosas a la vez. Primero, que "
        "cuando el cliente pida un producto lo tenga. Segundo, que no tenga más de lo "
        "necesario, porque tener mucho también cuesta. Hay que encontrar el equilibrio: "
        "si pide poco se le acaba y pierde la venta; si pide mucho se le empoza la "
        "plata.",
        "Para empezar basta un cuaderno. Una vez por semana anote qué productos se "
        "acabaron, cuáles se vendieron más y cuáles llevan semanas sin moverse. Así "
        "descubre sus productos estrella, que debe tener siempre, y sus productos "
        "dormidos, que quizás no vale la pena volver a comprar. Compre con base en lo "
        "que de verdad vende, no en lo que le ofrece el vendedor.",
        "Tenga cuidado con los descuentos por volumen. Comprar más barato solo sirve si "
        "alcanza a vender todo antes de que se venza y si no deja sin plata el resto "
        "del negocio. Haga la cuenta: ¿cuánto va a vender en un mes? Si la respuesta es "
        "menos de lo que le toca comprar, el descuento no es tal.",
        "En los productos que se vencen, como lácteos, pan o fruta, aplique la regla de "
        "primero en entrar, primero en salir. Ponga adelante lo que llegó antes y atrás "
        "lo nuevo, y revise las fechas cada semana. Y para los días de más venta, como "
        "quincena, fiestas o puentes, guarde un poquito de más de lo que más se vende, "
        "como una reserva de seguridad, pero sin exagerar.",
        "Esta semana haga un conteo rápido de su estante, anote los cinco productos que "
        "más rotan y los cinco que menos. Con eso ya tiene la base para decidir mejor "
        "su próximo pedido. Recuerde: lo que está en el estante es plata que todavía no "
        "recupera, así que compre según lo que de verdad vende.",
    ),
    key_points=(
        "Lo que está en el estante es plata que todavía no recupera.",
        "Busque el equilibrio: que no le falte lo que más se vende ni le sobre lo que "
        "no rota.",
        "Cada semana anote qué se acabó, qué se vendió más y qué lleva semanas quieto.",
        "En lo que se vence, ponga adelante lo que llegó primero y revise las fechas.",
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
        "¿Sabe usted qué es el préstamo gota a gota? Cuando la plata no alcanza, el "
        "préstamo rápido parece una salvación. Por eso el gota a gota se ofrece justo ahí: "
        "sin papeles, sin preguntas y con la plata en la mano el mismo día. El problema "
        "aparece después. Este tipo de préstamo informal nació en Medellín en los años "
        "noventa y se volvió muy conocido porque se paga a diario o a la semana y cobra "
        "intereses muy altos, mucho más caros que un microcrédito formal.",
        "Hay señales para reconocerlo. Le prestan sin pedir casi nada. Le cobran cuotas "
        "diarias o semanales que no le dicen cuánto suman al final. No le entregan un "
        "contrato claro ni le explican la tasa. Le piden fotos de su cédula, de su "
        "negocio o de su finca. Y lo más grave: si se atrasa, empiezan las "
        "presiones, las amenazas y las visitas. Por eso muchas veces no se pierde solo "
        "plata, también la tranquilidad.",
        "Ojo con las fachadas. A veces quien presta se hace pasar por una entidad "
        "seria, con carteles, mensajes o llamadas muy amables. Antes de aceptar, "
        "pregunte el nombre completo de la entidad y si está vigilada por la "
        "Superintendencia Financiera. Cobrar intereses por encima del límite legal es "
        "un delito, y quien se lo cobra no puede obligarlo con amenazas.",
        "Existen caminos más seguros. Pregunte en cooperativas, fondos de empleados y "
        "entidades que ofrecen microcrédito: compare por lo menos dos opciones y pida "
        "siempre el costo total, es decir, cuánto va a pagar en cuotas hasta el "
        "final. Si cultiva café, pregunte en su comité de cafeteros por las líneas "
        "para el sector. Si tiene tienda, llevar bien sus cuentas le sirve de "
        "respaldo cuando pida un crédito.",
        "Y la mejor defensa es tener un colchón. Aunque sea poquito, aparte una parte "
        "de cada venta o de cada cosecha en un fondo para imprevistos, así cuando algo "
        "falle no tiene que correr donde un prestamista. Si ya está en un gota a "
        "gota y lo están amenazando, no se quede en silencio: cuéntele a una persona "
        "de confianza y denuncie ante la Policía o la Fiscalía. Recuerde: si le prestan "
        "sin pedir casi nada y sin decirle el costo total, desconfíe.",
    ),
    key_points=(
        "Si le prestan sin pedir casi nada y no le dicen el costo total, desconfíe.",
        "Pregunte siempre cuánto pagará en total y si la entidad está vigilada.",
        "Compare por lo menos dos opciones: cooperativas, microcrédito, comité de cafeteros.",
        "Ahorre un poquito de cada venta o cosecha: es su defensa contra el gota a gota.",
    ),
    video_file="gota-a-gota.mp4",
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
    summary="Qué es la agricultura sostenible y cómo cuidar el suelo, el agua y la plata de su finca al mismo tiempo.",
    paragraphs=(
        "¿Sabe usted qué es la agricultura sostenible? Es una forma de trabajar el campo "
        "que busca tres cosas al mismo tiempo: que la finca dé comida y plata, que la "
        "tierra, el agua y los animales sigan sanos, y que la familia y la comunidad vivan "
        "mejor. No es una moda ni un lujo de fincas grandes. Es cultivar hoy sin dejar la "
        "tierra cansada para los que vienen después.",
        "Muchos productores ya lo están viviendo. Con el cambio del clima las lluvias "
        "llegan cuando no toca, la flor del café no pega o se cae, y la cosecha merma. "
        "Cuando el suelo está pobre y sin cobertura, cada aguacero se lleva la capa buena "
        "de la tierra y cada verano seca más rápido el cultivo. Una finca bien cuidada "
        "aguanta mejor esos golpes.",
        "El primer cuidado es el suelo, porque de él depende todo. Deje coberturas o "
        "arvenses nobles entre los surcos para que la tierra no quede pelada, devuelva al "
        "lote la pulpa y los residuos bien compostados y siembre en curvas de nivel si su "
        "terreno es pendiente. Un suelo vivo guarda más agua y necesita menos abono.",
        "El segundo es el agua. Proteja los nacimientos y las orillas de las quebradas con "
        "árboles, no lave fumigadoras ni tire empaques cerca de ellas y no desperdicie el "
        "agua del beneficio o del riego. El agua que se contamina arriba la toman abajo sus "
        "vecinos y sus animales.",
        "El tercero es manejar las plagas con cabeza. Antes de fumigar, revise qué tanto "
        "daño hay de verdad. Muchas veces la naturaleza ayuda: hay hongos, avispitas y "
        "hormigas que se comen las plagas, y si echa veneno sin necesidad también los "
        "mata. Cuando sí haga falta un producto, pregunte al técnico o al extensionista "
        "cuál conviene y cómo aplicarlo con seguridad.",
        "Y no se olvide de la plata. Una finca sostenible también tiene que ser rentable: "
        "anote lo que gasta en insumos y lo que vende, para saber qué prácticas le "
        "ahorran y cuáles no. Cuidar el suelo y el agua casi siempre baja los costos con el "
        "tiempo, porque necesita menos abono, menos riego y menos remedios.",
        "Esta semana camine su finca con una libreta y anote tres cosas: dónde la tierra "
        "queda pelada, por dónde corre el agua cuando llueve y qué tan cerca de la quebrada "
        "fumiga o lava los equipos. Escoja una sola de esas cosas para mejorar este mes. "
        "Recuerde: la idea es mantener el equilibrio entre la naturaleza, su familia y su "
        "bolsillo.",
    ),
    key_points=(
        "Agricultura sostenible es producir comida y plata sin acabar con el suelo, el agua ni la comunidad.",
        "Un suelo cubierto y con materia orgánica aguanta mejor los aguaceros y los veranos.",
        "Proteja los nacimientos y no lave equipos ni tire empaques cerca de las quebradas.",
        "Antes de fumigar revise el daño real y consulte al técnico qué producto usar.",
    ),
    video_file="agro-sostenible.mp4",
)

_AGRO_RIESGOS = CapsuleSpec(
    slug="agro-riesgos-del-campo",
    topic=TOPIC_GESTION_RIESGOS,
    tags=_CAMPO,
    relevance=8.7,
    title="Los riesgos del campo: conózcalos y prepárese",
    summary="Los cuatro riesgos principales de quien cultiva o cría animales, y cómo prevenirlos para que el golpe sea menor.",
    paragraphs=(
        "¿Sabe usted qué es un riesgo? Es la posibilidad de sufrir una pérdida o un daño "
        "por algo que no está del todo en sus manos. En el campo hay muchos: el clima que "
        "cambia, las plagas y enfermedades, los precios del producto y de los insumos, y "
        "hasta las normas del país. No se pueden eliminar todos, pero sí se pueden "
        "conocer, prevenir y preparar para que el golpe sea menor.",
        "El primero es el riesgo climático: heladas, vientos fuertes, aguaceros que no "
        "paran, inundaciones, granizadas o sequías que dañan la cosecha. Aquí entran "
        "también los deslizamientos que se forman cuando el exceso de lluvia satura la "
        "tierra. Para prepararse, siga los avisos del IDEAM, mantenga limpios los canales y "
        "desagües y no deje la tierra pelada en las pendientes.",
        "El segundo es el riesgo biológico: las plagas y enfermedades que atacan los "
        "cultivos o los animales y bajan la cantidad y la calidad de lo que produce. En el "
        "café, por ejemplo, la broca y la roya. La mejor defensa es revisar seguido, "
        "recoger bien, mantener las plantas sanas y pedir asesoría al técnico antes de "
        "aplicar cualquier producto.",
        "El tercero es el riesgo geológico: terremotos, erupciones volcánicas y los "
        "deslizamientos que ellos provocan. Estos no se pueden evitar, pero sí puede "
        "averiguar si su finca está en una zona de amenaza, no construir la casa ni el "
        "beneficio al pie de un talud y tener claro con su familia por dónde salir y a "
        "dónde ir si pasa algo.",
        "El cuarto es el riesgo financiero: cuando el precio de lo que vende baja o el de "
        "los abonos sube, cuando el dólar cambia o cuando no consigue crédito a tiempo. "
        "Para manejarlo, lleve las cuentas de cada cosecha, tenga un ahorro para "
        "emergencias, no dependa de un solo producto si puede diversificar y desconfíe de "
        "los préstamos gota a gota.",
        "Para los riesgos que no puede controlar existen herramientas que reparten el "
        "golpe, como los seguros agropecuarios: se paga una suma pequeña y, si pasa el daño "
        "cubierto, se recibe una ayuda para recuperarse. Vale la pena entender bien cómo "
        "funcionan y qué cubren antes de decidir. CIMA no vende seguros: aquí solo le "
        "explicamos para que decida con información.",
        "Esta semana haga su propio mapa de riesgos: en una hoja escriba los cuatro tipos y "
        "al lado lo que más le ha afectado en los últimos años. Escoja el que más le "
        "preocupa y anote una sola cosa que puede hacer este mes para prepararse. "
        "Recuerde: conocer los riesgos de su finca es el primer paso para que el golpe "
        "sea menor.",
    ),
    key_points=(
        "Los cuatro riesgos principales del campo son climáticos, biológicos, geológicos y financieros.",
        "Los riesgos siempre existen: lo importante es prevenirlos, prepararse y reducir su impacto.",
        "Llevar las cuentas y tener un ahorro de emergencia le protege del riesgo financiero.",
        "Antes de decidir sobre un seguro, entienda bien qué cubre y qué no.",
    ),
    video_file="agro-riesgos.mp4",
)

_TIENDA_VIDEOS = CapsuleSpec(
    slug="tienda-tu-negocio-en-video",
    topic=TOPIC_FINANZAS,
    # Todos los comercios de barrio (pymes): el video del tendero aplica a cualquiera.
    tags=("tienda_barrio", "panaderia", "miscelanea", "fruteria"),
    relevance=8.6,
    title="Muestre su negocio en video sin miedo a la cámara",
    summary="Cómo grabar videos sencillos con su celular para que más clientes conozcan "
    "su tienda, sin gastar plata.",
    paragraphs=(
        "¿Le da pena grabarse en video para mostrar su negocio? Si sabe atender a un "
        "cliente en el mostrador, ya sabe hacer un video. Hoy mucha gente busca en el "
        "celular dónde comprar, y prefiere negocios de personas trabajadoras y honestas "
        "que muestren cómo es su trabajo de verdad. Un video corto en su estado de "
        "WhatsApp o en sus redes puede traerle clientes nuevos sin gastar un peso en "
        "publicidad.",
        "El miedo a la cámara es normal. El truco es no pensar que le habla a un aparato. "
        "Cuando ponga el celular al frente, imagine que es su compadre o su clienta de "
        "toda la vida que vino a preguntarle algo. Háblele con la misma confianza con "
        "que la atiende en la tienda, y el video sale natural.",
        "No necesita equipos caros. Limpie el lente del celular, párese de frente a la "
        "luz de la puerta o de una ventana y apóyelo en algo firme para que no tiemble. "
        "Grabe en un lugar sin mucho ruido y hable un poco más despacio de lo normal. "
        "Con un minuto basta: la gente ve completos los videos cortos.",
        "¿De qué hablar? De lo que usted sabe y sus clientes valoran: la fruta que acaba "
        "de llegar y cómo escoger la más madura, la promoción de la semana, cómo guardar "
        "el pan para que dure o el horario de los domingos. Muestre los productos de "
        "cerca y diga los precios claros. Su experiencia vale y le sirve a otros.",
        "Cuide también su negocio y a su gente. No grabe a clientes ni a niños sin su "
        "permiso, no muestre la caja, el dinero ni dónde guarda la mercancía, y no diga "
        "a qué hora cierra con la plata del día. Lo que publica lo puede ver cualquiera.",
        "Y haga cuentas para saber si funciona. Pregunte a los clientes nuevos cómo "
        "supieron de usted y anote cuántos llegaron por un video. Si una idea trae "
        "gente, repítala; si no, pruebe otra. Así cada video es una pequeña inversión "
        "de tiempo que puede medir.",
        "Esta semana grabe un video de menos de un minuto mostrando el producto que más "
        "se vende en su tienda. Mírelo, pregúntele a alguien de confianza qué le pareció "
        "y publíquelo en su estado. Pierda el miedo: la confianza que le da a sus "
        "clientes en el mostrador también se nota en la pantalla. Recuerde: háblele a la "
        "cámara como a un cliente de confianza y grabe un minuto con buena luz.",
    ),
    key_points=(
        "Háblele a la cámara como si fuera un cliente de confianza, no un aparato.",
        "Con luz de frente, el celular firme y un minuto de video es suficiente.",
        "No grabe la caja, el dinero ni a personas sin su permiso.",
        "Anote cuántos clientes llegan por sus videos para saber qué funciona.",
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
    title="Las labores del platanal que cuidan su cosecha",
    summary=(
        "Deshije, deshoje, desbellote y herramientas limpias: lo básico para que el "
        "platanal no se enferme y el racimo llene bien."
    ),
    paragraphs=(
        "¿Le ha pasado que su platanal se enferma y no sabe por qué? Un platanal sano no "
        "depende de la suerte sino de unas labores sencillas hechas a tiempo. Cuando se "
        "dejan para después, las malezas le roban la comida a la planta, las hojas "
        "enfermas riegan la sigatoka y las herramientas sucias llevan enfermedades como "
        "el moko de una mata a otra. Con un poco de orden se pierde menos y el racimo "
        "sale más pesado.",
        "Los primeros cinco a siete meses son los más delicados, porque las malezas "
        "compiten fuerte con la planta joven. Mantenga limpio el plato alrededor de cada "
        "mata y, entre los surcos, deje coberturas nobles que protejan el suelo sin "
        "competir. Así la tierra no queda pelada con los aguaceros ni se seca tan rápido "
        "en verano.",
        "Haga el deshije con criterio: deje en cada sitio la planta madre, un hijo y un "
        "nieto bien ubicados, y quite los demás colinos para que no se peleen la comida. "
        "Con el deshoje retire las hojas secas, dobladas o muy manchadas, porque son la "
        "casa de la sigatoka. Después de cosechar, corte el tallo viejo y píquelo para "
        "que se descomponga en el lote.",
        "Cuide el racimo. Quitar la bellota, la flor que queda colgando al final, cada "
        "quince días evita que los insectos que la visitan lleven el moko a otras "
        "plantas. Quitar las últimas manos pequeñas ayuda a que las demás llenen mejor, "
        "y apuntalar o amarrar la mata evita que el viento la tumbe con el racimo "
        "encima. La bolsa protege la fruta de golpes, plagas y quemaduras del sol.",
        "Lo más importante es la higiene. Lave y desinfecte el machete y las demás "
        "herramientas al pasar de una mata a otra, con el producto y la forma que le "
        "indique el técnico. No traiga colinos ni tierra de otras fincas sin saber de "
        "dónde vienen. Si ve plantas que se marchitan de un momento a otro o con el "
        "tallo manchado por dentro, no las mueva y avise al ICA o al técnico de su "
        "zona: hay enfermedades que se riegan muy rápido y su control temprano protege "
        "a toda la vereda.",
        "Esta semana recorra su platanal con una libreta. Anote cuántas matas tienen "
        "más de tres colinos, cuántas tienen hojas secas colgando y si sus herramientas "
        "se están limpiando entre mata y mata. Escoja la labor más atrasada y póngase "
        "al día con ella antes de fin de mes. Recuerde: las labores a tiempo y las "
        "herramientas limpias entre mata y mata cuidan su platanal.",
    ),
    key_points=(
        "Mantenga limpio el plato de cada mata en los primeros meses y deje coberturas "
        "entre surcos.",
        "Deje madre, hijo y nieto, y quite las hojas secas o muy manchadas.",
        "Quite la bellota a tiempo y desinfecte las herramientas entre mata y mata.",
        "Si una planta se marchita de repente, no la mueva y avise al ICA o al técnico.",
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
    title="Aguacate: cuide el suelo y el agua para aguantar el clima",
    summary=(
        "El aguacate no tolera el encharcamiento y sufre con la erosión. Aprenda a "
        "conocer su terreno y a manejar el agua antes de que llegue el problema."
    ),
    paragraphs=(
        "¿Sabe usted qué le pasa a un aguacate cuando su suelo se encharca? El aguacate es "
        "un árbol exigente con el suelo. Sus raíces necesitan aire, así que no aguantan "
        "quedar encharcadas, y en las laderas un aguacero fuerte puede llevarse la capa "
        "buena de la tierra en pocas horas. Con lluvias cada vez más fuertes y veranos más "
        "largos, cuidar el suelo y el agua es la mejor forma de proteger su inversión.",
        "Empiece por conocer su finca. Camínela después de un aguacero y mire por dónde "
        "corre el agua, dónde se queda empozada, dónde se ven piedras que antes no "
        "estaban y dónde la tierra se está lavando. Esos son sus puntos de riesgo. "
        "Anótelos en un croquis sencillo: le servirán para decidir dónde sembrar, dónde "
        "hacer drenajes y dónde no conviene meter árboles.",
        "Si va a sembrar o a renovar, hágalo bien desde el principio. Adecúe el terreno, "
        "siembre siguiendo las curvas del terreno y deje listos los canales para sacar el "
        "agua sobrante antes de que llegue el invierno. Un árbol sembrado en un sitio que "
        "se encharca casi siempre termina enfermo de la raíz, y eso no se arregla después "
        "con abono.",
        "Proteja la tierra que ya tiene. Mantenga el suelo cubierto con hojarasca, "
        "coberturas o la misma poda picada, para que la lluvia no golpee directo y el sol "
        "no lo reseque. Fíjese en las señales: si ve lombrices y otros bichos en la "
        "tierra, es buena señal; si aparecen piedras y raíces al aire, el suelo se está "
        "perdiendo. Cada cierto tiempo vale la pena hacer un análisis de suelo para "
        "saber qué le falta, con la orientación del técnico.",
        "Cuide también el agua de la finca. No siembre ni fumigue pegado a las "
        "quebradas y nacimientos; deje esas orillas con su vegetación, porque frenan la "
        "erosión y evitan crecientes y derrumbes. En verano, si tiene riego, aplique el "
        "agua según lo que pide el árbol en cada etapa y no por costumbre.",
        "Esta semana haga su croquis: dibuje la finca, marque con una equis dónde se "
        "empoza el agua y con un círculo dónde se lava la tierra. Escoja un punto y "
        "piense qué arreglo puede hacer antes de las próximas lluvias: un canal, una "
        "cobertura o dejar de sembrar en ese sitio. Recuerde: saque el agua sobrante y "
        "mantenga el suelo cubierto para que su aguacate aguante el clima.",
    ),
    key_points=(
        "El aguacate no aguanta el encharcamiento: saque el agua sobrante con canales.",
        "Recorra la finca después de llover y marque dónde se empoza el agua y dónde "
        "se lava la tierra.",
        "Mantenga el suelo cubierto con hojarasca o coberturas.",
        "No siembre ni fumigue pegado a quebradas y nacimientos.",
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
    title="Cacao: frene la monilia y la mazorca negra a tiempo",
    summary=(
        "Dos enfermedades pueden llevarse más de la mitad de la cosecha. Con revisiones "
        "frecuentes, poda y orden en el lote usted las controla sin gastar de más."
    ),
    paragraphs=(
        "¿Sabe usted qué es lo que más daño le hace al cacao? La monilia y la mazorca "
        "negra, también llamada fitóftora. Si no se manejan, pueden llevarse más de la "
        "mitad de la cosecha. La buena noticia es que buena parte del control está en "
        "sus manos y no cuesta mucha plata: consiste en cortarle el paso al hongo antes "
        "de que se riegue.",
        "Aprenda a reconocerlas. La monilia empieza con manchas o abultamientos en la "
        "mazorca y, si se deja, la mazorca se cubre de un polvo blanco o crema. Ese polvo "
        "son millones de esporas que el viento y la lluvia llevan a las mazorcas sanas. "
        "La mazorca negra se ve como una mancha oscura que avanza rápido, sobre todo en "
        "épocas de mucha humedad.",
        "La clave es sacar las mazorcas enfermas antes de que hagan el polvo. Recorra el "
        "lote cada semana, de preferencia en la mañana, y retire todas las mazorcas "
        "enfermas que encuentre. No las deje colgando ni las amontone al aire libre: "
        "déjelas en el suelo y cúbralas con hojarasca para que se descompongan. Las "
        "cáscaras de la cosecha también deben amontonarse y manejarse, o convertirse en "
        "abono, como le indique el técnico.",
        "El hongo vive feliz donde hay humedad y poca luz. Por eso la poda es tan "
        "importante: quite ramas secas, enfermas o cruzadas, y regule el sombrío para que "
        "entre el sol y circule el aire. Desyerbe a tiempo y no deje que el lote se "
        "vuelva un monte cerrado. Coseche las mazorcas maduras con frecuencia, cada "
        "quince días más o menos, porque las que se quedan en el árbol se enferman y "
        "contagian.",
        "Una planta bien nutrida se defiende mejor. Antes de abonar, haga un análisis de "
        "suelo y pida al técnico o al extensionista de su zona un plan según lo que le "
        "falta a su tierra. Si piensa usar algún producto contra las enfermedades, "
        "pregunte primero cuál conviene y cómo aplicarlo con seguridad.",
        "Esta semana escoja veinte árboles de su lote y cuente cuántas mazorcas enfermas "
        "tienen. Retírelas y anote el número. Repita cada semana durante un mes: si el "
        "número baja, el manejo está funcionando; si no, revise con el técnico la poda y "
        "el sombrío. Recuerde: recorra el lote cada semana y saque las mazorcas enfermas "
        "antes de que hagan el polvo blanco.",
    ),
    key_points=(
        "Recorra el lote cada semana y saque las mazorcas enfermas antes de que hagan el "
        "polvo blanco.",
        "Deje las mazorcas enfermas en el suelo cubiertas con hojarasca.",
        "Pode y regule el sombrío para que entre luz y circule el aire.",
        "Abone según el análisis de suelo y consulte al técnico antes de aplicar productos.",
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
    title="Arroz: produzca lo mismo gastando menos agua",
    summary=(
        "Nivelar el lote, hacer caballones en curva y medir el agua que entra y sale "
        "permite ahorrar agua y plata, sobre todo en los veranos largos."
    ),
    paragraphs=(
        "¿Le ha pasado que el agua no le alcanza para todo el lote? El arroz es de los "
        "cultivos que más agua usa, y cada vez hay más veranos largos y más competencia "
        "por el agua de los distritos de riego y las quebradas. Cuando el agua escasea, "
        "el que la desperdicia es el primero en quedarse corto. Por eso aprender a usarla "
        "mejor no es solo cuidar el ambiente: es asegurar la cosecha y bajar los costos.",
        "El primer paso es nivelar bien el lote. En un terreno desparejo el agua se "
        "acumula en las partes bajas y no llega a las altas, así que toca echar mucha más "
        "para cubrirlo todo. Con una buena nivelación el agua se reparte pareja, la "
        "semilla no se ahoga en los charcos y la maleza no se aprovecha de los sitios "
        "secos. Los técnicos de los programas de los arroceros muestran que, con estas "
        "prácticas, se puede ahorrar una parte importante del agua.",
        "El segundo paso es hacer los caballones siguiendo las curvas del terreno. Así el "
        "agua entra y sale despacio y de forma uniforme, en lugar de correr y llevarse la "
        "tierra. Mantenga los canales de entrada y de drenaje bien trazados y limpios: el "
        "agua que se queda estancada donde no debe favorece plagas y enfermedades.",
        "El tercer paso es medir. Lo que no se mide no se puede mejorar. Poner una "
        "regleta o una canaleta sencilla a la entrada y a la salida del lote le permite "
        "saber cuánta agua está usando y cuánta se le va. Con esos datos puede ajustar "
        "los riegos y comparar un lote con otro o una cosecha con la siguiente.",
        "Usar menos agua también trae otros ahorros: menos semilla perdida, menos "
        "problemas de plagas y, en muchos casos, menos gasto en productos. Antes de hacer "
        "cambios grandes, como una nivelación, consulte con el técnico de los arroceros "
        "o de su asociación cómo hacerlo en su zona y qué apoyo hay disponible.",
        "Esta semana recorra su lote cuando esté con agua y anote dónde se empoza y dónde "
        "queda seco. Mire por dónde se escapa el agua al drenaje. Con ese recorrido ya "
        "sabe cuáles son los puntos que más necesitan arreglo antes de la próxima "
        "siembra. Recuerde: un lote bien nivelado y medido le ahorra agua y plata.",
    ),
    key_points=(
        "Un lote bien nivelado reparte el agua pareja y necesita menos riego.",
        "Haga los caballones en curva y mantenga limpios los canales de entrada y drenaje.",
        "Mida el agua que entra y sale para saber cuánta está gastando.",
        "Consulte al técnico de los arroceros antes de hacer cambios grandes en el lote.",
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
    title="Maíz sano: vigile antes de fumigar",
    summary=(
        "Monitorear el lote, sembrar a la distancia correcta, rotar con leguminosas y "
        "usar semilla de calidad previene más pérdidas que fumigar a ciegas."
    ),
    paragraphs=(
        "¿Fumiga su maíz por calendario o porque el vecino lo hizo? En el maíz, las "
        "plagas, los hongos y las malezas pueden quitarle buena parte de la cosecha. "
        "Fumigar así cuesta plata, mata a los insectos que le ayudan y con el tiempo hace "
        "que las plagas se vuelvan más resistentes. Funciona mejor un manejo integrado: "
        "mirar primero y actuar a tiempo, combinando varias prácticas.",
        "Todo empieza con buena semilla. Use semilla certificada o de calidad conocida, "
        "que cumpla lo que pide el ICA, porque una semilla mala trae problemas desde el "
        "primer día. Siembre a la distancia recomendada para su variedad: cuando las "
        "plantas quedan muy juntas, la humedad se encierra y los hongos de la mazorca "
        "encuentran el ambiente perfecto.",
        "Monitoree el lote cada semana. Camine en zigzag y revise plantas en varios "
        "sitios: busque hojas comidas, huequitos en el tallo, manchas en las hojas y "
        "mazorcas dañadas. Anote lo que ve. Si encuentra una plaga al comienzo, todavía "
        "se puede manejar con controladores biológicos o productos de bajo impacto; si "
        "espera a verla en todo el lote, ya es tarde y sale caro.",
        "Rote los cultivos. Sembrar maíz detrás de maíz en el mismo lote deja que las "
        "plagas y enfermedades se acumulen de una cosecha a la otra. Alternar con una "
        "leguminosa, como el frijol o la soya, corta ese ciclo y además mejora el suelo. "
        "En lotes que tuvieron mucha enfermedad, el manejo de los residuos de la cosecha "
        "también ayuda; pregunte al técnico cuál es la mejor forma en su zona.",
        "Cuando sí haga falta aplicar algo, que sea con criterio. Pregunte al técnico o "
        "al agrónomo qué producto conviene, en qué momento y cómo aplicarlo con "
        "protección. Los productos mal usados son peligrosos para su salud, la de su "
        "familia y el agua.",
        "Esta semana arme su hoja de monitoreo: en una libreta haga una tabla con la "
        "fecha, el sitio del lote y lo que encontró. Revise veinte plantas en cinco "
        "puntos distintos. Después de un mes tendrá una idea clara de qué problema le "
        "visita más y cuándo. Recuerde: mire primero, anote y aplique algo solo si el "
        "técnico se lo recomienda.",
    ),
    key_points=(
        "Use semilla certificada o de calidad conocida y siembre a la distancia "
        "recomendada.",
        "Revise el lote cada semana en varios puntos y anote lo que encuentra.",
        "Rote el maíz con leguminosas para cortar el ciclo de plagas y enfermedades.",
        "Antes de aplicar un producto, consulte al técnico cuál, cuándo y cómo.",
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
    summary=(
        "Las cercas vivas y los sistemas silvopastoriles le dan sombra y forraje al "
        "ganado y protegen el suelo. Usted puede empezar en pequeño."
    ),
    paragraphs=(
        "¿Ha notado cómo sufre su ganado con el calor? Con días más calientes y veranos "
        "más largos, el ganado come menos, produce menos leche y gana menos peso. Los "
        "potreros sin un solo árbol se secan rápido y el suelo se compacta. Una salida "
        "probada en Colombia es la ganadería con árboles, conocida como sistema "
        "silvopastoril, que combina pasto, arbustos forrajeros y árboles en el mismo "
        "potrero.",
        "No tiene que transformar toda la finca de una vez. Lo más sencillo para empezar "
        "son las cercas vivas: en lugar de postes muertos, sembrar estacas de árboles que "
        "pegan fácil y que con el tiempo dan sombra, forraje y madera. Escoja estacas de "
        "árboles sanos, córtelas en bisel y siémbrelas en tierra preparada. El técnico de "
        "su zona le puede decir qué especies se dan mejor en su clima.",
        "Lo más importante es proteger lo sembrado. El ganado se come los rebrotes "
        "tiernos y tumba las plantas jóvenes, así que aísle las siembras nuevas con una "
        "cerca eléctrica temporal, separada un buen trecho de las plantas. Tenga "
        "paciencia: los arbustos forrajeros necesitan varios meses, por lo general de "
        "seis a ocho, antes de que el ganado los pueda ramonear sin acabarlos.",
        "Cuando ya tenga árboles y forrajeras en el potrero, maneje bien el pastoreo. "
        "Divida en potreros más pequeños y rote el ganado, dejando que cada potrero "
        "descanse el tiempo suficiente para que el pasto y los arbustos se recuperen; en "
        "muchos casos hablamos de mes y medio a dos meses. Así el suelo se cubre mejor, "
        "guarda más agua y el potrero produce más comida por hectárea.",
        "Los beneficios se ven en la cuenta: menos plata en suplementos durante el "
        "verano, animales menos estresados por el calor y un suelo que no se lava con las "
        "lluvias. Además, los árboles cuidan las quebradas y atraen aves y otros animales "
        "que ayudan a controlar plagas.",
        "Esta semana escoja un lindero de su finca donde haga falta cambiar postes y "
        "planee sembrar ahí su primera cerca viva. Pregunte al técnico qué especie le "
        "conviene, consiga las estacas y aparte el material para aislarla del ganado. "
        "Empezar con un tramo corto es suficiente para aprender. Recuerde: empiece con "
        "una cerca viva y proteja lo sembrado del ganado.",
    ),
    key_points=(
        "Los árboles en el potrero dan sombra, forraje y protegen el suelo del calor y "
        "la lluvia.",
        "Empiece con cercas vivas y pregunte al técnico qué especie se da en su clima.",
        "Aísle lo sembrado del ganado y espere varios meses antes del primer ramoneo.",
        "Rote los potreros y deje que cada uno descanse para que se recupere.",
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
    title="Su huerta para comer y para vender",
    summary=(
        "Diversificar las hortalizas, hacer abono con los residuos y llevar las cuentas "
        "de lo que vende ayuda a ahorrar en comida y a ganar con los excedentes."
    ),
    paragraphs=(
        "¿Sabe usted que una huerta bien llevada da para dos cosas? Da para la comida de "
        "la casa y para vender lo que sobra. Cuando todo el lote está sembrado de una "
        "sola hortaliza, un mal precio o una plaga lo deja sin nada. Cuando usted siembra "
        "varias, siempre hay algo que comer y algo que vender, y el riesgo se reparte.",
        "Diversifique con cabeza. Combine hortalizas de ciclo corto, que se cosechan en "
        "pocas semanas, con otras de ciclo más largo, para tener cosecha casi todo el "
        "año. Escoja lo que se da bien en su clima y lo que la gente de su zona compra. "
        "Pregunte en la plaza o en la tienda qué se vende fácil y qué escasea en ciertas "
        "épocas: esa información vale plata.",
        "Ahorre en abono aprovechando lo que ya tiene. Con los residuos de la cosecha, "
        "las cáscaras de la cocina y el estiércol de los animales puede hacer compost o "
        "lombriabono. Así devuelve a la tierra lo que le sacó, gasta menos en abonos "
        "comprados y el suelo guarda mejor el agua. Use también buena semilla: una "
        "semilla barata pero mala le hace perder todo el trabajo.",
        "Cuide el agua y el suelo. Riegue temprano o al final de la tarde, cuando se "
        "evapora menos, y mantenga el suelo cubierto entre las plantas. Si tiene plagas, "
        "revise primero con el técnico qué opciones hay antes de usar cualquier producto, "
        "sobre todo en hortalizas que se comen frescas.",
        "Lleve las cuentas. Anote cuánto gasta en semilla, abono y agua en cada siembra, "
        "y cuánto vende. Anote también lo que la familia se come, porque es plata que no "
        "tuvo que gastar en el mercado. Al final de cada cosecha sabrá qué hortaliza "
        "le deja más y cuál conviene cambiar.",
        "Esta semana haga una lista de las hortalizas que más compra su familia y de las "
        "que más se venden en su vereda o en la plaza. Escoja una que no tenga y que se "
        "dé en su clima, y planee sembrar un pedacito para probar. Empiece también una "
        "hoja de cuentas solo para la huerta. Recuerde: varias hortalizas y cuentas "
        "claras le dan comida en la mesa y plata en el bolsillo.",
    ),
    key_points=(
        "Sembrar varias hortalizas reparte el riesgo y da cosecha casi todo el año.",
        "Pregunte en la plaza qué se vende fácil antes de decidir qué sembrar.",
        "Haga compost o lombriabono con los residuos para gastar menos en abono.",
        "Anote lo que gasta, lo que vende y lo que se come la familia.",
    ),
    video=VideoSpec(
        video_id="u_eytQ0Hwxc",
        title=(
            "Prácticas sostenibles en el modelo agroalimentario de hortalizas en el "
            "Caribe seco colombiano"
        ),
        channel="AGROSAVIA TV",
    ),
)

_PANADERIA_COSTOS = CapsuleSpec(
    slug="panaderia-cuanto-cuesta-tu-pan",
    topic=TOPIC_FINANZAS,
    tags=("panaderia",),
    relevance=8.0,
    title="¿Cuánto le cuesta de verdad cada pan?",
    summary="Aprenda a sacar el costo de cada producto con la receta, el gas, el empaque "
    "y lo que se pierde, para ponerle un precio que sí le deje ganancia.",
    paragraphs=(
        "¿Sabe usted cuánto le cuesta de verdad cada pan? Muchas panaderías venden "
        "bastante y aun así sienten que la plata no alcanza. Casi siempre el problema es "
        "el mismo: no saben cuánto les cuesta de verdad cada pan. Ponen el precio mirando "
        "al vecino y, cuando suben la harina, el azúcar o el gas, siguen vendiendo igual "
        "sin darse cuenta de que ya están perdiendo.",
        "Saque el costo con la receta. Escriba todo lo que lleva una tanda: harina, "
        "azúcar, huevos, mantequilla, levadura y sal, con la cantidad y lo que le costó. "
        "Sume todo y divida por el número de panes que salen de esa tanda. Eso es lo que "
        "le cuestan los ingredientes de cada pan. Repita la cuenta cada vez que le suban "
        "un insumo importante.",
        "No se olvide de los costos que no se ven. El gas o la energía del horno, las "
        "bolsas y el papel, el agua, el arriendo y el pago de quien le ayuda también "
        "salen de la venta del pan. Una forma sencilla es sumar lo que gasta en eso al "
        "mes y repartirlo entre los panes que vende en el mes. Incluya también su propio "
        "trabajo: si no se paga, el negocio parece ganar más de lo que gana.",
        "Cuente lo que se pierde. El pan que no se vende, el que se quema o se daña "
        "también es costo. Anote cada día cuánto le sobra de cada producto. Si de un pan "
        "siempre sobra, haga menos o cambie la hora en que lo hornea; si de otro siempre "
        "falta, ahí hay una venta que está dejando ir.",
        "Con el costo completo ya puede poner un precio con cabeza. El precio debe cubrir "
        "el costo y dejar una ganancia. Si no puede subirlo sin perder clientes, busque "
        "dónde ahorrar: comprar algunos insumos en mayor cantidad con otros panaderos, "
        "ajustar el tamaño o hacer menos de lo que no se vende.",
        "Esta semana escoja sus tres panes que más vende y saque el costo de cada uno con "
        "la receta. Compárelo con el precio al que lo vende. Si la diferencia es muy "
        "pequeña o no alcanza para los demás gastos, ya sabe por dónde empezar a "
        "ajustar. Recuerde: el precio de su pan debe cubrir el costo completo y dejarle "
        "una ganancia.",
    ),
    key_points=(
        "Saque el costo de cada pan con la receta y repítalo cuando suban los insumos.",
        "Sume el gas, el empaque, el arriendo y su propio trabajo, no solo los "
        "ingredientes.",
        "Anote cada día lo que sobra o se daña: también es costo.",
        "El precio debe cubrir el costo completo y dejar una ganancia.",
    ),
)

_MISCELANEA_FIADO = CapsuleSpec(
    slug="miscelanea-el-fiado",
    topic=TOPIC_FINANZAS,
    tags=("miscelanea",),
    relevance=8.0,
    title="El fiado: cómo darlo sin quebrar su negocio",
    summary="Fiar ayuda a los clientes y a vender más, pero sin control se vuelve plata "
    "que nunca vuelve. Aprenda a llevarlo con orden y con límites claros.",
    paragraphs=(
        "¿Sabe usted cuánta plata tiene hoy en la calle por cuenta del fiado? En muchos "
        "negocios de barrio el fiado es parte de la relación con los clientes. Ayuda a "
        "la gente cuando está corta de plata y hace que vuelvan. Pero cada cosa que "
        "fía es mercancía que ya pagó y todavía no le han pagado. Si el fiado crece sin "
        "control, un día se da cuenta de que tiene el estante vacío, la caja sin plata "
        "y un cuaderno lleno de deudas.",
        "Lleve el fiado por escrito, siempre. Tenga un cuaderno solo para eso, con una "
        "página por cliente. Anote la fecha, lo que se llevó, el valor y lo que abona. "
        "Pídale al cliente que revise y que firme o ponga sus iniciales cuando se lleve "
        "algo. Así no hay discusiones después y usted sabe en todo momento cuánto le "
        "deben.",
        "Póngale límites. Decida cuánto es lo máximo que le fía a cada cliente y hasta "
        "cuándo tiene para pagar, por ejemplo hasta la quincena. Dígaselo con claridad y "
        "con respeto desde el principio. Si alguien ya llegó a su límite o no ha pagado "
        "lo anterior, no le fíe más hasta que se ponga al día. No es desconfianza: es "
        "cuidar el negocio que también le sirve a él.",
        "Mire el total cada semana. Sume todo lo que le deben y compárelo con lo que "
        "vende en una semana. Si el fiado se le está acercando a lo que vende, está "
        "financiando a sus clientes con la plata que necesita para surtir. En ese caso, "
        "frene el fiado nuevo y concéntrese en cobrar lo que ya tiene en la calle.",
        "Cobre con tacto, pero cobre. Recuérdele al cliente la fecha acordada, ofrézcale "
        "abonar por partes si le queda difícil y agradézcale cuando paga. Separe la "
        "plata del negocio de la de la casa, para que lo que le pagan del fiado vuelva "
        "al negocio y no se pierda en otros gastos.",
        "Esta semana sume todo lo que le deben en el cuaderno del fiado y anote el "
        "total. Mire quiénes llevan más de un mes sin pagar y defina con cada uno una "
        "fecha para ponerse al día. Decida también cuál va a ser su límite de fiado por "
        "cliente de aquí en adelante. Recuerde: lo que fía es mercancía que ya pagó, "
        "así que anótela, póngale límite y cóbrela con respeto.",
    ),
    key_points=(
        "Lo que fía es mercancía que ya pagó y todavía no le han pagado.",
        "Anote todo en un cuaderno, con una página por cliente y su firma o iniciales.",
        "Ponga un límite y una fecha de pago a cada cliente, y dígaselo desde el "
        "principio.",
        "Sume el fiado cada semana: si se acerca a lo que vende, frene y cobre.",
    ),
)

# --------------------------------------------------------------------------- #
# Ruta de comercio: la plata digital del negocio (billeteras, Bre-B y fraudes).
# Fuentes: Banco de la República (Bre-B), Fogafín (Seguro de Depósitos) y
# Superintendencia Financiera (alertas de fraude). Sin marcas comerciales.
# --------------------------------------------------------------------------- #
_COMERCIO: Final[tuple[str, ...]] = ("tienda_barrio", "panaderia", "miscelanea", "fruteria")

_PLATA_BILLETERAS = CapsuleSpec(
    slug="comercio-billeteras-digitales",
    topic=TOPIC_FINANZAS,
    tags=_COMERCIO,
    relevance=8.0,
    title="Billeteras digitales: cómo usarlas en su negocio con confianza",
    summary="Qué son, quién las vigila y cómo aprovecharlas para cobrar y ordenar la plata "
    "de su negocio sin correr riesgos.",
    paragraphs=(
        "¿Le ha pasado que un cliente le pregunta si le puede pagar con el celular? Cada "
        "vez más personas en Colombia pagan y reciben plata con billeteras digitales, que "
        "son aplicaciones del celular donde se guarda dinero, se envía y se recibe. Muchas "
        "funcionan como un depósito de bajo monto o como una cuenta de ahorros, y para el "
        "negocio pueden ser una gran ayuda si se usan con orden.",
        "Antes de abrir una, averigüe quién la respalda. Las billeteras de bancos y de "
        "otras entidades financieras están vigiladas por la Superintendencia Financiera de "
        "Colombia, que es la que pone las reglas y atiende las quejas. Desconfíe de "
        "aplicaciones que prometen ganancias altas, que nadie conoce o que le piden pagar "
        "para abrir la cuenta.",
        "También vale la pena saber que existe el Seguro de Depósitos de Fogafín. Si una "
        "entidad inscrita en Fogafín llega a liquidarse, ese seguro le devuelve sus "
        "ahorros hasta 50 millones de pesos por persona en cada entidad. En la página de "
        "Fogafín puede revisar si la entidad de su billetera está inscrita. No tiene que "
        "pagar nada: viene incluido por tener el producto.",
        "¿Qué gana su negocio? Puede cobrar sin manejar tanto efectivo, y menos plata en "
        "la caja es menos riesgo de robo y de equivocarse con las vueltas. Además, la "
        "aplicación guarda cada movimiento con fecha y valor, y eso le sirve para saber "
        "cuánto vendió en el día sin tener que contar billetes.",
        "Use una billetera solo para el negocio. Si en la misma le llegan las ventas, la "
        "plata de la casa y lo que le mandan los familiares, se le mezcla todo y no sabe "
        "cuánto deja el negocio. Con una para el negocio y otra para la casa, cada peso "
        "tiene su lugar. Y cuide la clave como cuida la llave del local: no la anote en el "
        "celular ni se la diga a nadie, ni siquiera a quien le ayuda en el mostrador.",
        "Esta semana mire qué billetera usan más sus clientes, revise que su entidad esté "
        "vigilada por la Superintendencia Financiera y decida cuál va a ser la billetera "
        "del negocio. Al cerrar cada día, compare lo que dice la aplicación con lo que "
        "anotó en su cuaderno. Recuerde: una billetera digital le sirve al negocio si la "
        "usa separada de la plata de la casa y con la clave bien guardada.",
    ),
    key_points=(
        "Use billeteras de entidades vigiladas por la Superintendencia Financiera.",
        "El Seguro de Depósitos de Fogafín protege hasta 50 millones de pesos por persona "
        "en cada entidad inscrita.",
        "Tenga una billetera solo para el negocio y otra para la casa.",
        "Su clave no se le dice a nadie, ni siquiera a quien le ayuda en el negocio.",
    ),
)

_PLATA_BRE_B = CapsuleSpec(
    slug="comercio-bre-b-y-llaves",
    topic=TOPIC_FINANZAS,
    tags=_COMERCIO,
    relevance=7.5,
    title="Bre-B y las llaves: reciba pagos al instante en su negocio",
    summary="Cómo funciona el sistema de pagos inmediatos del Banco de la República, cómo "
    "registrar la llave de su negocio y cómo confirmar cada pago.",
    paragraphs=(
        "¿Sabe usted qué es Bre-B? Es el sistema de pagos inmediatos del Banco de la "
        "República. Con él la plata pasa al instante de una cuenta a otra, aunque estén en "
        "entidades distintas, a cualquier hora y también los fines de semana y festivos. "
        "Para un negocio de barrio eso significa que el cliente le puede pagar desde su "
        "banco o su billetera y usted ve la plata enseguida en la suya.",
        "Para recibir pagos necesita una llave. La llave es un dato que identifica su "
        "cuenta o depósito, para que la gente le pueda mandar plata sin pedirle el número "
        "de la cuenta. Puede ser su número de celular, su número de documento, su correo o "
        "un código que le da su entidad. Los comercios también pueden usar el código de "
        "comercio que les asigna la entidad. Cada llave va a una sola cuenta, pero una "
        "cuenta puede tener varias llaves.",
        "La llave se registra en la aplicación o en la página web de la entidad donde tiene "
        "su cuenta, en la zona marcada como Bre-B. El registro no tiene costo, no necesita "
        "intermediarios y no hay que descargar otra aplicación. Tenga presente que la llave "
        "no es la contraseña: la llave se comparte con quien le va a pagar, la contraseña "
        "no se comparte con nadie.",
        "En el negocio puede tener la llave escrita en un letrero o el código QR que le da "
        "su entidad, para que el cliente lo escanee y pague. Si prefiere no darle su "
        "celular personal a todo el mundo, use como llave el código que le genera la "
        "entidad o el código de comercio.",
        "Antes de entregar la mercancía, confirme el pago en su propia aplicación. No basta "
        "con que el cliente le muestre la pantalla de su celular: mire que la plata sí le "
        "llegó y por el valor correcto. Cuando sea usted quien paga, revise el nombre que "
        "aparece antes de confirmar. Su entidad le informa cuál es el tope por "
        "transacción, y puede ponerle un límite menor por seguridad.",
        "Esta semana entre a la aplicación de su entidad, busque la zona Bre-B y registre "
        "la llave del negocio. Haga una prueba con un familiar: que le mande una cantidad "
        "pequeña y mire cuánto tarda en llegar. Después anote en su cuaderno cada venta "
        "que le pagan por llave. Recuerde: la llave se comparte, la contraseña nunca, y la "
        "venta se entrega cuando la plata ya está en su cuenta.",
    ),
    key_points=(
        "Bre-B, del Banco de la República, pasa la plata al instante entre entidades "
        "distintas.",
        "La llave identifica su cuenta: celular, documento, correo o un código de su "
        "entidad.",
        "Registrar la llave no cuesta y se hace en la aplicación de su entidad.",
        "Entregue la mercancía cuando vea el pago en su propia aplicación.",
    ),
)

_PLATA_FRAUDES = CapsuleSpec(
    slug="comercio-fraudes-pagos-digitales",
    topic=TOPIC_FINANZAS,
    tags=_COMERCIO,
    relevance=7.0,
    title="Que no le roben por el celular: fraudes con pagos digitales",
    summary="Cómo reconocer comprobantes falsos y mensajes o llamadas que se hacen pasar "
    "por su entidad, y qué hacer si cae en un engaño.",
    paragraphs=(
        "¿Le ha llegado un mensaje que dice que su cuenta está bloqueada y que entre a un "
        "enlace para arreglarlo? Con los pagos digitales también llegaron nuevos engaños. "
        "Los delincuentes no necesitan entrar al negocio: buscan que usted les entregue "
        "mercancía sin pagar o que les dé sus claves. La buena noticia es que casi todos "
        "los engaños se repiten y se pueden reconocer.",
        "El primero es el comprobante falso. Alguien le muestra la pantalla o le manda un "
        "pantallazo con la transferencia, y se va con la mercancía. Pero la plata nunca "
        "llegó: la imagen era falsa o la transferencia fue a otra cuenta. Por eso la regla "
        "es siempre la misma: confirme el pago en su propia aplicación antes de entregar. "
        "Aunque haya mucha gente o el cliente tenga prisa, tómese el minuto de revisar.",
        "El segundo es la suplantación. Llega un mensaje de texto, un correo o una llamada "
        "de alguien que dice ser de su banco, de su billetera o de una entidad del Estado. "
        "Le piden la clave, el código que le acaba de llegar al celular o que entre a un "
        "enlace. Ninguna entidad seria le pide eso. La Superintendencia Financiera ha "
        "advertido que no ofrece créditos ni otros productos por llamadas, y el Banco de la "
        "República recomienda no poner sus datos en páginas que le llegan por mensaje.",
        "Si tiene dudas, cuelgue y llame usted a su entidad por el número que aparece en "
        "su aplicación o en su tarjeta, nunca al que le dieron en el mensaje. No descargue "
        "aplicaciones que le pidan por teléfono y no deje que otra persona maneje su "
        "celular para ayudarle con una transferencia. La Superintendencia Financiera tiene "
        "un espacio llamado Protégete de los fraudes, donde explica cómo funcionan estos "
        "engaños.",
        "Si cae en un engaño, actúe rápido. Llame de inmediato a su entidad por sus canales "
        "oficiales para bloquear la cuenta, cambie sus claves y denuncie ante las "
        "autoridades. Guarde los mensajes y los números que le escribieron. Entre más "
        "rápido avise, más posibilidades hay de frenar el daño. Y tenga presente que CIMA "
        "nunca le va a pedir sus claves ni plata.",
        "Esta semana repase estas tres reglas con quien le ayuda en el negocio y péguelas "
        "cerca de la caja: el pago se confirma en la aplicación, la clave y los códigos no "
        "se le dan a nadie, y ante la duda se cuelga y se llama a la entidad. Recuerde: si "
        "alguien le pide su clave o un código, es un engaño, aunque diga que llama de su "
        "banco.",
    ),
    key_points=(
        "Un pantallazo no es un pago: confírmelo en su propia aplicación.",
        "Ninguna entidad le pide su clave ni los códigos que le llegan al celular.",
        "Ante la duda, cuelgue y llame usted a su entidad por el número oficial.",
        "Si cae en un engaño, bloquee, cambie sus claves y denuncie de inmediato.",
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
    _PLATA_BILLETERAS,
    _PLATA_BRE_B,
    _PLATA_FRAUDES,
)

PATHS: Final[tuple[PathSpec, ...]] = (
    PathSpec(
        slug="ruta-campo-sostenibilidad-y-riesgos",
        title="Ruta del campo: sostenibilidad y riesgos",
        summary=(
            "Aprenda a cuidar el suelo, el agua y la plata de su finca, y a conocer "
            "los riesgos del campo para ir preparándose."
        ),
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
        title="Ruta corta: su negocio en video",
        summary=(
            "Aprenda a grabar videos sencillos con su celular para que más clientes "
            "conozcan su tienda, cuidando su seguridad."
        ),
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
                "¿Cómo sabe si sus videos le traen clientes?",
                (
                    "No hay forma de saberlo",
                    "Contando los me gusta",
                    "Preguntando a los clientes nuevos cómo supieron de usted",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-cafe-broca",
        title="Ruta corta: la broca del café",
        summary=(
            "Conozca la plaga que más daña el café y aprenda a revisar su lote y a "
            "recoger bien para que no se refugie."
        ),
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
                "¿Cómo sabe qué tan afectado está su lote?",
                (
                    "Mirando los frutos solo por fuera",
                    "Preguntándole al vecino",
                    "Revisando una muestra de frutos para ver si tienen perforación",
                ),
                2,
            ),
            QuestionSpec(
                "Antes de aplicar cualquier producto contra la plaga, ¿qué debe hacer?",
                (
                    "Consultar al técnico o al extensionista de su comité",
                    "Echarle el doble para asegurarse",
                    "Mezclar varios productos",
                ),
                0,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-comercio-plata-digital",
        title="Ruta: la plata digital de su negocio",
        summary=(
            "Aprenda a usar billeteras digitales y Bre-B para cobrar en su negocio, y a "
            "reconocer los fraudes más comunes con pagos por celular."
        ),
        capsule_slugs=(_PLATA_BILLETERAS.slug, _PLATA_BRE_B.slug, _PLATA_FRAUDES.slug),
        questions=(
            QuestionSpec(
                "¿Qué es una llave de Bre-B?",
                (
                    "La contraseña de su cuenta",
                    "Un dato, como su celular, que identifica su cuenta para recibir plata",
                    "Una aplicación que hay que descargar aparte",
                ),
                1,
            ),
            QuestionSpec(
                "Un cliente le muestra un pantallazo de su transferencia. ¿Qué hace antes de "
                "entregarle la mercancía?",
                (
                    "Revisar en su propia aplicación que la plata sí llegó",
                    "Entregarla, porque el pantallazo es suficiente",
                    "Pedirle que le reenvíe el pantallazo",
                ),
                0,
            ),
            QuestionSpec(
                "Recibe una llamada de alguien que dice ser de su banco y le pide el código "
                "que le llegó al celular. ¿Qué conviene hacer?",
                (
                    "Darlo rápido para que no le bloqueen la cuenta",
                    "Darlo solo si la persona sabe su nombre",
                    "No darlo, colgar y llamar usted a su entidad por el número oficial",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-tienda-inventario",
        title="Ruta corta: el inventario de su tienda",
        summary=(
            "Aprenda a ver qué se vende, qué se queda quieto y cuánto pedir para que "
            "la plata de su tienda no quede parada."
        ),
        capsule_slugs=(_TIENDA_INVENTARIO.slug,),
        questions=(
            QuestionSpec(
                "¿Por qué un producto que no se vende es un problema?",
                (
                    "Porque es plata que ya pagó y está parada",
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
                "Antes de aprovechar un descuento por comprar más, ¿qué debe calcular?",
                (
                    "El color del empaque",
                    "Si el vendedor es amable",
                    "Cuánto alcanza a vender antes de que se venza",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-finanzas-gota-a-gota",
        title="Ruta corta: cuidado con el gota a gota",
        summary=(
            "Para quien cultiva y para quien atiende un negocio: cómo reconocer el "
            "gota a gota y qué alternativas más seguras tiene."
        ),
        capsule_slugs=(_FINANZAS_GOTA_A_GOTA.slug,),
        questions=(
            QuestionSpec(
                "¿Cuál es una señal de alerta de un préstamo gota a gota?",
                (
                    "Le prestan sin pedir casi nada y no le dicen el costo total",
                    "Le entregan un contrato claro",
                    "Le explican la tasa y cuánto pagará en total",
                ),
                0,
            ),
            QuestionSpec(
                "Antes de aceptar un crédito, ¿qué debe preguntar?",
                (
                    "Solo el valor de la primera cuota",
                    "Cuánto pagará en total y si la entidad está vigilada",
                    "Nada: todos cobran igual",
                ),
                1,
            ),
            QuestionSpec(
                "Si ya le están amenazando por un gota a gota, ¿qué conviene hacer?",
                (
                    "Pagar y no decírselo a nadie",
                    "Esconderse unos días",
                    "Contarlo a alguien de confianza y denunciar",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-general-clima",
        title="Ruta general: clima, agua y plan B",
        summary=(
            "Lo básico para cualquier persona: leer el clima, cuidar el agua y tener "
            "un plan para las temporadas difíciles."
        ),
        capsule_slugs=(_GENERAL_CLIMA.slug, _GENERAL_AGUA.slug, _GENERAL_PLAN_B.slug),
        questions=(
            QuestionSpec(
                "¿Para qué sirve llevar una libreta con la lluvia y el calor de cada semana?",
                (
                    "Para descubrir los patrones de su propio terreno y decidir con tiempo",
                    "Para que el IDEAM le pague por los datos",
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
        summary=(
            "Proteja su cafetal del clima, ordene las cuentas de la cosecha y aprenda "
            "a manejar los riesgos."
        ),
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
                    "Porque así sabe cuánto cuesta producir y cuánto le queda realmente",
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
        summary=(
            "Cuide su negocio del calor y las lluvias, separe la plata del negocio y "
            "de la casa, y conozca sus riesgos."
        ),
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
                "¿Qué significa ponerse un sueldo en su tienda?",
                (
                    "Sacar del negocio un valor fijo, siempre el mismo día, "
                    "para sus gastos personales",
                    "Sacar plata de la caja cada vez que la necesite",
                    "Pagarle a un empleado",
                ),
                0,
            ),
            QuestionSpec(
                "Antes de contratar un seguro o pedir un crédito, ¿qué debe preguntar?",
                (
                    "Qué cubre, qué excluye y cuánto pagará en total",
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
        summary=(
            "Aprenda las labores que mantienen sano su platanal y hacen que el "
            "racimo llene bien."
        ),
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
                "Si una planta se marchita de un momento a otro, ¿qué debe hacer?",
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
        summary=(
            "Conozca su terreno y maneje el agua para que el aguacate aguante las "
            "lluvias fuertes y los veranos largos."
        ),
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
        summary=(
            "Reconozca las dos enfermedades que más dañan el cacao y aprenda a "
            "frenarlas con revisión, poda y orden."
        ),
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
                    "Porque entra luz y circula el aire, y el hongo prospera con "
                    "humedad y sombra",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-arroz-agua",
        title="Ruta corta: ahorre agua en el arroz",
        summary=(
            "Aprenda a nivelar, a hacer caballones en curva y a medir el agua para "
            "producir gastando menos."
        ),
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
                    "Para saber cuánta gasta y cuánta se le va",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-maiz-sanidad",
        title="Ruta corta: maíz sano",
        summary=(
            "Aprenda a vigilar su lote de maíz y a combinar prácticas para tener "
            "menos plagas y enfermedades."
        ),
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
                "Antes de aplicar un producto, ¿qué debe hacer?",
                (
                    "Usar el que tenga el vecino",
                    "Mezclar varios para asegurarse",
                    "Preguntar al técnico cuál, cuándo y cómo aplicarlo",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-ganaderia-arboles",
        title="Ruta corta: árboles en el potrero",
        summary=(
            "Aprenda a empezar con cercas vivas y a manejar el pastoreo para tener "
            "más sombra y comida para el ganado."
        ),
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
        title="Ruta corta: su huerta para comer y vender",
        summary=(
            "Aprenda a diversificar su huerta, a ahorrar en abono y a llevar las "
            "cuentas de lo que vende."
        ),
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
                    "Lo que gasta, lo que vende y lo que se come la familia",
                ),
                2,
            ),
        ),
    ),
    PathSpec(
        slug="ruta-panaderia-costos",
        title="Ruta corta: el costo de su pan",
        summary=(
            "Aprenda a sacar el costo real de cada pan para ponerle un precio que "
            "sí le deje ganancia."
        ),
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
                "¿Qué otros costos debe sumar además de los ingredientes?",
                (
                    "Ninguno",
                    "El gas, el empaque, el arriendo y su propio trabajo",
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
        summary=(
            "Aprenda a llevar el fiado por escrito y con límites para que no se "
            "coma la plata de su negocio."
        ),
        capsule_slugs=(_MISCELANEA_FIADO.slug,),
        questions=(
            QuestionSpec(
                "¿Qué es, en el fondo, lo que fía?",
                (
                    "Mercancía que ya pagó y todavía no le han pagado",
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
                "Si el total del fiado se acerca a lo que vende en una semana, ¿qué hace?",
                (
                    "Fiar más para vender más",
                    "Cerrar el negocio",
                    "Frenar el fiado nuevo y cobrar lo que ya le deben",
                ),
                2,
            ),
        ),
    ),
)
