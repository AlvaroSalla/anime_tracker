import requests
from database.queries import agregar_animes_api, obtener_animes_api_guardados
from ui.tablas import (
    mostrar_resultados_animes_api,
    mostrar_resultados_animes_api_filtrable
)


_animes_populares_cache = None


def _traer_animes(query, variables_base, total=200):
    url = "https://graphql.anilist.co"
    per_page = 50
    pagina = 1
    animes = []

    while len(animes) < total:
        variables = variables_base.copy()
        variables.update({
            "page": pagina,
            "perPage": per_page
        })

        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as error:
            print(f"No se pudo conectar con AniList: {error}")
            break
        except ValueError:
            print("AniList devolvio una respuesta invalida.")
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


def buscar_animes_api(busqueda, total=200):
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

    return _traer_animes(query, {"search": busqueda}, total)


def elegir_anime_api(busqueda):
    animes = buscar_animes_api(busqueda)
    anime_elegido = mostrar_resultados_animes_api(animes, busqueda)
    return anime_elegido


def _cargar_animes_populares(total=1000):
    print("Cargando animes populares...")
    animes = mostrar_anime_popul(total)

    if animes:
        agregar_animes_api(animes)
        return animes

    print("Mostrando animes guardados localmente.")
    animes_locales = obtener_animes_api_guardados(total)

    if not animes_locales:
        print("No hay animes disponibles localmente.")

    return animes_locales


def obtener_animes_populares(total=1000):
    global _animes_populares_cache

    if _animes_populares_cache is None:
        animes = _cargar_animes_populares(total)

        if not animes:
            return []

        _animes_populares_cache = animes

    return _animes_populares_cache[:total]


def elegir_anime_popular():
    animes = obtener_animes_populares(1000)

    if not animes:
        return None

    anime_elegido = mostrar_resultados_animes_api_filtrable(animes)
    return anime_elegido


def mostrar_anime_popul(total=200):
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

    return _traer_animes(query, {}, total)



