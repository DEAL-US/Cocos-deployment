# Cómo poner en marcha esta cosa

1. Descargar y descomprimir la base de datos de bakta en /data y configurar el docker-compose para que monte esa carpeta (solo hay que verificar la línea correspondiente).
2. Hacer que docker esté corriendo para poder ejecutar comandos de docker.
3. Ejecutar `docker compose up --build` para construir y levantar los contenedores. `--build` es necesario para que, si se han hecho cambios en el archivo de python, se hagan efectivos. Los contenedores usan la red `bio-network`, que tiene que existir antes (`docker network create bio-network`; `python deploy.py`, desde la raíz del proyecto, la crea si falta).
4. `test.http` contiene ejemplos de peticiones HTTP que se pueden hacer al servidor. Se puede usar la extensión REST Client de VSCode para ejecutarlas directamente desde el editor. Para eso hay que levantar el servicio en modo desarrollo (ver abajo), porque normalmente la API no es accesible desde fuera de Docker.

## Acceso a la API

La API no tiene autenticación, así que `docker-compose.yml` no publica ningún puerto: solo se puede llegar a ella desde la red `bio-network`, en `http://bio-assembly-api:8000`. Así es como la usa Cocos (`ANNOTATION_BASE` en su `.env`), que es la única interfaz para los usuarios. En producción se usa solo este fichero.

Para desarrollo, `docker-compose.dev.yml` publica además la API en `127.0.0.1:8000`, solo para el propio equipo (no para el resto de la red), que es la dirección que usa `test.http`. Se añade encima del compose principal:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

o, desde la raíz del proyecto, con todo el resto de Cocos:

```bash
python deploy.py --dev
```

Sin el modo desarrollo también se pueden hacer peticiones desde un contenedor dentro de la red, por ejemplo:

```bash
docker run --rm --network bio-network curlimages/curl http://bio-assembly-api:8000/health
```

Flower (perfil `monitoring`: `docker compose --profile monitoring up`) tampoco tiene autenticación y solo se publica en `127.0.0.1:5555`. En un servidor se llega a él con un túnel SSH (`ssh -L 5555:localhost:5555 <servidor>`).

El parámetro `assembler` de `POST /assembly/illumina` solo admite `spades`, y el de `POST /assembly/ont`, `flye` o `raven`; cualquier otro valor se rechaza con un 422. Si no se indica, se usa el ensamblador instalado.

## Versiones

Las versiones de las herramientas están fijadas en el `Dockerfile` (SPAdes 4.3.0, Raven 1.8.3, Bakta 1.12.1, AMRFinderPlus 4.2.7). Bakta 1.12 necesita la base de datos de Bakta v6 (por ejemplo, `db-light` 6.0).

Cada trabajo guarda las herramientas y bases de datos que usó (`versions.py`): `GET /jobs/{job_id}` las devuelve en `software`, una lista de entradas con nombre, versión, tipo (`tool` o `database`) y su id de bio.tools o su DOI. `GET /tools` devuelve las que hay instaladas, por tipo de trabajo, es decir, las que usaría un trabajo nuevo.
