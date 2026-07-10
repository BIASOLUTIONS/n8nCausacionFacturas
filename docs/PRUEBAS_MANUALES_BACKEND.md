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
