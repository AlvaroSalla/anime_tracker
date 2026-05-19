import sqlite3 as sql

db = "data/animes.db"

def conectar():
    conn = sql.connect(db)
    return conn

def cerrar_conexion(conn):
    conn.close()

