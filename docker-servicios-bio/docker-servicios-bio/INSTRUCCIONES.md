# Cómo poner en marcha esta cosa

1. Descargar y descomprimir la base de datos de bakta en /data y configurar el docker-compose para que monte esa carpeta (solo hay que verificar la línea correspondiente).
2. Hacer que docker esté corriendo para poder ejecutar comandos de docker.
3. Ejecutar `docker-compose up --build` para construir y levantar los contenedores en segundo plano. `--build` es necesario para que, si se han hecho cambios en el archivo de python, se hagan efectivos.
4. `test.http` contiene ejemplos de peticiones HTTP que se pueden hacer al servidor. Se puede usar la extensión REST Client de VSCode para ejecutarlas directamente desde el editor.

## Versiones

Las versiones de las herramientas están fijadas en el `Dockerfile` (SPAdes 4.3.0, Raven 1.8.3, Bakta 1.12.1, AMRFinderPlus 4.2.7). Bakta 1.12 necesita la base de datos de Bakta v6 (por ejemplo, `db-light` 6.0).

Cada trabajo guarda las herramientas y bases de datos que usó (`versions.py`): `GET /jobs/{job_id}` las devuelve en `software`, una lista de entradas con nombre, versión, tipo (`tool` o `database`) y su id de bio.tools o su DOI. `GET /tools` devuelve las que hay instaladas, por tipo de trabajo, es decir, las que usaría un trabajo nuevo.
