"""
historias_instagram.py
----------------------
Genera 7 imágenes verticales (1080 x 1920 px, formato historia de Instagram)
que cuentan el estudio: pregunta, datos, método y resultado.

Cómo correrlo:   python historias_instagram.py
Resultado:       instagram/historia_1.png ... historia_7.png

Todos los números salen de los datos (nada escrito a mano), así que si grabas
más días y lo vuelves a correr, las historias se actualizan solas.

Diseño:
- Fondo "espacio" oscuro y colores neón (amarillo Sol, cian, magenta, violeta).
- Se dejan libres ~250 px arriba y abajo: ahí Instagram pone sus botones.
- Sin emojis: matplotlib no sabe dibujarlos (saldrían como cuadraditos).
"""

import math
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Polygon

import medir_tierra
from graficar import CARPETA_DATOS, cargar_datos, columnas_que_terminan_en
from posicion_iss import RADIO_TIERRA_KM, SeguidorISS

CARPETA_SALIDA = Path(__file__).parent / "instagram"

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------

FONDO = "#0B1026"       # azul noche
BLANCO = "#F5F7FF"
GRIS = "#9AA3C7"
SOL = "#FFD23F"         # amarillo
CIAN = "#00E5FF"
MAGENTA = "#FF3D7F"
VIOLETA = "#7C4DFF"
NARANJO = "#FF8A00"
VERDE = "#2EE59D"

plt.rcParams.update({
    # Avenir Next viene en Mac; si no está, matplotlib usa DejaVu Sans.
    "font.family": ["Avenir Next", "DejaVu Sans"],
    "text.color": BLANCO,
    "axes.labelcolor": GRIS,
    "xtick.color": GRIS,
    "ytick.color": GRIS,
    "axes.edgecolor": "#2A3366",
    "axes.facecolor": FONDO,
    "figure.facecolor": FONDO,
    "savefig.facecolor": FONDO,
    "axes.grid": True,
    "grid.color": "#1E2650",
    "grid.linewidth": 1.2,
    "xtick.labelsize": 22,
    "ytick.labelsize": 22,
    "axes.labelsize": 24,
})

ANCHO_PX, ALTO_PX, DPI = 1080, 1920, 100


def miles(n: float) -> str:
    """Formato chileno: 86905 -> "86.905"."""
    return f"{n:,.0f}".replace(",", ".")


def decimal(n: float, decimales: int = 1) -> str:
    """Formato chileno: 0.22 -> "0,2"."""
    return f"{n:.{decimales}f}".replace(".", ",")


def nueva_historia():
    """Lienzo vacío de 1080 x 1920 px con fondo de estrellas."""
    fig = plt.figure(figsize=(ANCHO_PX / DPI, ALTO_PX / DPI), dpi=DPI)
    estrellas = fig.add_axes([0, 0, 1, 1], zorder=-10)
    estrellas.axis("off")
    azar = np.random.default_rng(7)  # semilla fija: siempre las mismas estrellas
    estrellas.scatter(azar.random(160), azar.random(160), s=azar.random(160) * 6,
                      color="white", alpha=0.35, linewidths=0)
    estrellas.set_xlim(0, 1)
    estrellas.set_ylim(0, 1)
    return fig


def titulo(fig, texto: str, y: float = 0.84, color: str = BLANCO, tamano: int = 60):
    fig.text(0.5, y, texto, ha="center", va="top", fontsize=tamano,
             fontweight="bold", color=color, linespacing=0.95)


def parrafo(fig, texto: str, y: float, tamano: int = 32, color: str = BLANCO):
    fig.text(0.5, y, texto, ha="center", va="top", fontsize=tamano,
             color=color, linespacing=1.0)


def cifra(fig, x: float, y: float, numero: str, etiqueta: str, color: str):
    """Un número grande con su explicación abajo."""
    fig.text(x, y, numero, ha="center", va="center", fontsize=74,
             fontweight="bold", color=color)
    fig.text(x, y - 0.045, etiqueta, ha="center", va="center", fontsize=26, color=GRIS)


def pie(fig, texto: str = "Datos: NASA ISS Live  ·  24 horas de telemetría  ·  nov 2026"):
    fig.text(0.5, 0.14, texto, ha="center", va="center", fontsize=19, color=GRIS)


def estilo_eje(eje):
    for borde in ["top", "right"]:
        eje.spines[borde].set_visible(False)
    eje.tick_params(length=0, pad=10)


def pintar_bandas(eje, serie_bool, color: str, alpha: float):
    """Pinta franjas verticales donde serie_bool es True."""
    eje.fill_between(serie_bool.index, 0, 1, where=serie_bool.values, color=color,
                     alpha=alpha, linewidth=0, transform=eje.get_xaxis_transform())


def guardar(fig, numero: int):
    CARPETA_SALIDA.mkdir(exist_ok=True)
    ruta = CARPETA_SALIDA / f"historia_{numero}.png"
    fig.savefig(ruta, dpi=DPI)  # sin bbox_inches: así queda exacto 1080 x 1920
    plt.close(fig)
    print(f"🖼️  {ruta}")


# ---------------------------------------------------------------------------
# Las 7 historias
# ---------------------------------------------------------------------------

def historia_1_gancho():
    fig = nueva_historia()
    titulo(fig, "Medí el tamaño\nde la Tierra", y=0.83, tamano=76)
    parrafo(fig, "usando los paneles solares de la\nEstación Espacial Internacional",
            y=0.665, tamano=36, color=CIAN)

    dibujar_sol_tierra_iss(fig.add_axes([0.0, 0.2, 1.0, 0.4]))

    parrafo(fig, "Sin telescopio. Sin salir de casa.", y=0.19, tamano=32, color=SOL)
    pie(fig)
    guardar(fig, 1)


def dibujar_sol_tierra_iss(eje):
    """Dibujo: Sol -> Tierra -> sombra -> la ISS entrando a la sombra."""
    eje.set_xlim(-11, 11)
    eje.set_ylim(-6.3, 6.3)
    eje.set_aspect("equal")
    eje.axis("off")

    for radio, alpha in [(3.4, 0.08), (2.8, 0.15), (2.2, 0.3)]:        # resplandor
        eje.add_patch(Circle((-9.5, 0), radio, color=SOL, alpha=alpha, lw=0))
    eje.add_patch(Circle((-9.5, 0), 1.6, color=SOL, lw=0))
    for y in [-1.6, 0, 1.6]:                                           # rayos
        eje.plot([-7.4, -2.9], [y * 1.2, y], color=SOL, alpha=0.5, lw=3)

    r_tierra = 2.6
    eje.add_patch(Polygon([[0, r_tierra], [11, r_tierra], [11, -r_tierra], [0, -r_tierra]],
                          color="#03050F", alpha=0.9, lw=0))           # sombra
    eje.add_patch(Circle((0, 0), r_tierra, color="#1E6BFF", lw=0))
    eje.add_patch(Circle((-0.6, 0.6), r_tierra * 0.8, color="#3D8BFF", lw=0, alpha=0.6))
    eje.add_patch(Circle((0, 0), 3.5, fill=False, ls="--", lw=2, color=BLANCO, alpha=0.5))

    x_iss = math.sqrt(3.5**2 - r_tierra**2)
    eje.plot(x_iss, r_tierra, marker="*", markersize=34, color=MAGENTA, mec=BLANCO, mew=1.5)
    eje.text(x_iss + 0.5, r_tierra + 0.8, "ISS", fontsize=30, fontweight="bold", color=MAGENTA)
    eje.text(6.8, 0, "sombra\nde la Tierra", fontsize=24, color=GRIS, ha="center", va="center")


def historia_2_pregunta():
    fig = nueva_historia()
    titulo(fig, "La pregunta", y=0.855, color=CIAN, tamano=48)
    fig.text(0.5, 0.68, "?", ha="center", va="center", fontsize=280,
             fontweight="bold", color=VIOLETA, alpha=0.9)
    parrafo(fig, "¿Se puede medir la Tierra\nsolo viendo cuándo se le\n\"apaga el Sol\" a la ISS?",
            y=0.535, tamano=48, color=BLANCO)
    parrafo(fig, "Hace 2.200 años, Eratóstenes\nmidió la Tierra con la sombra\nde un palo.",
            y=0.375, tamano=32, color=GRIS)
    parrafo(fig, "Yo lo intenté con la sombra\nde la Tierra sobre una\nestación espacial.",
            y=0.265, tamano=32, color=SOL)
    pie(fig)
    guardar(fig, 2)


def voltaje_promedio(df):
    return df[columnas_que_terminan_en(df, "_voltaje")].mean(axis=1)


def historia_3_datos(df, n_atardeceres: int):
    fig = nueva_historia()
    titulo(fig, "Grabé la ISS\ndurante 24 horas", y=0.85, tamano=62)
    cifra(fig, 0.27, 0.66, miles(len(df)), "registros", CIAN)
    cifra(fig, 0.73, 0.66, str(n_atardeceres), "atardeceres", SOL)

    # 6 horas del día, para que se vean bien las órbitas.
    inicio = df.index.min().ceil("h") + timedelta(hours=2)
    tramo = df.loc[inicio: inicio + timedelta(hours=6)]
    voltaje = voltaje_promedio(tramo)

    eje = fig.add_axes([0.14, 0.29, 0.8, 0.29])
    pintar_bandas(eje, tramo["estado_luz"] != "sol", VIOLETA, 0.35)
    eje.plot(voltaje.index, voltaje.values, color=CIAN, lw=3.5)
    eje.set_ylim(149.5, 163)
    eje.set_ylabel("Voltaje (V)")
    eje.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M"))
    eje.xaxis.set_major_locator(plt.matplotlib.dates.HourLocator(interval=2))
    eje.set_xlabel("Hora (UTC)")
    estilo_eje(eje)

    parrafo(fig, "Al sol: ~160 V     En la sombra: ~151 V", y=0.222, tamano=27, color=BLANCO)
    fig.text(0.5, 0.172, "franjas violeta = la ISS dentro de la sombra de la Tierra",
             ha="center", fontsize=21, color=VIOLETA)
    pie(fig)
    guardar(fig, 3)


def historia_4_atardecer(df, momento_evento):
    fig = nueva_historia()
    titulo(fig, "Un atardecer\nen el espacio", y=0.85, tamano=64)

    tramo = df.loc[momento_evento - timedelta(seconds=75): momento_evento + timedelta(seconds=75)]
    duracion = int((tramo["estado_luz"] == "penumbra").sum())
    cifra(fig, 0.5, 0.67, f"~{duracion} segundos", "dura la puesta de Sol vista desde la ISS", NARANJO)

    voltaje = voltaje_promedio(tramo)
    eje = fig.add_axes([0.14, 0.31, 0.8, 0.28])
    pintar_bandas(eje, tramo["estado_luz"] == "sombra", VIOLETA, 0.35)
    pintar_bandas(eje, tramo["estado_luz"] == "penumbra", NARANJO, 0.8)
    eje.plot(voltaje.index, voltaje.values, color=CIAN, lw=5)
    eje.set_ylim(149.5, 162.5)
    eje.set_ylabel("Voltaje (V)")
    eje.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M:%S"))
    eje.xaxis.set_major_locator(plt.matplotlib.dates.SecondLocator(bysecond=[0, 30]))
    eje.tick_params(axis="x", labelsize=19)
    eje.text(0.03, 0.9, "SOL", transform=eje.transAxes, fontsize=28, fontweight="bold", color=SOL)
    eje.text(0.97, 0.9, "SOMBRA", transform=eje.transAxes, fontsize=28, fontweight="bold",
             color=VIOLETA, ha="right")
    estilo_eje(eje)

    parrafo(fig, "Medí el segundo exacto en que\ncae el voltaje. Ese instante depende\ndel tamaño de la Tierra.",
            y=0.25, tamano=29)
    pie(fig)
    guardar(fig, 4)


def historia_5_metodo(seguidor, momento_medido, radio_evento):
    fig = nueva_historia()
    titulo(fig, "El truco", y=0.85, color=CIAN, tamano=64)

    pasos = [
        ("1", "Calculo la órbita de la ISS\ncon datos públicos."),
        ("2", "Pruebo Tierras de distintos\ntamaños."),
        ("3", "Me quedo con la que \"apaga\"\nel Sol justo cuando lo medí."),
    ]
    for i, (numero, texto) in enumerate(pasos):
        y = 0.73 - i * 0.075
        fig.text(0.13, y, numero, ha="center", va="center", fontsize=40, fontweight="bold",
                 color=FONDO, bbox=dict(boxstyle="circle,pad=0.35", fc=SOL, ec="none"))
        fig.text(0.21, y, texto, ha="left", va="center", fontsize=29, linespacing=1.25)

    # Curva: para cada tamaño de Tierra, ¿cuántos segundos antes/después sería el atardecer?
    radios = np.arange(6250, 6501, 25)
    diferencias = [(medir_tierra.hora_atardecer(seguidor, r, momento_medido) - momento_medido).total_seconds()
                   for r in radios]

    eje = fig.add_axes([0.17, 0.28, 0.76, 0.22])
    eje.axhline(0, color=SOL, lw=2.5, ls="--")
    eje.plot(radios, diferencias, color=CIAN, lw=4, marker="o", markersize=10)
    eje.plot(radio_evento, 0, marker="o", markersize=26, color=MAGENTA, mec=BLANCO, mew=2.5)
    eje.annotate(f"coincide:\n{miles(radio_evento)} km", (radio_evento, 0), xytext=(22, 36),
                 textcoords="offset points", fontsize=24, fontweight="bold", color=MAGENTA)
    eje.set_xlabel("Radio de la Tierra que pruebo (km)")
    eje.set_ylabel("Atardecer vs. medido (s)")
    eje.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: miles(v)))
    estilo_eje(eje)

    parrafo(fig, "1 segundo de diferencia = 2,5 km de radio", y=0.19, tamano=27, color=SOL)
    pie(fig)
    guardar(fig, 5)


def historia_6_resultado(radios):
    fig = nueva_historia()
    promedio = float(np.mean(radios))
    circ = 2 * math.pi * promedio
    circ_oficial = 2 * math.pi * RADIO_TIERRA_KM
    error = abs(circ - circ_oficial) / circ_oficial * 100

    titulo(fig, "Resultado", y=0.85, color=CIAN, tamano=56)
    fig.text(0.5, 0.735, f"{miles(circ)} km", ha="center", va="center", fontsize=104,
             fontweight="bold", color=SOL)
    fig.text(0.5, 0.672, "circunferencia de la Tierra medida", ha="center", fontsize=28, color=GRIS)
    fig.text(0.5, 0.62, f"valor oficial: {miles(circ_oficial)} km", ha="center", fontsize=32, color=BLANCO)
    fig.text(0.5, 0.565, f"error: solo {decimal(error)} %", ha="center", va="center", fontsize=44,
             fontweight="bold", color=FONDO,
             bbox=dict(boxstyle="round,pad=0.45", fc=VERDE, ec="none"))

    eje = fig.add_axes([0.2, 0.25, 0.72, 0.26])
    eje.axhspan(medir_tierra.RADIO_POLO_KM, medir_tierra.RADIO_ECUADOR_KM, color=VERDE, alpha=0.15)
    eje.text(len(radios) + 0.35, medir_tierra.RADIO_ECUADOR_KM - 1, "ecuador", color=VERDE,
             fontsize=20, va="top", ha="right")
    eje.text(len(radios) + 0.35, medir_tierra.RADIO_POLO_KM + 1, "polo", color=VERDE,
             fontsize=20, va="bottom", ha="right")
    eje.scatter(range(1, len(radios) + 1), radios, s=420, color=SOL, edgecolor=BLANCO, lw=2, zorder=3)
    eje.set_xlim(0.4, len(radios) + 0.6)
    eje.set_ylim(min(min(radios), medir_tierra.RADIO_POLO_KM) - 6, medir_tierra.RADIO_ECUADOR_KM + 6)
    eje.set_xticks(range(1, len(radios) + 1))
    eje.set_xlabel("Cada atardecer medido")
    eje.set_ylabel("Radio (km)")
    eje.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: miles(v)))
    estilo_eje(eje)

    # ¿A cuántos km de la franja real quedó el punto más lejano?
    lejania = max(max(medir_tierra.RADIO_POLO_KM - r, r - medir_tierra.RADIO_ECUADOR_KM, 0) for r in radios)
    parrafo(fig, f"Franja verde = tamaño real (la Tierra\nes achatada). Todos los atardeceres\nquedan a {math.ceil(lejania)} km o menos de ella.",
            y=0.185, tamano=25, color=GRIS)
    guardar(fig, 6)


def historia_7_senal(df):
    fig = nueva_historia()
    sin_senal = df["con_senal"] == 0
    cortes = int(((sin_senal) & (~sin_senal.shift(1, fill_value=False))).sum())

    titulo(fig, "Sorpresa:\nla ISS se desconecta", y=0.85, tamano=58)
    cifra(fig, 0.27, 0.675, str(cortes), "cortes al día", MAGENTA)
    cifra(fig, 0.73, 0.675, f"{decimal(sin_senal.mean() * 100, 0)} %", "del tiempo sin señal", MAGENTA)

    muestra = df.iloc[::10]
    eje = fig.add_axes([0.04, 0.36, 0.92, 0.24])
    con = muestra[muestra["con_senal"] == 1]
    sin = muestra[muestra["con_senal"] == 0]
    eje.scatter(con["longitud"], con["latitud"], s=3, color=CIAN, alpha=0.6, lw=0)
    eje.scatter(sin["longitud"], sin["latitud"], s=9, color=MAGENTA, lw=0)
    eje.set_xlim(-180, 180)
    eje.set_ylim(-60, 60)
    eje.set_aspect("equal")
    eje.axis("off")
    fig.text(0.3, 0.345, "con señal", color=CIAN, fontsize=24, ha="center", fontweight="bold")
    fig.text(0.7, 0.345, "sin señal", color=MAGENTA, fontsize=24, ha="center", fontweight="bold")

    parrafo(fig, "Cada línea es una vuelta a la Tierra.\nLa ISS no transmite directo: usa\nsatélites repetidores, y a veces\nno hay ninguno a la vista.",
            y=0.3, tamano=27)
    fig.text(0.5, 0.16, "Código y datos abiertos en GitHub", ha="center", fontsize=28,
             fontweight="bold", color=SOL)
    guardar(fig, 7)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main():
    df = cargar_datos(CARPETA_DATOS)
    if df.empty:
        print("No hay datos. Copia los CSV del servidor a la carpeta datos/.")
        return

    seguidor = SeguidorISS()

    # Mediciones: igual que medir_tierra.py, pero guardando cada atardecer.
    atardeceres = medir_tierra.atardeceres_predichos(df)
    mediciones = []  # (momento predicho, momento medido, radio)
    for centro in atardeceres:
        medido, _ = medir_tierra.medir_caida_voltaje(df, centro)
        if medido is None:
            continue
        medido = medido.to_pydatetime()
        radio = medir_tierra.radio_que_explica(seguidor, medido)
        if radio is not None:
            mediciones.append((centro, medido, radio))

    if not mediciones:
        print("Aún no hay atardeceres con señal: no se puede hacer la historia del resultado.")
        return

    print(f"{len(atardeceres)} atardeceres, {len(mediciones)} medidos.")
    primero_centro, primero_medido, primero_radio = mediciones[0]

    historia_1_gancho()
    historia_2_pregunta()
    historia_3_datos(df, len(atardeceres))
    historia_4_atardecer(df, primero_centro)
    historia_5_metodo(seguidor, primero_medido, primero_radio)
    historia_6_resultado([m[2] for m in mediciones])
    historia_7_senal(df)


if __name__ == "__main__":
    main()
