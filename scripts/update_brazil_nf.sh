#!/bin/bash
#
# Brazil NF - Script de Atualização (executa DENTRO do container)
# Uso: ./update_brazil_nf.sh [opções]
#
# Opções:
#   --no-migrate    Pular migração do banco de dados
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
DO_BUILD=false

# Parse argumentos
for arg in "$@"; do
    case $arg in
        --no-migrate)
            DO_MIGRATE=false
            ;;
        --build)
            DO_BUILD=true
            ;;
        --help)
            echo "Uso: ./update_brazil_nf.sh [opções]"
            echo ""
            echo "Opções:"
            echo "  --no-migrate    Pular migração do banco de dados"
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

cd "$BENCH_PATH"

# 1. Atualizar código
echo -e "${YELLOW}[1/6] Atualizando código do repositório...${NC}"
cd "$APP_PATH"

# Verificar se há mudanças locais
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}      Aviso: Existem mudanças locais não commitadas${NC}"
    git stash
    STASHED=true
fi

git pull

if [ "$STASHED" = true ]; then
    echo -e "${YELLOW}      Restaurando mudanças locais...${NC}"
    git stash pop || true
fi

echo -e "${GREEN}      Código atualizado!${NC}"

# 2. Garantir que brazil_nf está no apps.txt
echo -e "${YELLOW}[2/6] Verificando apps.txt...${NC}"
cd "$BENCH_PATH"

if grep -q "brazil_nf" sites/apps.txt; then
    echo -e "${GREEN}      brazil_nf já está em apps.txt${NC}"
else
    echo -e "${YELLOW}      Adicionando brazil_nf ao apps.txt...${NC}"
    echo "brazil_nf" >> sites/apps.txt
    echo -e "${GREEN}      Adicionado!${NC}"
fi

# 3. Reinstalar app com --force
echo -e "${YELLOW}[3/6] Reinstalando app (--force)...${NC}"
bench --site "$SITE_NAME" install-app brazil_nf --force
echo -e "${GREEN}      App reinstalado!${NC}"

# 4. Migrar banco de dados
if [ "$DO_MIGRATE" = true ]; then
    echo -e "${YELLOW}[4/6] Migrando banco de dados...${NC}"
    bench --site "$SITE_NAME" migrate
    echo -e "${GREEN}      Migração concluída!${NC}"
else
    echo -e "${BLUE}[4/6] Migração pulada (--no-migrate)${NC}"
fi

# 5. Build assets (opcional)
if [ "$DO_BUILD" = true ]; then
    echo -e "${YELLOW}[5/6] Recompilando assets...${NC}"
    bench build --app brazil_nf
    echo -e "${GREEN}      Assets recompilados!${NC}"
else
    echo -e "${BLUE}[5/6] Build pulado (use --build para recompilar)${NC}"
fi

# 6. Limpar cache
echo -e "${YELLOW}[6/6] Limpando cache...${NC}"
bench --site "$SITE_NAME" clear-cache
echo -e "${GREEN}      Cache limpo!${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Atualização concluída!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANTE: Reinicie os containers Docker:${NC}"
echo -e "${BLUE}   docker compose restart${NC}"
echo ""

# Mostrar versão atual
cd "$APP_PATH"
COMMIT=$(git rev-parse --short HEAD)
DATE=$(git log -1 --format=%cd --date=short)
echo -e "Versão atual: ${BLUE}${COMMIT}${NC} (${DATE})"
echo ""
