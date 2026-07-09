# FacturasIA – Bitácora de Implementación y Contexto para Codex

## 1. Objetivo del proyecto

Construir una solución para recepción, lectura, causación y posterior integración de facturas electrónicas de proveedores.

La solución actual procesa facturas electrónicas recibidas por correo, normalmente en archivo `.zip` con XML/PDF DIAN, extrae los datos principales del XML, guarda la información en una base local, propone/realiza causación contable y aprende de respuestas manuales enviadas por correo.

El objetivo final es que la solución pueda integrarse con SIIGO y posteriormente con otros ERP, usando históricos contables exportados desde cada ERP.

---

## 2. Arquitectura actual

### Componentes

- **n8n**
  - Orquesta el flujo de correos.
  - Lee correos por IMAP.
  - Detecta si el correo contiene una factura o si es una respuesta manual.
  - Envía adjuntos a Python.
  - Envía correos de notificación.
  - Llama endpoints de Python vía HTTP.

- **Python + FastAPI**
  - Procesa ZIP/XML.
  - Extrae información de factura electrónica DIAN.
  - Guarda datos en SQLite.
  - Genera causación automática en modo simulación.
  - Procesa respuestas manuales.
  - Guarda histórico contable.
  - Prepara payload para SIIGO.
  - Envía compra a SIIGO cuando se habilita.

- **SQLite**
  - Base local:
    - `facturas_ai.db`

- **SIIGO API**
  - Ya se validó autenticación.
  - Ya se consultaron catálogos.
  - Ya se preparó payload de compra.
  - El envío real falló porque SIIGO no permitió usar la cuenta contable `513535` como `Account`, lo que llevó a definir la necesidad de mapeo ERP por producto/servicio.

---

## 3. Estructura recomendada del proyecto

```text
n8nCausacionFacturas/
  adjuntos/
  errores/
  excel/
  logs/
  n8n/
    Causacion Fact Prov.json
  procesadas/
  python-api/
    main.py
    siigo_client.py
    .env
    .env.example
    requirements.txt
  docs/
    FACTURAS_IA_IMPLEMENTACION.md
    Plantilla_Historico_ERP_FacturasIA.xlsx
    Historico_ERP_FacturasIA_Normalizado.xlsx
  facturas_ai.db
```

Este archivo debe guardarse en:

```text
docs/FACTURAS_IA_IMPLEMENTACION.md
```

---

## 4. Flujo actual en n8n

Workflow actual:

```text
Email Trigger (IMAP)
  ↓
Variables
  ↓
Clasificar correo
  ↓
¿Es respuesta revisión?
   ├── true
   │     ↓
   │   Procesar respuesta revisión
   │     ↓
   │   ¿Respuesta procesada?
   │     ├── true  → Notificar respuesta procesada
   │     └── false → Notificar error respuesta
   │
   └── false
         ↓
      Detectar Adjuntos Factura
         ↓
      ¿Es procesable?
         ↓
      Procesar factura en Python
         ↓
      ¿Factura duplicada?
         ├── true  → Notificar factura duplicada
         └── false
               ↓
            Consultar histórico proveedor
               ↓
            Causar factura automáticamente
               ↓
            ¿Causación exitosa?
               ├── true  → Notificar causación automática
               └── false → Notificar revisión manual
```

### Nodos importantes

#### Email Trigger (IMAP)

Configuración usada:

```text
Mailbox Name: INBOX
Action: Mark as Read
Format: Resolved
Property Prefix Name: attachment_
```

Se confirmó que los adjuntos llegan en `binary` como:

```text
attachment_0
```

#### Variables

Debe tener activado:

```text
Include Other Input Fields: ON
```

Esto es importante para no borrar `subject`, `text`, `html`, `from` ni los binarios.

#### Clasificar correo

Debe conservar el JSON original y el binario.

Lógica:

- Si el cuerpo contiene `#CAUSAR_FACTURA`, clasifica como:
  - `RESPUESTA_REVISION`
- Si no, clasifica como:
  - `FACTURA`

#### Detectar Adjuntos Factura

Busca binarios `.zip`, `.xml` o `.pdf`.

El binario seleccionado se normaliza como:

```text
factura_file
```

#### Procesar factura en Python

Endpoint:

```text
POST http://127.0.0.1:8000/facturas/procesar-adjunto
```

Body:

```text
Form-Data
Name: file
Input Data Field Name: factura_file
```

#### Causar factura automáticamente

Endpoint:

```text
POST http://127.0.0.1:8000/causacion/causar/{{ $('Procesar factura en Python').item.json.factura_id }}
```

#### Procesar respuesta revisión

Endpoint:

```text
POST http://127.0.0.1:8000/revision/procesar-respuesta
```

Body JSON:

```json
{
  "subject": "{{ $json.subject }}",
  "from": "{{ ($json.from && $json.from.text) ? $json.from.text : ($json.from || '') }}",
  "body": "{{ $json.body_text }}"
}
```

Debe tener:

```text
Never Error: ON
Response Format: JSON
```

---

## 5. Funcionalidades implementadas en Python

### Endpoints principales

```text
GET  /health
GET  /facturas/listar
GET  /proveedores/listar
GET  /historico/proveedor/{nit}
POST /facturas/procesar-adjunto
GET  /causacion/proponer/{factura_id}
POST /causacion/causar/{factura_id}
GET  /causaciones/listar
POST /revision/procesar-respuesta
```

### Endpoints SIIGO implementados

```text
GET  /siigo/config
GET  /siigo/auth-test
GET  /siigo/catalogos
GET  /siigo/documentos-compra
GET  /siigo/medios-pago
GET  /siigo/impuestos
GET  /siigo/centros-costo
GET  /siigo/preparar-compra/{causacion_id}
POST /siigo/enviar-compra/{causacion_id}
```

---

## 6. Tablas SQLite actuales

### `proveedores`

Guarda proveedores detectados desde facturas.

### `facturas_recibidas`

Guarda encabezado de facturas procesadas.

Campos importantes:

```text
numero_factura
fecha_factura
hora_factura
cufe
proveedor_nombre
proveedor_nit
cliente_nombre
cliente_nit
subtotal
total_sin_impuestos
iva
total_con_impuestos
total_pagar
xml_principal
pdf_principal
archivo_recibido
```

### `facturas_lineas`

Guarda líneas del XML.

Campos:

```text
factura_id
descripcion
cantidad
valor_linea
```

### `contabilizaciones_historicas`

Histórico contable usado para aprender la causación.

Campos:

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

### `causaciones`

Guarda causaciones internas.

Estados usados:

```text
CAUSADA_SIMULADA
CAUSADA_RESPUESTA_MANUAL
ENVIADA_SIIGO
YA_CAUSADA
```

### `causacion_lineas`

Guarda líneas de causación.

---

## 7. Flujo de aprendizaje por respuesta manual

Cuando una factura no puede causarse automáticamente, n8n envía un correo de revisión:

```text
Factura requiere revisión - Factura ID X
```

Formato actual recomendado de respuesta:

```text
#CAUSAR_FACTURA

FACTURA_ID=X
CENTRO_COSTO=ADMIN

LINEA=GASTO|61553001|Servicios TI
LINEA=IVA|24081501|IVA descontable servicios 19%
LINEA=CXP|23359501|Otros proveedores
```

La respuesta manual debe servir para indicar:

```text
cuenta contable
nombre de cuenta
centro de costo
tipo de línea
```

Pero los valores no deben depender del usuario.

Regla funcional:

```text
Los valores de débito, crédito, gasto, IVA y CXP deben tomarse siempre del XML/ZIP de la factura.
```

---

## 8. Decisión funcional importante

La solución **debe validar el producto o servicio vendido antes de contabilizar**.

No basta con usar solo:

```text
proveedor_nit
```

Debe considerar:

```text
proveedor_nit
descripción de la línea del XML
concepto_servicio
histórico contable
reglas por palabra clave
mapeo ERP
```

Ejemplo:

Para un proveedor como **LATINOAMÉRICA HOSTING S.A.S.**, se debe diferenciar:

```text
HOSTING
DOMINIO
CORREO
CERTIFICADO_SSL
LICENCIA
SERVIDOR
OTRO
```

Si no se puede clasificar el concepto, la factura debe ir a revisión:

```text
REQUIERE_REVISION_CONCEPTO
```

---

## 9. Histórico ERP

Se descargaron informes desde SIIGO:

- Movimiento auxiliar por tercero/cuenta contable 2025.
- Movimiento auxiliar por tercero/cuenta contable 2026.
- Compras por proveedor 2025.
- Compras por proveedor 2026.

No hubo datos en compras por producto.

Se normalizó un archivo:

```text
Historico_ERP_FacturasIA_Normalizado.xlsx
```

Contiene:

```text
Historico_Contable
Mapeo_ERP
Resumen
Diccionarios
Instrucciones
```

Resultado normalizado:

```text
Historico_Contable: 1.390 líneas
Proveedores únicos: 112
Comprobantes FC únicos: 514
Líneas GASTO: 699
Líneas IVA: 177
Líneas CXP: 514
Mapeo_ERP: 133 mapeos candidatos
```

Para LATINOAMÉRICA HOSTING S.A.S. se detectaron cuentas reales:

```text
GASTO: 61553001 - Servicios TI: consultoría, desarrollo de software
IVA:   24081501 - Descontable por servicios 19%
CXP:   23359501 - Otros
```

Esto explica por qué la cuenta manual inicial `513535` no era adecuada para SIIGO.

---

## 10. SIIGO

### Configuración `.env`

Variables usadas:

```env
SIIGO_ENABLED=false
SIIGO_BASE_URL=https://api.siigo.com
SIIGO_USERNAME=...
SIIGO_ACCESS_KEY=...
SIIGO_PARTNER_ID=...
SIIGO_DOCUMENT_ID_COMPRA=18406
SIIGO_PAYMENT_ID_COMPRA=4246
SIIGO_TAX_ID_IVA_19=14132
SIIGO_DIAS_VENCIMIENTO_COMPRA=30
```

### Catálogos consultados

Documento de compra:

```text
id: 18406
name: Compra
type: FC
automatic_number: true
```

Medios de pago:

```text
4246 - Crédito proveedores
```

Impuestos:

```text
9901  - IVA 19%
14132 - IVA 19% SERVICIOS
```

Centros de costo:

```text
[]
```

### Error encontrado al enviar compra

Se intentó enviar una compra SIIGO usando:

```json
{
  "type": "Account",
  "code": "513535"
}
```

SIIGO respondió:

```text
account_not_allowed
The code 513535 cannot be used: transactional characteristic not allowed.
```

Conclusión:

```text
La causación interna puede usar cuenta contable, pero SIIGO no siempre permite enviar esa cuenta como Account.
```

Por eso se necesita `Mapeo_ERP`.

---

## 11. Cambios pendientes recomendados

### 11.1 Crear tabla `mapeo_erp`

Debe guardar equivalencias entre cuenta/concepto y cómo enviarlo al ERP.

Campos sugeridos:

```text
id
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
fecha_creacion
```

### 11.2 Crear tabla `reglas_concepto_servicio`

Campos sugeridos:

```text
id
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
fecha_creacion
```

### 11.3 Crear endpoint de carga de histórico

Endpoint recomendado:

```text
POST /historico/cargar-archivo
```

Debe recibir Excel y cargar:

```text
Historico_Contable → contabilizaciones_historicas
Mapeo_ERP          → mapeo_erp
Reglas             → reglas_concepto_servicio, si existe hoja
```

### 11.4 Ajustar causación automática

La causación automática debe:

1. Leer líneas del XML desde `facturas_lineas`.
2. Clasificar cada línea por `concepto_servicio`.
3. Buscar regla por proveedor + concepto.
4. Si no encuentra regla, devolver `REQUIERE_REVISION_CONCEPTO`.
5. Generar causación con valores reales del XML.
6. Guardar `concepto_servicio` en las líneas de causación.
7. Construir payload SIIGO usando `mapeo_erp`, no solo `cuenta_contable`.

### 11.5 Ajustar payload SIIGO

El payload SIIGO debe usar:

```text
item_type_erp
item_code_erp
item_description_erp
```

en lugar de asumir:

```text
type = Account
code = cuenta_contable
```

---

## 12. Prompt sugerido para Codex

```text
Analiza este proyecto de FastAPI + n8n para procesamiento de facturas electrónicas.

Contexto:
La solución recibe correos con ZIP/XML DIAN, procesa facturas, guarda datos en SQLite, causa internamente, aprende por respuesta manual y prepara/envía compras a SIIGO.

Cambio funcional obligatorio:
La solución debe validar el producto o servicio vendido antes de contabilizar. No basta con usar solo el NIT del proveedor.

Implementar:
1. Crear tabla mapeo_erp.
2. Crear tabla reglas_concepto_servicio.
3. Agregar concepto_servicio en la lógica de causación.
4. Crear endpoint POST /historico/cargar-archivo para cargar Excel con hojas Historico_Contable y Mapeo_ERP.
5. Cargar Historico_Contable en contabilizaciones_historicas.
6. Cargar Mapeo_ERP en la nueva tabla mapeo_erp.
7. Clasificar líneas de factura por descripción usando reglas/palabras clave.
8. Si no se puede clasificar, devolver REQUIERE_REVISION_CONCEPTO.
9. Si falta mapeo ERP, devolver REQUIERE_MAPEO_ERP.
10. Al preparar/enviar compra SIIGO, usar mapeo_erp item_type_erp e item_code_erp.
11. Mantener compatibilidad con los endpoints actuales.
12. No modificar credenciales ni .env real. Crear .env.example si no existe.
13. Agregar pruebas manuales/documentación de endpoints.

Archivos importantes:
- python-api/main.py
- python-api/siigo_client.py
- n8n/Causacion Fact Prov.json
- docs/Historico_ERP_FacturasIA_Normalizado.xlsx
```

---

## 13. Prompt sugerido para modificar n8n JSON

```text
Analiza el workflow n8n/Causacion Fact Prov.json.

Actualizar el flujo para soportar validación de concepto_servicio:

1. En el correo de revisión manual, solicitar concepto_servicio y líneas sin valores manuales.
2. Agregar mensajes para REQUIERE_REVISION_CONCEPTO y REQUIERE_MAPEO_ERP.
3. Mantener la rama de respuesta manual #CAUSAR_FACTURA.
4. No tocar credenciales.
5. Mantener endpoints actuales de Python.
6. Si agregas nodos, documenta qué hacen y cómo probarlos.
```

---

## 14. Estado actual resumido

Funciona:

```text
Recepción correo IMAP
Lectura de ZIP/XML
Extracción DIAN
Guardado en SQLite
Detección duplicados
Causación automática por histórico simple
Revisión manual por correo
Causación desde respuesta manual
Aprendizaje histórico
Autenticación SIIGO
Consulta catálogos SIIGO
Preparación payload SIIGO
Intento de envío SIIGO
```

Pendiente:

```text
Carga masiva de histórico Excel
Mapeo ERP
Clasificación por producto/servicio
Causación por concepto
Payload SIIGO basado en mapeo ERP
Manejo formal de REQUIERE_REVISION_CONCEPTO
Manejo formal de REQUIERE_MAPEO_ERP
```
