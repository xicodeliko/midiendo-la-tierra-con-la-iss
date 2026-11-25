"""
grabar_paneles.py
-----------------
Se conecta a la telemetría EN VIVO de la Estación Espacial Internacional (ISS)
y guarda, una vez por segundo, una "foto" con:
  - los 26 sensores de los paneles solares (sensores.py)
  - la posición de la ISS y cuánta luz del Sol recibe (posicion_iss.py)
  - si la ISS tiene señal con la Tierra (si no, los valores están congelados)
  - el retraso con que llegan los datos (hora de la NASA vs. reloj del servidor)

Está pensado para correr 24/7 en un servidor: genera un CSV por día en
datos/paneles_AAAA-MM-DD.csv y escribe en pantalla solo un resumen por minuto.

Cómo correrlo:   python grabar_paneles.py        (Ctrl + C para detener)

¿Cómo funciona por dentro?
1. La NASA publica la telemetría en un servidor "Lightstreamer" que nos
   AVISA cada vez que un sensor cambia (streaming). Llegan ~190 avisos por
   segundo, demasiados para guardarlos todos (~1 GB al día).
2. Por eso los avisos solo actualizan una "pizarra" en memoria con el
   último valor de cada sensor (clase EstadoISS).
3. El programa principal, cada 1 segundo, copia la pizarra, le agrega la
   posición e iluminación de la ISS y escribe UNA fila en el CSV (~25 MB/día).
"""

import csv
import os
import signal
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import certifi

# Arreglo SSL: en Mac, el Python descargado de python.org no trae los
# certificados que validan conexiones seguras (https), y la conexión falla con
# "CERTIFICATE_VERIFY_FAILED". certifi trae esos certificados; aquí le decimos
# a Python que los use. Debe ir ANTES de importar lightstreamer.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from lightstreamer.client import LightstreamerClient, Subscription, SubscriptionListener  # noqa: E402

from posicion_iss import SeguidorISS  # noqa: E402
from sensores import SENSORES  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

SERVIDOR = "https://push.lightstreamer.com"
ADAPTER = "ISSLIVE"

CARPETA_DATOS = Path(__file__).parent / "datos"
SEGUNDOS_ENTRE_FILAS = 1      # resolución del CSV (la penumbra dura ~9 s)
SEGUNDOS_ENTRE_RESUMENES = 60  # cada cuánto mostrar un resumen en pantalla

# Sensor especial de la NASA que indica si hay señal con la ISS.
# Su campo "Status.Class" vale "24" cuando hay señal (dato del proyecto ISS Mimic).
SENSOR_SENAL = "TIME_000001"

# Para el retraso usamos la mediana de los últimos N avisos (la mediana ignora
# los valores raros mejor que el promedio).
AVISOS_PARA_RETRASO = 50

# Orden fijo de las columnas del CSV ("formato ancho": una columna por dato).
COLUMNAS_POSICION = ["latitud", "longitud", "altitud_km", "fraccion_sol", "estado_luz"]
COLUMNAS_SENSORES = list(SENSORES.values())
COLUMNAS = ["hora_utc", *COLUMNAS_POSICION, "con_senal", "retraso_s", *COLUMNAS_SENSORES]


def hora_nasa_a_utc(horas: float, referencia: datetime) -> datetime:
    """
    La NASA marca cada dato con "horas desde el 31 de diciembre del año anterior"
    (ej: 7873.84 = 24 de noviembre, ~01:50 UTC). Lo convertimos a fecha y hora normal.
    """
    base = datetime(referencia.year - 1, 12, 31, tzinfo=timezone.utc)
    resultado = base + timedelta(hours=horas)
    # Caso borde de Año Nuevo: un dato del 31/12 que llega el 1/1 quedaría un año adelante.
    if resultado - referencia > timedelta(days=180):
        resultado = resultado.replace(year=resultado.year - 1)
    return resultado


# ---------------------------------------------------------------------------
# La "pizarra": último valor conocido de cada sensor
# ---------------------------------------------------------------------------

class EstadoISS:
    """
    Los datos llegan en un hilo (thread) de Lightstreamer y se leen desde el
    hilo principal. Un Lock ("candado") evita que ambos toquen la pizarra al
    mismo tiempo y se lea un dato a medio escribir.
    """

    def __init__(self):
        self.candado = threading.Lock()
        self.valores = {}          # nombre_sensor -> último valor
        self.con_senal = False
        self.avisos_recibidos = 0  # para el resumen por minuto
        # deque con maxlen = "fila" que bota el más antiguo al llenarse.
        self.retrasos = deque(maxlen=AVISOS_PARA_RETRASO)

    def guardar_valor(self, nombre: str, valor: str):
        with self.candado:
            self.valores[nombre] = valor
            self.avisos_recibidos += 1

    def guardar_senal(self, hay_senal: bool):
        with self.candado:
            self.con_senal = hay_senal

    def guardar_retraso(self, segundos: float):
        with self.candado:
            # Sin señal, los datos que llegan son viejos: no sirven para medir retraso.
            if self.con_senal:
                self.retrasos.append(segundos)

    def foto(self) -> tuple[dict, bool, float | None]:
        """Devuelve una COPIA de los valores actuales (para escribirla tranquilos)."""
        with self.candado:
            retraso = statistics.median(self.retrasos) if self.retrasos else None
            return dict(self.valores), self.con_senal, retraso


# ---------------------------------------------------------------------------
# Listeners: reciben los avisos de Lightstreamer y actualizan la pizarra
# ---------------------------------------------------------------------------

class ListenerSensores(SubscriptionListener):
    """Se ejecuta cada vez que cambia un sensor de los paneles."""

    def __init__(self, estado: EstadoISS):
        super().__init__()
        self.estado = estado

    def onSubscription(self):
        print("✅ Suscrito a los sensores de los paneles.", flush=True)

    def onSubscriptionError(self, code, message):
        print(f"❌ Error de suscripción ({code}): {message}", flush=True)

    def onItemUpdate(self, update):
        llegada = datetime.now(timezone.utc)
        nombre = SENSORES[update.getItemName()]  # "S4000001" -> "ala_1A_voltaje"
        self.estado.guardar_valor(nombre, update.getValue("Value"))

        # Retraso = cuándo llegó el dato - cuándo lo marcó la NASA.
        marca_nasa = update.getValue("TimeStamp")
        if marca_nasa:
            hora_nasa = hora_nasa_a_utc(float(marca_nasa), llegada)
            self.estado.guardar_retraso((llegada - hora_nasa).total_seconds())


class ListenerSenal(SubscriptionListener):
    """Se ejecuta cada vez que cambia el estado de la señal con la ISS."""

    def __init__(self, estado: EstadoISS):
        super().__init__()
        self.estado = estado

    def onItemUpdate(self, update):
        hay_senal = update.getValue("Status.Class") == "24"
        self.estado.guardar_senal(hay_senal)


# ---------------------------------------------------------------------------
# Escritura de CSV: un archivo por día
# ---------------------------------------------------------------------------

class EscritorDiario:
    """Escribe filas en datos/paneles_AAAA-MM-DD.csv y cambia de archivo a medianoche UTC."""

    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.carpeta.mkdir(exist_ok=True)
        self.fecha_actual = None
        self.archivo = None
        self.escritor = None

    def escribir(self, momento: datetime, fila: dict):
        fecha = momento.strftime("%Y-%m-%d")
        if fecha != self.fecha_actual:       # empezó un día nuevo (o es la 1ª fila)
            self._abrir_archivo(fecha)
        self.escritor.writerow(fila)
        self.archivo.flush()                 # a disco YA, por si se corta la luz

    def _abrir_archivo(self, fecha: str):
        self.cerrar()
        ruta = self._ruta_compatible(fecha)
        archivo_es_nuevo = not ruta.exists()
        # Modo "a" (append): si el programa se reinicia, sigue en el mismo archivo.
        self.archivo = open(ruta, "a", newline="", encoding="utf-8")
        # DictWriter escribe diccionarios respetando el orden de COLUMNAS.
        self.escritor = csv.DictWriter(self.archivo, fieldnames=COLUMNAS)
        if archivo_es_nuevo:
            self.escritor.writeheader()
        self.fecha_actual = fecha
        print(f"📄 Escribiendo en {ruta}", flush=True)

    def _ruta_compatible(self, fecha: str) -> Path:
        """
        Si el CSV del día ya existe pero con OTRAS columnas (porque cambiamos el
        programa), no podemos seguir escribiendo en él: las filas no calzarían.
        En ese caso usamos paneles_FECHA_2.csv, _3.csv... (graficar.py los lee todos).
        """
        encabezado = ",".join(COLUMNAS)
        ruta = self.carpeta / f"paneles_{fecha}.csv"
        numero = 1
        while ruta.exists():
            with open(ruta, encoding="utf-8") as f:
                if f.readline().strip() == encabezado:
                    return ruta  # mismas columnas: seguimos en este archivo
            numero += 1
            ruta = self.carpeta / f"paneles_{fecha}_{numero}.csv"
        return ruta

    def cerrar(self):
        if self.archivo:
            self.archivo.close()


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def detener(*_):
    """El servidor (systemctl stop) avisa con la señal SIGTERM; la tratamos como Ctrl + C."""
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, detener)

    estado = EstadoISS()
    seguidor = SeguidorISS()
    escritor = EscritorDiario(CARPETA_DATOS)

    # Conexión con la NASA. Si se corta, la librería reintenta sola.
    cliente = LightstreamerClient(SERVIDOR, ADAPTER)

    sub_sensores = Subscription("MERGE", list(SENSORES.keys()), ["Value", "TimeStamp"])
    sub_sensores.addListener(ListenerSensores(estado))

    sub_senal = Subscription("MERGE", [SENSOR_SENAL], ["Status.Class"])
    sub_senal.addListener(ListenerSenal(estado))

    cliente.subscribe(sub_sensores)
    cliente.subscribe(sub_senal)
    cliente.connect()
    print("📡 Conectando a la ISS... (Ctrl + C para detener)", flush=True)

    filas_escritas = 0
    ultimo_resumen = time.monotonic()

    try:
        while True:
            # Esperamos hasta el inicio del próximo segundo "redondo", así las
            # filas quedan en 12:00:00, 12:00:01... y no en 12:00:00.37.
            time.sleep(SEGUNDOS_ENTRE_FILAS - (time.time() % SEGUNDOS_ENTRE_FILAS))

            ahora = datetime.now(timezone.utc).replace(microsecond=0)
            valores, con_senal, retraso = estado.foto()
            if not valores:
                continue  # aún no llega ningún dato: no escribimos filas vacías

            posicion = seguidor.calcular(ahora)
            fila = {
                "hora_utc": ahora.isoformat(),
                **posicion,                  # ** "desarma" el diccionario dentro de otro
                "con_senal": int(con_senal),
                "retraso_s": "" if retraso is None else round(retraso, 2),
                **valores,
            }
            escritor.escribir(ahora, fila)
            filas_escritas += 1

            # Resumen cada minuto (en un servidor no queremos 190 líneas por segundo).
            if time.monotonic() - ultimo_resumen >= SEGUNDOS_ENTRE_RESUMENES:
                print(
                    f"[{ahora:%H:%M:%S}] filas={filas_escritas} "
                    f"avisos={estado.avisos_recibidos} "
                    f"conexión={cliente.getStatus()} señal={'sí' if con_senal else 'no'} "
                    f"luz={posicion['estado_luz']} "
                    f"retraso={'?' if retraso is None else f'{retraso:.1f}s'} "
                    f"voltaje_1A={valores.get('ala_1A_voltaje', '?')}",
                    flush=True,  # flush: que aparezca altiro en el log del servidor
                )
                ultimo_resumen = time.monotonic()

    except KeyboardInterrupt:
        # Ctrl + C o "systemctl stop" (vía detener()): cerramos ordenado.
        print("\n🛑 Deteniendo...", flush=True)
    finally:
        cliente.disconnect()
        escritor.cerrar()
        print(f"💾 {filas_escritas} filas guardadas en {CARPETA_DATOS}", flush=True)


# main() solo se ejecuta si corres este archivo directamente.
if __name__ == "__main__":
    main()
