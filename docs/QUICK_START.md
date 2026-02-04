# Quick Start - Brazil NF

Guia rápido para instalar o Brazil NF em ERPNext Docker.

## Instalação em 5 Minutos

### 1. Conectar ao Servidor

```bash
ssh root@seu-servidor-digital-ocean
```

### 2. Acessar Container

```bash
# Encontrar nome do container backend
docker ps | grep backend

# Acessar (ajuste o nome conforme sua instalação)
docker exec -it frappe_docker-backend-1 bash
```

### 3. Instalar App

```bash
cd /home/frappe/frappe-bench

# Baixar app (ajuste a URL do seu repositório)
bench get-app https://github.com/seu-usuario/brazil_nf.git

# Instalar no site
bench --site seu-site.com install-app brazil_nf

# Migrar banco de dados
bench --site seu-site.com migrate

# Sair do container
exit
```

### 4. Reiniciar Docker

```bash
docker compose restart
```

### 5. Configurar no ERPNext

1. **Acessar ERPNext** → Brazil NF → Nota Fiscal Settings
   - Habilitar módulo
   - Configurar tipos de documento (NF-e, CT-e, NFS-e)

2. **Configurar Empresa** → Brazil NF → NF Company Settings
   - Informar CNPJ
   - Upload do certificado .pfx
   - Informar senha do certificado

### Pronto!

O sistema começará a buscar notas fiscais automaticamente a cada 10 minutos.

---

## Comandos Essenciais

```bash
# Buscar NFs manualmente
docker exec -it frappe_docker-backend-1 bench --site seu-site.com execute brazil_nf.services.dfe_client.scheduled_fetch

# Ver logs
docker logs frappe_docker-backend-1 --tail 100

# Limpar cache
docker exec -it frappe_docker-backend-1 bench --site seu-site.com clear-cache

# Reiniciar
docker compose restart
```

---

Para instruções detalhadas, consulte [INSTALL.md](../INSTALL.md).
