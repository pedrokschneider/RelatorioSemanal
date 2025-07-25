# Validação de Canais - Bot Discord

## Visão Geral

O bot agora possui funcionalidades de validação e orientação para canais que não estão configurados corretamente para gerar relatórios semanais. Isso ajuda os coordenadores a entenderem por que o comando `!relatorio` não funciona em determinados canais e como proceder.

## Funcionalidades Implementadas

### 1. Validação Automática de Canais

Quando um usuário digita `!relatorio` em qualquer canal, o bot automaticamente:

- ✅ **Verifica se o canal está configurado** na planilha de projetos
- ✅ **Verifica se o projeto está ativo** (status = "Sim")
- ✅ **Verifica se possui ID do Construflow** configurado
- ✅ **Fornece orientações específicas** baseadas no problema encontrado

### 2. Novos Comandos Disponíveis

#### `!relatorio`
- **Funcionalidade:** Gera relatório semanal (com validação automática)
- **Comportamento:** 
  - Se o canal for válido → adiciona à fila de processamento
  - Se o canal for inválido → envia mensagem de orientação

#### `!topico`
- **Funcionalidade:** Encontra o tópico correto para o projeto
- **Uso:** Quando o usuário está no canal errado
- **Exemplo:** `!topico` → mostra qual é o tópico correto para gerar relatórios

#### `!canais`
- **Funcionalidade:** Lista todos os canais ativos para relatórios
- **Uso:** Para ver quais projetos estão configurados
- **Exemplo:** `!canais` → mostra lista de projetos ativos

### 3. Tipos de Validação

#### Canal Não Configurado
```
❌ Canal Não Configurado

Este canal não está configurado para gerar relatórios semanais.

Para solicitar o cadastro:
📧 Entre em contato com o time de Dados e Tecnologia
📋 Informe o nome do projeto e o ID do canal: 123456789

Canais ativos disponíveis:
• Projeto A (Canal: 111111111111111111)
• Projeto B (Canal: 222222222222222222)
```

#### Relatórios Desativados
```
❌ Relatórios Desativados

O projeto Nome do Projeto está com relatórios semanais desativados.

Status atual: NAO

Para reativar:
📧 Entre em contato com o time de Dados e Tecnologia
📋 Solicite a reativação do projeto: Nome do Projeto
```

#### Projeto Incompleto
```
❌ Projeto Incompleto

O projeto Nome do Projeto não possui ID do Construflow configurado.

Para completar o cadastro:
📧 Entre em contato com o time de Dados e Tecnologia
📋 Solicite a configuração do ID Construflow para: Nome do Projeto
```

## Como Funciona

### 1. Processo de Validação

```python
def validate_channel_for_reports(self, channel_id):
    # 1. Carrega planilha de configuração
    # 2. Busca o projeto pelo canal
    # 3. Verifica se existe
    # 4. Verifica se está ativo
    # 5. Verifica se tem ID Construflow
    # 6. Retorna resultado da validação
```

### 2. Fluxo de Comandos

```
Usuário digita !relatorio
         ↓
Bot valida o canal
         ↓
    ┌─────────────┐
    │ Canal Válido? │
    └─────────────┘
         ↓
    ┌─────────────┐
    │     SIM     │    ┌─────────────┐
    └─────────────┘    │     NÃO     │
         ↓             └─────────────┘
   Adiciona à fila           ↓
         ↓             Envia orientação
   Processa relatório    específica
```

## Benefícios

### Para os Coordenadores
- ✅ **Orientação clara** sobre por que o comando não funciona
- ✅ **Instruções específicas** sobre como proceder
- ✅ **Lista de canais ativos** para referência
- ✅ **Contato direto** com o time de suporte

### Para o Time de Dados e Tecnologia
- ✅ **Redução de dúvidas** sobre configuração
- ✅ **Padronização** das solicitações de cadastro
- ✅ **Informações precisas** sobre problemas de configuração
- ✅ **Melhor experiência** do usuário

## Testando a Funcionalidade

### Script de Teste
```bash
# Teste geral
python test_channel_validation.py

# Teste de canal específico
python test_channel_validation.py 1290649572372123678
```

### Cenários de Teste
1. **Canal válido** → Deve processar normalmente
2. **Canal inexistente** → Deve mostrar orientação de cadastro
3. **Canal desativado** → Deve mostrar orientação de reativação
4. **Projeto incompleto** → Deve mostrar orientação de configuração

## Configuração Necessária

### Planilha de Projetos
A planilha deve conter as seguintes colunas:
- `discord_id` - ID do canal Discord
- `relatoriosemanal_status` - Status "Sim" ou "Não"
- `construflow_id` - ID do projeto no Construflow
- `Projeto - PR` - Nome do projeto

### Exemplo de Configuração
| Projeto - PR | discord_id | relatoriosemanal_status | construflow_id |
|--------------|------------|------------------------|----------------|
| Projeto A    | 123456789  | Sim                    | CF001          |
| Projeto B    | 987654321  | Não                    | CF002          |

## Comandos Disponíveis

| Comando | Descrição | Exemplo |
|---------|-----------|---------|
| `!relatorio` | Gerar relatório semanal | `!relatorio` |
| `!fila` | Ver status da fila | `!fila` |
| `!status` | Ver status da fila | `!status` |
| `!controle` | Verificar controle de relatórios | `!controle` |
| `!notificar` | Enviar notificação de relatórios em falta | `!notificar` |
| `!notificar_coordenadores` | Enviar notificações diretas | `!notificar_coordenadores` |
| `!topico` | Encontrar tópico correto | `!topico` |
| `!canais` | Listar canais ativos | `!canais` |

## Suporte

Para dúvidas ou problemas com a validação de canais:

📧 **Contato:** Time de Dados e Tecnologia
📋 **Informações necessárias:**
- Nome do projeto
- ID do canal Discord
- Descrição do problema 