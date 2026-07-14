# Despliegue en Hostinger VPS

## Objetivo

Publicar la solucion en un VPS usando Docker Compose:

```text
Caddy        -> HTTPS publico
n8n          -> UI y ejecucion del workflow
facturas-api -> Backend FastAPI interno
SQLite       -> Base persistida en volumen Docker
```

El dominio recomendado para n8n es:

```text
https://causacionfacturas.biasolutions.co
```

Por seguridad, el backend no debe quedar publico de forma permanente. Solo se expone temporalmente cuando sea necesario cargar historicos o revisar Swagger.

## 1. Preparar el VPS

Conectarse por SSH:

```bash
ssh root@IP_DEL_VPS
```

Actualizar paquetes:

```bash
apt update
apt upgrade -y
```

Instalar Docker y Docker Compose si no existen:

```bash
curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

Crear carpeta del proyecto:

```bash
mkdir -p /opt/facturasia
cd /opt/facturasia
```

Subir el repo a esa carpeta usando `git clone`, `scp`, `rsync` o el metodo que se prefiera.

## 2. Configurar DNS

En Hostinger o en el proveedor DNS, crear un registro `A`:

```text
Nombre: causacionfacturas
Tipo: A
Valor: IP_DEL_VPS
TTL: automatico
```

Validar desde el VPS o desde local:

```bash
ping causacionfacturas.biasolutions.co
```

Debe resolver a la IP del VPS.

## 3. Crear variables de entorno

Crear el archivo general de produccion:

```bash
cp .env.production.example .env.production
nano .env.production
```

Contenido esperado:

```env
N8N_DOMAIN=causacionfacturas.biasolutions.co
```

Importante: no debe quedar duplicado como `N8N_DOMAIN=N8N_DOMAIN=...`.

Crear variables del backend:

```bash
cp python-api/.env.production.example python-api/.env.production
nano python-api/.env.production
```

Configurar valores reales:

```env
BASE_PATH=/data/facturasia

SIIGO_ENABLED=true
SIIGO_BASE_URL=https://api.siigo.com
SIIGO_USERNAME=
SIIGO_ACCESS_KEY=
SIIGO_PARTNER_ID=CausacionFactProv

SIIGO_DOCUMENT_ID_COMPRA=
SIIGO_PAYMENT_ID_COMPRA=
SIIGO_TAX_ID_IVA_19=
SIIGO_DIAS_VENCIMIENTO_COMPRA=30

IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURE=true
IMAP_USER=
IMAP_PASSWORD=
IMAP_SOURCE_MAILBOX=INBOX
IMAP_ARCHIVE_MAILBOX=Facturas Procesadas

NITS_CLIENTE_PERMITIDOS=
```

No subir `.env.production` ni `python-api/.env.production` al repo.

## 4. Levantar contenedores

Desde `/opt/facturasia`:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Ver estado:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Validar que n8n ve el backend:

```bash
docker exec facturas-n8n wget -qO- http://facturas-api:8000/health
```

Respuesta esperada:

```json
{"status":"ok","message":"API de Facturas IA funcionando correctamente"}
```

Abrir n8n:

```text
https://causacionfacturas.biasolutions.co
```

## 5. Configurar IMAP y SMTP

La solucion usa correo en dos partes:

```text
n8n IMAP  -> detecta facturas nuevas en el correo
n8n SMTP  -> envia notificaciones y correos de revision
Backend IMAP -> mueve el correo a Facturas Procesadas al finalizar
```

### 5.1 Preparar Gmail

En la cuenta de Gmail que recibira las facturas:

1. Activar verificacion en dos pasos.
2. Crear una contrasena de aplicacion.
3. Activar IMAP en Gmail.

Ruta usual en Gmail:

```text
Configuracion > Ver toda la configuracion > Reenvio y correo POP/IMAP > Acceso IMAP > Habilitar IMAP
```

La contrasena que se usa en n8n y en el backend debe ser la contrasena de aplicacion, no la contrasena normal de Gmail.

### 5.2 Configurar IMAP en el backend

En:

```bash
nano python-api/.env.production
```

Configurar:

```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SECURE=true
IMAP_USER=correo@gmail.com
IMAP_PASSWORD=contrasena_de_aplicacion
IMAP_SOURCE_MAILBOX=INBOX
IMAP_ARCHIVE_MAILBOX=Facturas Procesadas
```

Este IMAP del backend se usa para archivar el correo despues de causar y subir el PDF a OneDrive.

Despues de cambiar este archivo, reiniciar el backend:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart facturas-api
```

### 5.3 Configurar credencial IMAP en n8n

En n8n:

```text
Credentials > New credential > IMAP
```

Valores:

```text
Host: imap.gmail.com
Port: 993
Secure: true / SSL
User: correo@gmail.com
Password: contrasena_de_aplicacion
Mailbox: INBOX
```

Asignar esta credencial al nodo:

```text
Email Trigger (IMAP)
```

El workflow importado espera una credencial llamada parecido a:

```text
IMAP account
```

El nombre no es obligatorio, pero ayuda a identificarla.

### 5.4 Configurar credencial SMTP en n8n

En n8n:

```text
Credentials > New credential > SMTP
```

Opcion recomendada con SSL:

```text
Host: smtp.gmail.com
Port: 465
Secure: true / SSL
User: correo@gmail.com
Password: contrasena_de_aplicacion
```

Alternativa con STARTTLS:

```text
Host: smtp.gmail.com
Port: 587
Secure: false
STARTTLS: true
User: correo@gmail.com
Password: contrasena_de_aplicacion
```

Asignar esta credencial a todos los nodos `Send Email`.

El workflow importado espera una credencial llamada parecido a:

```text
SMTP account
```

### 5.5 Revisar remitente y destinatario

En el nodo:

```text
Variables
```

Validar:

```text
correo_destino   -> correo que recibe alertas o solicitudes de revision
correo_remitente -> correo usado como remitente en los nodos Send Email
```

Recomendacion:

```text
correo_remitente = mismo correo configurado en SMTP
```

Si se usa otro remitente, Gmail puede rechazar el envio o reemplazarlo por la cuenta autenticada.

### 5.6 Prueba rapida de correo

En n8n, abrir un nodo `Send Email` y ejecutar solo ese nodo con datos de prueba.

Validar:

```text
1. El correo sale correctamente.
2. El destinatario lo recibe.
3. No cae en spam.
4. El remitente se ve como se espera.
```

Luego probar el nodo `Email Trigger (IMAP)` reenviando una factura al correo monitoreado.

## 6. Configurar OAuth de Microsoft Graph

En Azure Portal, el redirect URI de produccion debe ser:

```text
https://causacionfacturas.biasolutions.co/rest/oauth2-credential/callback
```

En n8n, crear credencial OAuth2 generica para Microsoft Graph:

```text
Grant Type: Authorization Code
Authorization URL: https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize
Access Token URL: https://login.microsoftonline.com/consumers/oauth2/v2.0/token
Scope: offline_access Files.ReadWrite User.Read
Auth URI Query Parameters: prompt=select_account
Authentication: Body
```

Para cuenta empresarial se puede cambiar `consumers` por el tenant correspondiente si aplica.

## 7. Importar workflow de n8n

Importar en n8n:

```text
n8n/Causacion Fact Prov Docker.json
```

Este JSON usa la URL interna de Docker:

```text
http://facturas-api:8000
```

Configurar credenciales:

```text
IMAP
SMTP
Microsoft Graph OAuth2
```

Revisar el nodo `Variables`:

```text
correo_destino
correo_remitente
```

Publicar o activar el workflow.

## 8. Exponer temporalmente Swagger del backend

Por defecto, Caddy envia el dominio a n8n. Por eso `/docs` muestra un 404 de n8n.

Para abrir Swagger temporalmente, editar:

```bash
nano deploy/Caddyfile
```

Usar esta configuracion:

```caddy
{$N8N_DOMAIN} {
	@backend path /docs /redoc /openapi.json /health /historico/* /facturas/* /siigo/* /correo/* /clasificaciones/*
	reverse_proxy @backend facturas-api:8000

	reverse_proxy n8n:5678
}
```

Reiniciar Caddy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart caddy
```

Probar:

```bash
curl https://causacionfacturas.biasolutions.co/health
```

Abrir Swagger:

```text
https://causacionfacturas.biasolutions.co/docs
```

Cuando termine la carga o validacion, cerrar el acceso al backend dejando nuevamente:

```caddy
{$N8N_DOMAIN} {
	reverse_proxy n8n:5678
}
```

Reiniciar Caddy otra vez:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart caddy
```

## 9. Cargar historico desde Swagger

Con Swagger temporalmente abierto:

```text
https://causacionfacturas.biasolutions.co/docs
```

Buscar:

```text
POST /historico/cargar-archivo
```

Parametros:

```text
file: Excel .xlsx o .xlsm
reemplazar: false
```

Usar `reemplazar=false` para adicionar registros.

Usar `reemplazar=true` solo si se quiere borrar y reconstruir:

```text
contabilizaciones_historicas
mapeo_erp
reglas_concepto_servicio
```

Respuesta esperada:

```json
{
  "ok": true,
  "hojas_procesadas": {
    "Historico_Contable": true,
    "Mapeo_ERP": true,
    "Reglas": false
  },
  "filas_insertadas": {
    "contabilizaciones_historicas": 1390,
    "mapeo_erp": 133,
    "reglas_concepto_servicio": 0
  }
}
```

## 10. Validar que el historico quedo en el VPS

La base de datos del VPS vive dentro del volumen Docker en:

```text
/data/facturasia/facturas_ai.db
```

Validar conteos:

```bash
docker exec facturas-api python -c "import sqlite3; c=sqlite3.connect('/data/facturasia/facturas_ai.db'); print(c.execute('select count(*) from contabilizaciones_historicas').fetchone()[0])"
docker exec facturas-api python -c "import sqlite3; c=sqlite3.connect('/data/facturasia/facturas_ai.db'); print(c.execute('select count(*) from mapeo_erp').fetchone()[0])"
docker exec facturas-api python -c "import sqlite3; c=sqlite3.connect('/data/facturasia/facturas_ai.db'); print(c.execute('select count(*) from reglas_concepto_servicio').fetchone()[0])"
```

Consultar conceptos disponibles:

```text
https://causacionfacturas.biasolutions.co/clasificaciones/conceptos
```

Solo hacerlo mientras el backend este expuesto temporalmente.

## 11. Como construir el Excel historico

El archivo debe ser `.xlsx` o `.xlsm`.

Puede tener una, dos o tres hojas:

```text
Historico_Contable
Mapeo_ERP
Reglas
```

### Hoja Historico_Contable

Usada para aprender contabilizaciones anteriores por proveedor.

Columnas recomendadas:

```text
proveedor_nit
proveedor_nombre
descripcion
cuenta_contable
nombre_cuenta
centro_costo
debito
credito
cuenta_iva
cuenta_retencion
fuente
fecha_documento
```

Minimo requerido:

```text
proveedor_nit
cuenta_contable
```

Ejemplo:

```text
proveedor_nit | proveedor_nombre              | descripcion | cuenta_contable | nombre_cuenta       | centro_costo | debito | credito | fuente
901152321     | Latinoamerica Hosting S.A.S   | Hosting     | 61553001        | Servicios TI        | ADMIN        | 1620000| 0       | SIIGO
```

### Hoja Mapeo_ERP

Usada para saber que item/cuenta enviar a SIIGO segun proveedor y concepto.

Columnas recomendadas:

```text
erp
proveedor_nit
proveedor_nombre
concepto_servicio
cuenta_contable
nombre_cuenta
item_type_erp
item_code_erp
item_description_erp
document_id_erp
payment_id_erp
tax_id_erp
activo
observacion
```

Minimo recomendado:

```text
proveedor_nit
concepto_servicio
cuenta_contable
item_type_erp
item_code_erp
item_description_erp
activo
```

Ejemplo:

```text
erp   | proveedor_nit | concepto_servicio    | cuenta_contable | nombre_cuenta      | item_type_erp | item_code_erp | item_description_erp | activo
SIIGO | 901152321     | TELECOMUNICACIONES   | 61553001        | Servicios TI       | Account       | 61553001      | Servicios TI         | 1
SIIGO | 901152321     | SERVICIOS_PUBLICOS   | 51353501        | Servicios publicos | Account       | 51353501      | Servicios publicos   | 1
```

### Hoja Reglas

Usada para clasificar conceptos por palabras clave.

Columnas recomendadas:

```text
erp
proveedor_nit
concepto_servicio
palabras_clave
cuenta_contable
nombre_cuenta
item_type_erp
item_code_erp
tax_id_erp
prioridad
activo
```

Minimo requerido:

```text
proveedor_nit
concepto_servicio
palabras_clave
```

Ejemplo:

```text
erp   | proveedor_nit | concepto_servicio  | palabras_clave              | cuenta_contable | item_type_erp | item_code_erp | prioridad | activo
SIIGO | 830054090     | TELECOMUNICACIONES | internet, telefonia, tv     | 61553001        | Account       | 61553001      | 10        | 1
SIIGO | 830054090     | SERVICIOS_PUBLICOS | acueducto, aseo, energia    | 51353501        | Account       | 51353501      | 10        | 1
```

## 12. Prueba real en produccion

1. Enviar o reenviar una factura al correo monitoreado por IMAP.
2. Revisar ejecuciones en n8n.
3. Confirmar que el backend procesa la factura.
4. Confirmar que se crea causacion.
5. Confirmar que SIIGO recibe la compra si `SIIGO_ENABLED=true`.
6. Confirmar que el PDF se guarda en OneDrive.
7. Confirmar que el correo queda movido a `Facturas Procesadas`.

## 13. Backups

La informacion importante vive en volumenes Docker:

```text
n8n_data
facturas_data
caddy_data
caddy_config
```

Backup recomendado:

```bash
mkdir -p /opt/backups/facturasia
docker run --rm -v facturasia_facturas_data:/data -v /opt/backups/facturasia:/backup alpine tar czf /backup/facturas_data.tar.gz -C /data .
docker run --rm -v facturasia_n8n_data:/data -v /opt/backups/facturasia:/backup alpine tar czf /backup/n8n_data.tar.gz -C /data .
```

Validar el nombre real de los volumenes con:

```bash
docker volume ls
```

## 14. Notas de seguridad

- No subir archivos `.env` reales al repo.
- No dejar Swagger abierto permanentemente.
- Rotar credenciales si fueron pegadas en chats, capturas o archivos compartidos.
- Mantener `SIIGO_ENABLED=false` mientras se hacen pruebas de infraestructura.
- Activar `SIIGO_ENABLED=true` solo cuando n8n, backend, historico, OneDrive e IMAP ya esten validados.
