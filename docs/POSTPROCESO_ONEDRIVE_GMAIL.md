# Postproceso integrado: OneDrive e IMAP

## Objetivo

La causacion y el archivado documental ahora viven en un solo workflow:

```text
n8n/Causacion Fact Prov.json
```

Ya no es necesario publicar un segundo workflow con webhook para el postproceso.

## Flujo integrado

```text
Email Trigger (IMAP)
  -> procesar factura
  -> causar factura
  -> notificar resultado
  -> preparar postproceso integrado
  -> consultar detalle de factura
  -> crear carpetas OneDrive
  -> subir PDF a OneDrive
  -> mover correo por IMAP
```

La ruta de OneDrive queda:

```text
2. Contabilidad/Facturas Recibidas/AÑO/MM.Mes-AÑO/Proveedor/NumeroFactura.pdf
```

Ejemplo:

```text
2. Contabilidad/Facturas Recibidas/2026/07.Jul-2026/Latinoamerica Hosting S.A.S/FE71203.pdf
```

## Nodos agregados al workflow principal

```text
Preparar postproceso integrado
Obtener detalle factura
Construir ruta OneDrive
Crear carpeta raiz OneDrive
Crear carpeta Facturas Recibidas
Crear carpeta año
Crear carpeta mes
Crear carpeta proveedor
Descargar PDF factura
Subir PDF a OneDrive
Archivar correo por IMAP
Preparar resultado postproceso
Postproceso completado
```

## Endpoints backend usados

```text
GET /facturas/{factura_id}/detalle
GET /facturas/{factura_id}/pdf
POST /correo/archivar-imap
```

## OneDrive API

En n8n, seleccionar la credencial Microsoft Graph OAuth2 en estos nodos:

```text
Crear carpeta raiz OneDrive
Crear carpeta Facturas Recibidas
Crear carpeta año
Crear carpeta mes
Crear carpeta proveedor
Subir PDF a OneDrive
```

Permisos sugeridos:

```text
Files.ReadWrite
offline_access
```

## IMAP

Ya no se requiere `Gmail OAuth2` ni `gmail.modify`.

El backend mueve el correo por IMAP usando `email_uid` enviado por n8n. Si no hay UID, intenta ubicar el mensaje por `Message-ID`.

Configurar estas variables en `.env` del backend:

```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURE=true
IMAP_USER=tu_correo@gmail.com
IMAP_PASSWORD=tu_app_password
IMAP_SOURCE_MAILBOX=INBOX
IMAP_ARCHIVE_MAILBOX=Facturas Procesadas
```

Para Gmail, `IMAP_PASSWORD` debe ser una contraseña de aplicacion, no la contraseña normal de la cuenta.

## Importacion en n8n

Importar solo:

```text
n8n/Causacion Fact Prov.json
```

Despues de importar:

1. Seleccionar credencial IMAP en `Email Trigger (IMAP)`.
2. Seleccionar credencial SMTP en nodos de notificacion.
3. Seleccionar credencial Microsoft Graph OAuth2 en nodos OneDrive.
4. Publicar el workflow.
5. Probar reenviando una factura real.
