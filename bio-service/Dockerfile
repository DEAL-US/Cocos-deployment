FROM continuumio/miniconda3:26.7.1-1

WORKDIR /app

# Create conda environment and install all dependencies in one layer.
# Versions are pinned so that the image is reproducible: the jobs report them (versions.py), and
# Bakta 1.12 needs the Bakta database v6, light or full (BAKTA_DB_TYPE).
RUN conda create -n bio_env python=3.11.17 -y && \
    conda install -n bio_env -c bioconda -c conda-forge \
    spades=4.3.0 raven-assembler=1.8.3 flye=2.9.6 bakta=1.12.1 ncbi-amrfinderplus=4.2.7 biopython=1.88 \
    fastapi=0.142.2 uvicorn=0.54.0 python-multipart=0.0.32 gunicorn=26.2.0 -y && \
    conda clean -afy

# Install Redis client and Celery via pip
RUN conda run -n bio_env pip install redis==8.1.0 celery==5.6.3 flower==2.2.0

# Make conda environment activate by default
SHELL ["conda", "run", "-n", "bio_env", "/bin/bash", "-c"]
ENV PATH=/opt/conda/envs/bio_env/bin:$PATH

# Create non-root user for security
RUN useradd -m -u 1000 biouser && \
    mkdir -p /data/bakta_db /data/workdir && \
    chown -R biouser:biouser /app /data

# Install system dependencies before switching to non-root user
RUN apt-get update && \
    apt-get install -y libopenmpi40 && \
    rm -rf /var/lib/apt/lists/*

# Copy application files
COPY --chown=biouser:biouser app.py tasks.py utils.py versions.py update_amrfinderplus_db.py gunicorn.conf.py /app/

# Switch to non-root user
USER biouser

# Expose port
EXPOSE 8000