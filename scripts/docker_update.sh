#!/bin/bash
#
# Brazil NF - Atualização via Docker (executar no HOST)
#
# Este script é executado no host (fora do container)
# e automaticamente executa o update dentro do container.
#
# Uso: ./docker_update.sh [opções]
#
# Opções são passadas para update_brazil_nf.sh:
#   --no-migrate    Pular migração do banco de dados
#   --no-restart    Pular reinício dos workers
#   --build         Recompilar assets (JS/CSS)
#

# Nome do container (ajuste se necessário)
CONTAINER_NAME="${BRAZIL_NF_CONTAINER:-frappe_docker-backend-1}"

# Verificar se container existe
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '$CONTAINER_NAME' não encontrado ou não está rodando."
    echo ""
    echo "Containers disponíveis:"
    docker ps --format '{{.Names}}' | grep -E "(backend|frappe)" || echo "  Nenhum container frappe encontrado"
    echo ""
    echo "Defina a variável BRAZIL_NF_CONTAINER com o nome correto:"
    echo "  export BRAZIL_NF_CONTAINER=nome_do_container"
    exit 1
fi

echo "Executando atualização no container: $CONTAINER_NAME"
echo ""

# Executar script de update dentro do container
docker exec -it "$CONTAINER_NAME" bash -c "
    if [ -f /home/frappe/frappe-bench/apps/brazil_nf/scripts/update_brazil_nf.sh ]; then
        bash /home/frappe/frappe-bench/apps/brazil_nf/scripts/update_brazil_nf.sh $*
    else
        echo 'Script de update não encontrado. Executando comandos manualmente...'
        cd /home/frappe/frappe-bench/apps/brazil_nf && git pull
        cd /home/frappe/frappe-bench && bench --site frontend migrate
        supervisorctl restart frappe:
        echo 'Atualização concluída!'
    fi
"
