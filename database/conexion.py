import os
import sys
import sqlite3 as sql


BASE_DIR = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

API_DB = os.path.join(BASE_DIR, "animes_api.db")

TRACKER_DB = os.path.join(os.environ["APPDATA"], "AnimeTracker", "tracker.db")
os.makedirs(os.path.dirname(TRACKER_DB), exist_ok=True)


def conectar():
    conn = sql.connect(API_DB)
    return conn


def conectar_tracker():
    conn = sql.connect(TRACKER_DB)
    return conn


def cerrar_conexion(conn):
    conn.close()
