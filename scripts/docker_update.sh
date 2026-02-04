#!/bin/bash
#
# Brazil NF - Atualização via Docker (executar no HOST)
#
# Este script é executado no host (fora do container)
# e automaticamente executa o update dentro do container.
#
# Uso: ./docker_update.sh [opções]
#
# Opções:
#   --no-migrate    Pular migração do banco de dados
#   --build         Recompilar assets (JS/CSS)
#   --no-restart    Não reiniciar containers no final
#

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações - ajuste conforme necessário
CONTAINER_NAME="${BRAZIL_NF_CONTAINER:-frappe_docker-backend-1}"
DOCKER_COMPOSE_PATH="${BRAZIL_NF_COMPOSE_PATH:-.}"

# Flags
DO_RESTART=true
SCRIPT_ARGS=""

# Parse argumentos
for arg in "$@"; do
    case $arg in
        --no-restart)
            DO_RESTART=false
            ;;
        --no-migrate|--build)
            SCRIPT_ARGS="$SCRIPT_ARGS $arg"
            ;;
        --help)
            echo "Uso: ./docker_update.sh [opções]"
            echo ""
            echo "Opções:"
            echo "  --no-migrate    Pular migração do banco de dados"
            echo "  --build         Recompilar assets (JS/CSS)"
            echo "  --no-restart    Não reiniciar containers no final"
            echo "  --help          Mostrar esta ajuda"
            echo ""
            echo "Variáveis de ambiente:"
            echo "  BRAZIL_NF_CONTAINER      Nome do container (default: frappe_docker-backend-1)"
            echo "  BRAZIL_NF_COMPOSE_PATH   Caminho do docker-compose.yml (default: .)"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Brazil NF - Docker Update${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verificar se container existe
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Container '$CONTAINER_NAME' não encontrado ou não está rodando.${NC}"
    echo ""
    echo "Containers disponíveis:"
    docker ps --format '{{.Names}}' | grep -E "(backend|frappe|erpnext)" || echo "  Nenhum container frappe encontrado"
    echo ""
    echo "Defina a variável BRAZIL_NF_CONTAINER com o nome correto:"
    echo "  export BRAZIL_NF_CONTAINER=nome_do_container"
    exit 1
fi

echo -e "Container: ${BLUE}$CONTAINER_NAME${NC}"
echo ""

# Executar comandos dentro do container
docker exec -i "$CONTAINER_NAME" bash << 'SCRIPT'
set -e

BENCH_PATH="/home/frappe/frappe-bench"
APP_PATH="${BENCH_PATH}/apps/brazil_nf"
SITE_NAME="frontend"

echo "[1/5] Atualizando código..."
cd "$APP_PATH"
git pull

echo "[2/5] Verificando apps.txt..."
cd "$BENCH_PATH"
if ! grep -q "brazil_nf" sites/apps.txt; then
    echo "      Adicionando brazil_nf ao apps.txt..."
    echo "brazil_nf" >> sites/apps.txt
fi

echo "[3/5] Reinstalando app..."
bench --site "$SITE_NAME" install-app brazil_nf --force

echo "[4/5] Migrando banco de dados..."
bench --site "$SITE_NAME" migrate

echo "[5/5] Limpando cache..."
bench --site "$SITE_NAME" clear-cache

echo ""
echo "Comandos no container concluídos!"
SCRIPT

echo ""

# Reiniciar containers
if [ "$DO_RESTART" = true ]; then
    echo -e "${YELLOW}Reiniciando containers Docker...${NC}"

    # Tentar encontrar docker-compose.yml
    if [ -f "$DOCKER_COMPOSE_PATH/docker-compose.yml" ]; then
        cd "$DOCKER_COMPOSE_PATH"
        docker compose restart
    elif [ -f "$DOCKER_COMPOSE_PATH/compose.yml" ]; then
        cd "$DOCKER_COMPOSE_PATH"
        docker compose restart
    else
        echo -e "${YELLOW}docker-compose.yml não encontrado em $DOCKER_COMPOSE_PATH${NC}"
        echo -e "${YELLOW}Reiniciando container individualmente...${NC}"
        docker restart "$CONTAINER_NAME"
    fi

    echo -e "${GREEN}Containers reiniciados!${NC}"
else
    echo -e "${YELLOW}Reinício pulado. Execute manualmente:${NC}"
    echo -e "${BLUE}   docker compose restart${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Atualização concluída com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
