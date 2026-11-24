// CloudFront Function (cloudfront-js-2.0) para la PWA de CIMA.
//
// Se asocia SOLO al comportamiento por defecto (S3), nunca a /api/*.
// Las rutas de la app sin extensión (/mi-ruta, /aprendizaje/leccion/...) se
// sirven con index.html para que Angular resuelva la ruta. Los archivos con
// extensión (.js, .css, .mp4, ngsw.json...) pasan sin cambios.
function handler(event) {
  var request = event.request;
  var ultimo = request.uri.split('/').pop();
  if (ultimo.indexOf('.') === -1) {
    request.uri = '/index.html';
  }
  return request;
}
