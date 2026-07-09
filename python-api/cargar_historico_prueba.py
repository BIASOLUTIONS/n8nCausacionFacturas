import sqlite3
import os

BASE_PATH = r"C:\FacturasIA"
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")


historicos = [
    {
        "proveedor_nit": "830122566",
        "proveedor_nombre": "COLOMBIA TELECOMUNICACIONES S.A. E.S.P. BIC",
        "descripcion": "Servicio de internet fijo fibra",
        "cuenta_contable": "513535",
        "nombre_cuenta": "Servicios de telecomunicaciones",
        "centro_costo": "ADMIN",
        "debito": 117100,
        "credito": 0,
        "cuenta_iva": "240805",
        "cuenta_retencion": None,
        "fuente": "Prueba inicial",
        "fecha_documento": "2026-06-01"
    },
    {
        "proveedor_nit": "830122566",
        "proveedor_nombre": "COLOMBIA TELECOMUNICACIONES S.A. E.S.P. BIC",
        "descripcion": "IVA descontable servicio de telecomunicaciones",
        "cuenta_contable": "240805",
        "nombre_cuenta": "IVA descontable",
        "centro_costo": "ADMIN",
        "debito": 22249,
        "credito": 0,
        "cuenta_iva": "240805",
        "cuenta_retencion": None,
        "fuente": "Prueba inicial",
        "fecha_documento": "2026-06-01"
    },
    {
        "proveedor_nit": "830122566",
        "proveedor_nombre": "COLOMBIA TELECOMUNICACIONES S.A. E.S.P. BIC",
        "descripcion": "Cuenta por pagar proveedor telecomunicaciones",
        "cuenta_contable": "220505",
        "nombre_cuenta": "Proveedores nacionales",
        "centro_costo": "ADMIN",
        "debito": 0,
        "credito": 139349,
        "cuenta_iva": None,
        "cuenta_retencion": None,
        "fuente": "Prueba inicial",
        "fecha_documento": "2026-06-01"
    }
]


def cargar_historico():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for h in historicos:
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
            h["proveedor_nit"],
            h["proveedor_nombre"],
            h["descripcion"],
            h["cuenta_contable"],
            h["nombre_cuenta"],
            h["centro_costo"],
            h["debito"],
            h["credito"],
            h["cuenta_iva"],
            h["cuenta_retencion"],
            h["fuente"],
            h["fecha_documento"]
        ))

    conn.commit()
    conn.close()

    print("Histórico contable de prueba cargado correctamente.")


if __name__ == "__main__":
    cargar_historico()