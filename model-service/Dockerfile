FROM continuumio/miniconda3:26.7.1-1

WORKDIR /app

# The environment of the service itself (API and worker). Versions are pinned, like in the bio service.
RUN conda create -n service_env -c conda-forge python=3.11.17 \
    fastapi=0.142.2 uvicorn=0.54.0 python-multipart=0.0.32 -y && \
    conda run -n service_env pip install redis==8.1.0 celery==5.6.3 && \
    conda clean -afy

# One conda environment per tool, tool_<name>, from tools/<name>/environment.yml, so that tools with
# conflicting dependencies can live in the same image (see registry.py)
COPY tools/ /app/tools/
RUN for env in /app/tools/*/environment.yml; do \
        [ -e "$env" ] || continue; \
        name=$(basename "$(dirname "$env")"); \
        conda env create -n "tool_$name" -f "$env" || exit 1; \
    done && \
    conda clean -afy

ENV PATH=/opt/conda/envs/service_env/bin:$PATH

# Create non-root user for security
RUN useradd -m -u 1000 modeluser && \
    mkdir -p /data/workdir /data/databases && \
    chown -R modeluser:modeluser /app /data

COPY --chown=modeluser:modeluser app.py jobs.py registry.py results.py tasks.py /app/

USER modeluser

EXPOSE 8000
