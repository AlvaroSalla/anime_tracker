import hashlib
import session
from database.conexion import conectar, conectar_tracker, cerrar_conexion


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    conn = conectar_tracker()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            cerrar_conexion(conn)
            return False, "El usuario ya existe."
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                       (username, _hash_password(password)))
        conn.commit()
        cerrar_conexion(conn)
        return True, "Usuario registrado con éxito."
    except Exception as e:
        cerrar_conexion(conn)
        return False, str(e)


def login_user(username, password):
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    cerrar_conexion(conn)
    if row is None:
        return False, "El usuario no existe."
    user_id, pw_hash = row
    if pw_hash != _hash_password(password):
        return False, "Contraseña incorrecta."
    session.current_user_id = user_id
    session.current_username = username
    return True, "Login exitoso."


def _estado_segun_caps(caps_vistos, caps_totales, estado):
    if caps_totales is not None and caps_vistos == caps_totales:
        return "Completo"
    return estado


def _estado_al_actualizar_caps(caps_vistos, caps_totales):
    if caps_totales is not None and caps_vistos == caps_totales:
        return "Completo"
    return "En proceso"


def agregar_anime(nombre, vistos, totales, estado, score, api_id=None, imagen=None, estado_api=None):
    if session.current_user_id is None:
        return
    estado = _estado_segun_caps(vistos, totales, estado)
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM animes_usuario WHERE user_id = ? AND nombre = ?",
                   (session.current_user_id, nombre))
    if cursor.fetchone() is not None:
        print("Ese anime ya esta guardado.")
        cerrar_conexion(conn)
        return
    cursor.execute("""INSERT INTO animes_usuario
                (user_id, nombre, caps_vistos, caps_totales, estado, score, imagen, estado_api, api_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (session.current_user_id, nombre, vistos, totales, estado, score, imagen, estado_api, api_id))
    conn.commit()
    cerrar_conexion(conn)


def agregar_animes_api(animes):
    conn = conectar()
    cursor = conn.cursor()
    for anime in animes:
        api_id = anime["id"]
        nombre = anime["title"]["romaji"]
        caps_totales = anime["episodes"]
        imagen = anime["coverImage"]["medium"]
        estado_api = anime.get("status")
        popularity = anime.get("popularity", 0)
        na = anime.get("nextAiringEpisode")
        next_airing_ep = na.get("episode") if isinstance(na, dict) else None
        cursor.execute("""INSERT INTO animes_api (
                    api_id, nombre, caps_totales, imagen, estado_api, popularity, next_airing_episode)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(api_id) DO UPDATE SET
                    nombre = excluded.nombre,
                    caps_totales = excluded.caps_totales,
                    imagen = excluded.imagen,
                    estado_api = excluded.estado_api,
                    popularity = excluded.popularity,
                    next_airing_episode = excluded.next_airing_episode""",
                       (api_id, nombre, caps_totales, imagen, estado_api, popularity, next_airing_ep))
    conn.commit()
    cerrar_conexion(conn)


def obtener_animes_api_guardados(limite=1000):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""SELECT api_id, nombre, caps_totales, imagen, estado_api, next_airing_episode
                FROM animes_api ORDER BY popularity DESC LIMIT ?""", (limite,))
    datos = cursor.fetchall()
    cerrar_conexion(conn)
    animes = []
    for api_id, nombre, caps_totales, imagen, estado_api, next_airing_ep in datos:
        d = {
            "id": api_id,
            "title": {"romaji": nombre},
            "episodes": caps_totales,
            "status": estado_api,
            "coverImage": {"medium": imagen}
        }
        if next_airing_ep is not None:
            d["nextAiringEpisode"] = {"episode": next_airing_ep, "airingAt": 0}
        animes.append(d)
    return animes


def obtener_animes_usuario():
    if session.current_user_id is None:
        return []
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("""SELECT id, nombre, caps_vistos, caps_totales, estado, score, imagen, estado_api, api_id
                FROM animes_usuario
                WHERE user_id = ?
                ORDER BY nombre COLLATE NOCASE""", (session.current_user_id,))
    datos = cursor.fetchall()
    cerrar_conexion(conn)
    animes = []
    for anime_id, nombre, vistos, totales, estado, score, imagen, estado_api, api_id in datos:
        animes.append({
            "id": anime_id,
            "nombre": nombre,
            "caps_vistos": vistos,
            "caps_totales": totales,
            "estado": estado,
            "score": score,
            "imagen": imagen,
            "estado_api": estado_api,
            "api_id": api_id,
        })
    return animes


def obtener_anime_usuario(user_anime_id):
    if session.current_user_id is None:
        return None
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("""SELECT id, nombre, caps_vistos, caps_totales, estado, score
                FROM animes_usuario
                WHERE id = ? AND user_id = ?""", (user_anime_id, session.current_user_id))
    anime = cursor.fetchone()
    cerrar_conexion(conn)
    return anime


def actualizar_caps_anime(user_anime_id, caps_vistos):
    if session.current_user_id is None:
        return
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("SELECT caps_vistos, caps_totales FROM animes_usuario WHERE id = ? AND user_id = ?",
                   (user_anime_id, session.current_user_id))
    anime = cursor.fetchone()
    if anime is None:
        cerrar_conexion(conn)
        return
    caps_vistos_actuales, caps_totales = anime
    estado = _estado_al_actualizar_caps(caps_vistos, caps_totales)
    if estado is not None and caps_vistos != caps_vistos_actuales:
        cursor.execute("UPDATE animes_usuario SET caps_vistos = ?, estado = ? WHERE id = ? AND user_id = ?",
                       (caps_vistos, estado, user_anime_id, session.current_user_id))
    else:
        cursor.execute("UPDATE animes_usuario SET caps_vistos = ? WHERE id = ? AND user_id = ?",
                       (caps_vistos, user_anime_id, session.current_user_id))
    conn.commit()
    cerrar_conexion(conn)


def actualizar_estado_anime(user_anime_id, estado, caps_vistos=None):
    if session.current_user_id is None:
        return
    conn = conectar_tracker()
    cursor = conn.cursor()
    if caps_vistos is None:
        cursor.execute("SELECT caps_vistos, caps_totales FROM animes_usuario WHERE id = ? AND user_id = ?",
                       (user_anime_id, session.current_user_id))
        anime = cursor.fetchone()
        if anime is None:
            cerrar_conexion(conn)
            return
        caps_vistos_actuales, caps_totales = anime
        estado = _estado_segun_caps(caps_vistos_actuales, caps_totales, estado)
        cursor.execute("UPDATE animes_usuario SET estado = ? WHERE id = ? AND user_id = ?",
                       (estado, user_anime_id, session.current_user_id))
    else:
        cursor.execute("SELECT caps_totales FROM animes_usuario WHERE id = ? AND user_id = ?",
                       (user_anime_id, session.current_user_id))
        anime = cursor.fetchone()
        if anime is None:
            cerrar_conexion(conn)
            return
        caps_totales = anime[0]
        estado = _estado_segun_caps(caps_vistos, caps_totales, estado)
        cursor.execute("UPDATE animes_usuario SET estado = ?, caps_vistos = ? WHERE id = ? AND user_id = ?",
                       (estado, caps_vistos, user_anime_id, session.current_user_id))
    conn.commit()
    cerrar_conexion(conn)


def actualizar_score_anime(user_anime_id, score):
    if session.current_user_id is None:
        return
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("UPDATE animes_usuario SET score = ? WHERE id = ? AND user_id = ?",
                   (score, user_anime_id, session.current_user_id))
    conn.commit()
    cerrar_conexion(conn)


def eliminar_anime_usuario(user_anime_id):
    if session.current_user_id is None:
        return
    conn = conectar_tracker()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM animes_usuario WHERE id = ? AND user_id = ?",
                   (user_anime_id, session.current_user_id))
    conn.commit()
    cerrar_conexion(conn)
