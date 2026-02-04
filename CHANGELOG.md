# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2024-XX-XX

### Adicionado

#### DocTypes
- **Nota Fiscal**: Documento principal para NF-e, CT-e e NFS-e
  - Campos de identificação (chave de acesso, número, série)
  - Campos do emitente e tomador
  - Campos de valores e impostos (ICMS, IPI, PIS, COFINS, ISS)
  - Campos específicos para NFS-e (regime tributário, códigos de serviço)
  - Campos específicos para CT-e (modal, remetente, destinatário)
  - Status de processamento com indicadores visuais
  - Rastreamento de origem (SEFAZ/Email)

- **Nota Fiscal Item**: Tabela filha para itens da NF
  - Classificação fiscal (NCM, CEST, CFOP)
  - Impostos por item (ICMS, IPI, PIS, COFINS, ISS)
  - Vinculação com Item do ERPNext

- **Nota Fiscal Evento**: Tabela filha para eventos
  - Cancelamentos
  - Cartas de correção
  - Manifestações

- **Nota Fiscal Settings**: Configurações do módulo
  - Integração SEFAZ
  - Integração Email
  - Criação automática
  - Conciliação de PO

- **NF Company Settings**: Configurações por empresa
  - Certificado digital
  - NSU por tipo de documento

- **NF Import Log**: Rastreamento de importações

#### Serviços
- **dfe_client.py**: Cliente para API DF-e do SEFAZ
  - Suporte a NF-e, CT-e, NFS-e
  - Autenticação com certificado digital
  - Busca incremental por NSU

- **xml_parser.py**: Parser multi-schema para XMLs
  - NF-e v4.00
  - CT-e
  - NFS-e SPED/Nacional
  - NFS-e ABRASF

- **supplier_manager.py**: Gerenciamento de fornecedores
  - Busca por CNPJ
  - Criação automática

- **item_manager.py**: Gerenciamento de itens
  - Busca por código do fornecedor
  - Busca por NCM
  - Criação automática

- **po_matcher.py**: Conciliação de pedidos de compra
  - Algoritmo de pontuação
  - Tolerância configurável

- **invoice_creator.py**: Criação de Purchase Invoice

- **email_monitor.py**: Monitoramento de emails
  - Extração de anexos XML

- **cert_utils.py**: Utilitários para certificados PFX

#### Utilitários
- **cnpj.py**: Validação e formatação de CNPJ
- **chave_acesso.py**: Validação e parsing de chave de acesso

#### API
- Endpoints para busca manual
- Endpoints para processamento
- Endpoints para validação

#### Documentação
- README.md com visão geral
- INSTALL.md com guia detalhado para Docker
- QUICK_START.md com instalação rápida

### Notas
- Implementação inicial focada em recebimento de documentos (entrada)
- SOAP para NF-e/CT-e ainda não implementado (apenas REST para NFS-e)
- Requer ERPNext v15+ e Frappe v15+

---

## Roadmap

### [0.2.0] - Planejado
- Implementação completa de SOAP para NF-e/CT-e
- Dashboard com gráficos e estatísticas
- Relatório de conciliação
- Notificações por email

### [0.3.0] - Planejado
- Emissão de NF-e (saída)
- DANFE PDF generation
- Integração com módulo de vendas

### [1.0.0] - Planejado
- Versão estável para produção
- Testes automatizados completos
- Documentação da API
