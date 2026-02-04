# Guia de Instalação - Brazil NF para ERPNext

Este guia fornece instruções detalhadas para instalar o módulo Brazil NF em uma instalação ERPNext self-hosted com Docker na Digital Ocean.

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Método 1: Instalação via Git (Recomendado)](#método-1-instalação-via-git-recomendado)
3. [Método 2: Instalação Manual (Cópia de Arquivos)](#método-2-instalação-manual-cópia-de-arquivos)
4. [Pós-Instalação](#pós-instalação)
5. [Configuração Inicial](#configuração-inicial)
6. [Verificação da Instalação](#verificação-da-instalação)
7. [Troubleshooting](#troubleshooting)
8. [Atualização do App](#atualização-do-app)

---

## Pré-requisitos

### Requisitos do Sistema
- ERPNext v15.x instalado e funcionando
- Frappe Framework v15.x
- Python 3.10 ou superior
- Acesso SSH ao servidor Digital Ocean
- Docker e Docker Compose instalados

### Requisitos de Negócio
- Certificado Digital A1 (formato .pfx ou .p12)
- CNPJ da empresa cadastrado no ERPNext
- Credenciais de acesso ao SEFAZ (se aplicável)

---

## Método 1: Instalação via Git (Recomendado)

### Passo 1: Conectar ao Servidor

```bash
# Conectar via SSH ao seu servidor Digital Ocean
ssh root@seu-ip-do-servidor

# Ou se usar chave SSH
ssh -i ~/.ssh/sua-chave root@seu-ip-do-servidor
```

### Passo 2: Identificar os Containers Docker

```bash
# Listar containers em execução
docker ps

# Você deve ver containers como:
# - frappe_docker-backend-1 (ou similar)
# - frappe_docker-frontend-1
# - frappe_docker-queue-short-1
# - frappe_docker-scheduler-1
```

Anote o nome do container **backend** (geralmente `frappe_docker-backend-1` ou `erpnext-backend-1`).

### Passo 3: Acessar o Container Backend

```bash
# Acessar o container (substitua pelo nome correto do seu container)
docker exec -it frappe_docker-backend-1 bash
```

### Passo 4: Navegar até o Diretório do Bench

```bash
# Dentro do container, navegue até o diretório do bench
cd /home/frappe/frappe-bench
```

### Passo 5: Baixar o App Brazil NF

```bash
# Opção A: Se o repositório estiver no GitHub
bench get-app https://github.com/seu-usuario/brazil_nf.git

# Opção B: Se estiver em repositório privado
bench get-app https://usuario:token@github.com/seu-usuario/brazil_nf.git

# Opção C: Se estiver em outro Git (GitLab, Bitbucket)
bench get-app https://gitlab.com/seu-usuario/brazil_nf.git
```

### Passo 6: Instalar o App no Site

```bash
# Listar sites disponíveis
ls sites/

# Instalar o app no seu site (substitua pelo nome do seu site)
bench --site seu-site.com install-app brazil_nf

# Se tiver apenas um site, pode usar:
bench --site $(ls sites/ | grep -v apps.txt | grep -v common_site_config.json | head -1) install-app brazil_nf
```

### Passo 7: Executar Migrações

```bash
# Aplicar migrações do banco de dados
bench --site seu-site.com migrate

# Limpar cache
bench --site seu-site.com clear-cache
```

### Passo 8: Sair do Container e Reiniciar

```bash
# Sair do container
exit

# Reiniciar os containers para aplicar as mudanças
docker compose restart

# Ou se usar docker-compose (versão antiga)
docker-compose restart
```

---

## Método 2: Instalação Manual (Cópia de Arquivos)

Use este método se não tiver acesso ao repositório Git ou preferir copiar os arquivos manualmente.

### Passo 1: Preparar os Arquivos Localmente

```bash
# No seu computador local, navegue até a pasta do app
cd /caminho/para/brazil_nf

# Criar arquivo tar do app
tar -czvf brazil_nf.tar.gz brazil_nf/
```

### Passo 2: Copiar para o Servidor

```bash
# Copiar o arquivo para o servidor Digital Ocean
scp brazil_nf.tar.gz root@seu-ip-do-servidor:/tmp/
```

### Passo 3: Copiar para Dentro do Container

```bash
# No servidor, copiar para o container
docker cp /tmp/brazil_nf.tar.gz frappe_docker-backend-1:/tmp/
```

### Passo 4: Extrair e Instalar

```bash
# Acessar o container
docker exec -it frappe_docker-backend-1 bash

# Navegar e extrair
cd /home/frappe/frappe-bench/apps
tar -xzvf /tmp/brazil_nf.tar.gz

# Instalar dependências Python
cd brazil_nf
pip install -e .

# Voltar ao bench e instalar
cd /home/frappe/frappe-bench
bench --site seu-site.com install-app brazil_nf
bench --site seu-site.com migrate
```

### Passo 5: Reiniciar Containers

```bash
exit
docker compose restart
```

---

## Pós-Instalação

### Verificar se o App foi Instalado

```bash
# Acessar o container
docker exec -it frappe_docker-backend-1 bash

# Verificar apps instalados
bench --site seu-site.com list-apps

# Deve mostrar:
# frappe
# erpnext
# brazil_nf  <-- Novo app
```

### Verificar Logs

```bash
# Ver logs do container backend
docker logs frappe_docker-backend-1 --tail 100

# Ver logs do scheduler (importante para jobs agendados)
docker logs frappe_docker-scheduler-1 --tail 100
```

---

## Configuração Inicial

### 1. Acessar o ERPNext

1. Abra seu navegador e acesse `https://seu-site.com`
2. Faça login com suas credenciais de administrador

### 2. Configurar Nota Fiscal Settings

1. Na barra de pesquisa, digite "Nota Fiscal Settings" ou acesse:
   - Menu > Brazil NF > Nota Fiscal Settings

2. Configure as seguintes opções:

```
┌─────────────────────────────────────────────────────────────┐
│ NOTA FISCAL SETTINGS                                        │
├─────────────────────────────────────────────────────────────┤
│ General Settings                                            │
│ ☑ Module Enabled                                            │
│ Default Company: [Selecione sua empresa]                    │
├─────────────────────────────────────────────────────────────┤
│ SEFAZ Integration                                           │
│ SEFAZ Environment: [Production/Homologation]                │
│ Fetch Interval (minutes): 10                                │
│ ☑ Fetch NF-e                                                │
│ ☑ Fetch CT-e                                                │
│ ☑ Fetch NFS-e                                               │
├─────────────────────────────────────────────────────────────┤
│ Auto-Creation Settings                                      │
│ ☑ Auto-Create Suppliers                                     │
│ Default Supplier Group: [Selecione]                         │
│ ☐ Auto-Create Items (opcional)                              │
│ ☐ Auto-Create Purchase Invoice (opcional)                   │
├─────────────────────────────────────────────────────────────┤
│ PO Matching Settings                                        │
│ ☑ Enable PO Matching                                        │
│ Value Tolerance (%): 5                                      │
│ Date Range (days): 30                                       │
└─────────────────────────────────────────────────────────────┘
```

3. Clique em **Save**

### 3. Configurar NF Company Settings

1. Acesse: Menu > Brazil NF > NF Company Settings
2. Clique em **+ Add NF Company Settings**

3. Preencha os campos:

```
┌─────────────────────────────────────────────────────────────┐
│ NF COMPANY SETTINGS                                         │
├─────────────────────────────────────────────────────────────┤
│ Company Information                                         │
│ Company: [Selecione sua empresa ERPNext]                    │
│ CNPJ: 12345678000199 (apenas números, 14 dígitos)          │
│ Inscricao Estadual (IE): [Seu IE]                          │
│ Inscricao Municipal (IM): [Seu IM]                         │
├─────────────────────────────────────────────────────────────┤
│ Digital Certificate                                         │
│ Certificate File (PFX): [Upload do arquivo .pfx]           │
│ Certificate Password: [Senha do certificado]               │
│                                                             │
│ Certificate Expiry: (preenchido automaticamente)           │
│ ☑ Certificate Valid (verificado automaticamente)           │
├─────────────────────────────────────────────────────────────┤
│ Synchronization                                             │
│ ☑ Sync Enabled                                              │
│ Last NSU (NF-e): 0                                          │
│ Last NSU (CT-e): 0                                          │
│ Last NSU (NFS-e): 0                                         │
└─────────────────────────────────────────────────────────────┘
```

4. Clique em **Save**
5. Clique em **Test Connection** para verificar o certificado

### 4. Configurar Integração com Email (Opcional)

Se desejar capturar NFs de emails:

1. Primeiro, configure uma **Email Account** no ERPNext:
   - Setup > Email > Email Account
   - Configure com IMAP habilitado

2. Em **Nota Fiscal Settings**:
   - Marque "Enable Email Import"
   - Selecione a Email Account configurada
   - Defina padrões de assunto (ex: `*nota fiscal*`, `*nf-e*`, `*danfe*`)

---

## Verificação da Instalação

### Teste 1: Verificar Workspace

1. Acesse o ERPNext
2. No menu lateral, deve aparecer **Brazil NF**
3. Clique para ver os atalhos: Nota Fiscal, Settings, Import Logs

### Teste 2: Verificar DocTypes

```bash
# No container
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench

# Verificar se os DocTypes foram criados
bench --site seu-site.com console
```

```python
# No console Python
import frappe
frappe.get_all("DocType", filters={"module": "Brazil NF"})
# Deve retornar: Nota Fiscal, Nota Fiscal Item, Nota Fiscal Evento,
#                Nota Fiscal Settings, NF Company Settings, NF Import Log
exit()
```

### Teste 3: Verificar Scheduler

```bash
# Ver jobs agendados
bench --site seu-site.com show-pending-jobs

# Deve mostrar jobs do brazil_nf se configurado
```

### Teste 4: Upload Manual de XML

1. Acesse Brazil NF > Nota Fiscal
2. Clique em **+ Add Nota Fiscal**
3. Faça upload de um arquivo XML de teste
4. Verifique se os campos são preenchidos automaticamente

---

## Troubleshooting

### Problema: App não aparece no menu

**Solução:**
```bash
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site seu-site.com clear-cache
bench --site seu-site.com clear-website-cache
bench build --app brazil_nf
exit
docker compose restart
```

### Problema: Erro "Module not found"

**Solução:**
```bash
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench/apps/brazil_nf
pip install -e .
exit
docker compose restart
```

### Problema: Certificado não valida

**Possíveis causas:**
1. Senha incorreta
2. Certificado expirado
3. Formato inválido (deve ser .pfx ou .p12)

**Verificar:**
```bash
# No container
docker exec -it frappe_docker-backend-1 bash
python3 << 'EOF'
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

with open("/caminho/para/certificado.pfx", "rb") as f:
    pfx_data = f.read()

try:
    key, cert, chain = load_key_and_certificates(pfx_data, b"sua_senha")
    print("Certificado válido!")
    print(f"Expira em: {cert.not_valid_after_utc}")
except Exception as e:
    print(f"Erro: {e}")
EOF
```

### Problema: Jobs não executam

**Verificar scheduler:**
```bash
# Ver se o scheduler está rodando
docker logs frappe_docker-scheduler-1 --tail 50

# Reiniciar scheduler
docker compose restart scheduler
```

**Executar job manualmente:**
```bash
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site seu-site.com execute brazil_nf.services.dfe_client.scheduled_fetch
```

### Problema: Erro de permissão

**Solução:**
```bash
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site seu-site.com add-to-hosts
bench --site seu-site.com set-admin-password nova-senha
```

### Problema: Custom Fields não aparecem

**Solução:**
```bash
docker exec -it frappe_docker-backend-1 bash
cd /home/frappe/frappe-bench
bench --site seu-site.com migrate
bench --site seu-site.com clear-cache
# Executar setup de instalação manualmente
bench --site seu-site.com execute brazil_nf.setup.install.after_install
```

---

## Atualização do App

### Atualizar para Nova Versão

```bash
# Acessar servidor
ssh root@seu-ip-do-servidor

# Acessar container
docker exec -it frappe_docker-backend-1 bash

# Navegar até o app
cd /home/frappe/frappe-bench/apps/brazil_nf

# Atualizar código
git pull origin main

# Aplicar migrações
cd /home/frappe/frappe-bench
bench --site seu-site.com migrate
bench --site seu-site.com clear-cache

# Sair e reiniciar
exit
docker compose restart
```

---

## Comandos Úteis

```bash
# ============ DOCKER ============
# Listar containers
docker ps

# Ver logs em tempo real
docker logs -f frappe_docker-backend-1

# Reiniciar todos os containers
docker compose restart

# Parar containers
docker compose down

# Iniciar containers
docker compose up -d

# ============ BENCH ============
# Acessar console Python do Frappe
bench --site seu-site.com console

# Executar comando específico
bench --site seu-site.com execute modulo.funcao

# Ver sites
bench --site all list-apps

# Backup do site
bench --site seu-site.com backup

# Restaurar backup
bench --site seu-site.com restore /caminho/backup.sql.gz

# ============ BRAZIL NF ============
# Buscar documentos manualmente
bench --site seu-site.com execute brazil_nf.services.dfe_client.scheduled_fetch

# Processar emails
bench --site seu-site.com execute brazil_nf.services.email_monitor.check_emails

# Limpar logs antigos
bench --site seu-site.com execute brazil_nf.services.processor.cleanup_old_logs
```

---

## Suporte

Se encontrar problemas não cobertos neste guia:

1. Verifique os logs: `docker logs frappe_docker-backend-1 --tail 200`
2. Verifique o Error Log no ERPNext: Setup > Error Log
3. Abra uma issue no repositório do projeto com:
   - Versão do ERPNext/Frappe
   - Logs de erro completos
   - Passos para reproduzir o problema
