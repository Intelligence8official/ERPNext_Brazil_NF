# Guia de Contribuição

Obrigado pelo interesse em contribuir com o **Brazil NF**! Este documento fornece diretrizes para contribuir com o projeto.

## 📋 Sumário

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Reportando Bugs](#reportando-bugs)
- [Sugerindo Melhorias](#sugerindo-melhorias)
- [Processo de Pull Request](#processo-de-pull-request)
- [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Documentação](#documentação)

## 📜 Código de Conduta

Este projeto adota um código de conduta para garantir um ambiente acolhedor para todos. Ao participar, você concorda em:

- Usar linguagem acolhedora e inclusiva
- Respeitar diferentes pontos de vista e experiências
- Aceitar críticas construtivas com elegância
- Focar no que é melhor para a comunidade
- Mostrar empatia com outros membros da comunidade

## 🤝 Como Contribuir

Existem várias formas de contribuir:

1. **Reportar bugs** - Encontrou um problema? Abra uma issue!
2. **Sugerir funcionalidades** - Tem uma ideia? Compartilhe conosco!
3. **Melhorar documentação** - Documentação clara ajuda todos
4. **Corrigir bugs** - Escolha uma issue e envie um PR
5. **Implementar funcionalidades** - Ajude a desenvolver novas features
6. **Revisar PRs** - Ajude a revisar código de outros contribuidores
7. **Traduzir** - Ajude com traduções para outros idiomas

## 🐛 Reportando Bugs

Antes de criar uma issue de bug:

1. **Verifique issues existentes** - O bug pode já ter sido reportado
2. **Use a versão mais recente** - O bug pode já ter sido corrigido

Ao criar a issue, inclua:

```markdown
### Descrição
Descrição clara e concisa do bug.

### Passos para Reproduzir
1. Vá para '...'
2. Clique em '...'
3. Veja o erro

### Comportamento Esperado
O que você esperava que acontecesse.

### Comportamento Atual
O que realmente aconteceu.

### Screenshots
Se aplicável, adicione screenshots.

### Ambiente
- ERPNext Version: [ex: v15.x]
- Frappe Version: [ex: v15.x]
- Brazil NF Version: [ex: v0.0.1]
- Sistema Operacional: [ex: Ubuntu 22.04]
- Navegador: [ex: Chrome 120]
```

## 💡 Sugerindo Melhorias

Para sugerir uma nova funcionalidade:

1. **Verifique se já existe** - Procure em issues abertas e fechadas
2. **Descreva claramente** - Explique o problema que a funcionalidade resolve
3. **Dê exemplos** - Mostre casos de uso concretos

Template para sugestões:

```markdown
### Problema
Descrição do problema que você está tentando resolver.

### Solução Proposta
Descrição clara da solução que você imagina.

### Alternativas Consideradas
Outras soluções que você considerou.

### Contexto Adicional
Qualquer informação adicional relevante.
```

## 🔄 Processo de Pull Request

### 1. Fork e Clone

```bash
# Fork o repositório pelo GitHub

# Clone seu fork
git clone https://github.com/seu-usuario/ERPNext_Brazil_NF.git
cd ERPNext_Brazil_NF

# Adicione o upstream
git remote add upstream https://github.com/Intelligence8official/ERPNext_Brazil_NF.git
```

### 2. Crie uma Branch

```bash
# Atualize a main
git checkout main
git pull upstream main

# Crie uma branch para sua contribuição
git checkout -b tipo/descricao-curta

# Exemplos:
# git checkout -b fix/corrigir-validacao-cnpj
# git checkout -b feature/adicionar-suporte-nfce
# git checkout -b docs/melhorar-instalacao
```

### Tipos de Branch

- `feature/` - Nova funcionalidade
- `fix/` - Correção de bug
- `docs/` - Documentação
- `refactor/` - Refatoração de código
- `test/` - Adição ou correção de testes

### 3. Faça suas Alterações

- Mantenha commits atômicos e bem descritos
- Siga os padrões de código do projeto
- Adicione testes quando aplicável
- Atualize a documentação se necessário

### 4. Commit Messages

Use mensagens de commit claras e descritivas:

```
tipo(escopo): descrição curta

Descrição mais detalhada se necessário.

Fixes #123
```

**Tipos:**
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Documentação
- `style`: Formatação (não afeta lógica)
- `refactor`: Refatoração de código
- `test`: Adição/correção de testes
- `chore`: Tarefas de manutenção

**Exemplos:**
```
feat(xml-parser): adicionar suporte para NFC-e

fix(cnpj): corrigir validação para CNPJs com zeros à esquerda

docs(install): adicionar instruções para Docker
```

### 5. Push e Pull Request

```bash
# Push para seu fork
git push origin sua-branch

# Abra um PR pelo GitHub
```

### 6. Checklist do PR

- [ ] Código segue os padrões do projeto
- [ ] Testes passando (se aplicável)
- [ ] Documentação atualizada (se aplicável)
- [ ] Commit messages seguem o padrão
- [ ] Branch está atualizada com main
- [ ] PR tem descrição clara do que foi feito

## 🛠️ Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.10+
- ERPNext 15+
- Frappe 15+
- Node.js 18+

### Setup Local

```bash
# Clone o repositório para apps do bench
cd ~/frappe-bench/apps
git clone https://github.com/seu-usuario/ERPNext_Brazil_NF.git brazil_nf

# Instale no site de desenvolvimento
cd ~/frappe-bench
bench --site dev.localhost install-app brazil_nf

# Instale dependências de desenvolvimento
pip install -e "apps/brazil_nf[dev]"
```

### Executando em Modo de Desenvolvimento

```bash
# Inicie o bench em modo de desenvolvimento
bench start

# Em outro terminal, watch para mudanças de frontend
bench watch
```

## 📝 Padrões de Código

### Python

- Siga o [PEP 8](https://pep8.org/)
- Use type hints quando possível
- Docstrings no formato Google
- Máximo de 100 caracteres por linha

```python
def validate_cnpj(cnpj: str) -> bool:
    """
    Validate a CNPJ number.

    Args:
        cnpj: The CNPJ string to validate (14 digits).

    Returns:
        True if valid, False otherwise.

    Raises:
        ValueError: If cnpj is empty.
    """
    if not cnpj:
        raise ValueError("CNPJ cannot be empty")
    # ...
```

### JavaScript

- Use ES6+ features
- Siga as convenções do Frappe Framework
- Use `const`/`let` em vez de `var`

### Formatação

```bash
# Python - use black e isort
black brazil_nf/
isort brazil_nf/

# JavaScript - use prettier (se disponível)
npx prettier --write "**/*.js"
```

## 🧪 Testes

### Executando Testes

```bash
# Todos os testes
bench --site dev.localhost run-tests --app brazil_nf

# Testes específicos
bench --site dev.localhost run-tests --app brazil_nf --module brazil_nf.utils.cnpj

# Com coverage
bench --site dev.localhost run-tests --app brazil_nf --coverage
```

### Escrevendo Testes

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestCNPJ(FrappeTestCase):
    def test_valid_cnpj(self):
        """Test that valid CNPJs pass validation."""
        from brazil_nf.utils.cnpj import validate_cnpj
        
        self.assertTrue(validate_cnpj("11222333000181"))

    def test_invalid_cnpj(self):
        """Test that invalid CNPJs fail validation."""
        from brazil_nf.utils.cnpj import validate_cnpj
        
        self.assertFalse(validate_cnpj("11111111111111"))
```

## 📚 Documentação

- Use Markdown para documentação
- Mantenha o README.md atualizado
- Documente novas funcionalidades
- Inclua exemplos de uso
- Escreva em português (pt-BR) para docs principais

### Estrutura de Documentação

```
docs/
├── QUICK_START.md      # Guia rápido
├── api/                # Documentação da API
├── guides/             # Guias detalhados
└── examples/           # Exemplos de uso
```

## 🏷️ Versionamento

Este projeto usa [Semantic Versioning](https://semver.org/):

- **MAJOR**: Mudanças incompatíveis na API
- **MINOR**: Novas funcionalidades compatíveis
- **PATCH**: Correções de bugs compatíveis

## ❓ Dúvidas

Se tiver dúvidas:

1. **Verifique a documentação** - Muitas respostas estão nos docs
2. **Procure em issues** - Sua dúvida pode já ter sido respondida
3. **Abra uma issue** - Use a tag `question`
4. **Discussões** - Use a aba Discussions do GitHub

## 🙏 Agradecimentos

Agradecemos a todos os contribuidores que ajudam a melhorar este projeto!

---

**Nota**: Este guia pode ser atualizado conforme o projeto evolui. Verifique periodicamente por atualizações.
