import os
import sqlite3

BASE_PATH = r"C:\FacturasIA"
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")


def crear_tablas_mapeo_erp():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mapeo_erp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            erp TEXT DEFAULT 'SIIGO',
            proveedor_nit TEXT,
            proveedor_nombre TEXT,
            concepto_servicio TEXT,
            cuenta_contable TEXT,
            nombre_cuenta TEXT,
            item_type_erp TEXT,
            item_code_erp TEXT,
            item_description_erp TEXT,
            document_id_erp TEXT,
            payment_id_erp TEXT,
            tax_id_erp TEXT,
            activo INTEGER DEFAULT 1,
            observacion TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reglas_concepto_servicio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            erp TEXT DEFAULT 'SIIGO',
            proveedor_nit TEXT,
            concepto_servicio TEXT,
            palabras_clave TEXT,
            cuenta_contable TEXT,
            nombre_cuenta TEXT,
            item_type_erp TEXT,
            item_code_erp TEXT,
            tax_id_erp TEXT,
            prioridad INTEGER DEFAULT 100,
            activo INTEGER DEFAULT 1,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_mapeo_erp_busqueda
        ON mapeo_erp (
            erp,
            proveedor_nit,
            concepto_servicio,
            cuenta_contable,
            activo
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reglas_concepto_busqueda
        ON reglas_concepto_servicio (
            erp,
            proveedor_nit,
            concepto_servicio,
            activo,
            prioridad
        )
    """)

    conn.commit()
    conn.close()

    print("Tablas mapeo_erp y reglas_concepto_servicio creadas correctamente.")


if __name__ == "__main__":
    crear_tablas_mapeo_erp()
