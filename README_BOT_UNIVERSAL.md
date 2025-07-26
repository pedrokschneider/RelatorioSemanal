# 🤖 Bot Discord Universal - Guia Completo

## 🎯 Resumo

O **Bot Discord Universal** é a nova versão do bot que escuta **TODOS os canais e tópicos** do servidor Discord, não apenas os canais dos projetos configurados na planilha. Isso resolve o problema de "canais que não estão sendo ouvidos".

## 🚀 Como Inicializar o Bot Universal

### Opção 1: Migração Automática (Recomendado)

Execute o script de migração que fará tudo automaticamente:

```bash
python migrate_to_universal.py
```

Este script irá:
1. ✅ Verificar status dos serviços
2. ⏹️ Parar serviço original
3. 🗑️ Desinstalar serviço original
4. 🚀 Instalar serviço universal
5. ▶️ Iniciar serviço universal
6. 🧪 Testar bot universal

### Opção 2: Instalação Manual

```bash
# 1. Instalar o serviço universal
python install_service_final.py

# 2. Verificar se foi instalado
sc query DiscordReportBotUniversal

# 3. Iniciar o serviço
sc start DiscordReportBotUniversal
```

### Opção 3: Execução Direta (para testes)

```bash
# Executar diretamente (sem serviço)
python discord_bot_universal.py

# Ou usar o script de escolha
python run_bot.py
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

### Comandos que Funcionam em Qualquer Canal

| Comando | Descrição | Funciona em |
|---------|-----------|-------------|
| `!canais` | Listar canais ativos | ✅ Qualquer canal |
| `!ajuda` | Mostrar ajuda | ✅ Qualquer canal |

### Comandos que Funcionam em Canais Configurados

| Comando | Descrição | Funciona em |
|---------|-----------|-------------|
| `!relatorio` | Gerar relatório semanal | ✅ Canais configurados |
| `!fila` / `!status` | Ver status da fila | ✅ Canais configurados |
| `!controle` | Verificar controle de relatórios | ✅ Canais configurados |
| `!topico` | Encontrar tópico correto | ✅ Canais configurados |

### Comandos Administrativos (só no canal admin)

| Comando | Descrição | Funciona em |
|---------|-----------|-------------|
| `!notificar` | Enviar notificação de relatórios em falta | ✅ Só canal admin |
| `!notificar_coordenadores` | Enviar notificações diretas | ✅ Só canal admin |

## 🎯 Comportamento Inteligente

### Em Canais Configurados

```
Usuário: !relatorio
Bot: 📋 Relatório Solicitado
     Projeto: CFL_JPH
     Canal: #projeto-cfl-jph
     Status: Adicionado à fila de processamento
     ⏳ Aguarde o processamento...
```

### Em Canais Não Configurados

```
Usuário: !relatorio
Bot: ❌ Canal Não Configurado

Este canal não está configurado para gerar relatórios semanais.

Para solicitar o cadastro:
📧 Entre em contato com o time de Dados e Tecnologia
📋 Informe o nome do projeto e o ID do canal: 123456789

Canais ativos disponíveis:
• CFL_JPH (Canal: 1179395967204720710)
• CFL_MARECHAL (Canal: 1179395865375420427)
...
```

## 🔍 Verificação e Testes

### Testar o Bot Universal

```bash
python test_universal_bot.py
```

### Verificar Configuração

```bash
python run_bot.py
# Escolha opção 4: Verificar Configuração
```

### Verificar Status do Serviço

```bash
# Verificar se está rodando
sc query DiscordReportBotUniversal

# Ver logs em tempo real
Get-Content logs/discord_bot_universal_2025-07-25.log -Wait
```

## 📊 Logs

O bot gera logs detalhados em:
```
logs/discord_bot_universal_YYYY-MM-DD.log
```

### Informações nos Logs

- ✅ Conexão com Discord
- ✅ Canais carregados da planilha
- ✅ Comandos executados
- ✅ Erros e avisos
- ✅ Status do sistema

## 🛠️ Gerenciamento do Serviço

### Comandos do Windows

```bash
# Verificar status
sc query DiscordReportBotUniversal

# Parar serviço
sc stop DiscordReportBotUniversal

# Iniciar serviço
sc start DiscordReportBotUniversal

# Reiniciar serviço
sc stop DiscordReportBotUniversal && sc start DiscordReportBotUniversal

# Desinstalar serviço
sc delete DiscordReportBotUniversal
```

### Via PowerShell

```powershell
# Verificar status
Get-Service DiscordReportBotUniversal

# Parar serviço
Stop-Service DiscordReportBotUniversal

# Iniciar serviço
Start-Service DiscordReportBotUniversal

# Reiniciar serviço
Restart-Service DiscordReportBotUniversal
```

## 🔄 Migração e Rollback

### Migração do Bot Original

```bash
python migrate_to_universal.py
```

### Rollback para Bot Original

Se precisar voltar ao bot original:

```bash
# 1. Parar serviço universal
sc stop DiscordReportBotUniversal

# 2. Desinstalar serviço universal
sc delete DiscordReportBotUniversal

# 3. Instalar serviço original
python install_service_final.py
# (Editar o arquivo para usar discord_bot.pyw)

# 4. Iniciar serviço original
sc start DiscordReportBot
```

## 🚨 Troubleshooting

### Problemas Comuns

#### 1. Bot não responde
```bash
# Verificar se o serviço está rodando
sc query DiscordReportBotUniversal

# Verificar logs
Get-Content logs/discord_bot_universal_2025-07-25.log -Tail 50
```

#### 2. Token inválido
```bash
# Verificar arquivo .env
cat .env | grep DISCORD_TOKEN

# Testar configuração
python run_bot.py
# Escolha opção 4: Verificar Configuração
```

#### 3. Canais não carregados
```bash
# Testar carregamento de canais
python test_universal_bot.py
```

#### 4. Permissões insuficientes
- Verificar permissões do bot no Discord
- Verificar se o bot foi adicionado ao servidor
- Verificar se o token está correto

### Logs de Erro Comuns

```
❌ Token do Discord não configurado
   Solução: Verificar DISCORD_TOKEN no .env

❌ Planilha de configuração vazia
   Solução: Verificar acesso à planilha do Google

❌ Canal admin não configurado
   Solução: Verificar DISCORD_ADMIN_CHANNEL_ID no .env

❌ Erro de conexão com Discord
   Solução: Verificar internet e token
```

## 📞 Suporte

Para problemas ou dúvidas:

1. **Verificar logs**: `logs/discord_bot_universal_YYYY-MM-DD.log`
2. **Executar testes**: `python test_universal_bot.py`
3. **Verificar configuração**: `python run_bot.py` (opção 4)
4. **Contato**: Time de Dados e Tecnologia

## 🎉 Benefícios do Bot Universal

### Para os Usuários:
- ✅ **Flexibilidade**: Comandos funcionam em qualquer lugar
- ✅ **Orientação**: Mensagens claras quando algo não funciona
- ✅ **Conveniência**: Não precisam ir para canais específicos
- ✅ **Ajuda**: Comando `!ajuda` sempre disponível

### Para a Administração:
- ✅ **Visibilidade**: Bot sempre presente e acessível
- ✅ **Feedback**: Usuários recebem orientações claras
- ✅ **Redução de dúvidas**: Comandos explicativos
- ✅ **Melhor experiência**: Interface mais amigável

### Para o Sistema:
- ✅ **Monitoramento universal**: Escuta todos os canais
- ✅ **Validação inteligente**: Só processa canais configurados
- ✅ **Logs detalhados**: Melhor rastreabilidade
- ✅ **Estabilidade**: Serviço Windows robusto

---

**🎯 Resultado Final**: O bot agora escuta **TODOS os canais e tópicos**, mas só gera relatórios nos canais configurados, resolvendo o problema de "canais que não estão sendo ouvidos"! 