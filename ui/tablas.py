from ui.prompts import seleccionar_menu, seleccionar_menu_filtrable
from database.conexion import (
    conectar,
    cerrar_conexion
)


def _texto_caps(caps):
    if caps is None:
        return "En emision"
    return caps


def mostrar_resultados_animes_api(animes, busqueda):
    if not animes:
        print(f"No se encontraron busquedas relacionadas con {busqueda}")
        return None

    opciones = []

    for anime in animes:
        nombre = anime["title"]["romaji"]
        caps = _texto_caps(anime["episodes"])
        opciones.append(f"{nombre} - {caps} episodios")

    opcion = seleccionar_menu("=== RESULTADOS ===", opciones)
    anime_elegido = animes[opcion - 1]

    api_id = anime_elegido["id"]
    nombre = anime_elegido["title"]["romaji"]
    caps = anime_elegido["episodes"]
    imagen = anime_elegido["coverImage"]["medium"]

    return api_id, nombre, caps, imagen


def mostrar_resultados_animes_api_filtrable(animes):
    if not animes:
        print("No se encontraron animes.")
        return None

    opciones = []

    for anime in animes:
        nombre = anime["title"]["romaji"]
        caps = _texto_caps(anime["episodes"])
        opciones.append(f"{nombre} - {caps} episodios")

    opcion = seleccionar_menu_filtrable("=== RESULTADOS ===", opciones)

    if opcion is None:
        return None

    anime_elegido = animes[opcion - 1]

    api_id = anime_elegido["id"]
    nombre = anime_elegido["title"]["romaji"]
    caps = anime_elegido["episodes"]
    imagen = anime_elegido["coverImage"]["medium"]

    return api_id, nombre, caps, imagen


def obtener_animes_guardados():
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
                JOIN animes_api ON user_animes.anime_id = animes_api.id""")
    datos = cursor.fetchall()
    cerrar_conexion(conn)
    return datos


def seleccionar_anime_guardado():
    datos = obtener_animes_guardados()

    if not datos:
        print("No hay animes guardados.")
        return None

    opciones = _opciones_animes_guardados(datos)

    opcion = seleccionar_menu("=== ANIMES GUARDADOS ===", opciones)
    return datos[opcion - 1]


def _opciones_animes_guardados(datos):
    opciones = []

    for _, nombre, vistos, totales, estado, score in datos:
        totales = _texto_caps(totales)
        opciones.append(
            f"{nombre} | Vistos: {vistos}/{totales} | Estado: {estado} | Score: {score}"
        )

    return opciones


def mostrar_animes():
    datos = obtener_animes_guardados()

    if not datos:
        print("No hay animes guardados.")
        return False

    opciones = _opciones_animes_guardados(datos)
    opciones.append("Volver")
    seleccionar_menu("=== ANIMES GUARDADOS ===", opciones)
    return True
