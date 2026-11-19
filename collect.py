"""
collect.py — recolector de telemetria en vivo de la red de buses (TransApp/RED Gran Concepcion)
Pensado para correr cada 10 min via GitHub Actions (cron), escribiendo a Redis (Upstash).

CORREGIDO: la API solo acepta direction "I" (Ida) o "R" (Retorno).
Antes decia ["I", "V"] -- "V" no existe, esa mitad de las llamadas no traia nada.

Uso:
    export UPSTASH_REDIS_URL="rediss://default:<password>@<host>:<port>"
    python collect.py
"""
import os
import time
import requests
import redis

REDIS_URL = os.environ.get("UPSTASH_REDIS_URL")
if not REDIS_URL:
    raise ValueError("Falta la variable de entorno UPSTASH_REDIS_URL")
client = redis.from_url(REDIS_URL)

HEADERS = {"Os-type": "Android", "App-Version": "2.5.1"}
BASE_URL = "https://phone.dtpr.transapp.cl/v7/phone/f083f24e-7fee-4fdc-9520-dbbdae877f07/synoptic/machines"

with open("rutas.txt", "r") as f:
    rutas = [line.strip() for line in f.readlines() if line.strip()]

eventos_insertados = 0
for ruta in rutas:
    for direccion in ["I", "R"]:   # <-- corregido: antes era ["I", "V"], "V" no es un valor valido de la API
        url = f"{BASE_URL}?route={ruta}&direction={direccion}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for machine in data.get("machines", []):
                    stream_name = f"telemetry:{ruta}"
                    client.xadd(stream_name, {
                        "plate": machine.get("licensePlate", ""),
                        "lat": str(machine.get("latitude", "")),
                        "lon": str(machine.get("longitude", "")),
                        "bearing": str(machine.get("bearing", "")),
                        "timestamp": machine.get("timestamp", ""),
                        "direction": direccion
                    })
                    eventos_insertados += 1
        except Exception as e:
            print(f"Error consultando ruta {ruta}-{direccion}: {e}")
        time.sleep(0.5)

print(f"Eventos insertados en este ciclo: {eventos_insertados}")
