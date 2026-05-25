import requests
import time
import threading
from database.queries import agregar_animes_api, obtener_animes_api_guardados
from ui.tablas import (
    mostrar_resultados_animes_api,
    mostrar_resultados_animes_api_filtrable
)


_animes_populares_cache = None
ANIMES_POPULARES_TOTAL = 2000
_sincronizacion_catalogo_activa = False


def _traer_animes(query, variables_base, total=200, esperar_rate_limit=False):
    url = "https://graphql.anilist.co"
    per_page = 50
    pagina = 1
    animes = []
    max_reintentos = 4

    while len(animes) < total:
        variables = variables_base.copy()
        variables.update({
            "page": pagina,
            "perPage": per_page
        })

        data = None

        for intento in range(max_reintentos):
            try:
                response = requests.post(
                    url,
                    json={"query": query, "variables": variables},
                    timeout=15
                )

                if response.status_code == 429:
                    if not esperar_rate_limit:
                        print(f"AniList limito las consultas en pagina {pagina}. Usando reserva local para completar.")
                        return animes[:total]

                    retry_after = response.headers.get("Retry-After")
                    try:
                        espera = int(retry_after) if retry_after is not None else 30
                    except ValueError:
                        espera = 30

                    espera = min(max(espera, 10), 90)
                    print(f"AniList limito las consultas. Sincronizacion DB continua en {espera}s...")
                    time.sleep(espera)
                    continue

                response.raise_for_status()
                data = response.json()
                break
            except requests.RequestException as error:
                if intento < max_reintentos - 1:
                    print(f"No se pudo conectar con AniList. Reintentando pagina {pagina}...")
                    continue

                print(f"No se pudo conectar con AniList: {error}")
                break
            except ValueError:
                print("AniList devolvio una respuesta invalida.")
                break

        if data is None:
            break

        if data.get("data") is None:
            print(data.get("errors", "AniList no devolvio datos."))
            break

        page = data.get("data", {}).get("Page")

        if page is None:
            print("AniList devolvio una respuesta incompleta.")
            break

        pagina_animes = page.get("media", [])
        animes.extend(pagina_animes)

        page_info = page.get("pageInfo", {})

        if not page_info.get("hasNextPage"):
            break

        pagina += 1

    return animes[:total]


def buscar_animes_api(busqueda, total=200, esperar_rate_limit=False):
    query = """
        query ($search: String, $page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                media(search: $search, type: ANIME) {
                    id
                    title {
                        romaji
                    }
                    episodes
                    status
                    nextAiringEpisode {
                        episode
                        airingAt
                    }
                    coverImage {
                        medium
                    }
                }
            }
        }
    """

    return _traer_animes(query, {"search": busqueda}, total, esperar_rate_limit=esperar_rate_limit)


def elegir_anime_api(busqueda):
    animes = buscar_animes_api(busqueda)
    anime_elegido = mostrar_resultados_animes_api(animes, busqueda)
    return anime_elegido


def _cargar_animes_populares(total=ANIMES_POPULARES_TOTAL):
    print("Cargando animes populares...")
    animes_locales = obtener_animes_api_guardados(total)

    if len(animes_locales) > 100:
        print(f"Usando {len(animes_locales)} animes desde la base local.")
        sincronizar_animes_populares_background(total)
        return animes_locales

    print("Base local insuficiente. Consultando API de AniList...")
    animes = mostrar_anime_popul(total)

    if animes:
        agregar_animes_api(animes)
        if len(animes) >= total:
            return animes

        sincronizar_animes_populares_background(total)
        animes_locales = obtener_animes_api_guardados(total)
        animes_por_id = {anime.get("id"): anime for anime in animes if anime.get("id") is not None}
        completos = animes.copy()

        for anime in animes_locales:
            anime_id = anime.get("id")
            if anime_id is not None and anime_id not in animes_por_id:
                completos.append(anime)
                animes_por_id[anime_id] = anime

            if len(completos) >= total:
                break

        return completos[:total]

    print("No hay animes disponibles.")
    return animes_locales


def obtener_animes_populares(total=ANIMES_POPULARES_TOTAL):
    global _animes_populares_cache

    if _animes_populares_cache is None:
        animes = _cargar_animes_populares(total)

        if not animes:
            return []

        _animes_populares_cache = animes

    return _animes_populares_cache[:total]


def elegir_anime_popular():
    animes = obtener_animes_populares(ANIMES_POPULARES_TOTAL)

    if not animes:
        return None

    anime_elegido = mostrar_resultados_animes_api_filtrable(animes)
    return anime_elegido


def mostrar_anime_popul(total=200, esperar_rate_limit=False):
    query = """
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                pageInfo {
                    hasNextPage
                }
                media(type: ANIME, sort: POPULARITY_DESC) {
                    id
                    title {
                        romaji
                    }
                    episodes
                    status
                    popularity
                    nextAiringEpisode {
                        episode
                        airingAt
                    }
                    coverImage {
                        medium
                    }
                }
            }
        }
    """

    return _traer_animes(query, {}, total, esperar_rate_limit=esperar_rate_limit)


def sincronizar_animes_populares(total=ANIMES_POPULARES_TOTAL):
    animes = mostrar_anime_popul(total, esperar_rate_limit=True)

    if animes:
        agregar_animes_api(animes)

    return animes


def sincronizar_animes_populares_background(total=ANIMES_POPULARES_TOTAL):
    global _sincronizacion_catalogo_activa

    if _sincronizacion_catalogo_activa:
        return

    _sincronizacion_catalogo_activa = True

    def worker():
        global _sincronizacion_catalogo_activa
        try:
            animes = sincronizar_animes_populares(total)
            if len(animes) >= total:
                print("Catalogo local actualizado con AniList.")
        finally:
            _sincronizacion_catalogo_activa = False

    threading.Thread(target=worker, daemon=True).start()



