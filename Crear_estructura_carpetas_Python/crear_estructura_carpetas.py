
import os

def crear_estructura(nombre_proyecto):
    carpetas_principales = [
        "00_{}_Datos",
        "01_{}_Udala",
        "02_{}_Grafico",
        "03_{}_Proyecto",
        "04_{}_Seguridad",
        "05_{}_Prest",
        "06_{}_Gremios",
        "07_{}_Fotos",
        "08_{}_Calidad",
        "09_{}_Residuos",
    ]

    subcarpetas_gremios = [
        "{}_JAIZKIBEL",
        "{}_SALTOKI",
        "{}_TERMALDE",
        "{}_ZERTIQ",
        "{}_PINTOR",
        "{}_CRISTALERIA",
        "{}_CARPINTERIA"
    ]

    ruta_base = nombre_proyecto
    os.makedirs(ruta_base, exist_ok=True)

    for plantilla in carpetas_principales:
        nombre_carpeta = plantilla.format(nombre_proyecto)
        ruta_carpeta = os.path.join(ruta_base, nombre_carpeta)
        os.makedirs(ruta_carpeta, exist_ok=True)

        if plantilla.startswith("06_"):
            for sub in subcarpetas_gremios:
                nombre_sub = sub.format(nombre_proyecto)
                ruta_sub = os.path.join(ruta_carpeta, nombre_sub)
                os.makedirs(ruta_sub, exist_ok=True)

    print(f"Estructura creada en: {os.path.abspath(ruta_base)}")

if __name__ == "__main__":
    nombre = input("Introduce el nombre del proyecto: ").strip()
    crear_estructura(nombre)
