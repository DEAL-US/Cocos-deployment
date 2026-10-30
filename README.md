# Cocos-deployment

Deployment of [Cocos](https://github.com/DEAL-US/Cocos) together with the bio service that runs its assembly and annotation jobs, and a mock of that service for development.

| Folder or file      | What                                                                                         |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `cocos/`            | Cocos, as a Git submodule                                                                    |
| `bio-service/`      | The bio service: an HTTP API with Celery workers that assemble reads and annotate assemblies |
| `mock-bio-service/` | A mock of the bio service, which answers at once with example results                        |
| `deploy.py`         | Starts the bio service (or its mock) and the development stack of Cocos                      |

## Requirements

- Docker, with Docker Compose.
- Python 3, to run `deploy.py`.
- For the real bio service, a Bakta database, which `deploy.py` can download (see [Bakta database](#bakta-database)). The mock does not need it.

Clone the repository with its submodule:

```bash
git clone --recurse-submodules https://github.com/DEAL-US/Cocos-deployment.git
```

or, in a clone made without it, run `git submodule update --init`.

## Usage

From the root of the repository:

| Command                                      | What it starts                                                                             |
| -------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `python deploy.py --mock`                    | The mock of the bio service and the development stack of Cocos, without the Bakta database |
| `python deploy.py`                           | The real bio service and the development stack of Cocos                                    |
| `python deploy.py --expose-api`              | The same, also publishing the API of the bio service on `127.0.0.1:8000`                   |
| `python deploy.py --prod`                    | The real bio service and the production stack of Cocos                                     |
| `python deploy.py --down`                    | Nothing: stops and removes every container                                                 |
| `python deploy.py --download-bakta-db light` | Nothing: downloads the light (or `full`) Bakta database of the bio service                 |

`--no-build` skips rebuilding the images. `deploy.py` creates the Docker network `cocos-network`, which the stacks share, if it does not exist, and stops the bio service or the mock that is not used.

The development stack of Cocos is described in its [development guide](https://github.com/DEAL-US/Cocos/blob/main/docs/development.md), and the production one in its [production guide](https://github.com/DEAL-US/Cocos/blob/main/docs/production.md). Before deploying for production, `--prod` runs the setup script of Cocos on `cocos/.env.prod`: it creates the file if needed, generates its secrets and stops if a required value is still missing (such as the domain).

| Service             | Address                                                    |
| ------------------- | ---------------------------------------------------------- |
| Cocos               | `http://localhost:8080` (development) or `http://localhost`, port 80, or its domain (production) |
| Mock of the service | `http://localhost:8001`, only from this machine            |
| Bio service         | `http://bio-assembly-api:8000`, only inside `cocos-network` (and `127.0.0.1:8000` with `--expose-api`) |

## Bio Service

The bio service assembles Illumina reads with SPAdes and ONT reads with Raven or Flye, and annotates assemblies with Bakta, which runs AMRFinderPlus. An ONT assembly uses the assembler it asks for (`?assembler=raven` or `?assembler=flye`), or `DEFAULT_ONT_ASSEMBLER` otherwise. Each job reports the versions of the tools and databases it used, and `GET /tools` lists what a new job would use: under `assembly`, the default assembler of each technology, and under `assemblers`, every installed one.

| Container                       | What                                                       |
| ------------------------------- | ---------------------------------------------------------- |
| `bio-assembly-api`              | The HTTP API (FastAPI and Gunicorn)                        |
| `bio-celery-worker`             | Runs the assembly and annotation jobs                      |
| `bio-celery-maintenance-worker` | Cleans up the jobs whose worker stopped                    |
| `bio-celery-beat`               | Schedules that cleanup                                     |
| `bio-redis`                     | Redis, the Celery broker and the store of the jobs        |
| `bio-flower`                    | Optional: Flower, to monitor the workers                   |

To start it without `deploy.py`, from its folder:

```bash
docker network create cocos-network   # if it does not exist yet
docker compose -p bio-service up --build -d
```

The API has no authentication, so `docker-compose.yml` publishes no port: only Cocos reaches it, through `cocos-network`. For development, `docker-compose.dev.yml` also publishes it on `127.0.0.1:8000`, only for this machine, which is the address `test.http` uses (with the REST Client extension of VS Code):

```bash
docker compose -p bio-service -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

Without publishing it, requests can be made from a container in the network:

```bash
docker run --rm --network cocos-network curlimages/curl http://bio-assembly-api:8000/health
```

Flower has no authentication either. It starts with the `monitoring` profile (`docker compose -p bio-service --profile monitoring up -d`) and is published only on `127.0.0.1:5555`; on a server, reach it through an SSH tunnel (`ssh -L 5555:localhost:5555 <server>`).

### Bakta database

Bakta annotates with its own database, which is not in the image: it is downloaded once into `bio-service/data`. Bakta 1.12 needs version 6 of the database, which comes in two types ([Zenodo record](https://doi.org/10.5281/zenodo.14916843), [Bakta documentation](https://github.com/oschwengers/bakta#database)):

| Type    | Download | On disk | What                                                                                                     |
| ------- | -------- | ------- | -------------------------------------------------------------------------------------------------------- |
| `light` | 1.3 GB   | 3.9 GB  | Faster, and enough for most uses: the coding genes are annotated only from UniRef50 clusters             |
| `full`  | 32 GB    | 84 GB   | More specific annotations of the coding genes, at the cost of space and time; Bakta's own recommendation |

`BAKTA_DB_TYPE` (`light` by default) chooses the one the service uses, which it reads from `data/db-light` or `data/db-full`. Both can be downloaded and kept, and the service switches between them when it is started again. Each job records the type and version of the database it used.

`deploy.py` downloads one with Bakta itself, inside the image of the bio service (which it builds first if needed), so Bakta does not have to be installed on the machine:

```bash
python deploy.py --download-bakta-db light   # or full
```

It downloads into a temporary folder and only then moves the database into place, so a download that is cut can simply be started again. If the folder is already there, it does nothing. Without `deploy.py`, from `bio-service/`, the same can be done by hand:

```bash
docker compose -p bio-service build bio-assembly-api
docker run --rm -v ./data:/data/download bio-service-bio-assembly-api bakta_db download --output /data/download --type light
```

which leaves the light database in `data/db-light` and the full one in `data/db`, to be renamed `data/db-full`.

The last step of the download updates the AMRFinderPlus database inside it, and on Docker Desktop for Windows its indexing can fail with `LMDB runtime error: mdb_env_open: Input/output error`. The database is fine: `deploy.py` indexes it again by mounting the folder of the new AMRFinderPlus version on its own, which works. By hand, from `bio-service/`:

```bash
docker run --rm -v ./data/db-light/amrfinderplus-db/<version>:/amrfinderplus-db bio-service-bio-assembly-api amrfinder_index /amrfinderplus-db/
```

When it deploys the real bio service, `deploy.py` warns if the database of `BAKTA_DB_TYPE` is missing. The AMRFinderPlus database inside it is updated each time the workers start, so they need internet.

### Configuration

`BAKTA_DB_TYPE` and `DEFAULT_ONT_ASSEMBLER` are set in `bio-service/.env` (a copy of `.env.example`); the other variables are set in `docker-compose.yml`. The resources of each container (`deploy.resources`) are set there too: the worker may use up to 4 CPUs and 16 GB of memory, which should be adapted to the machine.

| Variable                                               | Compose value  | What                                                                        |
| ------------------------------------------------------ | -------------- | --------------------------------------------------------------------------- |
| `WORKERS`, `WORKER_TIMEOUT`                            | `2`, `120`     | Gunicorn workers of the API, and their timeout in seconds                   |
| `DEFAULT_MIN_CONTIG`                                   | `500`          | Minimum length of the contigs of an assembly, in bases                      |
| `DEFAULT_ILLUMINA_THREADS`, `DEFAULT_ILLUMINA_MEMORY_GB` | `4`, `16`    | Threads and memory of an Illumina assembly                                  |
| `DEFAULT_ONT_THREADS`                                  | `4`            | Threads of an ONT assembly                                                  |
| `BAKTA_DB_TYPE`                                        | `light`        | Bakta database of the annotations (`light` or `full`)                       |
| `DEFAULT_ONT_ASSEMBLER`                                | `raven`        | Assembler of an ONT assembly that does not ask for one (`raven` or `flye`)  |
| `DEFAULT_ANNOTATION_THREADS`                           | `4`            | Threads of an annotation                                                    |
| `CELERY_CONCURRENCY`                                   | `1`            | Jobs a worker runs at the same time                                         |
| `CELERY_MAIN_QUEUE`, `CELERY_MAINTENANCE_QUEUE`        | `default`, `maintenance` | Celery queues of the jobs and of the cleanup                      |
| `STALE_JOB_CLEANUP_INTERVAL_SECONDS`                   | `300`          | How often the jobs whose worker stopped are cleaned up                      |
| `WORKDIR_PATH`                                         | `/data/workdir` | Folder of the files of the jobs (`data/workdir` on the host)               |
| `REDIS_URL`                                            | `redis://bio-redis:6379/0` | Redis of the service                                            |

The `DEFAULT_*` values apply when a request does not give them. The time limits of the jobs are not in the compose file and have defaults in the code: `ASSEMBLY_SOFT_TIMEOUT` and `ASSEMBLY_HARD_TIMEOUT` (72,000 and 75,000 seconds), and `ANNOTATION_SOFT_TIMEOUT` and `ANNOTATION_HARD_TIMEOUT` (36,000 and 39,000 seconds).

## Mock of the Bio Service

The mock has the same API as the bio service and answers at once with example results, so Cocos can be developed without the Bakta database or long jobs. Each request can ask for a behaviour with `?behavior=`; otherwise it uses `MOCK_DEFAULT_BEHAVIOR`:

| Behaviour        | What the job does                                                        |
| ---------------- | ------------------------------------------------------------------------ |
| `success`        | Succeeds (default)                                                       |
| `slow`           | Runs for `MOCK_DEFAULT_DURATION` seconds, then succeeds                  |
| `fail`           | Fails because a tool could not process the input (`error_kind: input`)  |
| `fail_resources` | Fails because it ran out of time or memory (`error_kind: resources`)    |
| `busy`           | The service answers that it is busy (HTTP 503) when asked for the job   |
| `invalid`        | Succeeds, but its result file is invalid                                 |

`MOCK_DEFAULT_DURATION` is 2 seconds by default.

## License

Free software under the [GNU General Public License v3](LICENSE).
