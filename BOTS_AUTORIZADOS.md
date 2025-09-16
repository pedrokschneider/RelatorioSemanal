# 🤖 Bots Autorizados - Configuração

## 📋 Visão Geral

O bot Discord agora suporta processamento de comandos de bots específicos autorizados, além de suas próprias mensagens. Isso permite que outros bots (como o `n8n_bot`) executem comandos automaticamente.

## 🔧 Configuração

### Método 1: Variável de Ambiente (Recomendado)

Adicione no arquivo `.env`:

```env
DISCORD_AUTHORIZED_BOTS=n8n_bot,automatização de projetos,outro_bot
```

**Nota:** Separe múltiplos bots por vírgula.

### Método 2: Menu Interativo

1. Execute o bot: `python discord_bot.py`
2. Escolha a opção "10. Gerenciar bots autorizados"
3. Use as opções para adicionar/remover bots

## 🎯 Bots Padrão Autorizados

Por padrão, os seguintes bots estão autorizados:

- `n8n_bot` - Bot de automação n8n
- `automatização de projetos` - Bot de automação de projetos

## 📝 Comandos Suportados

Os bots autorizados podem executar os seguintes comandos:

- `!notificar` - Enviar notificação de relatórios em falta
- `!notificar_coordenadores` - Enviar notificações diretas aos coordenadores
- `!controle` - Verificar controle de relatórios semanais

## 🔍 Como Funciona

1. **Detecção:** O bot monitora mensagens de todos os bots
2. **Verificação:** Verifica se o bot está na lista de autorizados
3. **Processamento:** Se autorizado, processa comandos encontrados na mensagem
4. **Execução:** Executa o comando automaticamente

## 🚀 Exemplo de Uso

Quando o `n8n_bot` envia uma mensagem contendo `!notificar`, o bot:

1. Detecta que é uma mensagem de bot
2. Verifica se `n8n_bot` está autorizado
3. Procura por comandos na mensagem
4. Executa o comando `!notificar` automaticamente

## 🛠️ Gerenciamento

### Adicionar Bot Autorizado

```bash
# Via menu interativo
python discord_bot.py
# Escolha opção 10 > 1
# Digite o nome do bot

# Via .env
DISCORD_AUTHORIZED_BOTS=n8n_bot,meu_bot,outro_bot
```

### Remover Bot Autorizado

```bash
# Via menu interativo
python discord_bot.py
# Escolha opção 10 > 2
# Selecione o bot para remover
```

### Listar Bots Autorizados

```bash
# Via menu interativo
python discord_bot.py
# Escolha opção 10 > 3
```

## 🔒 Segurança

- Apenas bots explicitamente autorizados podem executar comandos
- A verificação é feita por nome de usuário (case-insensitive)
- Comandos são limitados a uma lista específica
- Logs detalhados de todas as ações

## 📊 Logs

Todas as ações são registradas nos logs:

```
🤖 Bot detectou comando !notificar de bot autorizado (n8n_bot) para PRC_CREFAZ!
Conteúdo: !notificar
```

## ⚠️ Troubleshooting

### Bot não está executando comandos

1. Verifique se o bot está na lista de autorizados
2. Confirme se o comando está na lista de comandos permitidos
3. Verifique os logs para mensagens de erro
4. Teste com o menu interativo (opção 9)

### Adicionar novo bot

1. Use a opção 10 do menu para adicionar
2. Ou configure via variável de ambiente
3. Reinicie o bot para aplicar mudanças

## 🔄 Atualizações

Para aplicar mudanças na lista de bots autorizados:

1. **Via .env:** Reinicie o bot
2. **Via menu:** Mudanças são aplicadas imediatamente
