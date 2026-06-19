# Strategy: pgvector/pgvector:pg16 already has pgvector pre-installed.
# We just add PostGIS on top — no compilation, no GitHub clone needed.
FROM pgvector/pgvector:pg16

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-postgis-3 \
        postgresql-16-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

# Runs automatically on first container start (empty data directory).
# Creates both extensions so Django's `migrate` finds them ready.
COPY initdb/00-extensions.sql /docker-entrypoint-initdb.d/
