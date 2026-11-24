"""Arma la configuración de la distribución de CloudFront de CIMA (hackatón).

La usa crear-infra.sh. Lee los identificadores de variables de entorno y escribe
el JSON en la salida estándar. No lleva secretos.

- Por defecto: la PWA desde S3 (carpeta app/, con OAC), caché optimizada,
  cabeceras de seguridad y la función que manda las rutas de la app a index.html.
- /api/*: el backend en EC2, sin caché y con todas las cabeceras, cookies y
  parámetros del visitante (la sesión va en cookies HttpOnly).
"""

import json
import os
import time

e = os.environ
s3 = f"{e['BUCKET']}.s3.{e['AWS_DEFAULT_REGION']}.amazonaws.com"
solo_lectura = {"Quantity": 2, "Items": ["GET", "HEAD"]}

config = {
    "CallerReference": f"cima-hackaton-{int(time.time())}",
    "Comment": "CIMA hackaton",
    "Enabled": True,
    "DefaultRootObject": "index.html",
    "PriceClass": "PriceClass_100",
    "HttpVersion": "http2and3",
    "Origins": {
        "Quantity": 2,
        "Items": [
            {
                "Id": "s3-app",
                "DomainName": s3,
                "OriginPath": "/app",
                "OriginAccessControlId": e["OAC"],
                "S3OriginConfig": {"OriginAccessIdentity": ""},
            },
            {
                "Id": "ec2-api",
                "DomainName": e["ORIGEN"],
                "CustomOriginConfig": {
                    "HTTPPort": 80,
                    "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only",
                    "OriginReadTimeout": 60,
                    "OriginKeepaliveTimeout": 5,
                },
            },
        ],
    },
    "DefaultCacheBehavior": {
        "TargetOriginId": "s3-app",
        "ViewerProtocolPolicy": "redirect-to-https",
        "Compress": True,
        "CachePolicyId": e["CACHE_OPT"],
        "ResponseHeadersPolicyId": e["CABECERAS"],
        "AllowedMethods": {**solo_lectura, "CachedMethods": solo_lectura},
        "FunctionAssociations": {
            "Quantity": 1,
            "Items": [{"FunctionARN": e["FUNCION_ARN"], "EventType": "viewer-request"}],
        },
    },
    "CacheBehaviors": {
        "Quantity": 1,
        "Items": [
            {
                "PathPattern": "/api/*",
                "TargetOriginId": "ec2-api",
                "ViewerProtocolPolicy": "https-only",
                "Compress": True,
                "CachePolicyId": e["CACHE_NO"],
                "OriginRequestPolicyId": e["TODO_VISOR"],
                "AllowedMethods": {
                    "Quantity": 7,
                    "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                    "CachedMethods": solo_lectura,
                },
            }
        ],
    },
}

print(json.dumps(config))
