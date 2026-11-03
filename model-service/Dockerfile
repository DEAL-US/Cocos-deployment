# Only what the environments of the tools are built from, so that changing the code of a tool does
# not build them again (nor download its database)
FROM busybox:1.37.0 AS tool-environments
COPY tools/ /tools/
RUN find /tools -type f ! -name environment.yml ! -name setup.sh -delete

FROM continuumio/miniconda3:26.7.1-1

WORKDIR /app

# The environment of the service itself (API and worker). Versions are pinned, like in the bio service.
RUN conda create -n service_env -c conda-forge python=3.11.17 \
    fastapi=0.142.2 uvicorn=0.54.0 python-multipart=0.0.32 -y && \
    conda run -n service_env pip install redis==8.1.0 celery==5.6.3 && \
    conda clean -afy

# One conda environment per tool, tool_<name>, from tools/<name>/environment.yml, so that tools with
# conflicting dependencies can live in the same image (see registry.py)
COPY --from=tool-environments /tools/ /app/tools/
RUN for env in /app/tools/*/environment.yml; do \
        [ -e "$env" ] || continue; \
        name=$(basename "$(dirname "$env")"); \
        conda env create -n "tool_$name" -f "$env" || exit 1; \
    done && \
    conda clean -afy

# A tool may have a setup.sh, run once in its environment when the image is built (e.g. to download
# its database into the image, so that its version is fixed with the image)
RUN for setup in /app/tools/*/setup.sh; do \
        [ -e "$setup" ] || continue; \
        name=$(basename "$(dirname "$setup")"); \
        conda run --no-capture-output -n "tool_$name" sh "$setup" || exit 1; \
    done

ENV PATH=/opt/conda/envs/service_env/bin:$PATH

# Create non-root user for security
RUN useradd -m -u 1000 modeluser && \
    mkdir -p /data/workdir /data/databases && \
    chown -R modeluser:modeluser /app /data

COPY --chown=modeluser:modeluser app.py jobs.py registry.py results.py tasks.py /app/
COPY --chown=modeluser:modeluser tools/ /app/tools/

USER modeluser

EXPOSE 8000
