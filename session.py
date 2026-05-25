import json
import os

current_user_id = None
current_username = None


def _remember_path():
    return os.path.join(os.environ["APPDATA"], "AnimeTracker", "remember.json")


def save_remember_session(user_id, username):
    data = {"user_id": user_id, "username": username}
    path = _remember_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def load_remember_session():
    path = _remember_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if "user_id" in data and "username" in data:
            return data
    except Exception:
        pass
    return None


def delete_remember_session():
    path = _remember_path()
    if os.path.exists(path):
        os.remove(path)


def user_exists_in_db(user_id):
    from database.conexion import conectar_tracker, cerrar_conexion
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    cerrar_conexion(conn)
    return row is not None
