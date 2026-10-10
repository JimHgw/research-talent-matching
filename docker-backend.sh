#!/bin/sh
set -eu

action=${1:-up}
if [ "$#" -gt 1 ]; then
    printf '%s\n' 'Usage: sh docker-backend.sh [up|build|stop|down|logs|status]' >&2
    exit 2
fi
case "$action" in
    up|build|stop|down|logs|status) ;;
    *) printf '%s\n' 'Usage: sh docker-backend.sh [up|build|stop|down|logs|status]' >&2; exit 2 ;;
esac

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Docker is not installed or is not on PATH. Install and start Docker Desktop / Docker Engine.' >&2
    exit 1
fi
if ! docker compose version; then
    printf '%s\n' 'Docker Compose is unavailable. Install or update the Docker Compose plugin.' >&2
    exit 1
fi
if ! docker_os=$(docker info --format '{{.OSType}}'); then
    printf '%s\n' 'Cannot connect to Docker. Start Docker Desktop / Docker Engine and retry.' >&2
    exit 1
fi
if [ "$docker_os" != linux ]; then
    printf '%s\n' 'This image requires Linux containers. Switch Docker Desktop to Linux containers.' >&2
    exit 1
fi

env_file="$repo_root/.env"
if [ ! -f "$env_file" ]; then env_file="$repo_root/.env.example"; fi
compose() {
    docker compose --project-directory "$repo_root" --env-file "$env_file" \
        --file "$repo_root/compose.yaml" "$@"
}

case "$action" in
    up)
        if ! compose up --build --detach --wait --wait-timeout 120 backend; then
            printf '%s\n' 'Docker Compose failed. Check the output above; run sh docker-backend.sh logs for startup errors. Database volumes were not deleted.' >&2
            exit 1
        fi
        printf '%s\n' 'Backend is healthy. Published address (append /healthz to check):'
        compose port backend 8000
        printf '%s\n' 'See README_DEVELOPER_EN.md to create accounts and connect the frontend.'
        ;;
    build)
        compose build backend
        printf '%s\n' 'Image built: banana-backend:local. No container was started.'
        ;;
    stop)
        compose stop backend
        printf '%s\n' 'Backend stopped. The SQLite data volume is preserved.'
        ;;
    down)
        compose down
        printf '%s\n' 'Compose containers and network removed. The SQLite data volume is preserved.'
        ;;
    logs) compose logs --follow --tail 100 backend ;;
    status) compose ps --all ;;
esac
