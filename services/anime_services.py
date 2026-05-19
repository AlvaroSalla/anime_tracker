import requests
from ui.tablas import (
    mostrar_resultados_animes_api,
    mostrar_resultados_animes_api_filtrable
)


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

        response = requests.post(url, json={"query": query, "variables": variables})
        data = response.json()

        if data.get("data") is None:
            print(data.get("errors"))
            break

        pagina_animes = data["data"]["Page"]["media"]
        animes.extend(pagina_animes)

        if not data["data"]["Page"]["pageInfo"]["hasNextPage"]:
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


def elegir_anime_popular():
    animes = mostrar_anime_popul(800)
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
                    coverImage {
                        medium
                    }
                }
            }
        }
    """

    return _traer_animes(query, {}, total)
