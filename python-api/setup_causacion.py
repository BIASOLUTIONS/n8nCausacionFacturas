import sqlite3
import os

BASE_PATH = r"C:\FacturasIA"
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")


def crear_tablas_causacion():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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

    print("Tablas de causación creadas correctamente.")


if __name__ == "__main__":
    crear_tablas_causacion()