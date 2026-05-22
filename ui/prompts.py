import os

try:
    import msvcrt
except ImportError:
    msvcrt = None


def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pedir_entero(mensaje, minimo=None, maximo=None):
    while True:
        try:
            numero = int(input(mensaje))
        except ValueError:
            print("Ingrese un numero valido.")
            continue

        if minimo is not None and numero < minimo:
            print(f"El numero no puede ser menor que {minimo}.")
        elif maximo is not None and numero > maximo:
            print(f"El numero no puede ser mayor que {maximo}.")
        else:
            return numero


def seleccionar_menu(titulo, opciones):
    if not opciones:
        return None

    if msvcrt is None:
        print(titulo)
        for indice, opcion in enumerate(opciones, start=1):
            print(f"{indice}. {opcion}")
        return pedir_entero("Ingrese una opcion: ", 1, len(opciones))

    seleccion = 0

    while True:
        limpiar_pantalla()
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
            limpiar_pantalla()
            return seleccion + 1


def seleccionar_menu_filtrable(titulo, opciones):
    if not opciones:
        return None

    if msvcrt is None:
        filtro = input("Filtrar resultados: ").strip().lower()
        opciones_filtradas = [
            (indice, opcion)
            for indice, opcion in enumerate(opciones)
            if filtro in opcion.lower() or opcion.lower() == "volver"
        ]

        if not opciones_filtradas:
            print("No hay resultados para ese filtro.")
            return None

        print(titulo)
        for indice, (_, opcion) in enumerate(opciones_filtradas, start=1):
            print(f"{indice}. {opcion}")

        seleccion = pedir_entero("Ingrese una opcion: ", 1, len(opciones_filtradas))
        return opciones_filtradas[seleccion - 1][0] + 1

    seleccion = 0
    filtro = ""

    while True:
        opciones_filtradas = [
            (indice, opcion)
            for indice, opcion in enumerate(opciones)
            if filtro.lower() in opcion.lower() or opcion.lower() == "volver"
        ]

        if seleccion >= len(opciones_filtradas):
            seleccion = 0

        limpiar_pantalla()
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
            limpiar_pantalla()
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


def pedir_estado(permitir_volver=False):
    estados = [
        "En proceso",
        "Completo",
        "Planeado",
        "En espera",
        "Abandonado"
    ]

    opciones = estados.copy()

    if permitir_volver:
        opciones.append("Volver")

    opcion = seleccionar_menu("=== ESTADOS ===", opciones)

    if permitir_volver and opcion == len(opciones):
        return None

    return estados[opcion - 1]


def pedir_opcion(mensaje):
    return pedir_entero(mensaje)


def pausar():
    input("\nPresione Enter para continuar...")


def pedir_caps_vistos(caps_totales, permitir_volver=False):
    while True:
        if permitir_volver:
            entrada = input("Capitulos vistos (v para volver): ").strip()

            if entrada.lower() == "v":
                return None

            try:
                caps_vistos = int(entrada)
            except ValueError:
                print("Ingrese un numero valido.")
                continue
        else:
            caps_vistos = pedir_entero("Capitulos vistos: ", 0)

        if caps_vistos < 0:
            print("Los capitulos vistos no pueden ser negativos.")
        elif caps_totales is not None and caps_vistos > caps_totales:
            print("No podes poner mas capitulos vistos que capitulos totales.")
        else:
            return caps_vistos


def elegir_caps_vistos(caps_totales, caps_actuales=0, permitir_volver=False):
    if caps_totales is None:
        return pedir_caps_vistos(caps_totales, permitir_volver)

    opciones = []

    for capitulo in range(caps_totales + 1):
        texto = f"{capitulo} capitulos vistos"

        if capitulo == caps_actuales:
            texto += " (actual)"

        opciones.append(texto)

    if permitir_volver:
        opciones.append("Volver")

    opcion = seleccionar_menu("=== CAPITULOS VISTOS ===", opciones)

    if permitir_volver and opcion == len(opciones):
        return None

    return opcion - 1


def pedir_score():
    return pedir_entero("Score (0-10): ", 0, 10)


def pedir_confirmacion(mensaje):
    opcion = seleccionar_menu(
        f"=== {mensaje.upper()} ===",
        [
            "Si",
            "No"
        ]
    )
    return opcion == 1

