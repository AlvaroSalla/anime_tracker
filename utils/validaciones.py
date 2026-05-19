def validacion_texto(mensaje):
    texto = input(mensaje)
    while texto.strip() == "":
        print("ERROR! Ingrese un texto válido")
        texto = input("Ingrese nuevamente: ")
    return texto.strip()