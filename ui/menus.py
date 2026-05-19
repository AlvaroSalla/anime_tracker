from database.queries import (
    agregar_anime,
    actualizar_caps_anime,
    actualizar_estado_anime,
    actualizar_score_anime,
    eliminar_anime_usuario,
    obtener_anime_usuario
)
from ui.tablas import mostrar_animes, seleccionar_anime_guardado
from ui.prompts import (
    seleccionar_menu,
    pedir_estado,
    pedir_caps_vistos,
    elegir_caps_vistos,
    pedir_score,
    pedir_confirmacion,
    pausar
)
from services.anime_services import elegir_anime_popular


def menu_principal():
    return seleccionar_menu(
        "=== ANIME TRACKER ===",
        [
            "Agregar anime",
            "Ver animes guardados",
            "Actualizar anime",
            "Salir"
        ]
    )


def menu_actualizar_anime():
    return seleccionar_menu(
        "=== ACTUALIZAR ANIME ===",
        [
            "Actualizar capitulos vistos",
            "Cambiar estado",
            "Cambiar score",
            "Eliminar anime",
            "Volver"
        ]
    )


def pedir_estado_actualizable(caps_vistos_actuales, caps_totales):
    while True:
        estado = pedir_estado()

        if (
            caps_totales is not None
            and caps_vistos_actuales == caps_totales
            and estado != "Completo"
        ):
            print(
                "No se puede cambiar el estado sin cambiar los capitulos: "
                "ya tiene todos los capitulos vistos."
            )
            pausar()
            continue

        return estado


def actualizar_anime():
    anime_seleccionado = seleccionar_anime_guardado()

    if anime_seleccionado is None:
        pausar()
        return

    user_anime_id = anime_seleccionado[0]
    anime = obtener_anime_usuario(user_anime_id)
    _, nombre, caps_vistos_actuales, caps_totales, _, _ = anime

    while True:
        opcion = menu_actualizar_anime()

        match opcion:
            case 1:
                caps_vistos = elegir_caps_vistos(caps_totales, caps_vistos_actuales)
                caps_cambiaron = caps_vistos != caps_vistos_actuales
                actualizar_caps_anime(user_anime_id, caps_vistos)

                if caps_cambiaron and caps_totales is not None and caps_vistos == caps_totales:
                    estado_actual = "Completo"
                elif caps_cambiaron and caps_totales is not None:
                    estado_actual = "En proceso"
                else:
                    estado_actual = None

                caps_vistos_actuales = caps_vistos

                if estado_actual == "Completo":
                    print("Capitulos actualizados. Estado cambiado a Completo.")
                elif estado_actual == "En proceso":
                    print("Capitulos actualizados. Estado cambiado a En proceso.")
                else:
                    print("Capitulos actualizados.")

                pausar()
            case 2:
                estado = pedir_estado_actualizable(caps_vistos_actuales, caps_totales)

                if estado == "Completo" and caps_totales is not None:
                    actualizar_estado_anime(user_anime_id, estado, caps_totales)
                    caps_vistos_actuales = caps_totales
                elif estado == "Completo":
                    caps_vistos = pedir_caps_vistos(caps_totales)
                    actualizar_estado_anime(user_anime_id, estado, caps_vistos)
                    caps_vistos_actuales = caps_vistos
                else:
                    actualizar_estado_anime(user_anime_id, estado)

                print("Estado actualizado.")
                pausar()
            case 3:
                score = pedir_score()
                actualizar_score_anime(user_anime_id, score)
                print("Score actualizado.")
                pausar()
            case 4:
                if pedir_confirmacion(f"Eliminar {nombre}"):
                    eliminar_anime_usuario(user_anime_id)
                    print("Anime eliminado.")
                    pausar()
                    break
            case 5:
                break
            case _:
                print("error")


def ejecutar_menu():
    while True:
        opcion = menu_principal()

        match opcion:
            case 1:
                anime_elegido = elegir_anime_popular()
                if anime_elegido == None:
                    pausar()
                    continue
                else:
                    api_id, nombre, caps, img = anime_elegido
                    estado = pedir_estado()

                    if estado == "Completo" and caps is not None:
                        caps_vistos = caps
                    else:
                        caps_vistos = pedir_caps_vistos(caps)

                    agregar_anime(nombre, caps_vistos, caps, estado, 0, api_id, img)
            case 2:
                if not mostrar_animes():
                    pausar()
            case 3:
                actualizar_anime()
            case 4:
                print("Saliendo")
                break
            case _:
                print("error")
