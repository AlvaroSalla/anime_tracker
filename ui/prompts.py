import os

try:
    import msvcrt
except ImportError:
    msvcrt = None


def seleccionar_menu(titulo, opciones):
    if not opciones:
        return None

    if msvcrt is None:
        print(titulo)
        for indice, opcion in enumerate(opciones, start=1):
            print(f"{indice}. {opcion}")
        return pedir_opcion("Ingrese una opcion: ")

    seleccion = 0

    while True:
        os.system("cls")
        print(titulo)
        print("Use las flechas y Enter para elegir.\n")

        for indice, opcion in enumerate(opciones):
            cursor = ">" if indice == seleccion else " "
            print(f"{cursor} {opcion}")

        tecla = msvcrt.getch()

        if tecla in (b"\xe0", b"\x00"):
            flecha = msvcrt.getch()

            if flecha == b"H":
                seleccion = (seleccion - 1) % len(opciones)
            elif flecha == b"P":
                seleccion = (seleccion + 1) % len(opciones)
        elif tecla == b"\r":
            os.system("cls")
            return seleccion + 1


def seleccionar_menu_filtrable(titulo, opciones):
    if not opciones:
        return None

    if msvcrt is None:
        filtro = input("Filtrar resultados: ").strip().lower()
        opciones_filtradas = [
            (indice, opcion)
            for indice, opcion in enumerate(opciones)
            if filtro in opcion.lower()
        ]

        if not opciones_filtradas:
            print("No hay resultados para ese filtro.")
            return None

        print(titulo)
        for indice, (_, opcion) in enumerate(opciones_filtradas, start=1):
            print(f"{indice}. {opcion}")

        seleccion = pedir_opcion("Ingrese una opcion: ")
        return opciones_filtradas[seleccion - 1][0] + 1

    seleccion = 0
    filtro = ""

    while True:
        opciones_filtradas = [
            (indice, opcion)
            for indice, opcion in enumerate(opciones)
            if filtro.lower() in opcion.lower()
        ]

        if seleccion >= len(opciones_filtradas):
            seleccion = 0

        os.system("cls")
        print(titulo)
        print("Use flechas, escriba para filtrar, Backspace para borrar y Enter para elegir.")
        print(f"Filtro: {filtro}\n")

        if not opciones_filtradas:
            print("Sin resultados.")
        else:
            for indice, (_, opcion) in enumerate(opciones_filtradas):
                cursor = ">" if indice == seleccion else " "
                print(f"{cursor} {opcion}")

        tecla = msvcrt.getch()

        if tecla in (b"\xe0", b"\x00"):
            flecha = msvcrt.getch()

            if not opciones_filtradas:
                continue

            if flecha == b"H":
                seleccion = (seleccion - 1) % len(opciones_filtradas)
            elif flecha == b"P":
                seleccion = (seleccion + 1) % len(opciones_filtradas)
        elif tecla == b"\r" and opciones_filtradas:
            os.system("cls")
            return opciones_filtradas[seleccion][0] + 1
        elif tecla == b"\x08":
            filtro = filtro[:-1]
            seleccion = 0
        else:
            try:
                caracter = tecla.decode("mbcs")
            except UnicodeDecodeError:
                continue

            if caracter.isprintable():
                filtro += caracter
                seleccion = 0


def pedir_estado():
    estados = [
        "En proceso",
        "Completo",
        "Planeado",
        "En espera",
        "Abandonado"
    ]
    opcion = seleccionar_menu("=== ESTADOS ===", estados)
    return estados[opcion - 1]


def pedir_opcion(mensaje):
    opcion = int(input(mensaje))
    return opcion


def pausar():
    input("\nPresione Enter para continuar...")


def pedir_caps_vistos(caps_totales):
    while True:
        caps_vistos = int(input("Capitulos vistos: "))

        if caps_vistos < 0:
            print("Los capitulos vistos no pueden ser negativos.")
        elif caps_totales is not None and caps_vistos > caps_totales:
            print("No podes poner mas capitulos vistos que capitulos totales.")
        else:
            return caps_vistos


def elegir_caps_vistos(caps_totales, caps_actuales=0):
    if caps_totales is None:
        return pedir_caps_vistos(caps_totales)

    opciones = []

    for capitulo in range(caps_totales + 1):
        texto = f"{capitulo} capitulos vistos"

        if capitulo == caps_actuales:
            texto += " (actual)"

        opciones.append(texto)

    opcion = seleccionar_menu("=== CAPITULOS VISTOS ===", opciones)
    return opcion - 1


def pedir_score():
    while True:
        score = int(input("Score (0-10): "))

        if score < 0 or score > 10:
            print("El score tiene que estar entre 0 y 10.")
        else:
            return score


def pedir_confirmacion(mensaje):
    opcion = seleccionar_menu(
        f"=== {mensaje.upper()} ===",
        [
            "Si",
            "No"
        ]
    )
    return opcion == 1
