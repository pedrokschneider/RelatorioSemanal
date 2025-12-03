# 📋 POP - Procedimento Operacional Padrão
## Sistema de Relatórios Semanais - Comando Discord

**Versão:** 1.0  
**Data:** Dezembro 2024  
**Responsável:** Equipe de Desenvolvimento

---

## 🎯 Objetivo

Este POP descreve o procedimento para gerar relatórios semanais através do comando Discord `!relatorio`, incluindo a opção de ocultar o botão do Dashboard de Indicadores.

---

## 📌 Comandos Disponíveis

### Comando Principal

```
!relatorio
```

**Descrição:** Gera relatório semanal completo para o projeto do canal.

**Comportamento:**
- Adiciona o relatório à fila de processamento
- Inclui o botão "Acessar Dashboard de Indicadores" no relatório do cliente
- Processamento assíncrono (notificação ao concluir)

---

### Comando com Parâmetro Opcional

```
!relatorio sem-dashboard
```

**Descrição:** Gera relatório semanal sem o botão do Dashboard de Indicadores.

**Quando usar:**
- Cliente não possui Dashboard configurado
- Cliente não tem acesso ao Dashboard
- Evitar confusão com link não funcional

**Comportamento:**
- Adiciona o relatório à fila de processamento
- **NÃO** inclui o botão "Acessar Dashboard de Indicadores"
- Processamento assíncrono (notificação ao concluir)

---

## 🔄 Fluxo de Processamento

### 1. Recebimento do Comando
- Bot detecta comando `!relatorio` no canal do projeto
- Extrai parâmetros (se houver)
- Valida configuração do canal

### 2. Adição à Fila
- Solicitação adicionada à fila de processamento
- Sistema verifica se já existe processamento em andamento
- Retorna posição na fila ao usuário

### 3. Processamento
- Worker processa solicitação da fila
- Executa script `run.py` com parâmetros apropriados
- Gera relatórios HTML (cliente e equipe)
- Upload para Google Drive

### 4. Notificação
- Mensagem enviada ao canal quando concluído
- Inclui links para relatórios e pasta do projeto

---

## 📝 Passo a Passo Operacional

### Para Gerar Relatório Padrão

1. Acesse o canal Discord do projeto
2. Digite: `!relatorio`
3. Aguarde confirmação de adição à fila
4. Aguarde processamento (pode levar alguns minutos)
5. Receba notificação com links dos relatórios

### Para Gerar Relatório Sem Dashboard

1. Acesse o canal Discord do projeto
2. Digite: `!relatorio sem-dashboard`
3. Aguarde confirmação de adição à fila
4. Aguarde processamento (pode levar alguns minutos)
5. Receba notificação com links dos relatórios

---

## ⚙️ Comandos Auxiliares

### Verificar Status da Fila

```
!status
```

ou

```
!fila
```

**Descrição:** Mostra status atual da fila de processamento, relatórios em andamento e workers disponíveis.

---

## 🔍 Verificações e Troubleshooting

### Problema: Comando não é reconhecido

**Solução:**
- Verifique se está no canal correto do projeto
- Confirme que o bot está online
- Verifique logs em `logs/discord_bot_YYYY-MM-DD.log`

### Problema: Relatório não é gerado

**Solução:**
- Verifique se o projeto está ativo na planilha (`relatoriosemanal_status = 'sim'`)
- Confirme que as colunas STATUS e DISCIPLINA do SmartSheet não estão vazias
- Verifique logs em `logs/service.log`

### Problema: Botão do Dashboard aparece quando não deveria

**Solução:**
- Use o comando `!relatorio sem-dashboard` explicitamente
- Verifique se o parâmetro foi passado corretamente

### Problema: Relatório em processamento há muito tempo

**Solução:**
- Use `!status` para verificar o status
- Se estiver preso há mais de 15 minutos, o sistema cancela automaticamente
- Tente gerar novamente após o cancelamento automático

---

## 📊 Estrutura dos Relatórios Gerados

### Relatório do Cliente
- **Arquivo:** `Email_cliente_[PROJETO]_[DATA].html`
- **Conteúdo:**
  - Pendências do Cliente
  - Atrasos e Desvios
  - Cronograma
  - Botão Dashboard (se não usar `sem-dashboard`)
  - Botões: Acessar Construflow, Enviar Feedback, Cronograma, Relatório Disciplinas

### Relatório da Equipe
- **Arquivo:** `Email_time_[PROJETO]_[DATA].html`
- **Conteúdo:**
  - Apontamentos Pendentes
  - Tarefas Concluídas
  - Atrasos e Desvios
  - Cronograma por Disciplina
  - Botões: Acessar Construflow, Enviar Feedback, Cronograma, Relatório Disciplinas

---

## 🎓 Projetos com Múltiplas Disciplinas do Cliente

### Como Funciona

O sistema suporta projetos onde o cliente possui **2 ou mais disciplinas** no Construflow.

### Configuração na Planilha

Na planilha de configuração de projetos, configure as disciplinas do cliente na coluna **`construflow_disciplinasclientes`**:

**Formato:**
- Separadas por **vírgula**: `Cliente 01, Cliente 02`
- Separadas por **ponto e vírgula**: `Cliente 01; Cliente 02`

**Exemplo:**
```
construflow_disciplinasclientes: "Cliente 01; Cliente 02"
```

### Comportamento do Sistema

#### 1. Filtragem de Issues do Construflow
- O sistema filtra automaticamente as issues do Construflow pelas disciplinas configuradas
- Apenas issues das disciplinas do cliente aparecem no relatório do cliente
- Issues de outras disciplinas não aparecem no relatório do cliente

#### 2. Agrupamento por Disciplina
- **Cronograma**: Tarefas são agrupadas automaticamente por disciplina
- **Atrasos e Desvios**: Tarefas são agrupadas por disciplina
- **Tarefas Concluídas** (equipe): Agrupadas por disciplina

#### 3. Botão "Relatório Disciplinas"
- **Atualmente**: Um único botão com um único URL (`email_url_disciplina`)
- **Comportamento**: O link aponta para um relatório consolidado que deve conter todas as disciplinas do cliente
- **Configuração**: Preencha a coluna `email_url_disciplina` na planilha com o link do relatório consolidado

### Exemplo Prático

**Projeto com 2 disciplinas:**
- Disciplina 1: "Cliente 01"
- Disciplina 2: "Cliente 02"

**Configuração:**
```
construflow_disciplinasclientes: "Cliente 01; Cliente 02"
email_url_disciplina: "https://docs.google.com/spreadsheets/d/..."
```

**Resultado no Relatório:**
- Cronograma mostra seções separadas:
  - **CLIENTE 01**
    - Tarefa A - 15/12
    - Tarefa B - 20/12
  - **CLIENTE 02**
    - Tarefa C - 18/12
    - Tarefa D - 22/12

- Botão "Relatório Disciplinas" aponta para o link configurado (deve conter ambas as disciplinas)

### Observações Importantes

⚠️ **Limitação Atual:**
- Há apenas **um botão** "Relatório Disciplinas" com **um único URL**
- Se você precisa de links separados para cada disciplina, será necessário criar um relatório consolidado no Google Sheets que contenha ambas as disciplinas

✅ **Recomendação:**
- Crie um relatório consolidado no Google Sheets que mostre todas as disciplinas do cliente
- Configure o link desse relatório consolidado na coluna `email_url_disciplina`
- O relatório consolidado deve permitir visualizar/filtrar por disciplina se necessário

---

## 🔐 Permissões e Acessos

### Requisitos para Executar Comando

- Bot deve estar autorizado no canal
- Canal deve estar configurado na planilha de projetos
- Projeto deve ter `relatoriosemanal_status = 'sim'`
- Projeto deve ter `smartsheet_id` configurado

### Acesso aos Relatórios

- Relatórios são salvos na pasta do projeto no Google Drive
- Link compartilhado via notificação no Discord
- Acesso depende das permissões da pasta do projeto

---

## 📚 Informações Técnicas

### Parâmetros do Sistema

- **Fila de Processamento:** Máximo de 2 workers simultâneos
- **Timeout:** 15 minutos por relatório
- **Cache:** Atualizado automaticamente antes de gerar relatório
- **Formato:** HTML otimizado para e-mail

### Arquivos Envolvidos

- `discord_bot.py` / `discord_bot.pyw` - Bot principal
- `report_queue.py` - Sistema de filas
- `run.py` - Script de geração
- `report_system/generators/html_report_generator.py` - Gerador HTML

---

## 📞 Suporte

### Em Caso de Problemas

1. Verifique os logs:
   - `logs/discord_bot_YYYY-MM-DD.log`
   - `logs/service.log`

2. Verifique status do sistema:
   - Use `!status` no Discord

3. Contate a equipe técnica se:
   - Erros persistentes após verificações
   - Problemas de configuração
   - Dúvidas sobre funcionalidades

---

## ✅ Checklist de Uso

- [ ] Canal do projeto configurado corretamente
- [ ] Bot online e respondendo
- [ ] Projeto ativo na planilha
- [ ] Comando digitado corretamente
- [ ] Aguardado confirmação de adição à fila
- [ ] Aguardado processamento
- [ ] Recebido notificação com links
- [ ] Verificado relatórios no Google Drive

---

## 🔄 Atualizações

**v1.1 (Dezembro 2024)**
- Adicionada seção sobre projetos com múltiplas disciplinas do cliente
- Documentação sobre agrupamento automático por disciplina
- Orientações sobre configuração de `email_url_disciplina` para múltiplas disciplinas

**v1.0 (Dezembro 2024)**
- Implementação do comando `!relatorio`
- Adição do parâmetro `sem-dashboard`
- Sistema de filas com workers
- Notificações automáticas

---

**Documento mantido por:** Equipe de Desenvolvimento  
**Última revisão:** Dezembro 2024


