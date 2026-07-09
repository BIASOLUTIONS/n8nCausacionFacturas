import sqlite3
import os

BASE_PATH = r"C:\FacturasIA"
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")


def crear_tabla_historico():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()

    print("Tabla contabilizaciones_historicas creada correctamente.")


if __name__ == "__main__":
    crear_tabla_historico()