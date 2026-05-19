from database.conexion import conectar, cerrar_conexion


def _estado_segun_caps(caps_vistos, caps_totales, estado):
    if caps_totales is not None and caps_vistos == caps_totales:
        return "Completo"
    return estado


def _estado_al_actualizar_caps(caps_vistos, caps_totales):
    if caps_totales is None:
        return None
    if caps_vistos == caps_totales:
        return "Completo"
    return "En proceso"


def agregar_anime(nombre, vistos, totales, estado, score, api_id=None, imagen=None):
    conn = conectar()
    cursor = conn.cursor()
    estado = _estado_segun_caps(vistos, totales, estado)

    if api_id is None:
        cursor.execute("SELECT id FROM animes_api WHERE nombre = ?", (nombre,))
    else:
        cursor.execute("SELECT id FROM animes_api WHERE api_id = ?", (api_id,))

    anime = cursor.fetchone()

    if anime is None:
        cursor.execute("""INSERT INTO animes_api (
                    api_id,
                    nombre,
                    caps_totales,
                    imagen)
                    VALUES (?, ?, ?, ?)""", (api_id, nombre, totales, imagen))
        anime_id = cursor.lastrowid
    else:
        anime_id = anime[0]

    cursor.execute("SELECT id FROM user_animes WHERE anime_id = ?", (anime_id,))
    anime_usuario = cursor.fetchone()

    if anime_usuario is not None:
        print("Ese anime ya esta guardado.")
        cerrar_conexion(conn)
        return

    cursor.execute("""INSERT INTO user_animes (
                anime_id,
                caps_vistos,
                estado,
                score)
                VALUES (?, ?, ?, ?)""", (anime_id, vistos, estado, score))

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

        cursor.execute("""INSERT INTO animes_api (
                    api_id,
                    nombre,
                    caps_totales,
                    imagen)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(api_id) DO UPDATE SET
                    nombre = excluded.nombre,
                    caps_totales = excluded.caps_totales,
                    imagen = excluded.imagen""", (api_id, nombre, caps_totales, imagen))

    conn.commit()
    cerrar_conexion(conn)


def obtener_anime_usuario(user_anime_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""SELECT
                user_animes.id,
                animes_api.nombre,
                user_animes.caps_vistos,
                animes_api.caps_totales,
                user_animes.estado,
                user_animes.score
                FROM user_animes
                JOIN animes_api ON user_animes.anime_id = animes_api.id
                WHERE user_animes.id = ?""", (user_anime_id,))
    anime = cursor.fetchone()
    cerrar_conexion(conn)
    return anime


def actualizar_caps_anime(user_anime_id, caps_vistos):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""SELECT
                user_animes.caps_vistos,
                animes_api.caps_totales
                FROM user_animes
                JOIN animes_api ON user_animes.anime_id = animes_api.id
                WHERE user_animes.id = ?""", (user_anime_id,))
    anime = cursor.fetchone()

    if anime is None:
        cerrar_conexion(conn)
        return

    caps_vistos_actuales, caps_totales = anime
    estado = _estado_al_actualizar_caps(caps_vistos, caps_totales)

    if estado is not None and caps_vistos != caps_vistos_actuales:
        cursor.execute("""UPDATE user_animes
                    SET caps_vistos = ?, estado = ?
                    WHERE id = ?""", (caps_vistos, estado, user_anime_id))
    else:
        cursor.execute("""UPDATE user_animes
                    SET caps_vistos = ?
                    WHERE id = ?""", (caps_vistos, user_anime_id))

    conn.commit()
    cerrar_conexion(conn)


def actualizar_estado_anime(user_anime_id, estado, caps_vistos=None):
    conn = conectar()
    cursor = conn.cursor()

    if caps_vistos is None:
        cursor.execute("""SELECT
                    user_animes.caps_vistos,
                    animes_api.caps_totales
                    FROM user_animes
                    JOIN animes_api ON user_animes.anime_id = animes_api.id
                    WHERE user_animes.id = ?""", (user_anime_id,))
        anime = cursor.fetchone()

        if anime is None:
            cerrar_conexion(conn)
            return

        caps_vistos_actuales, caps_totales = anime
        estado = _estado_segun_caps(caps_vistos_actuales, caps_totales, estado)

        cursor.execute("""UPDATE user_animes
                    SET estado = ?
                    WHERE id = ?""", (estado, user_anime_id))
    else:
        cursor.execute("""SELECT animes_api.caps_totales
                    FROM user_animes
                    JOIN animes_api ON user_animes.anime_id = animes_api.id
                    WHERE user_animes.id = ?""", (user_anime_id,))
        anime = cursor.fetchone()

        if anime is None:
            cerrar_conexion(conn)
            return

        caps_totales = anime[0]
        estado = _estado_segun_caps(caps_vistos, caps_totales, estado)

        cursor.execute("""UPDATE user_animes
                    SET estado = ?, caps_vistos = ?
                    WHERE id = ?""", (estado, caps_vistos, user_anime_id))

    conn.commit()
    cerrar_conexion(conn)


def actualizar_score_anime(user_anime_id, score):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""UPDATE user_animes
                SET score = ?
                WHERE id = ?""", (score, user_anime_id))
    conn.commit()
    cerrar_conexion(conn)


def eliminar_anime_usuario(user_anime_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_animes WHERE id = ?", (user_anime_id,))
    conn.commit()
    cerrar_conexion(conn)
