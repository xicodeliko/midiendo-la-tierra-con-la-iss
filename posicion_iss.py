"""
posicion_iss.py
---------------
Calcula DÓNDE está la ISS y CUÁNTA luz del Sol le llega, sin depender de
ninguna API externa: solo matemática orbital.

Ingredientes:
1. TLE ("Two-Line Element"): dos líneas de texto que describen la órbita
   de un satélite. CelesTrak las publica gratis y se actualizan varias veces
   al día. Con ellas se calcula la posición de la ISS en cualquier momento.
2. Efemérides de la NASA/JPL (archivo de421.bsp): posiciones de la Tierra y
   el Sol. Se descargan una sola vez (~17 MB).
3. La librería skyfield, que hace los cálculos astronómicos.

¿Sol, penumbra o sombra?
Desde la ISS, el Sol se ve como un disco pequeño (~0,5°) y la Tierra como un
disco enorme (~140°). Medimos qué fracción del disco solar NO está tapada
por la Tierra:
    1.0           -> "sol"       (el Sol se ve completo)
    entre 0 y 1   -> "penumbra"  (la Tierra tapa una parte del Sol)
    0.0           -> "sombra"    (la Tierra tapa el Sol completo)

Prueba rápida:  python posicion_iss.py
"""

import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import certifi

# Mismo arreglo SSL que en grabar_paneles.py (necesario en algunos Mac).
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from skyfield.api import Loader, wgs84  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CARPETA_CACHE = Path(__file__).parent / "cache"
URL_TLE = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"
HORAS_ENTRE_ACTUALIZACIONES_TLE = 6

RADIO_TIERRA_KM = 6371.0   # radio medio de la Tierra
RADIO_SOL_KM = 696_000.0   # radio del Sol


# ---------------------------------------------------------------------------
# Geometría: cuánto se tapan dos discos
# ---------------------------------------------------------------------------

def area_superpuesta(r1: float, r2: float, d: float) -> float:
    """
    Área en que se superponen dos círculos de radios r1 y r2 cuyos centros
    están a distancia d. (Fórmula clásica de la "lente" entre dos círculos.)
    """
    if d >= r1 + r2:                 # no se tocan
        return 0.0
    if d <= abs(r1 - r2):            # uno está completamente dentro del otro
        return math.pi * min(r1, r2) ** 2

    parte1 = r1**2 * math.acos((d**2 + r1**2 - r2**2) / (2 * d * r1))
    parte2 = r2**2 * math.acos((d**2 + r2**2 - r1**2) / (2 * d * r2))
    parte3 = 0.5 * math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2))
    return parte1 + parte2 - parte3


def angulo_entre(v1, v2) -> float:
    """Ángulo (en radianes) entre dos vectores 3D."""
    producto = sum(a * b for a, b in zip(v1, v2))
    largo1 = math.sqrt(sum(a * a for a in v1))
    largo2 = math.sqrt(sum(b * b for b in v2))
    coseno = max(-1.0, min(1.0, producto / (largo1 * largo2)))  # evita errores de redondeo
    return math.acos(coseno)


# ---------------------------------------------------------------------------
# El seguidor de la ISS
# ---------------------------------------------------------------------------

class SeguidorISS:
    """Calcula posición e iluminación de la ISS. Mantiene su TLE al día."""

    def __init__(self):
        CARPETA_CACHE.mkdir(exist_ok=True)
        self.cargador = Loader(str(CARPETA_CACHE))  # guarda descargas en cache/
        self.ts = self.cargador.timescale()

        efemerides = self.cargador("de421.bsp")     # se descarga solo la 1ª vez
        self.tierra = efemerides["earth"]
        self.sol = efemerides["sun"]

        self.iss = None
        self.ultima_actualizacion_tle = 0.0
        self.actualizar_tle()

    def actualizar_tle(self):
        """Descarga la órbita más reciente. Si falla, sigue con la anterior."""
        try:
            satelites = self.cargador.tle_file(URL_TLE, filename="iss.tle", reload=True)
        except Exception as error:
            print(f"⚠️  No se pudo descargar el TLE ({error}); uso el guardado.")
            satelites = self.cargador.tle_file(URL_TLE, filename="iss.tle", reload=False)

        self.iss = satelites[0]
        self.ultima_actualizacion_tle = time.time()
        print(f"🛰️  Órbita (TLE) cargada, época: {self.iss.epoch.utc_strftime()}")

    def fraccion_sol(self, momento: datetime, radio_tierra_km: float = RADIO_TIERRA_KM) -> float:
        """
        Fracción del disco solar visible desde la ISS (1 = completo, 0 = tapado).

        radio_tierra_km se puede cambiar: medir_tierra.py lo usa para probar
        "¿y si la Tierra midiera 6.200 km de radio? ¿y 6.500?".
        """
        t = self.ts.from_datetime(momento)

        # Posición de la ISS respecto al centro de la Tierra (km).
        r_iss = self.iss.at(t).position.km

        # Posición del Sol respecto al centro de la Tierra (km).
        r_sol = self.tierra.at(t).observe(self.sol).position.km

        # Vectores vistos DESDE la ISS:
        hacia_sol = [s - i for s, i in zip(r_sol, r_iss)]
        hacia_tierra = [-i for i in r_iss]

        # Tamaño aparente (radio angular) de cada disco visto desde la ISS.
        dist_sol = math.sqrt(sum(c * c for c in hacia_sol))
        dist_tierra = math.sqrt(sum(c * c for c in hacia_tierra))
        radio_sol = math.asin(RADIO_SOL_KM / dist_sol)
        radio_tierra = math.asin(radio_tierra_km / dist_tierra)

        # Separación entre el centro del Sol y el centro de la Tierra.
        separacion = angulo_entre(hacia_sol, hacia_tierra)

        # Fracción visible = 1 - (parte tapada / disco completo).
        tapado = area_superpuesta(radio_sol, radio_tierra, separacion)
        return 1 - tapado / (math.pi * radio_sol**2)

    def calcular(self, momento: datetime) -> dict:
        """Devuelve posición e iluminación de la ISS en un momento dado."""
        # ¿Toca actualizar la órbita? (un TLE viejo pierde precisión)
        horas_pasadas = (time.time() - self.ultima_actualizacion_tle) / 3600
        if horas_pasadas > HORAS_ENTRE_ACTUALIZACIONES_TLE:
            self.actualizar_tle()

        fraccion_sol = self.fraccion_sol(momento)

        if fraccion_sol >= 1.0:
            estado = "sol"
        elif fraccion_sol <= 0.0:
            estado = "sombra"
        else:
            estado = "penumbra"

        iss_geocentrica = self.iss.at(self.ts.from_datetime(momento))
        lat, lon = wgs84.latlon_of(iss_geocentrica)

        return {
            "latitud": round(float(lat.degrees), 4),
            "longitud": round(float(lon.degrees), 4),
            "altitud_km": round(float(wgs84.height_of(iss_geocentrica).km), 2),
            "fraccion_sol": round(fraccion_sol, 4),
            "estado_luz": estado,
        }


# Prueba rápida: muestra dónde está la ISS ahora.
if __name__ == "__main__":
    seguidor = SeguidorISS()
    ahora = datetime.now(timezone.utc)
    print(ahora.isoformat(timespec="seconds"), seguidor.calcular(ahora))
