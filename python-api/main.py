from fastapi import FastAPI, UploadFile, File, Body
from fastapi.responses import JSONResponse
from lxml import etree
from html import unescape
from dotenv import load_dotenv
import os
import shutil
import uuid
import zipfile
import sqlite3
import re

load_dotenv()

app = FastAPI(title="Facturas IA API")

BASE_PATH = r"C:\FacturasIA"
ADJUNTOS_PATH = os.path.join(BASE_PATH, "adjuntos")
PROCESADAS_PATH = os.path.join(BASE_PATH, "procesadas")
ERRORES_PATH = os.path.join(BASE_PATH, "errores")
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")

os.makedirs(ADJUNTOS_PATH, exist_ok=True)
os.makedirs(PROCESADAS_PATH, exist_ok=True)
os.makedirs(ERRORES_PATH, exist_ok=True)


def inicializar_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nit TEXT UNIQUE,
            nombre TEXT,
            ciudad TEXT,
            regimen TEXT,
            responsabilidad_fiscal TEXT,
            cuenta_gasto_default TEXT,
            cuenta_iva_default TEXT,
            cuenta_retencion_default TEXT,
            activo INTEGER DEFAULT 1,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturas_recibidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT,
            fecha_factura TEXT,
            hora_factura TEXT,
            cufe TEXT UNIQUE,
            proveedor_nombre TEXT,
            proveedor_nit TEXT,
            cliente_nombre TEXT,
            cliente_nit TEXT,
            subtotal REAL,
            total_sin_impuestos REAL,
            iva REAL,
            total_con_impuestos REAL,
            total_pagar REAL,
            xml_principal TEXT,
            pdf_principal TEXT,
            archivo_recibido TEXT,
            fecha_procesamiento DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facturas_lineas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER,
            descripcion TEXT,
            cantidad REAL,
            valor_linea REAL,
            FOREIGN KEY (factura_id) REFERENCES facturas_recibidas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contabilizaciones_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_nit TEXT,
            proveedor_nombre TEXT,
            descripcion TEXT,
            cuenta_contable TEXT,
            nombre_cuenta TEXT,
            centro_costo TEXT,
            debito REAL DEFAULT 0,
            credito REAL DEFAULT 0,
            cuenta_iva TEXT,
            cuenta_retencion TEXT,
            fuente TEXT,
            fecha_documento TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS causaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER,
            proveedor_nit TEXT,
            proveedor_nombre TEXT,
            numero_factura TEXT,
            estado TEXT,
            confianza REAL,
            total_debito REAL,
            total_credito REAL,
            mensaje TEXT,
            siigo_comprobante_id TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (factura_id) REFERENCES facturas_recibidas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS causacion_lineas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            causacion_id INTEGER,
            tipo TEXT,
            cuenta_contable TEXT,
            nombre_cuenta TEXT,
            centro_costo TEXT,
            debito REAL DEFAULT 0,
            credito REAL DEFAULT 0,
            descripcion TEXT,
            FOREIGN KEY (causacion_id) REFERENCES causaciones(id)
        )
    """)

    conn.commit()
    conn.close()


def buscar_xml_pdf(carpeta: str):
    xml_files = []
    pdf_files = []

    for root_dir, dirs, files in os.walk(carpeta):
        for file_name in files:
            ruta = os.path.join(root_dir, file_name)
            nombre_lower = file_name.lower()

            if nombre_lower.endswith(".xml"):
                xml_files.append(ruta)

            if nombre_lower.endswith(".pdf"):
                pdf_files.append(ruta)

    return xml_files, pdf_files


def safe_extract_zip(zip_ref: zipfile.ZipFile, destino: str):
    destino_abs = os.path.abspath(destino)

    for member in zip_ref.infolist():
        member_path = os.path.abspath(os.path.join(destino, member.filename))

        if not member_path.startswith(destino_abs):
            raise ValueError("ZIP contiene rutas no permitidas.")

    zip_ref.extractall(destino)


def cargar_xml_factura(xml_path: str):
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    tag_root = etree.QName(root).localname

    if tag_root == "Invoice":
        return root

    ns = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    }

    descripcion = root.findtext(
        ".//cac:Attachment//cac:ExternalReference//cbc:Description",
        namespaces=ns
    )

    if descripcion and "<Invoice" in descripcion:
        return etree.fromstring(descripcion.encode("utf-8"), parser=parser)

    raise ValueError(
        f"No se encontró una factura tipo Invoice en el XML. Tipo raíz encontrado: {tag_root}"
    )


def texto(root, xpath: str, ns: dict):
    valor = root.findtext(xpath, namespaces=ns)
    return valor.strip() if valor else None


def numero_decimal(valor):
    try:
        return float(valor) if valor not in [None, ""] else 0
    except Exception:
        return 0


def extraer_datos_xml(xml_path: str):
    root = cargar_xml_factura(xml_path)

    ns = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    }

    numero_factura = texto(root, "./cbc:ID", ns)
    fecha_factura = texto(root, "./cbc:IssueDate", ns)
    hora_factura = texto(root, "./cbc:IssueTime", ns)
    cufe = texto(root, "./cbc:UUID", ns)

    proveedor_nombre = texto(
        root,
        ".//cac:AccountingSupplierParty//cac:Party//cac:PartyLegalEntity//cbc:RegistrationName",
        ns
    )

    if not proveedor_nombre:
        proveedor_nombre = texto(
            root,
            ".//cac:AccountingSupplierParty//cac:Party//cac:PartyName//cbc:Name",
            ns
        )

    proveedor_nit = texto(
        root,
        ".//cac:AccountingSupplierParty//cac:Party//cac:PartyTaxScheme//cbc:CompanyID",
        ns
    )

    cliente_nombre = texto(
        root,
        ".//cac:AccountingCustomerParty//cac:Party//cac:PartyLegalEntity//cbc:RegistrationName",
        ns
    )

    cliente_nit = texto(
        root,
        ".//cac:AccountingCustomerParty//cac:Party//cac:PartyTaxScheme//cbc:CompanyID",
        ns
    )

    subtotal = numero_decimal(
        texto(root, ".//cac:LegalMonetaryTotal//cbc:LineExtensionAmount", ns)
    )

    total_sin_impuestos = numero_decimal(
        texto(root, ".//cac:LegalMonetaryTotal//cbc:TaxExclusiveAmount", ns)
    )

    total_con_impuestos = numero_decimal(
        texto(root, ".//cac:LegalMonetaryTotal//cbc:TaxInclusiveAmount", ns)
    )

    total_pagar = numero_decimal(
        texto(root, ".//cac:LegalMonetaryTotal//cbc:PayableAmount", ns)
    )

    iva = 0
    tax_totals = root.findall("./cac:TaxTotal", namespaces=ns)

    for tax_total in tax_totals:
        tax_id = tax_total.findtext(".//cac:TaxScheme/cbc:ID", namespaces=ns)
        tax_amount = tax_total.findtext("./cbc:TaxAmount", namespaces=ns)

        if tax_id == "01":
            iva += numero_decimal(tax_amount)

    lineas = []
    invoice_lines = root.findall(".//cac:InvoiceLine", namespaces=ns)

    for line in invoice_lines:
        descripcion = texto(line, ".//cac:Item/cbc:Description", ns)
        cantidad = numero_decimal(texto(line, "./cbc:InvoicedQuantity", ns))
        valor_linea = numero_decimal(texto(line, "./cbc:LineExtensionAmount", ns))

        lineas.append({
            "descripcion": descripcion,
            "cantidad": cantidad,
            "valor_linea": valor_linea
        })

    return {
        "numero_factura": numero_factura,
        "fecha_factura": fecha_factura,
        "hora_factura": hora_factura,
        "cufe": cufe,
        "proveedor_nombre": proveedor_nombre,
        "proveedor_nit": proveedor_nit,
        "cliente_nombre": cliente_nombre,
        "cliente_nit": cliente_nit,
        "subtotal": subtotal,
        "total_sin_impuestos": total_sin_impuestos,
        "iva": iva,
        "total_con_impuestos": total_con_impuestos,
        "total_pagar": total_pagar,
        "lineas": lineas
    }


def registrar_proveedor(datos_factura):
    proveedor_nit = datos_factura.get("proveedor_nit")
    proveedor_nombre = datos_factura.get("proveedor_nombre")

    if not proveedor_nit:
        return {
            "proveedor_id": None,
            "proveedor_nuevo": False
        }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM proveedores
        WHERE nit = ?
    """, (proveedor_nit,))

    row = cursor.fetchone()

    if row:
        conn.close()
        return {
            "proveedor_id": row[0],
            "proveedor_nuevo": False
        }

    cursor.execute("""
        INSERT INTO proveedores (
            nit,
            nombre
        )
        VALUES (?, ?)
    """, (
        proveedor_nit,
        proveedor_nombre
    ))

    proveedor_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return {
        "proveedor_id": proveedor_id,
        "proveedor_nuevo": True
    }


def guardar_factura_db(datos_factura, xml_principal, pdf_principal, archivo_recibido):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO facturas_recibidas (
                numero_factura,
                fecha_factura,
                hora_factura,
                cufe,
                proveedor_nombre,
                proveedor_nit,
                cliente_nombre,
                cliente_nit,
                subtotal,
                total_sin_impuestos,
                iva,
                total_con_impuestos,
                total_pagar,
                xml_principal,
                pdf_principal,
                archivo_recibido
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos_factura.get("numero_factura"),
            datos_factura.get("fecha_factura"),
            datos_factura.get("hora_factura"),
            datos_factura.get("cufe"),
            datos_factura.get("proveedor_nombre"),
            datos_factura.get("proveedor_nit"),
            datos_factura.get("cliente_nombre"),
            datos_factura.get("cliente_nit"),
            datos_factura.get("subtotal"),
            datos_factura.get("total_sin_impuestos"),
            datos_factura.get("iva"),
            datos_factura.get("total_con_impuestos"),
            datos_factura.get("total_pagar"),
            xml_principal,
            pdf_principal,
            archivo_recibido
        ))

        factura_id = cursor.lastrowid

        for linea in datos_factura.get("lineas", []):
            cursor.execute("""
                INSERT INTO facturas_lineas (
                    factura_id,
                    descripcion,
                    cantidad,
                    valor_linea
                )
                VALUES (?, ?, ?, ?)
            """, (
                factura_id,
                linea.get("descripcion"),
                linea.get("cantidad"),
                linea.get("valor_linea")
            ))

        conn.commit()

        return {
            "factura_id": factura_id,
            "duplicada": False
        }

    except sqlite3.IntegrityError:
        cufe = datos_factura.get("cufe")

        cursor.execute("""
            SELECT id
            FROM facturas_recibidas
            WHERE cufe = ?
        """, (cufe,))

        row = cursor.fetchone()
        factura_id = row[0] if row else None

        return {
            "factura_id": factura_id,
            "duplicada": True
        }

    finally:
        conn.close()


def construir_propuesta_causacion(factura_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM facturas_recibidas
        WHERE id = ?
    """, (factura_id,))

    factura_row = cursor.fetchone()

    if not factura_row:
        conn.close()
        return {
            "ok": False,
            "status_code": 404,
            "error": "Factura no encontrada"
        }

    factura = dict(factura_row)
    proveedor_nit = factura.get("proveedor_nit")

    cursor.execute("""
        SELECT *
        FROM contabilizaciones_historicas
        WHERE proveedor_nit = ?
        ORDER BY fecha_documento DESC, id DESC
        LIMIT 20
    """, (proveedor_nit,))

    historico = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not historico:
        return {
            "ok": True,
            "factura_id": factura_id,
            "proveedor_nit": proveedor_nit,
            "proveedor_nombre": factura.get("proveedor_nombre"),
            "numero_factura": factura.get("numero_factura"),
            "requiere_revision": True,
            "confianza": 0,
            "mensaje": "No existe histórico contable para este proveedor.",
            "propuesta": []
        }

    total_pagar = round(float(factura.get("total_pagar") or 0), 2)
    iva = round(float(factura.get("iva") or 0), 2)
    subtotal = round(float(factura.get("subtotal") or 0), 2)
    total_sin_impuestos = round(float(factura.get("total_sin_impuestos") or 0), 2)

    if subtotal > 0:
        valor_gasto = subtotal
    elif total_sin_impuestos > 0:
        valor_gasto = total_sin_impuestos
    else:
        valor_gasto = round(total_pagar - iva, 2)

    cuenta_gasto = None
    cuenta_iva = None
    cuenta_pagar = None
    centro_costo = None

    for h in historico:
        cuenta = h.get("cuenta_contable")
        nombre_cuenta = (h.get("nombre_cuenta") or "").lower()

        if not centro_costo and h.get("centro_costo"):
            centro_costo = h.get("centro_costo")

        if not cuenta_gasto:
            debito = float(h.get("debito") or 0)
            if debito > 0 and "iva" not in nombre_cuenta and cuenta != "240805":
                cuenta_gasto = h

        if not cuenta_iva:
            if "iva" in nombre_cuenta or cuenta == "240805":
                cuenta_iva = h

        if not cuenta_pagar:
            credito = float(h.get("credito") or 0)
            if credito > 0:
                cuenta_pagar = h

    propuesta = []

    if cuenta_gasto:
        propuesta.append({
            "tipo": "gasto",
            "cuenta_contable": cuenta_gasto.get("cuenta_contable"),
            "nombre_cuenta": cuenta_gasto.get("nombre_cuenta"),
            "centro_costo": centro_costo,
            "debito": valor_gasto,
            "credito": 0,
            "descripcion": "Gasto según histórico del proveedor"
        })

    if iva > 0 and cuenta_iva:
        propuesta.append({
            "tipo": "iva",
            "cuenta_contable": cuenta_iva.get("cuenta_contable"),
            "nombre_cuenta": cuenta_iva.get("nombre_cuenta"),
            "centro_costo": centro_costo,
            "debito": iva,
            "credito": 0,
            "descripcion": "IVA descontable según histórico del proveedor"
        })

    if cuenta_pagar:
        propuesta.append({
            "tipo": "cuenta_por_pagar",
            "cuenta_contable": cuenta_pagar.get("cuenta_contable"),
            "nombre_cuenta": cuenta_pagar.get("nombre_cuenta"),
            "centro_costo": centro_costo,
            "debito": 0,
            "credito": total_pagar,
            "descripcion": "Cuenta por pagar según histórico del proveedor"
        })

    requiere_revision = len(propuesta) == 0

    return {
        "ok": True,
        "factura_id": factura_id,
        "proveedor_nit": proveedor_nit,
        "proveedor_nombre": factura.get("proveedor_nombre"),
        "numero_factura": factura.get("numero_factura"),
        "fecha_factura": factura.get("fecha_factura"),
        "subtotal": subtotal,
        "iva": iva,
        "total_pagar": total_pagar,
        "valor_gasto": valor_gasto,
        "total_historicos": len(historico),
        "confianza": 80 if propuesta else 0,
        "requiere_revision": requiere_revision,
        "propuesta": propuesta
    }


def limpiar_cuerpo_correo(texto_correo: str):
    if not texto_correo:
        return ""

    texto_limpio = unescape(texto_correo)

    texto_limpio = re.sub(r"<br\s*/?>", "\n", texto_limpio, flags=re.IGNORECASE)
    texto_limpio = re.sub(r"</p>", "\n", texto_limpio, flags=re.IGNORECASE)
    texto_limpio = re.sub(r"<[^>]+>", "", texto_limpio)

    return texto_limpio.strip()


def extraer_factura_id(subject: str, body: str):
    texto_busqueda = f"{subject}\n{body}"

    patrones = [
        r"FACTURA_ID\s*=\s*(\d+)",
        r"Factura ID\s+(\d+)",
        r"factura_id\s*:\s*(\d+)"
    ]

    for patron in patrones:
        match = re.search(patron, texto_busqueda, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def parsear_respuesta_causacion(subject: str, body: str):
    texto_limpio = limpiar_cuerpo_correo(body)

    if "#CAUSAR_FACTURA" not in texto_limpio:
        raise ValueError("No se encontró el marcador #CAUSAR_FACTURA en la respuesta.")

    factura_id = extraer_factura_id(subject, texto_limpio)

    centro_costo_default = None
    lineas = []

    for raw_line in texto_limpio.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(">"):
            continue

        if line.upper().startswith("CENTRO_COSTO="):
            centro_costo_default = line.split("=", 1)[1].strip()
            continue

        if line.upper().startswith("LINEA="):
            contenido = line.split("=", 1)[1].strip()
            partes = [p.strip() for p in contenido.split("|")]

            if len(partes) < 3:
                raise ValueError(
                    f"Línea contable inválida. Debe tener al menos 3 partes: {line}"
                )

            tipo = partes[0].upper()
            cuenta = partes[1]
            nombre_cuenta = partes[2]

            if tipo not in ["GASTO", "IVA", "CXP", "CUENTA_POR_PAGAR"]:
                raise ValueError(
                    f"Tipo de línea no soportado: {tipo}. Use GASTO, IVA o CXP."
                )

            if tipo == "CUENTA_POR_PAGAR":
                tipo = "CXP"

            lineas.append({
                "tipo": tipo,
                "cuenta_contable": cuenta,
                "nombre_cuenta": nombre_cuenta,
                "centro_costo": centro_costo_default,
                "descripcion": nombre_cuenta
            })

    if not factura_id:
        raise ValueError("No se encontró FACTURA_ID en la respuesta.")

    if not lineas:
        raise ValueError("No se encontraron líneas contables en la respuesta.")

    return {
        "factura_id": factura_id,
        "centro_costo": centro_costo_default,
        "lineas": lineas
    }


def construir_lineas_respuesta_con_valores_factura(factura: dict, lineas_usuario: list):
    total_pagar = round(float(factura.get("total_pagar") or 0), 2)
    iva = round(float(factura.get("iva") or 0), 2)

    subtotal = round(float(factura.get("subtotal") or 0), 2)
    total_sin_impuestos = round(float(factura.get("total_sin_impuestos") or 0), 2)

    if subtotal > 0:
        valor_gasto = subtotal
    elif total_sin_impuestos > 0:
        valor_gasto = total_sin_impuestos
    else:
        valor_gasto = round(total_pagar - iva, 2)

    cuentas = {}

    for linea in lineas_usuario:
        tipo = linea.get("tipo")
        cuentas[tipo] = linea

    if "GASTO" not in cuentas:
        raise ValueError("La respuesta debe incluir una línea tipo GASTO.")

    if "CXP" not in cuentas:
        raise ValueError("La respuesta debe incluir una línea tipo CXP.")

    if iva > 0 and "IVA" not in cuentas:
        raise ValueError("La factura tiene IVA, por lo tanto debe incluir una línea tipo IVA.")

    lineas_calculadas = []

    gasto = cuentas["GASTO"]

    lineas_calculadas.append({
        "tipo": "GASTO",
        "cuenta_contable": gasto.get("cuenta_contable"),
        "nombre_cuenta": gasto.get("nombre_cuenta"),
        "centro_costo": gasto.get("centro_costo"),
        "debito": valor_gasto,
        "credito": 0,
        "descripcion": gasto.get("descripcion")
    })

    if iva > 0:
        iva_linea = cuentas["IVA"]

        lineas_calculadas.append({
            "tipo": "IVA",
            "cuenta_contable": iva_linea.get("cuenta_contable"),
            "nombre_cuenta": iva_linea.get("nombre_cuenta"),
            "centro_costo": iva_linea.get("centro_costo"),
            "debito": iva,
            "credito": 0,
            "descripcion": iva_linea.get("descripcion")
        })

    cxp = cuentas["CXP"]

    lineas_calculadas.append({
        "tipo": "CXP",
        "cuenta_contable": cxp.get("cuenta_contable"),
        "nombre_cuenta": cxp.get("nombre_cuenta"),
        "centro_costo": cxp.get("centro_costo"),
        "debito": 0,
        "credito": total_pagar,
        "descripcion": cxp.get("descripcion")
    })

    total_debito = round(sum(float(l.get("debito") or 0) for l in lineas_calculadas), 2)
    total_credito = round(sum(float(l.get("credito") or 0) for l in lineas_calculadas), 2)

    if total_debito != total_credito:
        raise ValueError(
            f"La contabilización calculada con valores de la factura está descuadrada. "
            f"Débito={total_debito}, Crédito={total_credito}"
        )

    return {
        "lineas": lineas_calculadas,
        "total_debito": total_debito,
        "total_credito": total_credito,
        "total_pagar_factura": total_pagar,
        "iva_factura": iva,
        "valor_gasto_factura": valor_gasto
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "message": "API de Facturas IA funcionando correctamente"
    }


@app.get("/facturas/listar")
def listar_facturas():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            numero_factura,
            fecha_factura,
            cufe,
            proveedor_nombre,
            proveedor_nit,
            cliente_nombre,
            cliente_nit,
            subtotal,
            iva,
            total_pagar,
            fecha_procesamiento
        FROM facturas_recibidas
        ORDER BY id DESC
        LIMIT 50
    """)

    rows = cursor.fetchall()
    conn.close()

    return {
        "ok": True,
        "facturas": [dict(row) for row in rows]
    }


@app.get("/proveedores/listar")
def listar_proveedores():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            nit,
            nombre,
            ciudad,
            regimen,
            responsabilidad_fiscal,
            cuenta_gasto_default,
            cuenta_iva_default,
            cuenta_retencion_default,
            activo,
            fecha_creacion
        FROM proveedores
        ORDER BY nombre
    """)

    rows = cursor.fetchall()
    conn.close()

    return {
        "ok": True,
        "proveedores": [dict(row) for row in rows]
    }


@app.get("/historico/proveedor/{nit}")
def buscar_historico_proveedor(nit: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            proveedor_nit,
            proveedor_nombre,
            descripcion,
            cuenta_contable,
            nombre_cuenta,
            centro_costo,
            debito,
            credito,
            cuenta_iva,
            cuenta_retencion,
            fuente,
            fecha_documento
        FROM contabilizaciones_historicas
        WHERE proveedor_nit = ?
        ORDER BY fecha_documento DESC, id DESC
        LIMIT 20
    """, (nit,))

    rows = cursor.fetchall()
    conn.close()

    return {
        "ok": True,
        "nit": nit,
        "total_registros": len(rows),
        "historico": [dict(row) for row in rows]
    }


@app.get("/causacion/proponer/{factura_id}")
def proponer_causacion(factura_id: int):
    resultado = construir_propuesta_causacion(factura_id)

    if not resultado.get("ok") and resultado.get("status_code") == 404:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": resultado.get("error")
            }
        )

    return resultado


@app.post("/causacion/causar/{factura_id}")
def causar_factura(factura_id: int):
    propuesta = construir_propuesta_causacion(factura_id)

    if not propuesta.get("ok"):
        return JSONResponse(
            status_code=propuesta.get("status_code", 400),
            content={
                "ok": False,
                "error": propuesta.get("error", "No fue posible construir la causación.")
            }
        )

    if propuesta.get("requiere_revision"):
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "estado": "REQUIERE_REVISION",
                "mensaje": propuesta.get("mensaje", "La factura requiere revisión antes de causar."),
                "factura_id": factura_id
            }
        )

    lineas = propuesta.get("propuesta", [])

    if not lineas:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "estado": "SIN_LINEAS",
                "mensaje": "No se generaron líneas contables para causar.",
                "factura_id": factura_id
            }
        )

    total_debito = round(sum(float(l.get("debito") or 0) for l in lineas), 2)
    total_credito = round(sum(float(l.get("credito") or 0) for l in lineas), 2)

    if total_debito != total_credito:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "estado": "DESCUADRADA",
                "mensaje": "La causación no cuadra. Débitos y créditos son diferentes.",
                "factura_id": factura_id,
                "total_debito": total_debito,
                "total_credito": total_credito,
                "diferencia": round(total_debito - total_credito, 2),
                "lineas": lineas
            }
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM causaciones
        WHERE factura_id = ?
          AND estado IN ('CAUSADA_SIMULADA', 'CAUSADA_RESPUESTA_MANUAL')
        LIMIT 1
    """, (factura_id,))

    existente = cursor.fetchone()

    if existente:
        conn.close()
        return {
            "ok": True,
            "estado": "YA_CAUSADA",
            "mensaje": "La factura ya tenía una causación registrada.",
            "factura_id": factura_id,
            "causacion_id": existente[0],
            "total_debito": total_debito,
            "total_credito": total_credito,
            "lineas": lineas
        }

    cursor.execute("""
        INSERT INTO causaciones (
            factura_id,
            proveedor_nit,
            proveedor_nombre,
            numero_factura,
            estado,
            confianza,
            total_debito,
            total_credito,
            mensaje
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        factura_id,
        propuesta.get("proveedor_nit"),
        propuesta.get("proveedor_nombre"),
        propuesta.get("numero_factura"),
        "CAUSADA_SIMULADA",
        propuesta.get("confianza"),
        total_debito,
        total_credito,
        "Factura causada automáticamente en modo simulación usando valores reales del XML."
    ))

    causacion_id = cursor.lastrowid

    for linea in lineas:
        cursor.execute("""
            INSERT INTO causacion_lineas (
                causacion_id,
                tipo,
                cuenta_contable,
                nombre_cuenta,
                centro_costo,
                debito,
                credito,
                descripcion
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            causacion_id,
            linea.get("tipo"),
            linea.get("cuenta_contable"),
            linea.get("nombre_cuenta"),
            linea.get("centro_costo"),
            linea.get("debito"),
            linea.get("credito"),
            linea.get("descripcion")
        ))

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "estado": "CAUSADA_SIMULADA",
        "mensaje": "Factura causada automáticamente en modo simulación usando valores reales del XML.",
        "factura_id": factura_id,
        "causacion_id": causacion_id,
        "proveedor_nit": propuesta.get("proveedor_nit"),
        "proveedor_nombre": propuesta.get("proveedor_nombre"),
        "numero_factura": propuesta.get("numero_factura"),
        "confianza": propuesta.get("confianza"),
        "total_debito": total_debito,
        "total_credito": total_credito,
        "lineas": lineas
    }


@app.post("/revision/procesar-respuesta")
def procesar_respuesta_revision(payload: dict = Body(...)):
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    from_email = payload.get("from", "")

    try:
        datos = parsear_respuesta_causacion(subject, body)

        factura_id = datos["factura_id"]
        lineas_usuario = datos["lineas"]

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM facturas_recibidas
            WHERE id = ?
        """, (factura_id,))

        factura_row = cursor.fetchone()

        if not factura_row:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "estado": "FACTURA_NO_ENCONTRADA",
                    "mensaje": f"No existe la factura_id {factura_id}."
                }
            )

        factura = dict(factura_row)

        cursor.execute("""
            SELECT id
            FROM causaciones
            WHERE factura_id = ?
              AND estado IN ('CAUSADA_SIMULADA', 'CAUSADA_RESPUESTA_MANUAL')
            LIMIT 1
        """, (factura_id,))

        causacion_existente = cursor.fetchone()

        if causacion_existente:
            conn.close()
            return {
                "ok": True,
                "estado": "YA_CAUSADA",
                "mensaje": "La factura ya tenía una causación registrada.",
                "factura_id": factura_id,
                "causacion_id": causacion_existente[0]
            }

        resultado_valores = construir_lineas_respuesta_con_valores_factura(
            factura,
            lineas_usuario
        )

        lineas = resultado_valores["lineas"]
        total_debito = resultado_valores["total_debito"]
        total_credito = resultado_valores["total_credito"]

        for linea in lineas:
            cursor.execute("""
                INSERT INTO contabilizaciones_historicas (
                    proveedor_nit,
                    proveedor_nombre,
                    descripcion,
                    cuenta_contable,
                    nombre_cuenta,
                    centro_costo,
                    debito,
                    credito,
                    cuenta_iva,
                    cuenta_retencion,
                    fuente,
                    fecha_documento
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                factura.get("proveedor_nit"),
                factura.get("proveedor_nombre"),
                linea.get("descripcion"),
                linea.get("cuenta_contable"),
                linea.get("nombre_cuenta"),
                linea.get("centro_costo"),
                linea.get("debito"),
                linea.get("credito"),
                linea.get("cuenta_contable") if linea.get("tipo") == "IVA" else None,
                None,
                f"Respuesta correo revisión - {from_email}",
                factura.get("fecha_factura")
            ))

        cursor.execute("""
            INSERT INTO causaciones (
                factura_id,
                proveedor_nit,
                proveedor_nombre,
                numero_factura,
                estado,
                confianza,
                total_debito,
                total_credito,
                mensaje
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            factura_id,
            factura.get("proveedor_nit"),
            factura.get("proveedor_nombre"),
            factura.get("numero_factura"),
            "CAUSADA_RESPUESTA_MANUAL",
            100,
            total_debito,
            total_credito,
            "Factura causada desde respuesta manual por correo usando valores reales del XML."
        ))

        causacion_id = cursor.lastrowid

        for linea in lineas:
            cursor.execute("""
                INSERT INTO causacion_lineas (
                    causacion_id,
                    tipo,
                    cuenta_contable,
                    nombre_cuenta,
                    centro_costo,
                    debito,
                    credito,
                    descripcion
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                causacion_id,
                linea.get("tipo"),
                linea.get("cuenta_contable"),
                linea.get("nombre_cuenta"),
                linea.get("centro_costo"),
                linea.get("debito"),
                linea.get("credito"),
                linea.get("descripcion")
            ))

        conn.commit()
        conn.close()

        return {
            "ok": True,
            "estado": "CAUSADA_RESPUESTA_MANUAL",
            "mensaje": "La factura fue causada con la respuesta manual usando valores reales del XML y el histórico fue guardado.",
            "factura_id": factura_id,
            "causacion_id": causacion_id,
            "proveedor_nit": factura.get("proveedor_nit"),
            "proveedor_nombre": factura.get("proveedor_nombre"),
            "numero_factura": factura.get("numero_factura"),
            "total_debito": total_debito,
            "total_credito": total_credito,
            "total_pagar_factura": resultado_valores["total_pagar_factura"],
            "iva_factura": resultado_valores["iva_factura"],
            "valor_gasto_factura": resultado_valores["valor_gasto_factura"],
            "lineas": lineas
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "estado": "ERROR_RESPUESTA_REVISION",
                "mensaje": str(e)
            }
        )


@app.get("/causaciones/listar")
def listar_causaciones():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            factura_id,
            proveedor_nit,
            proveedor_nombre,
            numero_factura,
            estado,
            confianza,
            total_debito,
            total_credito,
            mensaje,
            siigo_comprobante_id,
            fecha_creacion
        FROM causaciones
        ORDER BY id DESC
        LIMIT 50
    """)

    causaciones = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "ok": True,
        "causaciones": causaciones
    }


@app.post("/facturas/procesar-adjunto")
async def procesar_adjunto(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    nombre_original = file.filename or "archivo_sin_nombre"
    extension = os.path.splitext(nombre_original)[1].lower()

    ruta_guardada = os.path.join(
        ADJUNTOS_PATH,
        f"{file_id}_{nombre_original}"
    )

    with open(ruta_guardada, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    carpeta_trabajo = os.path.join(PROCESADAS_PATH, file_id)
    os.makedirs(carpeta_trabajo, exist_ok=True)

    try:
        if extension == ".zip":
            with zipfile.ZipFile(ruta_guardada, "r") as zip_ref:
                safe_extract_zip(zip_ref, carpeta_trabajo)

            xml_files, pdf_files = buscar_xml_pdf(carpeta_trabajo)

        elif extension == ".xml":
            xml_files = [ruta_guardada]
            pdf_files = []

        else:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": f"Tipo de archivo no soportado: {extension}",
                    "archivo_recibido": ruta_guardada
                }
            )

        if not xml_files:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "No se encontró ningún XML dentro del archivo recibido.",
                    "archivo_recibido": ruta_guardada,
                    "carpeta_trabajo": carpeta_trabajo
                }
            )

        xml_principal = xml_files[0]
        pdf_principal = pdf_files[0] if pdf_files else None

        datos_factura = extraer_datos_xml(xml_principal)

        resultado_proveedor = registrar_proveedor(datos_factura)

        resultado_db = guardar_factura_db(
            datos_factura,
            xml_principal,
            pdf_principal,
            ruta_guardada
        )

        return {
            "ok": True,
            "mensaje": "Factura procesada correctamente",
            "factura_id": resultado_db.get("factura_id"),
            "duplicada": resultado_db.get("duplicada"),
            "proveedor_id": resultado_proveedor.get("proveedor_id"),
            "proveedor_nuevo": resultado_proveedor.get("proveedor_nuevo"),
            "nombre_original": nombre_original,
            "archivo_recibido": ruta_guardada,
            "carpeta_trabajo": carpeta_trabajo,
            "total_xml_encontrados": len(xml_files),
            "total_pdf_encontrados": len(pdf_files),
            "xml_principal": xml_principal,
            "pdf_principal": pdf_principal,
            "factura": datos_factura
        }

    except zipfile.BadZipFile:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "El archivo ZIP está dañado o no es un ZIP válido.",
                "archivo_recibido": ruta_guardada
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(e),
                "archivo_recibido": ruta_guardada
            }
        )

@app.get("/siigo/auth-test")
def siigo_auth_test():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()
        resultado = client.autenticar()

        return {
            "ok": True,
            "enabled": client.enabled,
            "mensaje": "Conexión con SIIGO validada correctamente.",
            "siigo": resultado
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "mensaje": "No fue posible autenticar contra SIIGO.",
                "error": str(e)
            }
        )


@app.get("/siigo/config")
def siigo_config():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        return {
            "ok": True,
            "enabled": client.enabled,
            "base_url": client.base_url,
            "username_configurado": bool(client.username),
            "access_key_configurado": bool(client.access_key),
            "partner_id": client.partner_id
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e)
            }
        )

@app.get("/siigo/catalogos")
def siigo_catalogos():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        catalogos = client.consultar_catalogos_basicos()

        return {
            "ok": True,
            "mensaje": "Catálogos SIIGO consultados correctamente.",
            "catalogos": catalogos
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "mensaje": "No fue posible consultar catálogos de SIIGO.",
                "error": str(e)
            }
        )


@app.get("/siigo/documentos-compra")
def siigo_documentos_compra():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        return {
            "ok": True,
            "documentos": client.consultar_tipos_documento_compra()
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e)
            }
        )


@app.get("/siigo/medios-pago")
def siigo_medios_pago():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        return {
            "ok": True,
            "medios_pago": client.consultar_medios_pago()
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e)
            }
        )


@app.get("/siigo/impuestos")
def siigo_impuestos():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        return {
            "ok": True,
            "impuestos": client.consultar_impuestos()
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e)
            }
        )


@app.get("/siigo/centros-costo")
def siigo_centros_costo():
    try:
        from siigo_client import SiigoClient

        client = SiigoClient()

        return {
            "ok": True,
            "centros_costo": client.consultar_centros_costo()
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": str(e)
            }
        )

def separar_prefijo_numero_siigo(numero_factura: str):
    numero_limpio = re.sub(r"[^A-Za-z0-9]", "", numero_factura or "")

    if not numero_limpio:
        return {
            "prefix": "FC",
            "number": "0"
        }

    match = re.search(r"(\d+)$", numero_limpio)

    if match:
        number = match.group(1)
        prefix = numero_limpio[:match.start()]
    else:
        prefix = "FC"
        number = re.sub(r"\D", "", numero_limpio) or "0"

    prefix = prefix[:6] if prefix else "FC"
    number = number[-11:] if len(number) > 11 else number

    return {
        "prefix": prefix,
        "number": number
    }


def calcular_fecha_vencimiento_siigo(fecha_factura: str):
    try:
        from datetime import datetime, timedelta

        dias = int(os.getenv("SIIGO_DIAS_VENCIMIENTO_COMPRA", "30"))
        fecha = datetime.strptime(fecha_factura, "%Y-%m-%d")
        return (fecha + timedelta(days=dias)).strftime("%Y-%m-%d")

    except Exception:
        return fecha_factura


def obtener_env_int(nombre: str):
    valor = os.getenv(nombre)

    if valor is None or str(valor).strip() == "":
        raise ValueError(f"Falta configurar {nombre} en el archivo .env")

    return int(valor)


def construir_payload_siigo_compra_desde_causacion(causacion_id: int):
    document_id = obtener_env_int("SIIGO_DOCUMENT_ID_COMPRA")
    payment_id = obtener_env_int("SIIGO_PAYMENT_ID_COMPRA")
    tax_id_iva_19 = obtener_env_int("SIIGO_TAX_ID_IVA_19")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM causaciones
        WHERE id = ?
    """, (causacion_id,))

    causacion_row = cursor.fetchone()

    if not causacion_row:
        conn.close()
        raise ValueError(f"No existe la causación {causacion_id}.")

    causacion = dict(causacion_row)

    cursor.execute("""
        SELECT *
        FROM facturas_recibidas
        WHERE id = ?
    """, (causacion.get("factura_id"),))

    factura_row = cursor.fetchone()

    if not factura_row:
        conn.close()
        raise ValueError(f"No existe la factura asociada a la causación {causacion_id}.")

    factura = dict(factura_row)

    cursor.execute("""
        SELECT *
        FROM causacion_lineas
        WHERE causacion_id = ?
        ORDER BY id
    """, (causacion_id,))

    lineas = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_pagar = round(float(factura.get("total_pagar") or 0), 2)
    iva = round(float(factura.get("iva") or 0), 2)
    subtotal = round(float(factura.get("subtotal") or 0), 2)
    total_sin_impuestos = round(float(factura.get("total_sin_impuestos") or 0), 2)

    if subtotal > 0:
       valor_gasto_factura = subtotal
    elif total_sin_impuestos > 0:
       valor_gasto_factura = total_sin_impuestos
    else:
       valor_gasto_factura = round(total_pagar - iva, 2)

    lineas_gasto = [
        l for l in lineas
        if float(l.get("debito") or 0) > 0
        and str(l.get("tipo") or "").upper() not in ["IVA"]
        and str(l.get("cuenta_contable") or "") != "240805"
    ]

    if not lineas_gasto:
        raise ValueError("No se encontró una línea de gasto para construir el ítem SIIGO.")

    if len(lineas_gasto) > 1:
        raise ValueError(
            "La simulación SIIGO actual solo soporta una línea de gasto. "
            "Luego habilitamos múltiples líneas."
        )

    linea_gasto = lineas_gasto[0]

    datos_factura_proveedor = separar_prefijo_numero_siigo(
        factura.get("numero_factura")
    )

    item = {
        "type": "Account",
        "code": str(linea_gasto.get("cuenta_contable")),
        "description": linea_gasto.get("nombre_cuenta") or linea_gasto.get("descripcion") or "Gasto factura proveedor",
        "quantity": 1,
        "price": valor_gasto_factura
    }

    if iva > 0:
        item["taxes"] = [
            {
                "id": tax_id_iva_19
            }
        ]

    payload = {
        "document": {
            "id": document_id
        },
        "date": factura.get("fecha_factura"),
        "supplier": {
            "identification": str(factura.get("proveedor_nit")),
            "branch_office": 0
        },
        "provider_invoice": {
            "prefix": datos_factura_proveedor["prefix"],
            "number": datos_factura_proveedor["number"]
        },
        "tax_included": False,
        "observations": (
            f"Factura generada desde FacturasIA. "
            f"Factura ID: {factura.get('id')}. "
            f"Causación ID: {causacion_id}. "
            f"Factura proveedor: {factura.get('numero_factura')}."
        ),
        "items": [
            item
        ],
        "payments": [
            {
                "id": payment_id,
                "value": total_pagar,
                "due_date": calcular_fecha_vencimiento_siigo(factura.get("fecha_factura"))
            }
        ]
    }

    return {
        "payload": payload,
        "factura": factura,
        "causacion": causacion,
        "lineas": lineas,
        "validacion": {
            "total_pagar_factura": total_pagar,
            "iva_factura": iva,
            "cuenta_gasto_siigo": linea_gasto.get("cuenta_contable"),
            "valor_gasto_factura": valor_gasto_factura,
            "document_id": document_id,
            "payment_id": payment_id,
            "tax_id_iva_19": tax_id_iva_19,
            "modo": "SIMULACION_NO_ENVIADO"
        }
    }


@app.get("/siigo/preparar-compra/{causacion_id}")
def siigo_preparar_compra(causacion_id: int):
    try:
        resultado = construir_payload_siigo_compra_desde_causacion(causacion_id)

        return {
            "ok": True,
            "mensaje": "Payload de compra SIIGO preparado correctamente. No se envió a SIIGO.",
            "modo": "SIMULACION_NO_ENVIADO",
            "causacion_id": causacion_id,
            "validacion": resultado["validacion"],
            "payload_siigo": resultado["payload"]
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "mensaje": "No fue posible preparar el payload SIIGO.",
                "error": str(e),
                "causacion_id": causacion_id
            }
        )

@app.post("/siigo/enviar-compra/{causacion_id}")
def siigo_enviar_compra(causacion_id: int):
    try:
        from siigo_client import SiigoClient

        if os.getenv("SIIGO_ENABLED", "false").lower() != "true":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "estado": "SIIGO_DESHABILITADO",
                    "mensaje": "SIIGO_ENABLED está en false. Cambie SIIGO_ENABLED=true en .env para permitir envío real.",
                    "causacion_id": causacion_id
                }
            )

        resultado = construir_payload_siigo_compra_desde_causacion(causacion_id)
        payload = resultado["payload"]

        client = SiigoClient()
        respuesta_siigo = client.post("/v1/purchases", payload)

        siigo_id = (
            respuesta_siigo.get("id")
            or respuesta_siigo.get("uuid")
            or respuesta_siigo.get("purchase_id")
        )

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE causaciones
            SET
                estado = ?,
                siigo_comprobante_id = ?,
                mensaje = ?
            WHERE id = ?
        """, (
            "ENVIADA_SIIGO",
            str(siigo_id) if siigo_id else None,
            "Compra enviada correctamente a SIIGO.",
            causacion_id
        ))

        conn.commit()
        conn.close()

        return {
            "ok": True,
            "estado": "ENVIADA_SIIGO",
            "mensaje": "Compra enviada correctamente a SIIGO.",
            "causacion_id": causacion_id,
            "siigo_id": siigo_id,
            "respuesta_siigo": respuesta_siigo,
            "payload_enviado": payload
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "estado": "ERROR_ENVIANDO_SIIGO",
                "mensaje": str(e),
                "causacion_id": causacion_id
            }
        )

inicializar_db()