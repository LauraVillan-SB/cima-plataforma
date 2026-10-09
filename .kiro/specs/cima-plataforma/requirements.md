# Requirements Document

## Introduction

CIMA (Conocimiento, Inteligencia, Mercado y Agro) es una plataforma de "Escuela de Sostenibilidad e Inclusión" de Seguros Bolívar cuyo propósito es liderar la inclusión financiera en Colombia hacia 2030, logrando un crecimiento de 2x a 5x en la protección del sector agrícola y de pequeños negocios (pymes, tenderos de barrio).

El reto central es la inviabilidad financiera de escalar educación y ventas por canales tradicionales (SMS o consolas de WhatsApp) debido al alto costo por mensaje, sumado a que plataformas orgánicas (YouTube, redes sociales) no permiten certificar procesos formativos, obtener métricas por zona geográfica ni aplicar evaluaciones.

CIMA se construye como una aplicación web ultraligera (PWA) de consumo de datos mínimo, con autenticación "sin fricción" solo por número de teléfono, y un Agente Conversacional de IA Generativa como motor de interacción. El público objetivo son 2.5 millones de agricultores no asegurados y 5 millones de tenderos de barrio no asegurados, con edad promedio de 40 a 60 años, baja alfabetización digital, ausencia de correo electrónico y equipos móviles de gama de entrada con almacenamiento limitado.

El alcance de este documento son los requisitos de negocio y comportamiento del sistema (el "qué"). Las decisiones de implementación (el "cómo") se abordarán en el documento de diseño.

## Glossary

- **CIMA**: Plataforma web progresiva (PWA) de la Escuela de Sostenibilidad e Inclusión de Seguros Bolívar. Nombre compuesto de Conocimiento, Inteligencia, Mercado y Agro.
- **Agente_Conversacional**: Componente de IA generativa que interactúa con el Usuario en español coloquial colombiano mediante texto y notas de voz, actuando como asesor virtual empático.
- **Usuario**: Persona (agricultor o tendero de barrio) que accede a la plataforma CIMA para formarse y acceder a microseguros.
- **Microcápsula**: Unidad de micro-aprendizaje de duración entre 3 y 5 minutos enfocada en gestión de riesgos, finanzas o adaptación al clima.
- **Ruta_de_Aprendizaje**: Secuencia ordenada de Microcápsulas que el Usuario completa para obtener un incentivo o certificación.
- **Perfil_de_Usuario**: Conjunto de datos del Usuario que incluye número de teléfono, tipo de cultivo o tipo de comercio, y zona geográfica.
- **Microseguro**: Producto de aseguramiento de bajo costo adaptado a la economía popular, ofrecido tras completar una Ruta_de_Aprendizaje.
- **Nota_de_Voz**: Mensaje de audio enviado o recibido como medio de interacción entre el Usuario y el Agente_Conversacional.
- **Modulo_de_Autenticacion**: Componente responsable del inicio de sesión sin fricción basado únicamente en número de teléfono.
- **Modulo_de_Metricas**: Componente que registra y agrega datos de uso, progreso formativo y conversión por zona geográfica.
- **Certificado**: Constancia digital emitida al completar una Ruta_de_Aprendizaje.
- **Clave**: Contraseña numérica de 4 dígitos definida por el Usuario para autenticarse en CIMA. Se almacena cifrada (hash) y nunca en texto plano.
- **PII**: Información de identificación personal (Personally Identifiable Information), como número de teléfono y ubicación.
- **STT**: Reconocimiento de voz a texto (Speech-to-Text), proceso que transcribe el audio de una Nota_de_Voz a texto.
- **TTS**: Texto a voz (Text-to-Speech), proceso que convierte una respuesta de texto en audio reproducible.
- **ODS**: Objetivos de Desarrollo Sostenible definidos por las Naciones Unidas, referencia para medir el impacto social del programa.
- **Correlation-ID**: Identificador de correlación único que acompaña a una petición a través de los servicios para permitir la trazabilidad de extremo a extremo.
- **SLO**: Objetivo de nivel de servicio (Service Level Objective), umbral medible de calidad (por ejemplo latencia o tasa de errores) que un servicio se compromete a cumplir.
- **Service_Worker**: Componente del navegador que permite a la PWA almacenar recursos en caché, operar sin conexión y sincronizar acciones en segundo plano.
- **Tablero_de_Impacto**: Vista administrativa que presenta métricas agregadas y anonimizadas del impacto social del programa, relacionadas con los ODS.
- **Insignia**: Reconocimiento digital otorgado al Usuario por alcanzar un logro formativo (por ejemplo completar una Microcápsula o una Ruta_de_Aprendizaje), asociado al Perfil_de_Usuario. Puede acompañarse de puntos acumulables.
- **Encuesta_de_Satisfaccion**: Cuestionario breve y opcional que CIMA presenta al Usuario tras completar una Ruta_de_Aprendizaje o un hito definido, con al menos una calificación en una escala definida, para conocer su satisfacción con la Escuela. Sus respuestas se registran de forma agregada y anonimizada, sin PII.

## Requirements

### Requirement 1: Autenticación sin fricción por número de teléfono

**User Story:** Como Usuario con baja alfabetización digital y sin correo electrónico, quiero iniciar sesión con mi número de teléfono y una clave de 4 dígitos desde el navegador móvil, para acceder a la plataforma sin contraseñas complejas, sin correo y sin descargas.

#### Acceptance Criteria

1. CUANDO el Usuario accede a CIMA desde el navegador web del teléfono móvil, EL Modulo_de_Autenticacion DEBERÁ solicitar únicamente el número de teléfono y la Clave de 4 dígitos como credenciales de ingreso.
2. CUANDO un Usuario ingresa un número de teléfono con formato válido E.164 para el cual no existe una cuenta registrada, EL Modulo_de_Autenticacion DEBERÁ solicitar al Usuario ingresar la Clave de 4 dígitos dos veces de forma idéntica para confirmarla antes de activar la cuenta.
3. CUANDO el Modulo_de_Autenticacion solicita al Usuario crear su Clave de 4 dígitos, EL Modulo_de_Autenticacion DEBERÁ mostrar un texto de ayuda en español coloquial que sugiera usar los últimos 4 dígitos de su número de cédula como forma de recordarla, sin validar la Clave contra el número de cédula y sin almacenar el número de cédula.
4. SI al crear la Clave la confirmación no coincide con la Clave ingresada, ENTONCES EL Modulo_de_Autenticacion DEBERÁ rechazar la creación, no activar la cuenta y presentar un mensaje de corrección en español coloquial.
5. SI la Clave ingresada no está compuesta exactamente por 4 dígitos numéricos, ENTONCES EL Modulo_de_Autenticacion DEBERÁ rechazar la Clave y presentar un mensaje de corrección en español coloquial.
6. CUANDO el Usuario crea o actualiza su Clave, EL Modulo_de_Autenticacion DEBERÁ almacenar la Clave cifrada mediante un algoritmo de hash de contraseñas y nunca en texto plano.
7. CUANDO el Usuario ingresa un número de teléfono y una Clave que coinciden con las credenciales almacenadas, EL Modulo_de_Autenticacion DEBERÁ autenticar al Usuario y crear una sesión activa.
8. SI el Usuario ingresa una Clave incorrecta para su número de teléfono, ENTONCES EL Modulo_de_Autenticacion DEBERÁ rechazar el ingreso y presentar un mensaje de error en español coloquial sin revelar si el número de teléfono existe.
9. SI el número de teléfono ingresado no cumple el formato E.164, ENTONCES EL Modulo_de_Autenticacion DEBERÁ rechazar la solicitud y presentar un mensaje de corrección en español coloquial.
10. EL Modulo_de_Autenticacion DEBERÁ completar el flujo de ingreso sin requerir contraseña alfanumérica, correo electrónico ni descarga de aplicaciones.
11. CUANDO se generan tokens de sesión, EL Modulo_de_Autenticacion DEBERÁ emitir un token de acceso de vida corta no mayor a 15 minutos con rotación de refresco y almacenarlos en cookies con atributos Secure, HttpOnly y SameSite.
12. SI un número de teléfono acumula 5 intentos de ingreso con Clave incorrecta consecutivos, ENTONCES EL Modulo_de_Autenticacion DEBERÁ bloquear temporalmente nuevos intentos de ingreso para ese número durante 15 minutos y presentar un mensaje de bloqueo en español coloquial.
13. CUANDO transcurren 15 minutos desde el inicio del bloqueo temporal de un número de teléfono, EL Modulo_de_Autenticacion DEBERÁ reactivar los intentos de ingreso para ese número con el conteo de intentos fallidos reiniciado a cero.
14. MIENTRAS una sesión está activa, SI el Usuario permanece inactivo por más de 30 minutos, ENTONCES EL Modulo_de_Autenticacion DEBERÁ invalidar la sesión y exigir una nueva autenticación.
15. CUANDO el Usuario autenticado solicita cambiar su Clave, EL Modulo_de_Autenticacion DEBERÁ exigir la Clave actual válida antes de registrar la nueva Clave.

### Requirement 2: Operación como PWA ultraligera de bajo consumo de datos

**User Story:** Como Usuario con un teléfono de gama de entrada con almacenamiento limitado y datos móviles costosos, quiero acceder a una aplicación web ligera sin instalar nada, para usar la plataforma sin saturar la memoria ni consumir muchos datos.

#### Acceptance Criteria

1. EL CIMA DEBERÁ ejecutarse como aplicación web progresiva (PWA) accesible desde el navegador móvil sin instalación desde tiendas de aplicaciones.
2. CUANDO el Usuario carga la pantalla inicial de CIMA en una conexión 3G de 1.6 Mbps, EL CIMA DEBERÁ alcanzar el estado interactivo (Time to Interactive) en 3 segundos o menos.
3. EL CIMA DEBERÁ transferir como máximo 500 kilobytes de recursos en la carga inicial de la pantalla principal.
4. DONDE el navegador del Usuario soporta almacenamiento en caché de recursos, EL CIMA DEBERÁ almacenar en caché los recursos estáticos de modo que la carga de una visita posterior transfiera como máximo 50 kilobytes de recursos estáticos.
5. SI el navegador del Usuario no soporta almacenamiento en caché de recursos, ENTONCES EL CIMA DEBERÁ continuar operando descargando los recursos necesarios en cada visita.
6. CUANDO el Usuario reabre CIMA tras una sesión previa en el mismo navegador y la sesión previa se encuentra dentro de su periodo de validez vigente, EL CIMA DEBERÁ restaurar la sesión activa sin solicitar nuevamente la Clave.
7. SI el Usuario reabre CIMA y su sesión previa ha expirado, ENTONCES EL CIMA DEBERÁ redirigir al flujo de autenticación y solicitar nuevamente la Clave, conservando el destino solicitado para retomarlo tras la autenticación.
8. SI durante una interacción la red no responde durante 3 segundos o más, ENTONCES EL CIMA DEBERÁ presentar un indicador de estado de conexión en 2 segundos o menos tras detectar la interrupción y conservar el último paso completado de la Ruta_de_Aprendizaje registrado antes de la interrupción.
9. CUANDO la conexión de red se restablece tras una interrupción, EL CIMA DEBERÁ restaurar el progreso de la Ruta_de_Aprendizaje conservado sin pérdida de los pasos ya completados antes de la interrupción.

### Requirement 3: Interacción con el Agente Conversacional por texto y voz

**User Story:** Como Usuario de 40 a 60 años con baja alfabetización digital, quiero conversar con un asesor virtual empático en español coloquial colombiano por texto o notas de voz, para aprender y resolver dudas de forma natural.

#### Acceptance Criteria

1. CUANDO el Usuario envía un mensaje de texto de hasta 2000 caracteres, EL Agente_Conversacional DEBERÁ responder en español coloquial colombiano con una respuesta de texto no vacía dentro de los 15 segundos siguientes a la recepción del mensaje.
2. SI el Usuario envía un mensaje de texto que excede los 2000 caracteres o está vacío tras eliminar espacios, ENTONCES EL Agente_Conversacional DEBERÁ rechazar el mensaje sin invocar el modelo de IA generativa y mostrar un mensaje de error que indique el límite de longitud permitido, conservando el contenido ingresado por el Usuario.
3. CUANDO el Usuario envía una Nota_de_Voz en uno de los formatos de audio soportados (m4a/aac, ogg o mp3) y de duración entre 1 y 120 segundos, EL Agente_Conversacional DEBERÁ transcribir el audio a texto y responder según el contenido transcrito dentro de los 15 segundos siguientes a la recepción de la Nota_de_Voz.
4. SI la transcripción de la Nota_de_Voz falla, produce texto vacío, o la Nota_de_Voz excede los 120 segundos o usa un formato de audio distinto de los soportados (m4a/aac, ogg o mp3), ENTONCES EL Agente_Conversacional DEBERÁ rechazar la Nota_de_Voz sin invocar el modelo de IA generativa y solicitar en español coloquial colombiano que el Usuario repita el mensaje, indicando el límite de duración y los formatos soportados.
5. DONDE el Usuario lo solicita o lo tiene configurado, EL Agente_Conversacional DEBERÁ emitir su respuesta como Nota_de_Voz que corresponda al mismo contenido de la respuesta de texto y que no exceda 120 segundos de duración, además del texto en el mismo intercambio.
6. SI el Agente_Conversacional no logra interpretar la intención del Usuario, ENTONCES EL Agente_Conversacional DEBERÁ solicitar una aclaración en español coloquial colombiano y ofrecer entre 2 y 5 opciones de ayuda seleccionables.
7. SI el Agente_Conversacional no genera una respuesta dentro de 15 segundos contados desde la recepción de la entrada del Usuario, ENTONCES EL CIMA DEBERÁ mostrar un indicador de procesamiento visible al Usuario hasta que la respuesta esté disponible o se agote el tiempo de espera máximo de 60 segundos.
8. SI el Agente_Conversacional no genera una respuesta dentro de los 60 segundos siguientes a la recepción de la entrada del Usuario, ENTONCES EL CIMA DEBERÁ retirar el indicador de procesamiento y mostrar un mensaje de error que indique que el servicio no está disponible, conservando el historial de la conversación.
9. CUANDO el Agente_Conversacional procesa una entrada o genera una salida, EL Agente_Conversacional DEBERÁ registrar cada entrada y salida de la interacción en el servicio de registro centralizado con un identificador de correlación, excluyendo cualquier PII del contenido registrado.
10. DONDE la entrada del Usuario contiene PII, EL Agente_Conversacional DEBERÁ redactar la totalidad de la PII detectada antes de enviar el contenido al modelo de IA generativa.
11. SI la redacción de PII no puede completarse con éxito, ENTONCES EL Agente_Conversacional DEBERÁ no enviar el contenido al modelo de IA generativa y solicitar al Usuario reformular el mensaje sin datos personales.

### Requirement 4: Micro-aprendizaje personalizado

**User Story:** Como Usuario agricultor o tendero, quiero recibir cápsulas de aprendizaje cortas y personalizadas según mi tipo de cultivo o comercio, para formarme en temas relevantes para mi actividad en pocos minutos.

#### Acceptance Criteria

1. CUANDO el Usuario inicia una sesión formativa, EL CIMA DEBERÁ entregar Microcápsulas con una duración de contenido entre 3 y 5 minutos, ambos valores inclusive.
2. EL CIMA DEBERÁ clasificar cada Microcápsula en exactamente uno de los siguientes temas: gestión de riesgos, finanzas o adaptación al clima.
3. DONDE el Perfil_de_Usuario indica un tipo de cultivo o un tipo de comercio, EL CIMA DEBERÁ seleccionar entre 1 y 10 Microcápsulas cuyo contenido corresponda a ese tipo de cultivo o comercio, y SI existen más de 10 Microcápsulas coincidentes, EL CIMA DEBERÁ seleccionar las 10 primeras ordenadas por relevancia descendente y, ante igual relevancia, por fecha de publicación descendente.
4. SI el Perfil_de_Usuario indica un tipo de cultivo o un tipo de comercio para el cual no existe ninguna Microcápsula correspondiente, ENTONCES EL CIMA DEBERÁ entregar Microcápsulas del tema general de adaptación al clima.
5. SI el Perfil_de_Usuario indica un tipo de cultivo o un tipo de comercio para el cual no existe ninguna Microcápsula correspondiente, ENTONCES EL CIMA DEBERÁ notificar al Usuario que no hay contenido específico disponible para su actividad.
6. CUANDO el Usuario completa una Microcápsula, EL Modulo_de_Metricas DEBERÁ registrar la finalización asociada al Perfil_de_Usuario en un tiempo máximo de 5 segundos.
7. SI el registro de finalización de una Microcápsula falla, ENTONCES EL Modulo_de_Metricas DEBERÁ reintentar el registro hasta 3 veces y, de persistir el fallo, conservar el evento de finalización para registro posterior sin pérdida de datos.
8. SI el Perfil_de_Usuario no contiene tipo de cultivo ni tipo de comercio, ENTONCES EL Agente_Conversacional DEBERÁ solicitar al Usuario esa información antes de personalizar las Microcápsulas, hasta un máximo de 3 solicitudes.
9. SI el Usuario no proporciona el tipo de cultivo ni el tipo de comercio tras 3 solicitudes, ENTONCES EL CIMA DEBERÁ entregar Microcápsulas del tema general de adaptación al clima sin personalización.
10. CUANDO cada Microcápsula de una Ruta_de_Aprendizaje tiene su finalización registrada para un Usuario, EL CIMA DEBERÁ marcar la Ruta_de_Aprendizaje como completada para ese Usuario.

### Requirement 5: Conversión a negocio y entrega de incentivos

**User Story:** Como Seguros Bolívar, quiero que al completar rutas de aprendizaje el Usuario reciba incentivos inmediatos y opciones de microseguro adaptadas, para convertir la formación en protección efectiva de la economía popular.

#### Acceptance Criteria

1. CUANDO el Usuario completa el 100% de las actividades de una Ruta_de_Aprendizaje, EL CIMA DEBERÁ entregar al Usuario el incentivo asociado a esa Ruta_de_Aprendizaje en un tiempo máximo de 5 segundos, mostrando una confirmación observable de entrega exitosa.
2. SI la entrega del incentivo falla tras completar la Ruta_de_Aprendizaje, ENTONCES EL CIMA DEBERÁ informar al Usuario mediante un mensaje indicando que la entrega no se completó, conservar el estado de completitud de la Ruta_de_Aprendizaje y reintentar la entrega automáticamente hasta un máximo de 3 intentos, con un intervalo mínimo de 5 segundos entre intentos.
3. SI la entrega del incentivo sigue fallando después de 3 intentos, ENTONCES EL CIMA DEBERÁ conservar el estado de completitud de la Ruta_de_Aprendizaje y la condición de incentivo pendiente, informar al Usuario mediante un mensaje indicando que la entrega quedó pendiente, y registrar la falla de entrega asociada al identificador del Perfil_de_Usuario para resolución posterior.
4. CUANDO el Usuario completa una Ruta_de_Aprendizaje, EL Agente_Conversacional DEBERÁ presentar entre 1 y 5 opciones de Microseguro cuyo tipo corresponda al tipo de cultivo o comercio registrado en el Perfil_de_Usuario, en un tiempo máximo de 3 segundos.
5. CUANDO el Usuario selecciona una opción de Microseguro, EL CIMA DEBERÁ registrar la intención de conversión asociada al identificador del Perfil_de_Usuario y a la Ruta_de_Aprendizaje completada, y confirmar al Usuario mediante un mensaje observable que la selección fue registrada.
6. SI el registro de la intención de conversión falla, ENTONCES EL CIMA DEBERÁ informar al Usuario mediante un mensaje indicando que la selección no se registró, no confirmar la selección como registrada y conservar la opción de Microseguro seleccionada disponible para reintento por parte del Usuario.
7. SI el Perfil_de_Usuario no tiene registrado un tipo de cultivo o comercio, ENTONCES EL Agente_Conversacional DEBERÁ solicitar al Usuario que especifique dicho tipo antes de presentar opciones de Microseguro.
8. SI no existe una opción de Microseguro disponible para el tipo de cultivo o comercio del Perfil_de_Usuario, ENTONCES EL Agente_Conversacional DEBERÁ informar al Usuario que no hay oferta disponible y registrar la ausencia de oferta, incluyendo el tipo de cultivo o comercio solicitado, para análisis posterior.
9. EL CIMA DEBERÁ enmascarar la PII del Usuario en toda respuesta que presente datos de conversión o de Perfil_de_Usuario, dejando visibles como máximo los últimos 4 caracteres de cada campo que contenga nombre, número de documento de identidad, teléfono, correo electrónico o dirección del Usuario.

### Requirement 6: Certificación de procesos formativos

**User Story:** Como Seguros Bolívar, quiero certificar los procesos de formación completados, para acreditar el aprendizaje de forma verificable, a diferencia de las plataformas orgánicas.

#### Acceptance Criteria

1. CUANDO el Usuario completa una Ruta_de_Aprendizaje y aprueba su evaluación asociada con un puntaje igual o superior al 70%, EL CIMA DEBERÁ emitir un Certificado digital asociado al Perfil_de_Usuario y a la Ruta_de_Aprendizaje en un tiempo máximo de 5 segundos.
2. SI el Usuario completa una Ruta_de_Aprendizaje pero su evaluación asociada obtiene un puntaje inferior al 70%, ENTONCES EL CIMA DEBERÁ rechazar la emisión del Certificado y presentar un mensaje que indique que no se alcanzó el puntaje mínimo de aprobación.
3. EL Certificado DEBERÁ contener el identificador único del Usuario, el identificador de la Ruta_de_Aprendizaje completada, la fecha de emisión en formato ISO-8601 (AAAA-MM-DDThh:mm:ssZ) y un código único verificable con una longitud mínima de 16 y máxima de 64 caracteres alfanuméricos.
4. SI ya existe un Certificado emitido para el mismo Perfil_de_Usuario y la misma Ruta_de_Aprendizaje, ENTONCES EL CIMA DEBERÁ devolver el Certificado existente sin emitir uno nuevo.
5. CUANDO el Usuario autenticado solicita un Certificado emitido previamente del cual es titular, EL CIMA DEBERÁ presentar el Certificado correspondiente en un tiempo máximo de 3 segundos.
6. SI el Usuario solicita un Certificado que no existe, ENTONCES EL CIMA DEBERÁ presentar un mensaje que indique que no se encontró el Certificado solicitado, sin exponer información de otros Perfiles_de_Usuario.
7. SI el Usuario que solicita un Certificado no es el titular del Perfil_de_Usuario asociado, ENTONCES EL CIMA DEBERÁ rechazar la solicitud con un error de autorización, no revelar el contenido del Certificado y registrar el intento de acceso no autorizado con el identificador del Usuario solicitante y la fecha en formato ISO-8601.

### Requirement 7: Evaluaciones del aprendizaje

**User Story:** Como Seguros Bolívar, quiero aplicar evaluaciones sobre el contenido formativo, para medir la apropiación del conocimiento antes de certificar.

#### Acceptance Criteria

1. CUANDO el Usuario finaliza todas las Microcápsulas de una Ruta_de_Aprendizaje, EL CIMA DEBERÁ presentar una evaluación asociada a esa Ruta_de_Aprendizaje.
2. CUANDO el Usuario envía la evaluación con todas las preguntas respondidas, EL CIMA DEBERÁ calcular el puntaje obtenido en una escala de 0 a 100 y registrar el puntaje asociado al Perfil_de_Usuario.
3. SI el puntaje obtenido es igual o superior al umbral de aprobación definido para la Ruta_de_Aprendizaje, que estará en el rango de 0 a 100 con valor por defecto de 70, ENTONCES EL CIMA DEBERÁ marcar la evaluación como aprobada.
4. SI el puntaje obtenido es inferior al umbral de aprobación, ENTONCES EL CIMA DEBERÁ marcar la evaluación como no aprobada y permitir al Usuario reintentarla hasta un máximo de 3 intentos.
5. SI el Usuario agota los 3 intentos sin aprobar, ENTONCES EL CIMA DEBERÁ bloquear nuevos intentos durante un periodo de enfriamiento de 24 horas y, transcurrido dicho periodo, reiniciar el contador de intentos.
6. CUANDO EL CIMA recibe una respuesta de evaluación, EL CIMA DEBERÁ validar en el servidor el tipo, formato y rango esperados de la respuesta antes de calcular el puntaje.
7. SI una respuesta de evaluación no cumple la validación de tipo, formato o rango, ENTONCES EL CIMA DEBERÁ rechazar la evaluación sin calcular puntaje y devolver un error indicando la respuesta inválida.

### Requirement 8: Métricas por zona geográfica y seguimiento

**User Story:** Como Seguros Bolívar, quiero obtener métricas de uso, progreso y conversión agregadas por zona geográfica, para dirigir la estrategia de inclusión financiera y medir el crecimiento de la protección.

#### Acceptance Criteria

1. CUANDO el Usuario completa una Microcápsula, una Ruta_de_Aprendizaje o una conversión de Microseguro, EL Modulo_de_Metricas DEBERÁ registrar en un máximo de 5 segundos el evento asociado a la zona geográfica definida en el Perfil_de_Usuario, incluyendo tipo de evento, identificador de zona geográfica y marca de tiempo en formato ISO-8601.
2. SI el Perfil_de_Usuario no tiene una zona geográfica asignada al momento de completar el evento, ENTONCES EL Modulo_de_Metricas DEBERÁ registrar el evento asociándolo a una zona geográfica designada como "sin_zona" y marcar el evento como no clasificado.
3. CUANDO el Modulo_de_Metricas registra un evento, EL Modulo_de_Metricas DEBERÁ actualizar los agregados por zona geográfica y por tipo de evento (Microcápsula completada, Ruta_de_Aprendizaje completada y conversión de Microseguro) de modo que la frescura de los agregados consultables no exceda 60 segundos respecto del evento registrado.
4. SI el registro de un evento de métrica falla, ENTONCES EL Modulo_de_Metricas DEBERÁ reintentar el registro hasta 3 veces, conservar el evento en una cola de pendientes y presentar una indicación de error genérica sin pérdida de datos.
5. CUANDO se solicita un reporte de métricas por zona geográfica, EL Modulo_de_Metricas DEBERÁ entregar los datos agregados sin exponer PII individual de los Usuarios, enmascarando o excluyendo cualquier campo que permita identificar a un Usuario individual.
6. SI una zona geográfica contiene menos de 5 Usuarios con eventos registrados, ENTONCES EL Modulo_de_Metricas DEBERÁ suprimir los datos agregados de esa zona en el reporte para prevenir la reidentificación de Usuarios individuales.
7. CUANDO se solicita un reporte y no hay datos disponibles tras la supresión, EL Modulo_de_Metricas DEBERÁ devolver conteo cero por cada tipo de evento e indicar la ausencia de datos clasificables.
8. MIENTRAS un dato sensible asociado a un evento tiene una antigüedad igual o superior a 90 días, EL Modulo_de_Metricas DEBERÁ eliminar o anonimizar ese dato sensible conservando únicamente los agregados no identificables.

### Requirement 9: Gestión del Perfil de Usuario y protección de datos

**User Story:** Como Usuario, quiero que mis datos personales se traten de forma segura y mínima, para confiar en la plataforma cumpliendo la normativa de protección de datos.

#### Acceptance Criteria

1. CUANDO se crea un Perfil_de_Usuario, EL CIMA DEBERÁ almacenar únicamente los campos número de teléfono, tipo de cultivo o comercio y zona geográfica, y SI la solicitud incluye un campo adicional no incluido en esa lista, ENTONCES EL CIMA DEBERÁ rechazar la solicitud y devolver una indicación de error que señale el campo no permitido.
2. CUANDO se recibe un dato destinado al Perfil_de_Usuario, EL CIMA DEBERÁ normalizar la entrada eliminando espacios iniciales y finales (trim) y luego validar en el servidor que el número de teléfono contenga entre 7 y 15 dígitos numéricos, que el tipo de cultivo o comercio corresponda a un valor de la lista de valores permitidos, y que la zona geográfica no exceda 100 caracteres.
3. SI un dato destinado al Perfil_de_Usuario no cumple las reglas de validación de tipo, formato, longitud o rango, ENTONCES EL CIMA DEBERÁ rechazar la solicitud sin crear ni modificar el Perfil_de_Usuario y devolver un error que indique el campo inválido.
4. CUANDO una respuesta de API incluye datos del Perfil_de_Usuario o se genera un registro de log que contiene PII del Perfil_de_Usuario, EL CIMA DEBERÁ exponer la PII enmascarada mostrando como máximo los últimos 4 caracteres del valor.
5. CUANDO una respuesta de API incluye datos del Perfil_de_Usuario, EL CIMA DEBERÁ exponer únicamente los campos definidos en el DTO autorizado para esa respuesta y omitir cualquier otro campo del Perfil_de_Usuario.
6. SI una solicitud intenta acceder o modificar un Perfil_de_Usuario distinto al del Usuario autenticado, ENTONCES EL CIMA DEBERÁ rechazar la solicitud con un error de autorización, no aplicar ningún cambio al Perfil_de_Usuario objetivo y registrar el intento sin exponer PII.
7. SI un Usuario autenticado acumula múltiples intentos de acceso a Perfiles_de_Usuario ajenos, ENTONCES EL CIMA DEBERÁ aplicar un límite de tasa a las solicitudes de ese Usuario y registrar el patrón para análisis de seguridad sin exponer PII.
8. CUANDO un dato sensible del Perfil_de_Usuario alcanza 90 días desde su creación, EL CIMA DEBERÁ eliminarlo o anonimizarlo de forma que deje de ser recuperable como PII.

### Requirement 10: Integración opcional con el sitio WordPress existente

**User Story:** Como Seguros Bolívar, quiero poder integrar CIMA con el sitio WordPress existente (www.sostenibilidadbolivar.com), para aprovechar el canal web actual de sostenibilidad.

#### Acceptance Criteria

1. DONDE la plataforma se despliega integrada con el sitio WordPress existente, EL CIMA DEBERÁ ser accesible desde www.sostenibilidadbolivar.com reutilizando la sesión autenticada activa del usuario, siempre que dicha sesión no haya expirado ni acumulado más de 30 minutos de inactividad, sin requerir un segundo inicio de sesión.
2. DONDE la plataforma se despliega integrada con el sitio WordPress existente, SI el usuario no cuenta con una sesión autenticada activa al acceder desde www.sostenibilidadbolivar.com, ENTONCES EL CIMA DEBERÁ redirigir al flujo de autenticación y denegar el acceso al contenido protegido hasta que la autenticación se complete.
3. DONDE CIMA se integra con el sitio WordPress, EL CIMA DEBERÁ preservar su comportamiento de PWA, manteniendo un peso de carga inicial no mayor a 1 MB y un tiempo de carga interactiva menor a 3 segundos.
4. CUANDO CIMA consume datos del sitio WordPress o de servicios externos, EL CIMA DEBERÁ realizar la comunicación mediante llamadas autenticadas con token firmado, únicamente sobre HTTPS, hacia dominios incluidos en una lista de permitidos configurada, con un timeout máximo de 5 segundos, un máximo de 2 redirecciones y bloqueando las direcciones IP privadas y de enlace local (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 y 169.254.169.254).
5. SI CIMA intenta consumir datos de un dominio no incluido en la lista de permitidos, mediante un canal no HTTPS, o hacia una dirección IP privada o de enlace local (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 o 169.254.169.254), ENTONCES EL CIMA DEBERÁ bloquear la comunicación, no transmitir datos y registrar el intento con su identificador de correlación, informando al llamador un error que indique acceso no permitido.

### Requirement 11: Observabilidad y operación

**User Story:** Como equipo de operación, quiero trazabilidad y métricas del comportamiento de la plataforma, para detectar y resolver problemas antes de que afecten a los Usuarios.

#### Acceptance Criteria

1. CUANDO un servicio de CIMA emite una petición hacia otro servicio, EL CIMA DEBERÁ propagar un Correlation-ID en esa petición y conservarlo a lo largo de toda la cadena de llamadas asociadas a la interacción.
2. CUANDO un componente de CIMA genera un registro de log, EL CIMA DEBERÁ emitir el log en formato estructurado hacia el servicio de registro centralizado y nunca hacia archivos locales.
3. EL CIMA DEBERÁ exponer métricas de las señales doradas (latencia, tráfico, tasa de errores y saturación) por cada servicio, junto con el SLO definido para cada señal.
4. CUANDO una métrica de un servicio supera el umbral de su SLO definido, EL CIMA DEBERÁ activar una alerta hacia el canal de operación configurado.
5. CUANDO un servicio de CIMA invoca un servicio externo (modelo de IA generativa, canal de voz, pasarela de pagos o core de pólizas), EL CIMA DEBERÁ aplicar un circuit breaker, un timeout definido y un comportamiento de fallback documentado para esa invocación.
6. SI un servicio externo supera el timeout definido o el circuit breaker se encuentra abierto, ENTONCES EL CIMA DEBERÁ ejecutar el fallback documentado y registrar el evento con su Correlation-ID sin exponer PII.

### Requirement 12: Escalabilidad y costo marginal bajo

**User Story:** Como patrocinador de la iniciativa, quiero atender a millones de Usuarios sin que el costo por interacción se dispare, para que el programa sea sostenible financieramente.

#### Acceptance Criteria

1. EL CIMA DEBERÁ soportar interacciones del Usuario con el Agente_Conversacional sin un límite de cantidad por Usuario impuesto por el costo del canal, manteniendo un costo marginal por interacción menor al de un canal comercial de SMS o WhatsApp.
2. EL CIMA DEBERÁ aplicar límites de tasa (rate limiting) a los componentes core para proteger los recursos frente a picos de demanda.
3. CUANDO la demanda de uso aumenta, EL CIMA DEBERÁ escalar horizontalmente sus servicios sin estado agregando instancias adicionales sin pérdida de sesiones activas.
4. CUANDO el Usuario inicia una tarea de larga duración, EL CIMA DEBERÁ procesarla en segundo plano mediante un patrón asíncrono y devolver al Usuario un acuse de recibo observable sin bloquear la interacción.
5. SI un componente core alcanza su límite de tasa configurado, ENTONCES EL CIMA DEBERÁ rechazar las solicitudes excedentes con una indicación de reintento y registrar el evento sin exponer PII.

### Requirement 13: Accesibilidad e inclusión

**User Story:** Como persona mayor con baja alfabetización digital, quiero una interfaz simple, legible y usable por voz, para no sentirme excluido por la tecnología.

#### Acceptance Criteria

1. EL CIMA DEBERÁ presentar los flujos principales con la menor cantidad de pasos de interacción necesarios para completar cada acción.
2. EL CIMA DEBERÁ presentar los textos con una relación de contraste de color y tamaños de fuente conformes a las pautas de accesibilidad WCAG 2.1 nivel AA.
3. EL CIMA DEBERÁ presentar los objetivos táctiles interactivos con un tamaño mínimo de 44 por 44 píxeles CSS.
4. EL CIMA DEBERÁ ofrecer, para cada contenido textual destinado al Usuario, una alternativa de lectura por voz y una alternativa de entrada por voz.
5. EL CIMA DEBERÁ presentar los textos destinados al Usuario en español coloquial colombiano, claro y sin tecnicismos.
6. MIENTRAS el Usuario opera CIMA en una conexión 3G de 1.6 Mbps y en una pantalla con ancho de 320 píxeles CSS o superior, EL CIMA DEBERÁ mantener operables todos los flujos críticos de autenticación, aprendizaje y conversión.

### Requirement 14: Experiencia voz-first

**User Story:** Como persona que lee y escribe con dificultad, quiero poder hablar y escuchar al asesor en lugar de teclear, para usar la plataforma de forma natural.

#### Acceptance Criteria

1. CUANDO el Usuario accede a CIMA, EL CIMA DEBERÁ ofrecer la interacción por voz como modo primario y mantener la interacción por texto como alternativa disponible en el mismo flujo.
2. CUANDO el Usuario activa el control de voz y habla, EL CIMA DEBERÁ transcribir el audio mediante STT y procesar la intención resultante.
3. CUANDO el Agente_Conversacional responde al Usuario, EL CIMA DEBERÁ ofrecer la respuesta en audio mediante TTS con una voz neutra entendible en el contexto colombiano, además del texto en el mismo intercambio.
4. EL CIMA DEBERÁ presentar los controles de voz con un tamaño mínimo de 44 por 44 píxeles CSS y operables con una sola mano.
5. SI la transcripción STT resulta con una confianza inferior al umbral configurado, ENTONCES EL CIMA DEBERÁ solicitar confirmación o repetición al Usuario en lenguaje simple, sin atribuir el error al Usuario.
6. CUANDO el Usuario envía audio para interacción por voz, EL CIMA DEBERÁ aplicar redacción de PII al contenido antes de enviarlo al modelo de IA generativa y conservar el audio únicamente durante el tiempo necesario para su transcripción, eliminándolo o anonimizándolo conforme a la política de retención de datos sensibles de 90 días.

### Requirement 15: Tablero de impacto social (ODS)

**User Story:** Como patrocinador o aliado del programa, quiero ver el impacto social en tiempo real, para comunicar y gestionar el valor generado.

#### Acceptance Criteria

1. EL Tablero_de_Impacto DEBERÁ exponer métricas agregadas de personas alcanzadas, Microcápsulas completadas, Microseguros activados y cobertura contratada, desagregadas por región y por tipo de perfil.
2. EL Tablero_de_Impacto DEBERÁ relacionar cada métrica de impacto con el ODS pertinente entre el ODS 10 (reducción de las desigualdades), el ODS 13 (acción por el clima) y el ODS 8 (trabajo decente y crecimiento económico).
3. EL Tablero_de_Impacto DEBERÁ calcular sus métricas únicamente sobre datos agregados y anonimizados, sin exponer PII de Usuarios individuales.
4. SI una región contiene menos de 5 Usuarios con eventos registrados, ENTONCES EL Tablero_de_Impacto DEBERÁ suprimir los datos agregados de esa región para prevenir la reidentificación de Usuarios individuales.
5. CUANDO un usuario solicita acceder al Tablero_de_Impacto, EL CIMA DEBERÁ verificar en el backend que el usuario posee un rol administrativo autorizado antes de entregar los datos.
6. SI el usuario que solicita el Tablero_de_Impacto no posee un rol administrativo autorizado, ENTONCES EL CIMA DEBERÁ rechazar la solicitud con un error de autorización y registrar el intento sin exponer PII.
7. CUANDO se consultan métricas del Tablero_de_Impacto, EL CIMA DEBERÁ servirlas desde una vista agregada precalculada para no impactar el rendimiento de los servicios operativos.

### Requirement 16: IA responsable y gobernada

**User Story:** Como responsable de riesgo y como Usuario vulnerable, quiero que el uso de la IA sea seguro, transparente y supervisado, para confiar en las recomendaciones.

#### Acceptance Criteria

1. CUANDO el Usuario envía una entrada al Agente_Conversacional, EL CIMA DEBERÁ aplicar guardrails que bloqueen el contenido inseguro, fuera del dominio de la plataforma o que induzca a decisiones financieras indebidas, antes de generar una respuesta.
2. CUANDO el Agente_Conversacional va a ofrecer un Microseguro o un incentivo al Usuario, EL CIMA DEBERÁ validar la salida contra las reglas de negocio antes de presentarla al Usuario.
3. SI la confianza de la respuesta del Agente_Conversacional es inferior al umbral configurado o se detecta un tema sensible, ENTONCES EL CIMA DEBERÁ derivar la interacción a un canal humano o a una respuesta segura de respaldo.
4. CUANDO el Agente_Conversacional procesa una entrada o genera una salida, EL CIMA DEBERÁ registrar de forma auditable la entrada redactada, la salida, la versión del modelo utilizada y la decisión del guardrail aplicada, excluyendo cualquier PII del contenido registrado.
5. CUANDO el Usuario interactúa con el Agente_Conversacional, EL CIMA DEBERÁ indicar de forma reconocible al Usuario que está interactuando con un asistente de inteligencia artificial.
6. DONDE se declara un incidente operativo con el Agente_Conversacional, EL CIMA DEBERÁ permitir desactivar o degradar el Agente_Conversacional de forma controlada, presentando al Usuario una respuesta de respaldo segura.

### Requirement 17: Aprendizaje adaptativo

**User Story:** Como Usuario con mi propio ritmo de aprendizaje, quiero que las lecciones se ajusten a cómo voy avanzando, para no frustrarme ni aburrirme.

#### Acceptance Criteria

1. CUANDO el Usuario repite una Microcápsula, excede el tiempo esperado para completarla o falla una comprobación de comprensión, EL CIMA DEBERÁ ajustar el ritmo y simplificar el contenido de la Microcápsula siguiente.
2. EL CIMA DEBERÁ fundamentar la adaptación del contenido únicamente en las señales de progreso ya capturadas del Usuario, sin solicitar datos adicionales al Usuario.
3. EL CIMA DEBERÁ ejecutar la lógica de adaptación del aprendizaje en el backend y nunca en el cliente.
4. EL CIMA DEBERÁ permitir evolucionar la personalización hacia recuperación por similitud mediante PgVector sin modificar el contrato de la API expuesta al frontend.
5. SI no existen señales de progreso suficientes del Usuario para adaptar el contenido, ENTONCES EL CIMA DEBERÁ entregar la Ruta_de_Aprendizaje estándar correspondiente al Perfil_de_Usuario como comportamiento por defecto.

### Requirement 18: Resiliencia offline como pilar de inclusión

**User Story:** Como Usuario en zona rural con señal intermitente, quiero seguir aprendiendo y conversando aunque me quede sin internet, para que la falta de conectividad no me excluya.

#### Acceptance Criteria

1. MIENTRAS no hay conexión de red disponible, EL CIMA DEBERÁ permitir al Usuario consultar las Microcápsulas ya descargadas y la última conversación registrada en el dispositivo.
2. CUANDO el Usuario completa una Microcápsula o responde una evaluación sin conexión de red, EL CIMA DEBERÁ encolar localmente esas acciones y sincronizarlas de forma idempotente al restablecerse la conexión, sin generar registros duplicados.
3. DONDE existe conexión de red disponible, EL CIMA DEBERÁ precargar la siguiente Microcápsula de la Ruta_de_Aprendizaje del Usuario.
4. CUANDO se restablece la conexión de red tras una interrupción, EL CIMA DEBERÁ resolver los conflictos de sincronización conservando el progreso del Usuario sin pérdida de pasos ya completados.
5. EL CIMA DEBERÁ presentar al Usuario el estado de conexión y el estado de sincronización en lenguaje simple.

### Requirement 19: Gamificación e insignias

**User Story:** Como Usuario, quiero recibir reconocimientos inmediatos a medida que aprendo (insignias y puntos), para sentirme motivado a continuar en la Escuela.

#### Acceptance Criteria

1. CUANDO el Usuario completa una Microcápsula o una Ruta_de_Aprendizaje, EL CIMA DEBERÁ otorgar un reconocimiento (Insignia o puntos) asociado a ese logro y presentarlo de forma visible al Usuario en un tiempo máximo de 5 segundos.
2. CUANDO EL CIMA otorga una Insignia o puntos, EL CIMA DEBERÁ registrar la Insignia y los puntos obtenidos asociados al Perfil_de_Usuario.
3. CUANDO EL CIMA evalúa el otorgamiento de una Insignia o de puntos, EL CIMA DEBERÁ ejecutar las reglas de otorgamiento en el backend y no depender de lógica ejecutada en el cliente.
4. SI un reconocimiento está vinculado a un beneficio sobre un Microseguro, ENTONCES EL CIMA DEBERÁ validar la elegibilidad del beneficio en el backend antes de aplicarlo y, si la elegibilidad no se cumple, no aplicar el beneficio.
5. SI el Usuario ya posee una Insignia específica, ENTONCES EL CIMA DEBERÁ no otorgar un duplicado de esa Insignia y conservar el registro existente asociado al Perfil_de_Usuario, de forma idempotente.
6. SI el otorgamiento o el registro de un reconocimiento falla, ENTONCES EL CIMA DEBERÁ reintentar la operación hasta 3 veces y, de persistir el fallo, conservar el evento de reconocimiento para otorgamiento posterior sin pérdida de datos.
7. CUANDO el Usuario autenticado consulta sus reconocimientos, EL CIMA DEBERÁ presentar las Insignias y el total de puntos asociados a su Perfil_de_Usuario, verificando la titularidad del Perfil_de_Usuario en el backend antes de entregar la información.
8. SI el Usuario que consulta reconocimientos no es el titular del Perfil_de_Usuario solicitado, ENTONCES EL CIMA DEBERÁ rechazar la solicitud con un error de autorización, no revelar las Insignias ni los puntos de otro Perfil_de_Usuario y registrar el intento sin exponer PII.

### Requirement 20: Encuesta de satisfacción

**User Story:** Como Seguros Bolívar, quiero conocer la satisfacción del Usuario con la Escuela, para mejorar la experiencia formativa y de servicio.

#### Acceptance Criteria

1. CUANDO el Usuario completa una Ruta_de_Aprendizaje o un hito definido, EL CIMA DEBERÁ presentar al Usuario una Encuesta_de_Satisfaccion breve y opcional en español coloquial colombiano, con al menos una calificación en una escala definida de 1 a 5.
2. EL CIMA DEBERÁ permitir al Usuario responder la Encuesta_de_Satisfaccion por texto o por voz, de forma coherente con la experiencia voz-first, y omitirla sin bloquear el acceso al resto de la plataforma.
3. CUANDO el Usuario envía una respuesta de la Encuesta_de_Satisfaccion, EL CIMA DEBERÁ validar en el servidor el tipo, formato y rango de cada respuesta, incluyendo que la calificación esté dentro de la escala permitida de 1 a 5, antes de registrarla.
4. SI una respuesta de la Encuesta_de_Satisfaccion no cumple la validación de tipo, formato o rango, ENTONCES EL CIMA DEBERÁ rechazarla indicando el campo inválido y no registrar la Encuesta_de_Satisfaccion.
5. CUANDO el Usuario envía una respuesta válida de la Encuesta_de_Satisfaccion, EL Modulo_de_Metricas DEBERÁ registrar la respuesta asociada al Perfil_de_Usuario y a la zona geográfica, excluyendo cualquier PII del contenido registrado, en un tiempo máximo de 5 segundos.
6. SI el registro de la respuesta de la Encuesta_de_Satisfaccion falla, ENTONCES EL Modulo_de_Metricas DEBERÁ reintentar el registro hasta 3 veces y, de persistir el fallo, conservar la respuesta para registro posterior sin pérdida de datos.
7. SI el Usuario ya respondió u omitió explícitamente la Encuesta_de_Satisfaccion de una Ruta_de_Aprendizaje, ENTONCES EL CIMA DEBERÁ no presentar nuevamente la misma Encuesta_de_Satisfaccion para esa Ruta_de_Aprendizaje, de forma idempotente.
8. CUANDO se solicita un reporte de satisfacción, EL Modulo_de_Metricas DEBERÁ entregar los resultados agregados por zona geográfica sin exponer PII individual, suprimiendo las zonas con menos de 5 Usuarios con respuestas registradas, de forma consistente con el reporte de métricas existente.
9. MIENTRAS una respuesta de la Encuesta_de_Satisfaccion asociada a datos sensibles tiene una antigüedad igual o superior a 90 días, EL Modulo_de_Metricas DEBERÁ eliminar o anonimizar ese dato sensible conservando únicamente los agregados no identificables.
