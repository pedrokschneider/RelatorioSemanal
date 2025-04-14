# Bot Discord para Relatórios Semanais 🤖

Este bot foi desenvolvido para automatizar a geração e envio de relatórios semanais através do Discord.

## 📋 Pré-requisitos

Antes de começar, você precisa ter instalado:

- Python 3.8 ou superior
- pip (gerenciador de pacotes do Python)
- Git (opcional, para clonar o repositório)

## 🔧 Instalação

1. **Clone o repositório ou baixe os arquivos**
```bash
git clone [URL_DO_REPOSITORIO]
cd [NOME_DA_PASTA]
```

2. **Instale as dependências necessárias**
```bash
pip install discord.py pandas openpyxl tqdm smartsheet-python-sdk pywin32 requests python-dotenv setuptools google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

3. **Configure o arquivo .env**
Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
```env
DISCORD_TOKEN=seu_token_aqui
SMARTSHEET_TOKEN=seu_token_smartsheet
```

## 🚀 Como Usar

### Opção 1: Executar como Aplicação em Segundo Plano

1. Simplesmente dê duplo clique no arquivo `discord_bot.pyw`
2. O bot iniciará em segundo plano sem mostrar janela
3. Para verificar se está funcionando, confira os logs na pasta `logs`

### Opção 2: Instalar como Serviço do Windows (Recomendado)

1. **Abra o PowerShell como administrador**

2. **Navegue até a pasta do bot**
```powershell
cd caminho/para/pasta/do/bot
```

3. **Instale o serviço**
```powershell
python discord_bot.pyw install
```

4. **Inicie o serviço**
```powershell
net start DiscordBotService
```

### Comandos para Gerenciar o Serviço

- **Parar o serviço**
```powershell
net stop DiscordBotService
```

- **Remover o serviço**
```powershell
python discord_bot.pyw remove
```

## 💬 Comandos do Discord

O bot responde aos seguintes comandos nos canais configurados:

- `!relatorio` - Gera um novo relatório semanal
- `!fila` - Mostra o status da fila de relatórios
- `!status` - Mostra o status atual do bot

## 🔄 Modos de Execução

O sistema opera em dois modos distintos com comportamentos diferentes de notificação:

### Modo Bot (Interativo)
- **Comando:** `!relatorio` no canal Discord
- **Comportamento:** Envia atualizações de progresso durante todo o processamento
- **Vantagem:** Feedback detalhado em tempo real 
- **Uso:** Para relatórios individuais sob demanda

### Modo Batch (via run.py)
- **Comando:** `python run.py [opções]`
- **Comportamento:** Processa múltiplos relatórios sequencialmente
- **Notificações:** Apenas mensagem final quando relatório está pronto
- **Opções:**
  - `--force` - Executa independente do dia da semana
  - `--no-notifications` - Desativa completamente as notificações
  - `--quiet` - Modo silencioso para terminal

### Controle de Rate Limit
O sistema implementa pausas automáticas entre mensagens do Discord (2s padrão) para evitar bloqueios por limite de taxa, especialmente importante no modo batch.

## 📁 Estrutura de Arquivos

```
.
├── discord_bot.pyw     # Arquivo principal do bot
├── report_queue.py     # Sistema de filas
├── .env               # Configurações sensíveis
└── logs/             # Pasta com logs do bot
    └── discord_bot_YYYY-MM-DD.log
```

## 📊 Monitoramento

Você pode monitorar o bot de três formas:

1. **Gerenciador de Serviços do Windows**
   - Abra `services.msc`
   - Procure por "Discord Bot Service"

2. **Arquivos de Log**
   - Verifique a pasta `logs`
   - Os arquivos são nomeados como `discord_bot_YYYY-MM-DD.log`

3. **Comandos do Discord**
   - Use `!status` ou `!fila` nos canais configurados

## ⚠️ Resolução de Problemas

### O bot não inicia

1. Verifique se todas as dependências estão instaladas
2. Confira os logs na pasta `logs`
3. Verifique se o arquivo `.env` está configurado corretamente

### Erros de permissão

1. Certifique-se de executar como administrador ao instalar o serviço
2. Verifique se o token do Discord tem as permissões necessárias

### Bot não responde

1. Verifique se o serviço está rodando
2. Confira os logs para ver possíveis erros
3. Teste a conexão com o Discord usando `!status`

## 🔒 Segurança

- Nunca compartilhe seu arquivo `.env`
- Mantenha os tokens seguros
- Use sempre HTTPS para clonar o repositório
- Evite compartilhar logs com informações sensíveis

## 📝 Logs

Os logs são salvos em:
```
./logs/discord_bot_YYYY-MM-DD.log
```

Exemplo de como ler os últimos logs:
```powershell
Get-Content .\logs\discord_bot_*.log -Tail 50
```

## 🤝 Contribuindo

1. Faça um Fork do projeto
2. Crie sua Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a Branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## ✨ Agradecimentos

- Equipe de desenvolvimento da Otus Engenharia
- Contribuidores
- Comunidade Python
- Discord API