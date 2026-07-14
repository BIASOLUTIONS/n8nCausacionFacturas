# Prueba local con Docker

## Objetivo

Probar la solucion completa en contenedores antes de llevarla al VPS de Hostinger.

Servicios:

```text
facturas-api  -> FastAPI en http://localhost:8000
n8n           -> n8n en http://localhost:5678
```

Dentro de Docker, n8n llama al backend usando:

```text
http://facturas-api:8000
```

Por eso para esta prueba se debe importar:

```text
n8n/Causacion Fact Prov Docker.json
```

## 1. Crear variables locales Docker

Copiar la plantilla:

```powershell
Copy-Item .\python-api\.env.docker.example .\python-api\.env.docker.local
```

Editar:

```powershell
notepad .\python-api\.env.docker.local
```

Configurar valores reales:

```env
BASE_PATH=/data/facturasia

SIIGO_ENABLED=false
SIIGO_BASE_URL=https://api.siigo.com
SIIGO_USERNAME=
SIIGO_ACCESS_KEY=
SIIGO_PARTNER_ID=CausacionFactProv

SIIGO_DOCUMENT_ID_COMPRA=
SIIGO_PAYMENT_ID_COMPRA=
SIIGO_TAX_ID_IVA_19=

IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURE=true
IMAP_USER=
IMAP_PASSWORD=
IMAP_SOURCE_MAILBOX=INBOX
IMAP_ARCHIVE_MAILBOX=Facturas Procesadas

NITS_CLIENTE_PERMITIDOS=
```

Para pruebas sin enviar a SIIGO, dejar:

```env
SIIGO_ENABLED=false
```

## 2. Levantar contenedores

```powershell
docker compose -f .\docker-compose.local.yml up -d --build
```

Ver logs:

```powershell
docker compose -f .\docker-compose.local.yml logs -f
```

## 3. Validar backend

Abrir:

```text
http://localhost:8000/health
```

Swagger:

```text
http://localhost:8000/docs
```

Validar conceptos:

```text
http://localhost:8000/clasificaciones/conceptos
```

## 4. Entrar a n8n

Abrir:

```text
http://localhost:5678
```

Importar:

```text
n8n/Causacion Fact Prov Docker.json
```

Configurar credenciales:

```text
IMAP
SMTP
Microsoft Graph OAuth2
```

Publicar el workflow.

## 5. Probar flujo real

1. Enviar o reenviar una factura al correo IMAP.
2. Ver ejecuciones en n8n.
3. Confirmar que el backend procesa la factura.
4. Confirmar que el PDF sube a OneDrive.
5. Confirmar que el correo se mueve a `Facturas Procesadas`.

## 6. Apagar

```powershell
docker compose -f .\docker-compose.local.yml down
```

Apagar y borrar datos locales Docker:

```powershell
docker compose -f .\docker-compose.local.yml down -v
```

Usar `down -v` solo si se quiere borrar la base SQLite y datos persistidos de la prueba.

## Notas

Si n8n no conecta con el backend, revisar que el workflow importado sea el Docker:

```text
Causacion Fact Prov Docker
```

Los nodos HTTP deben apuntar a:

```text
http://facturas-api:8000
```

No deben apuntar a:

```text
http://127.0.0.1:8000
```
