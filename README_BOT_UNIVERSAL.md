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

### Opção 2: Instalação como Serviço Windows (NSSM)

```powershell
# Instalar o serviço
.\install_service.ps1

# Gerenciar o serviço
nssm status "Discord Report Bot"    # Ver status
nssm stop "Discord Report Bot"      # Parar serviço
nssm start "Discord Report Bot"     # Iniciar serviço
nssm restart "Discord Report Bot"   # Reiniciar serviço

# Monitorar logs
Get-Content "C:\GitHub\RelatorioSemanal\logs\service.log" -Wait    # Ver logs em tempo real
Get-Content "C:\GitHub\RelatorioSemanal\logs\service.log" -Tail 50 # Ver últimas 50 linhas
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

### Verificar Status do Serviço

```powershell
# Verificar status do serviço
nssm status "Discord Report Bot"

# Ver logs do serviço
Get-Content "C:\GitHub\RelatorioSemanal\logs\service.log" -Wait

# Ver logs do bot
Get-Content "C:\GitHub\RelatorioSemanal\logs\discord_bot_$(Get-Date -Format 'yyyy-MM-dd').log" -Wait
```

### Reiniciar Serviço

Se o bot não estiver respondendo:

```powershell
# Parar o serviço
nssm stop "Discord Report Bot"

# Aguardar 5 segundos
Start-Sleep -Seconds 5

# Iniciar o serviço
nssm start "Discord Report Bot"

# Verificar status
nssm status "Discord Report Bot"
```

### Verificar Configuração

```bash
python run_bot.py
# Escolha opção 2 para verificar configuração
```

### Problemas Comuns

1. **Serviço não inicia**
   - Verificar logs em `C:\GitHub\RelatorioSemanal\logs\service.log`
   - Verificar se Python está instalado e no PATH
   - Verificar permissões do usuário

2. **Bot não responde**
   - Verificar se o token está correto no `.env`
   - Verificar permissões no Discord
   - Verificar logs do bot e do serviço

3. **Comandos não funcionam**
   - Verificar se o canal está configurado na planilha
   - Verificar se o projeto está ativo
   - Verificar permissões do bot no canal

4. **Erro de conexão**
   - Verificar internet
   - Verificar se o Discord está online
   - Reiniciar o serviço usando NSSM

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

```powershell
# Gerenciamento do Serviço
nssm status "Discord Report Bot"    # Ver status
nssm stop "Discord Report Bot"      # Parar
nssm start "Discord Report Bot"     # Iniciar
nssm restart "Discord Report Bot"   # Reiniciar

# Monitoramento
Get-Content "C:\GitHub\RelatorioSemanal\logs\service.log" -Wait  # Logs do serviço
Get-Content "logs\discord_bot_$(Get-Date -Format 'yyyy-MM-dd').log" -Wait  # Logs do bot

# Execução Manual (para testes)
python discord_bot.py              # Executar bot
python run.py --project ID_PROJETO # Executar relatórios
python run_bot.py                  # Menu interativo

# Instalação
.\install_service.ps1             # Instalar serviço com NSSM
```

## 📞 Suporte

Para problemas ou dúvidas:
1. Verificar logs em `logs/discord_bot_YYYY-MM-DD.log`
2. Verificar configuração com `python run_bot.py`
3. Verificar se todos os arquivos estão presentes 


PS C:\Users\Otus - TI> C:\GitHub\RelatorioSemanal\nssm\nssm.exe restart "Discord Report Bot"