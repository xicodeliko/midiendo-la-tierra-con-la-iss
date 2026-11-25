"""
historias_graficos.py
---------------------
Versión "sin texto" de las historias de Instagram: los gráficos REALES del
análisis (todas las alas, todos los datos), en formato vertical 1080 x 1920,
con el tercio de arriba vacío para escribir encima con la herramienta de
texto de Instagram.

Cómo correrlo:   python historias_graficos.py
Resultado:       instagram/sin_texto/1_ilustracion.png ... 6_mapa_senal.png
"""

from datetime import timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

import historias_instagram as hi
import medir_tierra
from graficar import (CARPETA_DATOS, cargar_datos, columnas_que_terminan_en, etiqueta_corta,
                      pintar_fondo_por_luz)
from posicion_iss import RADIO_TIERRA_KM, SeguidorISS

CARPETA_SALIDA = Path(__file__).parent / "instagram" / "sin_texto"

# Zona del gráfico dentro de la historia (en proporción de la imagen):
# arriba queda libre ~30 % para tu texto; abajo ~13 % para los botones de Instagram.
ABAJO, ARRIBA = 0.15, 0.70
IZQUIERDA, ANCHO = 0.15, 0.78

# historias_instagram cambia el estilo al importarse: volvemos al estándar
# de matplotlib (fondo oscuro), para que se vea como un gráfico de análisis.
plt.rcdefaults()
plt.style.use("dark_background")
plt.rcParams.update({
    "figure.facecolor": "#101318",
    "axes.facecolor": "#101318",
    "savefig.facecolor": "#101318",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "font.size": 20,
    "axes.labelsize": 22,
    "xtick.labelsize": 18,
    "ytick.labelsize": 18,
    "legend.fontsize": 16,
})


def lienzo():
    return plt.figure(figsize=(hi.ANCHO_PX / hi.DPI, hi.ALTO_PX / hi.DPI), dpi=hi.DPI)


def ejes_apilados(fig, cantidad: int, separacion: float = 0.025):
    """Varios gráficos uno debajo del otro, compartiendo el eje del tiempo."""
    alto = (ARRIBA - ABAJO - separacion * (cantidad - 1)) / cantidad
    ejes = []
    for i in range(cantidad):
        y = ARRIBA - (i + 1) * alto - i * separacion
        ejes.append(fig.add_axes([IZQUIERDA, y, ANCHO, alto], sharex=ejes[0] if ejes else None))
    for eje in ejes[:-1]:
        eje.tick_params(labelbottom=False)
    return ejes


def lineas(eje, df, columnas, grosor: float = 1.0):
    """
    Dibuja columnas con matplotlib directo. (No usamos df.plot de pandas: maneja
    las fechas a su manera y choca con los formatos de hora de matplotlib.)
    """
    for columna in columnas:
        eje.plot(df.index, df[columna], lw=grosor, label=etiqueta_corta(columna))


def guardar(fig, nombre: str):
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = CARPETA_SALIDA / nombre
    fig.savefig(ruta, dpi=hi.DPI)  # exacto 1080 x 1920
    plt.close(fig)
    print(f"🖼️  {ruta}")


# ---------------------------------------------------------------------------
# Las historias
# ---------------------------------------------------------------------------

def ilustracion():
    """El dibujo Sol-Tierra-ISS, sin título (con el estilo de las otras historias)."""
    with plt.rc_context({"font.family": ["Avenir Next", "DejaVu Sans"]}):
        fig = hi.nueva_historia()
        hi.dibujar_sol_tierra_iss(fig.add_axes([0.0, 0.24, 1.0, 0.4]))
        guardar(fig, "1_ilustracion.png")


def un_dia(df):
    fig = lienzo()
    eje_v, eje_s, eje_f = ejes_apilados(fig, 3)

    lineas(eje_v, df, columnas_que_terminan_en(df, "_voltaje"))
    eje_v.set_ylabel("Voltaje (V)")
    eje_v.legend(ncol=4, loc="lower left", fontsize=13, framealpha=0.85)

    lineas(eje_s, df, ["sarj_babor_angulo", "sarj_estribor_angulo"], grosor=1.5)
    eje_s.set_ylabel("SARJ (°)")
    eje_s.legend(loc="lower left", fontsize=13, framealpha=0.85)

    eje_f.plot(df.index, df["fraccion_sol"], color="gold", lw=1.2)
    eje_f.set_ylabel("Fracción de Sol")
    eje_f.set_xlabel("Hora (UTC)")
    eje_f.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    eje_f.xaxis.set_major_locator(mdates.HourLocator(interval=6))

    for eje in (eje_v, eje_s, eje_f):
        pintar_fondo_por_luz(eje, df)
    guardar(fig, "2_un_dia.png")


def atardecer(df, centro):
    margen = timedelta(minutes=2)
    tramo = df.loc[centro - margen: centro + margen]

    fig = lienzo()
    eje_v, eje_f = ejes_apilados(fig, 2)

    lineas(eje_v, tramo, columnas_que_terminan_en(tramo, "_voltaje"), grosor=2)
    eje_v.set_ylabel("Voltaje (V)")
    eje_v.legend(ncol=2, loc="lower left", fontsize=14, framealpha=0.85)

    eje_f.plot(tramo.index, tramo["fraccion_sol"], color="gold", lw=3)
    eje_f.set_ylabel("Fracción de Sol (calculada)")
    eje_f.set_ylim(-0.05, 1.05)
    eje_f.set_xlabel("Hora (UTC)")
    eje_f.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    eje_f.xaxis.set_major_locator(mdates.MinuteLocator())  # una marca por minuto

    for eje in (eje_v, eje_f):
        pintar_fondo_por_luz(eje, tramo)
    guardar(fig, "3_atardecer.png")


def metodo(seguidor, momento_medido, radio_evento):
    radios = np.arange(6250, 6501, 25)
    diferencias = [(medir_tierra.hora_atardecer(seguidor, r, momento_medido) - momento_medido).total_seconds()
                   for r in radios]

    fig = lienzo()
    eje = fig.add_axes([IZQUIERDA, 0.24, ANCHO, 0.42])
    eje.axhline(0, color="gold", ls="--", lw=2, label="Atardecer medido")
    eje.plot(radios, diferencias, "o-", color="tab:cyan", lw=2.5, markersize=9,
             label="Atardecer calculado")
    eje.plot(radio_evento, 0, "o", color="tab:red", markersize=16, label=f"Coincide: {hi.miles(radio_evento)} km")
    eje.set_xlabel("Radio de la Tierra probado (km)")
    eje.set_ylabel("Diferencia con lo medido (s)")
    eje.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: hi.miles(v)))
    eje.legend(loc="upper right")
    guardar(fig, "4_metodo.png")


def resultado(mediciones):
    horas = [m[1] for m in mediciones]
    radios = [m[2] for m in mediciones]
    promedio = float(np.mean(radios))

    fig = lienzo()
    eje = fig.add_axes([0.2, 0.24, 0.73, 0.42])
    eje.axhspan(medir_tierra.RADIO_POLO_KM, medir_tierra.RADIO_ECUADOR_KM, color="tab:green",
                alpha=0.2, label="Tierra real (polo a ecuador)")
    eje.axhline(RADIO_TIERRA_KM, color="tab:green", ls="--", lw=2, label=f"Radio medio oficial ({hi.miles(RADIO_TIERRA_KM)} km)")
    eje.axhline(promedio, color="tab:cyan", lw=2, label=f"Promedio medido ({hi.miles(promedio)} km)")
    eje.plot(horas, radios, "o", color="tab:cyan", markersize=14, label="Cada atardecer")
    eje.set_ylabel("Radio de la Tierra (km)")
    eje.set_xlabel("Atardecer (UTC)")
    eje.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    eje.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    eje.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: hi.miles(v)))
    eje.set_ylim(6342, 6386)
    eje.legend(loc="upper left", fontsize=14)
    guardar(fig, "5_resultado.png")


def mapa(df):
    muestra = df.iloc[::10]  # 1 de cada 10 segundos basta para ver la traza
    fig = lienzo()
    eje = fig.add_axes([0.1, 0.27, 0.85, 0.36])
    grupos = [
        ("Al sol", (muestra["estado_luz"] == "sol") & (muestra["con_senal"] == 1), "gold"),
        ("En sombra", (muestra["estado_luz"] != "sol") & (muestra["con_senal"] == 1), "tab:blue"),
        ("Sin señal", muestra["con_senal"] == 0, "tab:red"),
    ]
    for nombre, filtro, color in grupos:
        puntos = muestra[filtro]
        eje.scatter(puntos["longitud"], puntos["latitud"], s=2, color=color, label=nombre)
    eje.set_xlim(-180, 180)
    eje.set_ylim(-60, 60)
    eje.set_aspect("equal")
    eje.set_xlabel("Longitud (°)")
    eje.set_ylabel("Latitud (°)")
    eje.set_xticks(range(-180, 181, 90))
    eje.legend(markerscale=7, loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=3, frameon=False)
    guardar(fig, "6_mapa_senal.png")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main():
    df = cargar_datos(CARPETA_DATOS)
    if df.empty:
        print("No hay datos. Copia los CSV del servidor a la carpeta datos/.")
        return

    seguidor = SeguidorISS()
    mediciones = []  # (momento predicho, momento medido, radio)
    for centro in medir_tierra.atardeceres_predichos(df):
        medido, _ = medir_tierra.medir_caida_voltaje(df, centro)
        if medido is None:
            continue
        medido = medido.to_pydatetime()
        radio = medir_tierra.radio_que_explica(seguidor, medido)
        if radio is not None:
            mediciones.append((centro, medido, radio))

    if not mediciones:
        print("Aún no hay atardeceres con señal.")
        return

    ilustracion()
    un_dia(df)
    atardecer(df, mediciones[0][0])
    metodo(seguidor, mediciones[0][1], mediciones[0][2])
    resultado(mediciones)
    mapa(df)


if __name__ == "__main__":
    main()
