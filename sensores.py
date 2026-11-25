"""
sensores.py
-----------
Catálogo de los sensores de los paneles solares de la ISS que vamos a escuchar.

Cada sensor tiene un código (ej: "S4000001") que es como la NASA lo publica.
Los códigos y descripciones salen de la planilla oficial que mantiene el
proyecto open source ISS Mimic:
https://github.com/ISS-Mimic/Mimic/blob/main/Telemetry/ISS_Public_Telemetry.xlsx

Un poco de contexto sobre la ISS:
- Tiene 8 "alas" de paneles solares: 1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B.
- Cada ala puede inclinarse con un motor llamado BGA (Beta Gimbal Assembly).
- Además, todo el conjunto de alas de cada lado (babor / estribor) gira
  como una rueda gigante con el SARJ (Solar Alpha Rotary Joint) para
  seguir al Sol en cada órbita (~92 minutos).
"""

# Diccionario: código NASA -> nombre legible que usaremos en el CSV.
# Lo separamos en su propio archivo para que el script principal quede limpio
# y para que puedas agregar o quitar sensores sin tocar la lógica.
SENSORES = {
    # --- Voltaje de cada ala (Volts) ---
    "S4000001": "ala_1A_voltaje",
    "S6000004": "ala_1B_voltaje",
    "P4000001": "ala_2A_voltaje",
    "P6000004": "ala_2B_voltaje",
    "S4000004": "ala_3A_voltaje",
    "S6000001": "ala_3B_voltaje",
    "P4000004": "ala_4A_voltaje",
    "P6000001": "ala_4B_voltaje",

    # --- Corriente de cada ala (Amperes) ---
    "S4000002": "ala_1A_corriente",
    "S6000005": "ala_1B_corriente",
    "P4000002": "ala_2A_corriente",
    "P6000005": "ala_2B_corriente",
    "S4000005": "ala_3A_corriente",
    "S6000002": "ala_3B_corriente",
    "P4000005": "ala_4A_corriente",
    "P6000002": "ala_4B_corriente",

    # --- Ángulo de inclinación de cada ala, motor BGA (grados) ---
    "S4000007": "ala_1A_angulo_beta",
    "S6000008": "ala_1B_angulo_beta",
    "P4000007": "ala_2A_angulo_beta",
    "P6000008": "ala_2B_angulo_beta",
    "S4000008": "ala_3A_angulo_beta",
    "S6000007": "ala_3B_angulo_beta",
    "P4000008": "ala_4A_angulo_beta",
    "P6000007": "ala_4B_angulo_beta",

    # --- Rotación de la "rueda" completa de cada lado, SARJ (grados) ---
    "S0000003": "sarj_estribor_angulo",
    "S0000004": "sarj_babor_angulo",
}
