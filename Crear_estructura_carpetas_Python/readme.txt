# Estructurador de Proyectos Python

Esta app crea automáticamente una estructura de carpetas para nuevos proyectos, pensada especialmente para organizar diferentes áreas y gremios dentro del proyecto.

## Características

- Genera 10 carpetas principales por proyecto.
- Dentro de “Gremios” crea subcarpetas específicas para distintos gremios.
- Permite el uso de cualquier nombre de proyecto.
- Todo se crea en la ubicación local con solo ejecutar el script.

## Estructura generada

Al ejecutar el programa y proporcionar el nombre del proyecto, se crea la siguiente estructura:

<nombre_proyecto>/
├── 00_<nombre_proyecto>Datos
├── 01<nombre_proyecto>Udala
├── 02<nombre_proyecto>Grafico
├── 03<nombre_proyecto>Proyecto
├── 04<nombre_proyecto>Seguridad
├── 05<nombre_proyecto>Prest
├── 06<nombre_proyecto>_Gremios
│ ├── <nombre_proyecto>_JAIZKIBEL
│ ├── <nombre_proyecto>_SALTOKI
│ ├── <nombre_proyecto>_TERMALDE
│ ├── <nombre_proyecto>_ZERTIQ
│ ├── <nombre_proyecto>_PINTOR
│ ├── <nombre_proyecto>_CRISTALERIA
│ ├── <nombre_proyecto>CARPINTERIA
├── 07<nombre_proyecto>Fotos
├── 08<nombre_proyecto>Calidad
├── 09<nombre_proyecto>_Residuos

text

## Uso

1. Ejecuta el script en Python 3:

    ```
    python crear_estructura.py
    ```

2. Indica el nombre del proyecto cuando se solicite en consola.

3. Se generará toda la estructura de carpetas automáticamente en la ubicación actual.

## Requisitos

- Python 3.x

## Autor

Desarrollado por [Tu Nombre]

---

Este programa facilita la organización y gestión de proyectos complejos mediante una estructura clara y modular.