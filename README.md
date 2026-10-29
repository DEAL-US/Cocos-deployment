# Cocos-deployment

Deployment of [Cocos](https://github.com/DEAL-US/Cocos) together with the bio service that runs its assembly and annotation jobs, and a mock of that service for development.

| Folder or file                              | What                                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `cocos/`                                    | Cocos, as a Git submodule                                                                  |
| `docker-servicios-bio/docker-servicios-bio/` | The bio service: an HTTP API with Celery workers that assemble reads and annotate assemblies |
| `mock-bio-service/`                         | A mock of the bio service, which answers at once with example results                      |
| `deploy.py`                                 | Starts the bio service (or its mock) and the development stack of Cocos                    |

## Requirements

- Docker, with Docker Compose.
- Python 3, to run `deploy.py`.
- For the real bio service, the light Bakta database, version 6 (the one Bakta 1.12 needs), in `docker-servicios-bio/docker-servicios-bio/data/db-light`. Bakta can download it with `bakta_db download --output data --type light`, from that folder (see the [Bakta documentation](https://github.com/oschwengers/bakta#database)). The AMRFinderPlus database inside it is updated each time the workers start, so they need internet.

Clone the repository with its submodule:

```bash
git clone --recurse-submodules https://github.com/DEAL-US/Cocos-deployment.git
```

or, in a clone made without it, run `git submodule update --init`.

## Usage

From the root of the repository:

| Command                     | What it starts                                                                     |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `python deploy.py --mock`   | The mock of the bio service and Cocos, without the Bakta database                   |
| `python deploy.py`          | The real bio service and Cocos                                                       |
| `python deploy.py --dev`    | The same, also publishing the API of the bio service on `127.0.0.1:8000`             |
| `python deploy.py --down`   | Nothing: stops and removes every container                                           |

`--no-build` skips rebuilding the images. `deploy.py` creates the Docker network `cocos-network`, which the stacks share, if it does not exist, and stops the bio service or the mock that is not used.

| Service             | Address                                                    |
| ------------------- | ---------------------------------------------------------- |
| Cocos               | `http://localhost:8080`                                    |
| Mock of the service | `http://localhost:8001`, only from this machine            |
| Bio service         | `http://bio-assembly-api:8000`, only inside `cocos-network` (and `127.0.0.1:8000` with `--dev`) |

Cocos is started with its development stack (see its [development guide](https://github.com/DEAL-US/Cocos/blob/main/docs/development.md)). For production, start the bio service on its own (see below) and then the production stack of Cocos (see its [production guide](https://github.com/DEAL-US/Cocos/blob/main/docs/production.md)).

## Bio Service

The bio service assembles Illumina reads with SPAdes and ONT reads with Raven (or Flye, if it is installed), and annotates assemblies with Bakta, which runs AMRFinderPlus. Each job reports the versions of the tools and databases it used (`GET /tools` lists them).

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

### Configuration

The variables are set in `docker-compose.yml`. The resources of each container (`deploy.resources`) are set there too: the worker may use up to 4 CPUs and 16 GB of memory, which should be adapted to the machine.

| Variable                                               | Compose value  | What                                                                        |
| ------------------------------------------------------ | -------------- | --------------------------------------------------------------------------- |
| `WORKERS`, `WORKER_TIMEOUT`                            | `2`, `120`     | Gunicorn workers of the API, and their timeout in seconds                   |
| `DEFAULT_MIN_CONTIG`                                   | `500`          | Minimum length of the contigs of an assembly, in bases                      |
| `DEFAULT_ILLUMINA_THREADS`, `DEFAULT_ILLUMINA_MEMORY_GB` | `4`, `16`    | Threads and memory of an Illumina assembly                                  |
| `DEFAULT_ONT_THREADS`                                  | `4`            | Threads of an ONT assembly                                                  |
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
