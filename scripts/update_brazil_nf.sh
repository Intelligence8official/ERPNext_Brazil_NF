#!/bin/bash
#
# Brazil NF - Script de Atualização
# Uso: ./update_brazil_nf.sh [opções]
#
# Opções:
#   --no-migrate    Pular migração do banco de dados
#   --no-restart    Pular reinício dos workers
#   --build         Recompilar assets (JS/CSS)
#

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações
BENCH_PATH="/home/frappe/frappe-bench"
APP_PATH="${BENCH_PATH}/apps/brazil_nf"
SITE_NAME="frontend"

# Flags
DO_MIGRATE=true
DO_RESTART=true
DO_BUILD=false

# Parse argumentos
for arg in "$@"; do
    case $arg in
        --no-migrate)
            DO_MIGRATE=false
            ;;
        --no-restart)
            DO_RESTART=false
            ;;
        --build)
            DO_BUILD=true
            ;;
        --help)
            echo "Uso: ./update_brazil_nf.sh [opções]"
            echo ""
            echo "Opções:"
            echo "  --no-migrate    Pular migração do banco de dados"
            echo "  --no-restart    Pular reinício dos workers"
            echo "  --build         Recompilar assets (JS/CSS)"
            echo "  --help          Mostrar esta ajuda"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Brazil NF - Atualizador${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verificar se estamos no ambiente correto
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}ERRO: Diretório do app não encontrado: $APP_PATH${NC}"
    echo -e "${YELLOW}Certifique-se de executar este script dentro do container Docker${NC}"
    exit 1
fi

# 1. Atualizar código
echo -e "${YELLOW}[1/4] Atualizando código do repositório...${NC}"
cd "$APP_PATH"

# Verificar se há mudanças locais
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}      Aviso: Existem mudanças locais não commitadas${NC}"
    git stash
    STASHED=true
fi

git pull origin main

if [ "$STASHED" = true ]; then
    echo -e "${YELLOW}      Restaurando mudanças locais...${NC}"
    git stash pop || true
fi

echo -e "${GREEN}      Código atualizado!${NC}"

# 2. Migrar banco de dados
if [ "$DO_MIGRATE" = true ]; then
    echo -e "${YELLOW}[2/4] Migrando banco de dados...${NC}"
    cd "$BENCH_PATH"
    bench --site "$SITE_NAME" migrate
    echo -e "${GREEN}      Migração concluída!${NC}"
else
    echo -e "${BLUE}[2/4] Migração pulada (--no-migrate)${NC}"
fi

# 3. Build assets (opcional)
if [ "$DO_BUILD" = true ]; then
    echo -e "${YELLOW}[3/4] Recompilando assets...${NC}"
    cd "$BENCH_PATH"
    bench build --app brazil_nf
    echo -e "${GREEN}      Assets recompilados!${NC}"
else
    echo -e "${BLUE}[3/4] Build pulado (use --build para recompilar)${NC}"
fi

# 4. Reiniciar workers
if [ "$DO_RESTART" = true ]; then
    echo -e "${YELLOW}[4/4] Reiniciando workers...${NC}"
    supervisorctl restart frappe: || {
        echo -e "${YELLOW}      supervisorctl falhou, tentando alternativa...${NC}"
        cd "$BENCH_PATH"
        bench restart || true
    }
    echo -e "${GREEN}      Workers reiniciados!${NC}"
else
    echo -e "${BLUE}[4/4] Reinício pulado (--no-restart)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Atualização concluída com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Mostrar versão atual
cd "$APP_PATH"
COMMIT=$(git rev-parse --short HEAD)
DATE=$(git log -1 --format=%cd --date=short)
echo -e "Versão atual: ${BLUE}${COMMIT}${NC} (${DATE})"
echo ""
