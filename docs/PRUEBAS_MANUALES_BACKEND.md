# Pruebas manuales backend FacturasIA

## Levantar API

```powershell
cd .\python-api
.\venv\Scripts\activate
python -m pip install -r .\requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Validar:

```text
GET http://127.0.0.1:8000/health
```

## Cargar historico y mapeo ERP

Desde Swagger:

```text
POST http://127.0.0.1:8000/historico/cargar-archivo
```

Usar el archivo:

```text
Historico_ERP_FacturasIA_Normalizado.xlsx
```

Resultado esperado:

```text
Historico_Contable cargado en contabilizaciones_historicas
Mapeo_ERP cargado en mapeo_erp
```

## Procesar factura

```text
POST http://127.0.0.1:8000/facturas/procesar-adjunto
```

Enviar ZIP/XML DIAN como `file`.

## Clasificar conceptos

```text
POST http://127.0.0.1:8000/facturas/{factura_id}/clasificar-conceptos
```

Estados esperados:

```text
CONCEPTOS_CLASIFICADOS
REQUIERE_REVISION_CONCEPTO
```

## Causar factura

```text
POST http://127.0.0.1:8000/causacion/causar/{factura_id}
```

Estados esperados:

```text
CAUSADA_SIMULADA
REQUIERE_REVISION_CONCEPTO
REQUIERE_MAPEO_ERP
REQUIERE_REVISION
DESCUADRADA
```

## Preparar SIIGO

```text
GET http://127.0.0.1:8000/siigo/preparar-compra/{causacion_id}
```

Debe construir `items` usando:

```text
mapeo_erp.item_type_erp
mapeo_erp.item_code_erp
mapeo_erp.item_description_erp
```

Si falta mapeo, debe responder con error `REQUIERE_MAPEO_ERP`.

## Facturas recurrentes de servicios publicos

El clasificador base reconoce como `SERVICIOS_PUBLICOS` descripciones como:

```text
Energia Domiciliario
Acueducto
Aseo
Alcantarillado
TASA
Alumbrado Publico
```

Si una factura mensual de servicios publicos pide revision manual la primera vez, responder con un concepto general:

```text
#CAUSAR_FACTURA

FACTURA_ID=123
CENTRO_COSTO=ADMIN

TIPO     CUENTA      NOMBRE_CUENTA          CONCEPTO
GASTO    51353001    Servicios publicos     SERVICIOS_PUBLICOS
CXP      23359501    Otros proveedores      CXP
```

Reemplazar `51353001` por la cuenta real que corresponda en el plan contable.

Si tiene IVA, incluir tambien la linea IVA correspondiente.

Al procesar la respuesta manual, el backend guarda historico contable y tambien crea/actualiza `mapeo_erp` para:

```text
proveedor_nit + concepto_servicio + cuenta_contable
```

Con eso, las siguientes facturas del mismo proveedor y concepto deberian causarse automaticamente, siempre que el NIT receptor este permitido y los valores cuadren.

## Facturas recurrentes de telecomunicaciones

El clasificador base reconoce como `TELECOMUNICACIONES` descripciones como:

```text
TELEFONIA
INTERNET
TELEVISION
TELEVISON
TV
CABLE
```

`TELEVISON` se incluye como variante mal escrita porque algunos XML llegan con esa descripcion.

Si pide revision manual la primera vez, responder usando el mismo concepto:

```text
#CAUSAR_FACTURA

FACTURA_ID=123
CENTRO_COSTO=ADMIN

TIPO     CUENTA       NOMBRE_CUENTA          CONCEPTO
GASTO    CUENTA_REAL  Telecomunicaciones     TELECOMUNICACIONES
CXP      23359501     Otros proveedores      CXP
```

Reemplazar `CUENTA_REAL` por la cuenta contable real que corresponda. Si tiene IVA, incluir tambien la linea IVA correspondiente.
