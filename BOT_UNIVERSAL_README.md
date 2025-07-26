# Bot Discord Universal - Documentação

## Visão Geral

O **Bot Discord Universal** é uma nova versão do bot que escuta **todos os canais e tópicos** do servidor Discord, não apenas os canais dos projetos configurados na planilha.

## Diferenças entre os Bots

### Bot Original (`discord_bot.py`)
- ✅ **Monitoramento limitado**: Só escuta canais configurados na planilha
- ✅ **Polling**: Verifica mensagens periodicamente nos canais específicos
- ✅ **Comandos**: Funciona apenas em canais de projetos
- ❌ **Limitação**: Não responde em outros canais/tópicos

### Bot Universal (`discord_bot_universal.py`)
- ✅ **Monitoramento universal**: Escuta TODOS os canais e tópicos
- ✅ **Eventos em tempo real**: Responde instantaneamente a comandos
- ✅ **Comandos inteligentes**: 
  - Funciona em qualquer canal
  - Valida se o canal é configurado para relatórios
  - Fornece orientações quando não configurado
- ✅ **Melhor experiência**: Usuários podem usar comandos de qualquer lugar

## Funcionalidades do Bot Universal

### 1. Comandos Disponíveis em Qualquer Canal

| Comando | Descrição | Funciona em |
|---------|-----------|-------------|
| `!relatorio` | Gerar relatório semanal | Canais configurados |
| `!fila` / `!status` | Ver status da fila | Canais configurados |
| `!controle` | Verificar controle de relatórios | Canais configurados |
| `!notificar` | Enviar notificação de relatórios em falta | Só canal admin |
| `!notificar_coordenadores` | Enviar notificações diretas | Só canal admin |
| `!topico` | Encontrar tópico correto | Canais configurados |
| `!canais` | Listar canais ativos | Qualquer canal |
| `!ajuda` | Mostrar ajuda | Qualquer canal |

### 2. Comportamento Inteligente

#### Em Canais Configurados:
```
Usuário: !relatorio
Bot: 📋 Relatório Solicitado
     Projeto: CFL_JPH
     Canal: #projeto-cfl-jph
     Status: Adicionado à fila de processamento
     ⏳ Aguarde o processamento...
```

#### Em Canais Não Configurados:
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

### 3. Comandos Administrativos

Os comandos `!notificar` e `!notificar_coordenadores` só funcionam no canal administrativo configurado no `.env`:

```
Usuário: !notificar (em canal não-admin)
Bot: ❌ Este comando só funciona no canal administrativo.
```

## Como Usar

### 1. Iniciar o Bot Universal

```bash
python discord_bot_universal.py
```

### 2. Testar o Bot

```bash
python test_universal_bot.py
```

### 3. Verificar Status

O bot mostrará informações de conexão:
```
Bot Universal conectado como BotName#1234
Servidores conectados: 1
Servidor: Nome do Servidor (ID: 123456789)
  Canais: 25
  Tópicos: 10
```

## Vantagens do Bot Universal

### Para os Usuários:
- ✅ **Flexibilidade**: Podem usar comandos de qualquer lugar
- ✅ **Orientação**: Recebem instruções claras quando algo não funciona
- ✅ **Conveniência**: Não precisam ir para canais específicos
- ✅ **Ajuda**: Comando `!ajuda` sempre disponível

### Para a Administração:
- ✅ **Visibilidade**: Bot sempre presente e acessível
- ✅ **Feedback**: Usuários recebem orientações claras
- ✅ **Redução de dúvidas**: Comandos explicativos
- ✅ **Melhor experiência**: Interface mais amigável

## Configuração

### Variáveis de Ambiente Necessárias

```env
DISCORD_TOKEN=seu_token_aqui
DISCORD_ADMIN_CHANNEL_ID=id_do_canal_admin
```

### Permissões do Bot

O bot precisa das seguintes permissões no Discord:
- ✅ Ler mensagens
- ✅ Enviar mensagens
- ✅ Usar comandos slash (se aplicável)
- ✅ Ver canais

## Logs

O bot gera logs detalhados em:
```
logs/discord_bot_universal_YYYY-MM-DD.log
```

## Troubleshooting

### Problemas Comuns

1. **Bot não responde**
   - Verificar se o token está correto
   - Verificar permissões do bot no servidor
   - Verificar logs para erros

2. **Comandos não funcionam**
   - Verificar se o canal está configurado na planilha
   - Verificar se o projeto está ativo
   - Usar `!canais` para ver canais disponíveis

3. **Erro de conexão**
   - Verificar conexão com internet
   - Verificar se o Discord está online
   - Verificar logs para detalhes

## Migração do Bot Original

Para migrar do bot original para o universal:

1. **Parar o bot original**
2. **Iniciar o bot universal**
3. **Testar comandos em diferentes canais**
4. **Verificar logs para garantir funcionamento**

## Comandos de Teste

### Testar em Canal Configurado:
```
!relatorio
!fila
!controle
!topico
```

### Testar em Canal Não Configurado:
```
!relatorio
!canais
!ajuda
```

### Testar Comandos Admin (só no canal admin):
```
!notificar
!notificar_coordenadores
```

## Suporte

Para dúvidas ou problemas:
- 📧 Entre em contato com o time de Dados e Tecnologia
- 📋 Verifique os logs para detalhes de erro
- 🔍 Use o comando `!ajuda` no Discord 