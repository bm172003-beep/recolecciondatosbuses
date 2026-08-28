import os
import time
import requests
import redis

# 1. Conexión segura a Upstash 
REDIS_URL = os.environ.get("UPSTASH_REDIS_URL")
if not REDIS_URL:
    raise ValueError("Falta la variable de entorno UPSTASH_REDIS_URL")
client = redis.from_url(REDIS_URL)

HEADERS = {"Os-type": "Android", "App-Version": "2.5.1"}
BASE_URL = "https://phone.dtpr.transapp.cl/v7/phone/f083f24e-7fee-4fdc-9520-dbbdae877f07/synoptic/machines"

# 2. Leer dinámicamente las rutas desde el archivo
with open("rutas.txt", "r") as f:
    rutas = [line.strip() for line in f.readlines() if line.strip()]

print(f"Iniciando recolección masiva para {len(rutas)} rutas...")

eventos_insertados = 0

# 3. Iterar sobre las 198 combinaciones
for ruta in rutas:
    for direccion in ["I", "V"]:
        url = f"{BASE_URL}?route={ruta}&direction={direccion}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for machine in data.get("machines", []):
                    stream_name = f"telemetry:{ruta}"
                    
                    # Insertar como evento de streaming en Redis (XADD)
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
        
        # 4. Retraso de 0.5 seg para no saturar la API del backend
        time.sleep(0.5)

print(f"Captura completada. {eventos_insertados} eventos enviados a Redis Streams.")
