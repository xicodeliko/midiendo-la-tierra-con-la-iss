"""
medir_tierra.py
---------------
QUÉ BUSCAMOS (en 2 líneas):
  Medir el tamaño de la Tierra con el "atardecer" de la ISS: el segundo exacto en que sus paneles
  dejan de recibir Sol depende de qué tan grande es la Tierra que proyecta la sombra.

CÓMO (la idea de Eratóstenes, pero con una estación espacial):
  1. En los datos REALES buscamos el segundo en que el voltaje de los paneles
     cae de golpe (~160 V -> ~151 V): ese es el atardecer MEDIDO.
  2. Con la órbita de la ISS calculamos cuándo sería el atardecer si la Tierra
     tuviera radio 6.000 km, 6.001 km, ... y buscamos el radio cuyo atardecer
     CALCULADO coincide con el MEDIDO. Ese radio es nuestra medición.
  3. Circunferencia = 2 x pi x radio.

Resultado esperado: algo cercano a 6.371 km de radio (~40.030 km de vuelta).
Si sale un poco MÁS grande, no es un error: la atmósfera también da sombra.

Cómo correrlo:   python medir_tierra.py            (tabla en pantalla)
                 python medir_tierra.py --guardar  (además: graficos/medicion_tierra.png)
Necesita: entradas a la sombra grabadas CON señal (con_senal = 1).
"""

import math
import sys
from datetime import datetime, timedelta

import pandas as pd

from graficar import CARPETA_DATOS, CARPETA_GRAFICOS, cargar_datos, columnas_que_terminan_en
from posicion_iss import RADIO_TIERRA_KM, SeguidorISS

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Ventana alrededor de cada atardecer que analizamos (segundos).
SEGUNDOS_ANTES = 180
SEGUNDOS_DESPUES = 180

# Para aceptar un atardecer, el voltaje debe caer al menos esto (V).
# Si las baterías no estaban llenas, el voltaje ya venía bajo y no hay "caída".
CAIDA_MINIMA_V = 1.0

# La telemetría llega con unos segundos de retraso. El grabador lo mide en la
# columna "retraso_s" y lo descontamos automáticamente. Este valor fijo solo se
# usa en datos antiguos que no tienen esa columna.
RETRASO_TELEMETRIA_S = 0.0

# Definimos "atardecer" como el instante en que queda la MITAD del Sol visible.
FRACCION_ATARDECER = 0.5

# Rango de radios que probamos (km).
RADIO_MINIMO, RADIO_MAXIMO = 5500.0, 7500.0

# La Tierra no es una esfera perfecta: es un poco achatada (datos WGS84).
RADIO_ECUADOR_KM = 6378.1
RADIO_POLO_KM = 6356.8


# ---------------------------------------------------------------------------
# Paso 1: encontrar el atardecer MEDIDO en los datos
# ---------------------------------------------------------------------------

def atardeceres_predichos(df: pd.DataFrame) -> list[pd.Timestamp]:
    """Momentos en que el estado pasa de "sol" a otra cosa (según el cálculo con 6.371 km)."""
    era_sol = df["estado_luz"].shift(1) == "sol"
    ya_no_es_sol = df["estado_luz"] != "sol"
    return list(df.index[era_sol & ya_no_es_sol])


def medir_caida_voltaje(df: pd.DataFrame, centro: pd.Timestamp):
    """
    Busca el segundo en que el voltaje promedio de las alas cruza la mitad
    de su caída. Devuelve (momento, explicación). Si no sirve: (None, motivo).
    """
    tramo = df.loc[centro - timedelta(seconds=SEGUNDOS_ANTES): centro + timedelta(seconds=SEGUNDOS_DESPUES)]

    if (tramo["con_senal"] == 0).any():
        return None, "hubo un corte de señal en la ventana"

    # Promedio de las 8 alas, segundo a segundo (mean(axis=1) = promedio por fila).
    voltaje = tramo[columnas_que_terminan_en(tramo, "_voltaje")].mean(axis=1)

    antes = voltaje[: centro - timedelta(seconds=30)].median()     # nivel "de día"
    despues = voltaje[centro + timedelta(seconds=60):].median()    # nivel "de noche"
    caida = antes - despues
    if caida < CAIDA_MINIMA_V:
        return None, f"el voltaje casi no cayó ({caida:.2f} V)"

    # Primer segundo en que el voltaje queda bajo la mitad de la caída.
    umbral = (antes + despues) / 2
    bajo_umbral = voltaje[voltaje < umbral]

    # El dato lo VIMOS en ese segundo, pero la ISS lo midió "retraso" segundos antes.
    retraso, origen = retraso_en(tramo)
    momento = bajo_umbral.index[0] - timedelta(seconds=retraso)
    return momento, f"cayó {caida:.1f} V ({antes:.1f} → {despues:.1f}), retraso {retraso:.1f} s {origen}"


def retraso_en(tramo: pd.DataFrame) -> tuple[float, str]:
    """Retraso de la telemetría en este tramo: el medido si existe, si no el fijo."""
    if "retraso_s" in tramo.columns and tramo["retraso_s"].notna().any():
        return float(tramo["retraso_s"].median()), "(medido)"
    return RETRASO_TELEMETRIA_S, "(fijo, sin medir)"


# ---------------------------------------------------------------------------
# Paso 2: encontrar el radio que explica ese atardecer
# ---------------------------------------------------------------------------

def hora_atardecer(seguidor: SeguidorISS, radio_km: float, cerca_de: datetime):
    """
    ¿A qué hora sería el atardecer si la Tierra tuviera este radio?
    Usamos "bisección": partimos el intervalo de tiempo por la mitad una y otra
    vez, quedándonos con la mitad donde ocurre el cruce. 20 cortes -> precisión < 1 ms.
    """
    inicio = cerca_de - timedelta(seconds=600)   # aquí todavía es de día
    fin = cerca_de + timedelta(seconds=600)      # aquí ya es de noche

    def es_de_dia(t):
        return seguidor.fraccion_sol(t, radio_km) > FRACCION_ATARDECER

    if not es_de_dia(inicio) or es_de_dia(fin):
        return None  # con este radio el atardecer queda fuera de la ventana

    for _ in range(20):
        medio = inicio + (fin - inicio) / 2
        if es_de_dia(medio):
            inicio = medio
        else:
            fin = medio
    return inicio + (fin - inicio) / 2


def radio_que_explica(seguidor: SeguidorISS, atardecer_medido: datetime):
    """
    Bisección otra vez, ahora sobre el RADIO: una Tierra más grande hace que el
    atardecer llegue ANTES. Buscamos el radio cuyo atardecer cae justo en el medido.
    """
    chico, grande = RADIO_MINIMO, RADIO_MAXIMO
    for _ in range(25):  # 25 cortes -> precisión de centímetros (de sobra)
        medio = (chico + grande) / 2
        t = hora_atardecer(seguidor, medio, atardecer_medido)
        if t is None:
            return None
        if t > atardecer_medido:
            chico = medio    # el atardecer calculado llega tarde: la Tierra debe ser más grande
        else:
            grande = medio   # llega temprano: la Tierra debe ser más chica
    return (chico + grande) / 2


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main():
    df = cargar_datos(CARPETA_DATOS)
    if df.empty:
        print("No hay datos. Copia los CSV del servidor a la carpeta datos/.")
        return

    seguidor = SeguidorISS()
    resultados = []

    print(f"\n{'atardecer (UTC)':<22}{'diferencia':>11}{'radio':>11}   detalle")
    print("-" * 75)

    for centro in atardeceres_predichos(df):
        medido, detalle = medir_caida_voltaje(df, centro)
        if medido is None:
            print(f"{centro:%Y-%m-%d %H:%M:%S}   descartado: {detalle}")
            continue

        medido = medido.to_pydatetime()
        geometrico = hora_atardecer(seguidor, RADIO_TIERRA_KM, medido)
        radio = radio_que_explica(seguidor, medido)
        if geometrico is None or radio is None:
            print(f"{medido:%Y-%m-%d %H:%M:%S}   descartado: no se pudo ajustar el radio")
            continue

        diferencia = (medido - geometrico).total_seconds()
        resultados.append((medido, radio))
        print(f"{medido:%Y-%m-%d %H:%M:%S}  {diferencia:>+8.1f} s {radio:>8.0f} km   {detalle}")

    if not resultados:
        print("\nAún no hay atardeceres útiles. Deja grabando más tiempo.")
        return

    # Resumen: promedio y dispersión (desviación estándar) de todas las mediciones.
    serie = pd.Series(dict(resultados))  # índice = hora, valor = radio
    radio = serie.mean()
    dispersion = serie.std() if len(serie) > 1 else float("nan")
    print("-" * 75)
    print(f"Atardeceres usados:   {len(serie)}")
    print(f"Radio medido:         {radio:,.0f} km  (± {dispersion:,.0f} km)")
    print(f"Circunferencia:       {2 * math.pi * radio:,.0f} km")
    print(f"Valor de referencia:  {RADIO_TIERRA_KM:,.0f} km  /  {2 * math.pi * RADIO_TIERRA_KM:,.0f} km")
    print(f"Diferencia:           {radio - RADIO_TIERRA_KM:+,.0f} km  "
          f"({(radio - RADIO_TIERRA_KM) / RADIO_TIERRA_KM:+.2%})")

    if "--guardar" in sys.argv:
        graficar_resultados(serie)


def graficar_resultados(serie: pd.Series):
    """Un punto por atardecer, comparado con el tamaño real de la Tierra."""
    import matplotlib.pyplot as plt  # solo se necesita aquí (el servidor no lo tiene)

    fig, eje = plt.subplots(figsize=(11, 5.5), layout="constrained")

    # Franja: la Tierra real mide entre 6.357 (polos) y 6.378 km (ecuador).
    eje.axhspan(RADIO_POLO_KM, RADIO_ECUADOR_KM, color="green", alpha=0.12,
                label="Tierra real: del polo al ecuador")
    eje.axhline(RADIO_TIERRA_KM, color="green", linestyle="--", label=f"Radio medio oficial ({RADIO_TIERRA_KM:,.0f} km)")

    promedio = serie.mean()
    eje.axhline(promedio, color="tab:blue", label=f"Nuestro promedio ({promedio:,.0f} km)")
    eje.plot(serie.index, serie.values, "o", color="tab:blue", markersize=9, label="Cada atardecer medido")

    eje.set_ylabel("Radio de la Tierra (km)")
    eje.set_xlabel("Atardecer (UTC)")
    eje.set_title(f"Midiendo la Tierra con la sombra de la ISS — {len(serie)} atardeceres → "
                  f"circunferencia {2 * math.pi * promedio:,.0f} km")
    eje.grid(alpha=0.3)
    eje.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0, fontsize=9)

    CARPETA_GRAFICOS.mkdir(exist_ok=True)
    ruta = CARPETA_GRAFICOS / "medicion_tierra.png"
    fig.savefig(ruta, dpi=110)
    print(f"🖼️  Guardado {ruta}")


if __name__ == "__main__":
    main()
