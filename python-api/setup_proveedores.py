import sqlite3
import os

BASE_PATH = r"C:\FacturasIA"
DB_PATH = os.path.join(BASE_PATH, "facturas_ai.db")


def crear_tabla_proveedores():
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

    conn.commit()
    conn.close()

    print("Tabla proveedores creada correctamente.")


def cargar_proveedores_desde_facturas():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO proveedores (
            nit,
            nombre
        )
        SELECT DISTINCT
            proveedor_nit,
            proveedor_nombre
        FROM facturas_recibidas
        WHERE proveedor_nit IS NOT NULL
          AND proveedor_nit <> ''
    """)

    conn.commit()
    conn.close()

    print("Proveedores cargados desde facturas existentes.")


if __name__ == "__main__":
    crear_tabla_proveedores()
    cargar_proveedores_desde_facturas()