from database.conexion import (
    conectar,
    conectar_tracker,
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
                estado_api TEXT,
                popularity INTEGER DEFAULT 0
            )""")

    try:
        cursor.execute("ALTER TABLE animes_api ADD COLUMN estado_api TEXT")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE animes_api ADD COLUMN popularity INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE animes_api ADD COLUMN next_airing_episode INTEGER")
    except Exception:
        pass

    conn.commit()
    cerrar_conexion(conn)

def crear_tablas_tracker():
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS animes_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        caps_vistos INTEGER DEFAULT 0,
        caps_totales INTEGER,
        estado TEXT,
        score INTEGER,
        imagen TEXT,
        estado_api TEXT,
        api_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")

    try:
        cursor.execute("ALTER TABLE animes_usuario ADD COLUMN api_id INTEGER")
    except Exception:
        pass

    conn.commit()
    cerrar_conexion(conn)

