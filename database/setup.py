from database.conexion import (
    conectar, 
    cerrar_conexion
)

def crear_tabla():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(""" CREATE TABLE IF NOT EXISTS user_animes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER NOT NULL,
                caps_vistos INTEGER DEFAULT 0,
                estado TEXT,
                score INTEGER,
                FOREIGN KEY (anime_id) REFERENCES animes_api(id)
            )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS animes_api (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER UNIQUE,
                nombre TEXT NOT NULL,
                caps_totales INTEGER,
                imagen TEXT,
                estado_api TEXT
            )""")

    try:
        cursor.execute("ALTER TABLE animes_api ADD COLUMN estado_api TEXT")
    except Exception:
        pass

    conn.commit()
    cerrar_conexion(conn)

