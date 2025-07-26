# 🤖 Bot Discord - Guia Completo

## 🎯 Resumo

O **Bot Discord** monitora os canais configurados na planilha de configuração e permite gerar relatórios semanais através de comandos no Discord.

## 🚀 Como Inicializar o Bot

### Opção 1: Execução Direta (para testes)

```bash
# Executar diretamente
python discord_bot.py

# Ou usar o script de execução
python run_bot.py
```

### Opção 2: Instalação como Serviço Windows

```bash
# Instalar o serviço
.\install_service_powershell.ps1

# Verificar se foi instalado
sc query DiscordReportBot

# Iniciar o serviço
sc start DiscordReportBot
```

### Opção 3: Instalação Simples

```bash
# Instalação simples
.\install_service_simple.ps1
```

## 🔧 Configuração

### Variáveis de Ambiente Necessárias

No arquivo `.env`:

```env
DISCORD_TOKEN=seu_token_aqui
DISCORD_ADMIN_CHANNEL_ID=id_do_canal_admin
```

### Permissões do Bot no Discord

O bot precisa das seguintes permissões:
- ✅ Ler mensagens
- ✅ Enviar mensagens
- ✅ Usar comandos slash (se aplicável)
- ✅ Ver canais

## 📋 Comandos Disponíveis

### Comandos em Canais Configurados

| Comando | Descrição |
|---------|-----------|
| `!relatorio` | Gerar relatório semanal |
| `!fila` / `!status` | Ver status da fila |
| `!controle` | Verificar controle de relatórios |
| `!topico` | Encontrar tópico correto |
| `!canais` | Listar canais ativos |
| `!ajuda` | Mostrar ajuda |

### Comandos Administrativos (só no canal admin)

| Comando | Descrição |
|---------|-----------|
| `!notificar` | Enviar notificação de relatórios em falta |
| `!notificar_coordenadores` | Enviar notificações diretas |

## 🎯 Funcionalidades

### Monitoramento de Canais
- Monitora apenas os canais configurados na planilha
- Usa polling para verificar mensagens
- Interface de menu interativo

### Sistema de Filas
- Processamento em fila para evitar sobrecarga
- Status em tempo real
- Notificações de progresso

### Geração de Relatórios
- Integração com o sistema de relatórios
- Upload automático para Google Drive
- Notificações no Discord

## 🔍 Troubleshooting

### Verificar Logs

```bash
# Ver logs em tempo real
Get-Content logs/discord_bot_2025-01-27.log -Wait

# Ver últimas linhas
Get-Content logs/discord_bot_2025-01-27.log -Tail 50
```

### Verificar Configuração

```bash
python run_bot.py
# Escolha opção 2 para verificar configuração
```

### Problemas Comuns

1. **Bot não responde**
   - Verificar se o token está correto
   - Verificar permissões no Discord
   - Verificar logs

2. **Comandos não funcionam**
   - Verificar se o canal está configurado na planilha
   - Verificar se o projeto está ativo

3. **Erro de conexão**
   - Verificar internet
   - Verificar se o Discord está online

## 📁 Estrutura do Projeto

```
RelatorioSemanal/
├── discord_bot.py          # Bot principal
├── run_bot.py              # Script de execução
├── report_queue.py         # Sistema de filas
├── run.py                  # Sistema de relatórios
├── report_system/          # Sistema principal
├── logs/                   # Logs do sistema
└── config/                 # Configurações
```

## 🚀 Comandos Rápidos

```bash
# Executar bot
python discord_bot.py

# Executar relatórios
python run.py --project ID_PROJETO

# Verificar configuração
python run_bot.py

# Instalar serviço
.\install_service_powershell.ps1
```

## 📞 Suporte

Para problemas ou dúvidas:
1. Verificar logs em `logs/discord_bot_YYYY-MM-DD.log`
2. Verificar configuração com `python run_bot.py`
3. Verificar se todos os arquivos estão presentes 