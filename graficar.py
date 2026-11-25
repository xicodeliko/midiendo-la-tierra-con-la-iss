"""
graficar.py
-----------
Lee todos los CSV de datos/ y hace 2 figuras:

1. Vista general: corriente, voltaje, ángulo SARJ y fracción de Sol visible,
   con el fondo pintado según la luz:  blanco = sol,
   naranjo = penumbra, gris = sombra, rayado azul = sin señal.
2. Zoom a una entrada a la sombra: compara segundo a segundo lo que PREDICE
   la geometría (fracción de Sol) con lo que MIDEN los paneles (voltaje).

Ojo: los sensores de corriente públicos ("Drive Current") marcaban 0 tanto
al sol como en sombra en nuestras pruebas. Se grafican igual por si cambian,
pero la variable que reacciona a la luz es el voltaje.

Sin señal (con_senal = 0): varias veces al día la ISS queda sin cobertura de
los satélites repetidores (TDRS) y la NASA deja de enviar datos. El grabador
sigue escribiendo filas, pero los sensores quedan CONGELADOS en su último
valor. Aquí los borramos (NaN) para que el gráfico muestre un hueco en vez
de una "meseta" falsa. La posición y la luz sí son válidas: son calculadas.

3. Mapa: por dónde pasó la ISS, de día o de noche, y dónde perdió la señal.

Cómo correrlo:
    python graficar.py              -> abre las ventanas con los gráficos
    python graficar.py --guardar    -> los guarda como PNG en graficos/

Tip: con 1 fila por segundo, un día son ~86.400 filas. Si copias los CSV del
servidor a tu PC (carpeta datos/), este script los lee todos juntos.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from sensores import SENSORES

CARPETA_DATOS = Path(__file__).parent / "datos"
CARPETA_GRAFICOS = Path(__file__).parent / "graficos"

# Contornos de los continentes: Natural Earth 1:110m (dominio público,
# https://www.naturalearthdata.com). Es un GeoJSON: polígonos de [lon, lat].
ARCHIVO_CONTINENTES = Path(__file__).parent / "mapa" / "continentes_110m.geojson"
MINUTOS_ALREDEDOR_DEL_ZOOM = 3


def cargar_datos(carpeta: Path) -> pd.DataFrame:
    """
    Lee y une todos los paneles_*.csv (o .csv.gz comprimidos) en una sola tabla.
    Si un archivo está en las dos versiones, usa solo una para no duplicar filas.
    """
    por_nombre = {}
    for archivo in sorted(carpeta.glob("paneles_*.csv*")):
        nombre = archivo.name.removesuffix(".gz")   # "x.csv.gz" y "x.csv" -> "x.csv"
        por_nombre.setdefault(nombre, archivo)      # setdefault: se queda con el primero
    archivos = list(por_nombre.values())
    if not archivos:
        return pd.DataFrame()

    # pd.concat "apila" varias tablas una debajo de la otra.
    # read_csv descomprime los .gz solo, sin que hagamos nada.
    df = pd.concat((pd.read_csv(a) for a in archivos), ignore_index=True)
    df["hora_utc"] = pd.to_datetime(df["hora_utc"])
    df = df.set_index("hora_utc").sort_index()

    # Sin señal = valores congelados -> los reemplazamos por NaN ("no hay dato").
    # pandas y matplotlib ignoran los NaN: no entran en promedios y no se dibujan.
    # (retraso_s también: sin señal, el retraso que queda anotado es viejo).
    columnas_sensores = [c for c in [*SENSORES.values(), "retraso_s"] if c in df.columns]
    df.loc[df["con_senal"] == 0, columnas_sensores] = float("nan")
    return df


def pintar_fondo_por_luz(eje, df: pd.DataFrame):
    """Pinta el fondo: naranjo = penumbra, gris = sombra, rayado azul = sin señal."""
    # get_xaxis_transform: el eje Y va de 0 a 1 = de abajo a arriba del gráfico
    abajo_a_arriba = eje.get_xaxis_transform()

    for estado, color in [("penumbra", "orange"), ("sombra", "0.6")]:
        eje.fill_between(
            df.index, 0, 1,
            where=df["estado_luz"] == estado,
            color=color, alpha=0.3, linewidth=0,
            transform=abajo_a_arriba,
        )

    # hatch="///" dibuja rayas diagonales; facecolor="none" deja ver el color de abajo.
    eje.fill_between(
        df.index, 0, 1,
        where=df["con_senal"] == 0,
        facecolor="none", edgecolor="tab:blue", hatch="///", alpha=0.4, linewidth=0,
        transform=abajo_a_arriba,
    )


def columnas_que_terminan_en(df: pd.DataFrame, final: str) -> list[str]:
    return [c for c in df.columns if c.endswith(final)]


def etiqueta_corta(columna: str) -> str:
    """Nombre corto para la leyenda: "ala_1A_voltaje" -> "Ala 1A", "sarj_babor_angulo" -> "SARJ babor"."""
    partes = columna.split("_")
    if partes[0] == "ala":
        return f"Ala {partes[1]}"
    if partes[0] == "sarj":
        return f"SARJ {partes[1]}"
    if columna == "fraccion_sol":
        return "Fracción de Sol"
    return columna.replace("_", " ")


def leyenda_afuera(eje, separacion: float = 1.01):
    """Pone la leyenda a la DERECHA del gráfico, para que no tape las curvas."""
    # bbox_to_anchor=(x, y): dónde se ancla la leyenda, en proporción del eje
    # (1.0 = borde derecho). loc="upper left" = la esquina de la leyenda que se ancla.
    eje.legend(fontsize=8, loc="upper left", bbox_to_anchor=(separacion, 1), borderaxespad=0)


def dibujar(eje, df: pd.DataFrame, columnas: list[str]):
    """Dibuja las columnas usando nombres cortos en la leyenda."""
    df[columnas].rename(columns=etiqueta_corta).plot(ax=eje, linewidth=0.8)


def figura_general(df: pd.DataFrame):
    # layout="constrained" reserva espacio automáticamente para las leyendas de afuera.
    fig, ejes = plt.subplots(4, 1, figsize=(14, 10), sharex=True, layout="constrained")

    paneles = [
        (ejes[0], columnas_que_terminan_en(df, "_corriente"), "Corriente (A)"),
        (ejes[1], columnas_que_terminan_en(df, "_voltaje"), "Voltaje (V)"),
        (ejes[2], ["sarj_babor_angulo", "sarj_estribor_angulo"], "SARJ (°)"),
        (ejes[3], ["fraccion_sol"], "Fracción de Sol"),
    ]
    for eje, columnas, titulo in paneles:
        dibujar(eje, df, columnas)
        pintar_fondo_por_luz(eje, df)
        eje.set_ylabel(titulo)
        leyenda_afuera(eje)
        eje.grid(alpha=0.3)

    ejes[0].set_title("Paneles solares de la ISS  (naranjo = penumbra, gris = sombra, rayado = sin señal)")
    ejes[-1].set_xlabel("Hora (UTC)")


def figura_zoom_penumbra(df: pd.DataFrame) -> bool:
    """Busca la primera entrada a la sombra con señal en toda la ventana y la muestra."""
    # shift(1) = el valor de la fila anterior. Buscamos filas donde el estado
    # anterior era "sol" y el actual ya no lo es: ahí empieza la penumbra.
    era_sol = df["estado_luz"].shift(1) == "sol"
    ya_no_es_sol = df["estado_luz"] != "sol"
    # & = "y" lógico, fila por fila: ambas condiciones deben cumplirse.
    entradas = df.index[era_sol & ya_no_es_sol]
    margen = pd.Timedelta(minutes=MINUTOS_ALREDEDOR_DEL_ZOOM)

    # Elegimos la primera entrada cuya ventana COMPLETA tiene señal.
    for centro in entradas:
        tramo = df.loc[centro - margen: centro + margen]
        if (tramo["con_senal"] == 1).all():
            break
    else:  # el "else" de un for se ejecuta si el for terminó sin "break"
        print("Aún no hay ninguna entrada a la sombra grabada CON señal. Graba más tiempo.")
        return False

    fig, eje_voltaje = plt.subplots(figsize=(12, 5), layout="constrained")
    dibujar(eje_voltaje, tramo, columnas_que_terminan_en(tramo, "_voltaje"))
    eje_voltaje.set_ylabel("Voltaje medido (V)")
    pintar_fondo_por_luz(eje_voltaje, tramo)

    # twinx(): un segundo eje Y a la derecha, compartiendo el tiempo.
    eje_sol = eje_voltaje.twinx()
    eje_sol.plot(tramo.index, tramo["fraccion_sol"], "k--", linewidth=2, label="fracción de Sol (calculada)")
    eje_sol.set_ylabel("Fracción de Sol calculada")
    eje_sol.set_ylim(-0.05, 1.05)
    eje_sol.legend(loc="lower left")

    eje_voltaje.set_title(f"Entrada a la sombra — {centro:%Y-%m-%d %H:%M:%S} UTC")
    eje_voltaje.set_xlabel("Hora (UTC)")
    # Más separación: a la derecha también está el eje de la fracción de Sol.
    leyenda_afuera(eje_voltaje, separacion=1.09)
    return True


def dibujar_continentes(eje, relleno: str = "0.88", borde: str = "0.6"):
    """Dibuja los continentes de fondo (debajo de la traza de la ISS)."""
    datos = json.loads(ARCHIVO_CONTINENTES.read_text(encoding="utf-8"))
    for pais in datos["features"]:
        # Un polígono GeoJSON = [contorno exterior, agujeros...]; dibujamos el exterior.
        contorno = pais["geometry"]["coordinates"][0]
        longitudes = [punto[0] for punto in contorno]
        latitudes = [punto[1] for punto in contorno]
        eje.fill(longitudes, latitudes, facecolor=relleno, edgecolor=borde, linewidth=0.6, zorder=0)


def figura_mapa(df: pd.DataFrame):
    """
    Traza de la ISS sobre la Tierra (longitud vs latitud), con los continentes de fondo.
    """
    # Con 86.400 puntos el gráfico se pone lento: tomamos 1 de cada 10 segundos.
    muestra = df.iloc[::10]

    fig, eje = plt.subplots(figsize=(13, 6.5), layout="constrained")
    dibujar_continentes(eje)
    grupos = [
        ("Al sol", (muestra["estado_luz"] == "sol") & (muestra["con_senal"] == 1), "gold"),
        ("En sombra", (muestra["estado_luz"] != "sol") & (muestra["con_senal"] == 1), "midnightblue"),
        ("Sin señal", muestra["con_senal"] == 0, "red"),
    ]
    for nombre, filtro, color in grupos:
        puntos = muestra[filtro]
        eje.scatter(puntos["longitud"], puntos["latitud"], s=2, color=color, label=nombre)

    eje.set_xlim(-180, 180)
    eje.set_ylim(-90, 90)
    eje.set_xlabel("Longitud (°)")
    eje.set_ylabel("Latitud (°)")
    eje.set_title("Por dónde pasó la ISS: de día, de noche y dónde perdió la señal")
    eje.grid(alpha=0.3)
    eje.set_aspect("equal")  # que 1° de latitud mida lo mismo que 1° de longitud
    eje.legend(markerscale=6, loc="lower left")


def mostrar_o_guardar(nombres: list[str]):
    """Con --guardar escribe PNG en graficos/; si no, abre las ventanas."""
    if "--guardar" not in sys.argv:
        plt.show()
        return
    CARPETA_GRAFICOS.mkdir(exist_ok=True)
    # plt.get_fignums() = números de las figuras abiertas, en orden de creación.
    for numero, nombre in zip(plt.get_fignums(), nombres):
        ruta = CARPETA_GRAFICOS / nombre
        plt.figure(numero).savefig(ruta, dpi=110)
        print(f"🖼️  Guardado {ruta}")
    plt.close("all")


def main():
    df = cargar_datos(CARPETA_DATOS)
    if df.empty:
        print("No hay datos todavía. Corre primero: python grabar_paneles.py")
        return

    print(f"Datos desde {df.index.min()} hasta {df.index.max()}  ({len(df)} filas)\n")

    # ¿Cuánto tiempo pasó la ISS en cada estado? (1 fila = 1 segundo)
    print("Segundos en cada estado de luz:")
    print(df["estado_luz"].value_counts(), "\n")

    # mean() de una columna de 0 y 1 = proporción de unos.
    sin_senal = 1 - df["con_senal"].mean()
    print(f"Tiempo sin señal (valores descartados): {sin_senal:.1%}\n")

    # Voltaje promedio de cada ala según la luz: aquí se ve el efecto.
    voltajes = columnas_que_terminan_en(df, "_voltaje")
    print("Voltaje promedio por estado de luz (V):")
    print(df.groupby("estado_luz")[voltajes].mean().round(2).T)

    nombres = ["vista_general.png"]
    figura_general(df)
    if figura_zoom_penumbra(df):
        nombres.append("zoom_sombra.png")
    figura_mapa(df)
    nombres.append("mapa_senal.png")
    mostrar_o_guardar(nombres)


if __name__ == "__main__":
    main()
