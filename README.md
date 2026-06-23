# Stay Finder

A Dockerized vacation rental management system built with Django, GeoDjango, PostGIS, and pgvector. The project includes property listings, admin management, image uploads, location autocomplete, and semantic search support.

## Tech Stack

- Django 6
- PostgreSQL 16 with PostGIS and pgvector
- Docker and Docker Compose
- Sentence Transformers for embeddings


## Setup

### 1. Clone the repository

```bash
git clone https://github.com/tamim-cste/vacation-rental-pms-Farman-Arefin-Tamim
cd vacation-rental-pms-Farman-Arefin-Tamim
```

### 2. Create the environment file

```bash
cp .env.example .env
```

If needed, edit `.env` and update the secret key, database name, and other values.

### 3. Build the Docker images

```bash
docker compose build
```

### 4. Start the application

```bash
docker compose up
```

The web container runs database migrations on startup and serves the app at:

```text
http://localhost:8000
```

## First-Time Data Setup

Open a new terminal and run:

```bash
docker compose exec web python manage.py import_properties
docker compose exec web python manage.py generate_embeddings
docker compose exec web python manage.py createsuperuser
```

## Main Features

- Property browsing and detail pages
- Django admin for managing locations, properties, and images
- Location autocomplete on the home page search box
- Semantic search using vector embeddings and pgvector

## Notes

- The database service is defined in [docker-compose.yml](docker-compose.yml).
- The PostgreSQL image with PostGIS and pgvector is built from [docker/postgres/Dockerfile](docker/postgres/Dockerfile).
- Semantic search works after embeddings are generated for the imported records.
