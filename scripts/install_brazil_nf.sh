#!/bin/bash
#
# Brazil NF - Script de Instalação Inicial
# Execute este script apenas UMA VEZ para instalar o app
#

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações
BENCH_PATH="/home/frappe/frappe-bench"
SITE_NAME="frontend"
REPO_URL="https://github.com/Intelligence8official/ERPNext_Brazil_NF.git"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Brazil NF - Instalação Inicial${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd "$BENCH_PATH"

# 1. Verificar se já está instalado
if [ -d "apps/brazil_nf" ]; then
    echo -e "${YELLOW}App brazil_nf já existe em apps/${NC}"
    echo -e "${YELLOW}Use update_brazil_nf.sh para atualizar${NC}"
    exit 1
fi

# 2. Obter o app do repositório
echo -e "${YELLOW}[1/3] Baixando app do repositório...${NC}"
bench get-app "$REPO_URL" --branch main

echo -e "${GREEN}      Download concluído!${NC}"

# 3. Instalar no site
echo -e "${YELLOW}[2/3] Instalando app no site ${SITE_NAME}...${NC}"
bench --site "$SITE_NAME" install-app brazil_nf

echo -e "${GREEN}      Instalação concluída!${NC}"

# 4. Reiniciar
echo -e "${YELLOW}[3/3] Reiniciando workers...${NC}"
supervisorctl restart frappe: || bench restart || true

echo -e "${GREEN}      Workers reiniciados!${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Brazil NF instalado com sucesso!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Próximos passos:"
echo -e "  1. Acesse: ${BLUE}Nota Fiscal Settings${NC} para configurar"
echo -e "  2. Acesse: ${BLUE}NF Company Settings${NC} para adicionar certificado"
echo -e "  3. Para atualizações futuras, use: ${BLUE}./update_brazil_nf.sh${NC}"
echo ""
