#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
#
# symdue.sh — Symdue OSS lifecycle helper
#
# Subcommand-based wrapper around docker compose for first-time setup,
# launch, stop, restart, and rebuild flows. Auto-detects the host's
# docker group GID so Docker-out-of-Docker works without a manual env.
#
# Usage:
#   ./setup/symdue.sh init              # First-time: generate .env, preview, optional edit
#   ./setup/symdue.sh init -i           # Per-service Q&A walkthrough
#   ./setup/symdue.sh start             # up -d (build only if needed)
#   ./setup/symdue.sh stop              # compose stop
#   ./setup/symdue.sh restart           # stop + start (no rebuild)
#   ./setup/symdue.sh rebuild           # full reset
#   ./setup/symdue.sh logs [service]    # tail logs
#   ./setup/symdue.sh status            # compose ps
#   ./setup/symdue.sh help              # this help

set -euo pipefail

# ────────────────────────────────────────────────────────────────────
# Locations
# ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_ENV="$SCRIPT_DIR/../server/.env"
SERVER_ENV_EXAMPLE="$SCRIPT_DIR/../server/.env.example"

# ────────────────────────────────────────────────────────────────────
# Colors (degrade on non-TTY)
# ────────────────────────────────────────────────────────────────────
if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    RED="$(tput setaf 1)"
    GREEN="$(tput setaf 2)"
    YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"
    BOLD="$(tput bold)"
    DIM="$(tput dim)"
    RESET="$(tput sgr0)"
else
    RED="" GREEN="" YELLOW="" BLUE="" BOLD="" DIM="" RESET=""
fi

info()    { echo -e "${BLUE}ℹ${RESET}  $*"; }
ok()      { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*" >&2; }
err()     { echo -e "${RED}✗${RESET}  $*" >&2; }
section() { echo; echo -e "${BOLD}━━━ $* ━━━${RESET}"; }

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────
require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        err "$1 is required but not installed."
        exit 1
    fi
}

detect_docker_gid() {
    local gid="999"
    if command -v getent >/dev/null 2>&1; then
        gid="$(getent group docker | cut -d: -f3 || true)"
        [ -z "$gid" ] && gid="999"
    fi
    echo "$gid"
}

random_password() {
    openssl rand -base64 32 | tr -d '\n=' | tr '/+' '_-' | cut -c1-32
}

random_secret() {
    openssl rand -hex 32
}

mask_secret() {
    local val="$1"
    if [ -z "$val" ]; then
        echo "(empty)"
    elif [ "${#val}" -gt 8 ]; then
        echo "${val:0:4}…${val: -2} ${DIM}(${#val} chars)${RESET}"
    else
        echo "*** ${DIM}(${#val} chars)${RESET}"
    fi
}

print_env_preview() {
    if [ ! -f "$SERVER_ENV" ]; then
        warn "No .env to preview."
        return
    fi
    section "Generated configuration"
    echo "  ${DIM}File: $SERVER_ENV${RESET}"
    echo
    while IFS='=' read -r key val; do
        case "$key" in \#*|"") continue ;; esac
        val="${val%\"}"; val="${val#\"}"
        case "$key" in
            *PASSWORD*|*SECRET*|*KEY*|*TOKEN*)
                printf "  ${DIM}%-32s${RESET} %s\n" "$key" "$(mask_secret "$val")"
                ;;
            *)
                printf "  ${DIM}%-32s${RESET} %s\n" "$key" "$val"
                ;;
        esac
    done < "$SERVER_ENV"
    echo
}

services_running() {
    cd "$SCRIPT_DIR"
    docker compose ps --services --filter status=running 2>/dev/null | grep -c . || true
}

images_built() {
    cd "$SCRIPT_DIR"
    docker compose images --quiet 2>/dev/null | grep -q .
}

print_endpoints() {
    set -a
    [ -f "$SERVER_ENV" ] && . "$SERVER_ENV"
    set +a
    section "Endpoints"
    echo "  Frontend:        http://localhost:${FRONTEND_PORT:-3000}"
    echo "  Backend (API):   http://localhost:${BACKEND_PORT:-8000}"
    echo "  Backend Swagger: http://localhost:${BACKEND_PORT:-8000}/docs"
    echo "  MinIO console:   http://localhost:${MINIO_CONSOLE_PORT:-9001}"
    echo "  Temporal UI:     http://localhost:${TEMPORAL_UI_PORT:-8089}"
    echo
}

# Mac sed needs '' after -i; GNU sed does not.
sed_inplace_init() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SED_INPLACE=(sed -i '')
    else
        SED_INPLACE=(sed -i)
    fi
}

set_env_var() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$SERVER_ENV"; then
        "${SED_INPLACE[@]}" "s|^${key}=.*|${key}=${val}|g" "$SERVER_ENV"
    else
        echo "${key}=${val}" >> "$SERVER_ENV"
    fi
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: init
# ────────────────────────────────────────────────────────────────────
cmd_init() {
    require_cmd openssl
    sed_inplace_init

    local interactive=0 force=0
    while [ $# -gt 0 ]; do
        case "$1" in
            -i|--interactive) interactive=1; shift ;;
            -f|--force) force=1; shift ;;
            *) err "Unknown init option: $1"; exit 2 ;;
        esac
    done

    if [ -f "$SERVER_ENV" ] && [ "$force" -eq 0 ]; then
        warn ".env already exists at $SERVER_ENV"
        info "Run 'init --force' to regenerate (overwrites secrets), or 'start' to launch."
        exit 0
    fi

    if [ ! -f "$SERVER_ENV_EXAMPLE" ]; then
        err "Missing template: $SERVER_ENV_EXAMPLE"
        exit 1
    fi

    section "Generating .env"
    cp "$SERVER_ENV_EXAMPLE" "$SERVER_ENV"

    local pg_password minio_user minio_password secret_key docker_gid
    pg_password="$(random_password)"
    secret_key="$(random_secret)"
    minio_user="admin-$(openssl rand -hex 4)"
    minio_password="$(random_password)"
    docker_gid="$(detect_docker_gid)"

    "${SED_INPLACE[@]}" "s|<set-via-setup-or-environment>|${pg_password}|g" "$SERVER_ENV"
    "${SED_INPLACE[@]}" "s|<run: openssl rand -hex 32>|${secret_key}|g" "$SERVER_ENV"
    "${SED_INPLACE[@]}" "s|^MINIO_ROOT_USER=.*|MINIO_ROOT_USER=${minio_user}|g" "$SERVER_ENV"
    "${SED_INPLACE[@]}" "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${minio_password}|g" "$SERVER_ENV"

    if ! grep -q "^DOCKER_GID=" "$SERVER_ENV"; then
        echo "" >> "$SERVER_ENV"
        echo "# Docker-out-of-Docker — auto-detected from host docker group" >> "$SERVER_ENV"
        echo "DOCKER_GID=${docker_gid}" >> "$SERVER_ENV"
    fi

    chmod 600 "$SERVER_ENV"
    ok "Generated $SERVER_ENV (mode 600)"
    info "Host docker group GID detected: ${docker_gid}"

    if [ "$interactive" -eq 1 ]; then
        cmd_init_interactive
    fi

    print_env_preview

    if [ -t 0 ]; then
        read -rp "Edit .env before launching? [y/N] " edit
        case "${edit:-n}" in
            y|Y|yes|YES) "${EDITOR:-vi}" "$SERVER_ENV" ;;
        esac
    fi

    section "Next step"
    echo "  ./setup/symdue.sh start"
    echo
}

cmd_init_interactive() {
    section "Per-service configuration"
    echo "Press Enter to accept defaults, or type a custom value."
    echo

    echo "${BOLD}Postgres${RESET}"
    read -rp "  Database name [symdue_db]: " v
    [ -n "${v:-}" ] && set_env_var POSTGRES_DB "$v"
    read -rp "  External port [5433]: " v
    [ -n "${v:-}" ] && set_env_var POSTGRES_PORT "$v"

    echo "${BOLD}MinIO${RESET}"
    read -rp "  API port [9000]: " v
    [ -n "${v:-}" ] && set_env_var MINIO_API_PORT "$v"
    read -rp "  Console port [9001]: " v
    [ -n "${v:-}" ] && set_env_var MINIO_CONSOLE_PORT "$v"

    echo "${BOLD}Backend (FastAPI)${RESET}"
    read -rp "  Port [8000]: " v
    [ -n "${v:-}" ] && set_env_var BACKEND_PORT "$v"

    echo "${BOLD}Frontend (React)${RESET}"
    read -rp "  Port [3000]: " v
    [ -n "${v:-}" ] && set_env_var FRONTEND_PORT "$v"
    echo
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: start
# ────────────────────────────────────────────────────────────────────
cmd_start() {
    require_cmd docker

    if [ ! -f "$SERVER_ENV" ]; then
        err "No .env yet. Run: ./setup/symdue.sh init"
        exit 1
    fi

    cd "$SCRIPT_DIR"

    if ! docker info >/dev/null 2>&1; then
        err "Docker daemon not running. Start Docker Desktop / dockerd first."
        exit 1
    fi

    set -a
    . "$SERVER_ENV"
    set +a
    export DOCKER_GID="${DOCKER_GID:-$(detect_docker_gid)}"

    section "Starting Symdue"
    info "DOCKER_GID = $DOCKER_GID (host)"

    local running
    running="$(services_running)"
    if [ "${running:-0}" -gt 0 ]; then
        warn "${running} service(s) already running. Use 'restart' or 'rebuild' to replace."
        cmd_status
        exit 0
    fi

    if ! images_built; then
        info "Images not built yet — building (first-time only, ~5-10 min)..."
        docker compose build
    else
        info "Images present — skipping build. Use 'rebuild' to force from scratch."
    fi

    docker compose up -d
    sleep 2
    ok "Stack started"
    cmd_status
    print_endpoints
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: stop
# ────────────────────────────────────────────────────────────────────
cmd_stop() {
    cd "$SCRIPT_DIR"
    if [ "$(services_running)" = "0" ]; then
        info "No services running."
        exit 0
    fi
    info "Stopping services..."
    docker compose stop
    ok "Stopped"
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: restart
# ────────────────────────────────────────────────────────────────────
cmd_restart() {
    cmd_stop
    cmd_start
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: rebuild
# ────────────────────────────────────────────────────────────────────
cmd_rebuild() {
    require_cmd docker

    local force=0
    while [ $# -gt 0 ]; do
        case "$1" in
            -f|--force) force=1; shift ;;
            *) err "Unknown rebuild option: $1"; exit 2 ;;
        esac
    done

    cd "$SCRIPT_DIR"

    if [ "$force" -eq 0 ] && [ -t 0 ]; then
        warn "This will:"
        warn "  • Stop all running containers"
        warn "  • Remove all containers, volumes, and locally-built images"
        warn "  • Rebuild every image from scratch (--no-cache)"
        warn "  • Start the stack fresh"
        echo
        read -rp "Continue? [y/N] " confirm
        case "${confirm:-n}" in
            y|Y|yes|YES) ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi

    set -a
    [ -f "$SERVER_ENV" ] && . "$SERVER_ENV"
    set +a
    export DOCKER_GID="${DOCKER_GID:-$(detect_docker_gid)}"

    section "Full rebuild"
    info "Tearing down stack..."
    docker compose down -v --rmi local --remove-orphans || true
    info "Rebuilding from scratch..."
    docker compose build --no-cache
    info "Starting fresh stack..."
    docker compose up -d
    sleep 2
    ok "Rebuild complete"
    cmd_status
    print_endpoints
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: logs
# ────────────────────────────────────────────────────────────────────
cmd_logs() {
    cd "$SCRIPT_DIR"
    if [ $# -eq 0 ]; then
        docker compose logs -f --tail=100
    else
        docker compose logs -f --tail=100 "$@"
    fi
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: status
# ────────────────────────────────────────────────────────────────────
cmd_status() {
    cd "$SCRIPT_DIR"
    docker compose ps
}

# ────────────────────────────────────────────────────────────────────
# Subcommand: help
# ────────────────────────────────────────────────────────────────────
cmd_help() {
    cat <<'EOF'

Symdue OSS — setup and lifecycle helper

USAGE
  ./setup/symdue.sh <command> [options]

COMMANDS
  init                 First-time setup. Generates .env with random secrets,
                       auto-detects host docker GID, prints config preview
                       (passwords masked), and optionally opens $EDITOR
                       before continuing. Refuses to overwrite existing .env
                       unless --force.
  init -i              Same as init, but adds a per-service Q&A pass for
                       database name and ports before the preview.
  init --force         Regenerate .env (overwrites existing secrets).

  start                Launch the stack (docker compose up -d).
                       Builds images only if missing — idempotent on re-runs.

  stop                 Stop all running services (docker compose stop).

  restart              stop + start (no image rebuild).

  rebuild              Full reset: down -v --rmi local --remove-orphans,
                       then build --no-cache, then up -d.
                       Asks for confirmation unless --force.

  logs [service ...]   Tail logs (all services, or named ones).

  status (alias: ps)   Show docker compose state.

  help                 Show this help.

QUICK START
  # First time:
    ./setup/symdue.sh init
    ./setup/symdue.sh start

  # Subsequent runs:
    ./setup/symdue.sh start          # bring up if stopped
    ./setup/symdue.sh restart        # cycle without rebuild
    ./setup/symdue.sh rebuild        # full clean rebuild
    ./setup/symdue.sh logs backend   # tail backend logs
    ./setup/symdue.sh stop           # halt the stack

NOTES
  • Auto-detects your host's docker group GID for Docker-out-of-Docker.
    No need for `DOCKER_GID=$(getent group docker | cut -d: -f3) docker compose up`.
  • Generated .env is mode 600 (owner-only readable).
  • Falls back to GID 999 on systems without `getent` (Mac/WSL).
EOF
}

# ────────────────────────────────────────────────────────────────────
# Dispatch
# ────────────────────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
    init)              cmd_init "$@" ;;
    start|up)          cmd_start "$@" ;;
    stop|down)         cmd_stop "$@" ;;
    restart)           cmd_restart "$@" ;;
    rebuild)           cmd_rebuild "$@" ;;
    logs)              cmd_logs "$@" ;;
    status|ps)         cmd_status "$@" ;;
    help|-h|--help|"") cmd_help ;;
    *)
        err "Unknown command: $COMMAND"
        cmd_help
        exit 1
        ;;
esac
