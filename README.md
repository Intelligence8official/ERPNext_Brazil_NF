# Brazil NF - Brazilian Nota Fiscal Management for ERPNext

Este módulo Frappe fornece gerenciamento completo de documentos fiscais eletrônicos brasileiros (NF-e, CT-e, NFS-e) no ERPNext.

## Funcionalidades

- **Captura Automática de Documentos**: Monitora a API de Distribuição DF-e do SEFAZ para NF-e, CT-e e NFS-e recebidos
- **Integração com Email**: Captura documentos fiscais de anexos de email
- **Criação Automática**: Cria automaticamente Fornecedores e Itens a partir dos documentos fiscais
- **Conciliação com Pedido de Compra**: Vincula notas fiscais recebidas com Pedidos de Compra
- **Rastreamento Visual de Status**: Indicadores coloridos para status de processamento
- **Suporte Completo a Impostos**: Trata ICMS, IPI, PIS, COFINS, ISS e todos os impostos brasileiros

## Tipos de Documentos Suportados

- **NF-e** (Nota Fiscal Eletrônica): Notas fiscais de produtos
- **CT-e** (Conhecimento de Transporte Eletrônico): Documentos de transporte
- **NFS-e** (Nota Fiscal de Serviço Eletrônica): Notas fiscais de serviços

## Requisitos

- Frappe Framework >= 15.0.0
- ERPNext >= 15.0.0
- Python >= 3.10
- Certificado Digital A1 (formato PFX/PKCS12)

## Instalação

Consulte o arquivo [INSTALL.md](INSTALL.md) para instruções detalhadas de instalação, incluindo instalação em Docker.

### Instalação Rápida (Ambientes Padrão)

```bash
# Baixar o app
bench get-app https://github.com/seu-repositorio/brazil_nf

# Instalar no site
bench --site seu-site install-app brazil_nf

# Executar migrações
bench --site seu-site migrate
```

## Configuração

### 1. Configurações Gerais

Acesse **Brazil NF > Nota Fiscal Settings** e configure:

- **Ambiente SEFAZ**: Produção ou Homologação
- **Tipos de Documentos**: Habilite NF-e, CT-e e/ou NFS-e
- **Intervalo de Busca**: Frequência de verificação (mínimo 5 minutos)
- **Criação Automática**: Configurações para criar fornecedores/itens automaticamente
- **Conciliação de PO**: Tolerância de valores e período de busca

### 2. Configurações por Empresa

Acesse **Brazil NF > NF Company Settings** e adicione para cada empresa:

- **CNPJ**: CNPJ da empresa (14 dígitos)
- **Certificado Digital**: Upload do arquivo PFX
- **Senha do Certificado**: Senha para desbloquear o PFX
- **Inscrição Estadual/Municipal**: Registros fiscais

### 3. Integração com Email (Opcional)

Se desejar capturar notas fiscais de emails:

1. Configure uma **Email Account** no ERPNext
2. Em **Nota Fiscal Settings**, habilite "Email Import"
3. Selecione a conta de email configurada
4. Defina padrões de assunto para identificar emails com NF

## Uso

### Visualizando Notas Fiscais

- Acesse **Brazil NF > Nota Fiscal** para ver todas as notas capturadas
- Use os filtros para encontrar notas por status, fornecedor, data, etc.
- Os indicadores coloridos mostram o status de cada etapa do processamento

### Status e Indicadores

| Status | Cor | Significado |
|--------|-----|-------------|
| Pending | Cinza | Aguardando processamento |
| Linked | Verde | Vinculado a registro existente |
| Created | Azul | Registro criado automaticamente |
| Not Found | Laranja | Registro não encontrado |
| Failed | Vermelho | Erro no processamento |
| Partial | Amarelo | Processamento parcial |

### Ações Manuais

Na visualização de uma Nota Fiscal, você pode:

- **Processar Documento**: Executar todo o fluxo de processamento
- **Criar Fornecedor**: Criar fornecedor manualmente
- **Criar Itens**: Criar itens faltantes
- **Vincular PO**: Vincular a um Pedido de Compra existente
- **Criar Fatura**: Criar Purchase Invoice a partir da NF

## Estrutura de Campos Fiscais

### Impostos NF-e/CT-e
- ICMS (base, alíquota, valor, ST)
- IPI (CST, base, alíquota, valor)
- PIS (CST, base, alíquota, valor)
- COFINS (CST, base, alíquota, valor)
- II (Imposto de Importação)
- FCP (Fundo de Combate à Pobreza)

### Impostos NFS-e
- ISS (base, alíquota, valor, retenção)
- IRRF, INSS, CSLL (retenções)
- PIS/COFINS sobre serviços

## API

O módulo expõe endpoints para integração:

```python
# Buscar documentos manualmente
frappe.call("brazil_nf.api.fetch_documents", company="Sua Empresa")

# Processar uma nota fiscal
frappe.call("brazil_nf.api.process_nota_fiscal", nota_fiscal_name="NF-00001")

# Validar chave de acesso
frappe.call("brazil_nf.api.validate_chave_acesso", chave="44 dígitos")
```

## Desenvolvimento

### Estrutura do Projeto

```
brazil_nf/
├── brazil_nf/
│   ├── brazil_nf/
│   │   ├── doctype/          # DocTypes
│   │   └── workspace/        # Workspace
│   ├── services/             # Lógica de negócio
│   ├── utils/                # Utilitários
│   ├── api/                  # Endpoints API
│   └── setup/                # Instalação
├── pyproject.toml
└── README.md
```

### Executando Testes

```bash
bench --site seu-site run-tests --app brazil_nf
```

## Licença

MIT

## Suporte

Para reportar bugs ou solicitar funcionalidades, abra uma issue no repositório do projeto.
