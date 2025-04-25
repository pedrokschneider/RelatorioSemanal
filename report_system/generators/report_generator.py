"""
Gerador de relatórios otimizado combinando recursos do SimpleReportGenerator original e V2.
"""

import os
import sys
import inspect
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

class SimpleReportGenerator:
    """Gera relatórios com formato personalizado e links para o Construflow."""
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o gerador de relatórios.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.prompt_template = self._load_prompt_template()
        # Criar diretório de relatórios se não existir
        self.reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def _load_prompt_template(self) -> str:
        """Carrega o template de prompt do arquivo."""
        try:
            with open(self.config.prompt_template_path, 'r', encoding='utf-8') as f:
                template = f.read()
                logger.info(f"Template carregado de '{self.config.prompt_template_path}'")
                return template
        except FileNotFoundError:
            logger.error(f"Arquivo de template não encontrado: {self.config.prompt_template_path}")
            
            # Template padrão caso o arquivo não exista
            return """Bom dia pessoal,

Espero que essa mensagem os encontre bem.

Segue abaixo um breve resumo do andamento do projeto do empreendimento [NOME_PROJETO]:

### Pontos que precisam de respostas [NOME_CLIENTE]:
[APONTAMENTOS_CLIENTE]

### Realizados:
[TAREFAS_REALIZADAS]

### Atrasos e desvios do período:
[ATRASOS_PERIODO]

### Programado para esta semana:
[PROGRAMACAO_SEMANA]

### Status de Apontamentos por Disciplina:
[TABELA_APONTAMENTOS]

Abaixo disponibilizamos os links para acesso ao formulário de feedback, ao cronograma e Construflow para acompanhamento do projeto.

[LINK_FEEDBACK]
[LINK_CRONOGRAMA]
[LINK_CONSTRUFLOW]

Qualquer dúvida, estamos à disposição!
"""
    
    def generate_report(self, data: Dict[str, Any]) -> str:
        """
        Gera um relatório para o projeto usando template personalizado.
        
        Args:
            data: Dados processados do projeto
            
        Returns:
            Texto do relatório gerado
        """
        if not self.prompt_template:
            logger.error("Template de prompt não disponível")
            return "Erro: Template de relatório não disponível."
        
        # Obter nome do cliente - primeiro nome ou nome do projeto se não houver cliente
        project_name = data.get('project_name', 'Projeto')
        project_id = data.get('project_id', '')
        system = self._get_system_instance()  # Obtém instância do sistema
        client_names = system.get_client_names(project_id) if system else []
        client_name = client_names[0] if client_names else project_name
        
        # Preparar substituições básicas
        replacements = {
            "[NOME_PROJETO]": project_name,
            "[NOME_CLIENTE]": client_name,
            "[DATA_ATUAL]": datetime.now().strftime("%d/%m/%Y"),
            "[LINK_FEEDBACK]": "https://forms.construflow.com.br/feedback",
            "[LINK_CRONOGRAMA]": "https://drive.google.com/drive/folders/...",
            "[LINK_CONSTRUFLOW]": f"https://app.construflow.com.br/project/{project_id}"
        }
        
        # Gerar apontamentos do cliente com links
        apontamentos_cliente = self._gerar_apontamentos_cliente(data)
        replacements["[APONTAMENTOS_CLIENTE]"] = apontamentos_cliente
        
        # Gerar lista de tarefas realizadas - garantir funcionamento com os dois placeholders
        tarefas_realizadas = self._gerar_tarefas_realizadas(data)
        replacements["[TAREFAS_REALIZADAS]"] = tarefas_realizadas
        replacements["[TAREFAS_CONCLUIDAS]"] = tarefas_realizadas
        
        # Gerar lista de atrasos do período - garantir funcionamento com os dois placeholders
        atrasos_periodo = self._gerar_atrasos_periodo(data)
        replacements["[ATRASOS_PERIODO]"] = atrasos_periodo
        replacements["[TAREFAS_ATRASADAS]"] = atrasos_periodo
        
        # Gerar programação da semana - garantir funcionamento com os dois placeholders
        programacao_semana = self._gerar_programacao_semana(data)
        replacements["[PROGRAMACAO_SEMANA]"] = programacao_semana
        replacements["[TAREFAS_PROGRAMADAS]"] = programacao_semana
        
        # Gerar tabela de apontamentos por disciplina
        tabela_apontamentos = self._gerar_tabela_apontamentos(data)
        replacements["[TABELA_APONTAMENTOS]"] = tabela_apontamentos
        
        # Aplicar substituições
        report = self.prompt_template
        for key, value in replacements.items():
            report = report.replace(key, str(value))
        
        return report
    
    def _get_system_instance(self):
        """
        Tenta obter uma instância do sistema WeeklyReportSystem.
        Necessário para acessar métodos como get_client_names.
        """
        # Procurar classes WeeklyReportSystem no módulo atual
        for name, obj in inspect.getmembers(sys.modules['__main__']):
            if inspect.isclass(obj) and name == 'WeeklyReportSystem':
                # Procurar instâncias dessa classe
                for frame in inspect.stack():
                    for var in frame[0].f_locals.values():
                        if isinstance(var, obj):
                            return var
        
        # Se não encontrou, verificar se self.config é da classe ConfigManager
        # e se foi passado por um WeeklyReportSystem
        return None
    
    def _gerar_apontamentos_cliente(self, data: Dict[str, Any]) -> str:
        """Gera a seção de apontamentos que precisam de resposta do cliente."""
        project_id = data.get('project_id', '')
        
        # Verificar se temos dados de apontamentos
        if not data.get('construflow_data', {}).get('active_issues'):
            return "Sem apontamentos pendentes para o cliente nesta semana."
            
        # Obter apontamentos do cliente
        system = self._get_system_instance()
        active_issues = data.get('construflow_data', {}).get('active_issues', [])
        client_issues = data.get('construflow_data', {}).get('client_issues', [])
        
        # Usar client_issues se disponível, caso contrário tentar filtrar active_issues
        if client_issues:
            logger.info(f"Usando {len(client_issues)} apontamentos já filtrados do cliente")
        else:
            # Tentar usar o método filter_client_issues do sistema
            try:
                import pandas as pd
                if system and hasattr(system, 'filter_client_issues') and active_issues:
                    df_issues = pd.DataFrame(active_issues)
                    filtered_issues = system.filter_client_issues(df_issues, project_id).to_dict('records')
                    client_issues = filtered_issues
                    logger.info(f"Filtrados {len(client_issues)} apontamentos via system.filter_client_issues")
            except Exception as e:
                logger.warning(f"Erro ao filtrar apontamentos do cliente: {e}")
                # Fallback: usar os primeiros 5 active_issues
                client_issues = active_issues[:5]
                logger.info(f"Usando {len(client_issues)} primeiros apontamentos como fallback")
        
        if not client_issues:
            return "Sem apontamentos pendentes para o cliente nesta semana."
        
        # Filtrar apenas apontamentos com status_y == 'todo' (A Fazer)
        todo_issues = []
        for issue in client_issues:
            if issue.get('status_y') == 'todo':
                todo_issues.append(issue)
        
        logger.info(f"Filtrados {len(todo_issues)} apontamentos com status 'todo' de {len(client_issues)} apontamentos do cliente")
        
        # Se não houver apontamentos com status 'todo', usar client_issues original
        if not todo_issues:
            todo_issues = client_issues
            logger.warning("Nenhum apontamento com status 'todo' encontrado, usando lista original")
        
        # Obter todas as issues do projeto do cache (issues_cache)
        all_issues = data.get('construflow_data', {}).get('all_issues', [])
        issues_cache = {}
        
        # Criar um dicionário de issues por code para busca rápida
        # Isso é necessário para garantir que o link correto para o apontamento seja gerado
        # usando o ID do apontamento que está em issues_cache, não em issues-disciplines_cache
        for issue in all_issues:
            # O projectId pode não estar disponível após o merge, então confiamos que
            # todas as issues em all_issues são do projeto atual
            if issue.get('code'):
                issues_cache[str(issue.get('code'))] = issue
        
        logger.info(f"Encontradas {len(issues_cache)} issues no cache para busca por code")
        
        # Agora vamos buscar nos dados originais de issues para garantir que o ID correto seja obtido
        try:
            # Tentar obter diretamente do connector
            if hasattr(self, 'construflow') and self.construflow:
                issues_df = self.construflow.get_issues()
            elif system and hasattr(system, 'processor') and hasattr(system.processor, 'construflow'):
                issues_df = system.processor.construflow.get_issues()
            else:
                issues_df = None
            
            if issues_df is not None and not issues_df.empty:
                # Converter para dicionário para busca rápida
                # Chave é uma tupla (project_id, code)
                raw_issues = {}
                for _, row in issues_df.iterrows():
                    if pd.notna(row.get('code')) and pd.notna(row.get('projectId')):
                        key = (str(row['projectId']), str(row['code']))
                        raw_issues[key] = row.to_dict()
                
                logger.info(f"Carregadas {len(raw_issues)} issues brutas para busca precisa por (projectId, code)")
        except Exception as e:
            logger.warning(f"Erro ao carregar issues brutas: {e}")
            raw_issues = {}
        
        # Agrupar issues por prioridade
        issues_por_prioridade = {
            'alta': [],
            'media': [],
            'baixa': [],
            'sem_prioridade': []
        }
        
        # Processar cada issue para encontrar o ID correto e criar o link
        for issue in todo_issues:
            issue_code = str(issue.get('code', 'N/A'))
            issue_title = issue.get('title', 'Apontamento sem título')
            
            # Buscar o ID correto primeiro no dicionário de issues brutas usando (project_id, code)
            correct_issue_id = None
            
            # 1. Primeiro tentar encontrar o ID exato nas issues brutas (melhor opção)
            if raw_issues and (str(project_id), issue_code) in raw_issues:
                correct_issue_id = raw_issues[(str(project_id), issue_code)]['id']
                priority_raw = raw_issues[(str(project_id), issue_code)].get('priority')
                logger.info(f"Encontrado ID direto por (projectId, code) para o apontamento {issue_code}: {correct_issue_id}")
            # 2. Se não encontrar, tentar no issues_cache (pode ser menos preciso devido ao merge)
            elif issue_code in issues_cache and issues_cache[issue_code].get('id'):
                correct_issue_id = issues_cache[issue_code].get('id')
                priority_raw = issues_cache[issue_code].get('priority')
                logger.info(f"Encontrado ID via issues_cache para o apontamento {issue_code}: {correct_issue_id}")
            # 3. Fallback para o ID atual (antigo)
            else:
                correct_issue_id = issue.get('id')
                priority_raw = issue.get('priority')
                if correct_issue_id:
                    logger.warning(f"Não foi encontrado ID para o apontamento {issue_code}. Usando ID atual: {correct_issue_id}")
                else:
                    # Se nem o ID antigo estiver disponível, usar um ID genérico (não ideal, mas evita links quebrados)
                    correct_issue_id = "0"
                    logger.error(f"Não foi possível determinar o ID para o apontamento {issue_code}. Usando ID genérico.")
            
            # Construir o link para o apontamento com o ID correto
            construflow_url = f"https://app.construflow.com.br/workspace/project/{project_id}/issues?issueId={correct_issue_id}"
        
            # Calcular tempo de abertura
            dias_aberto = ""
            created_at = issue.get('createdAt') or issue.get('created_at')
            if created_at:
                try:
                    from datetime import datetime
                    if isinstance(created_at, str):
                        if 'Z' in created_at:
                            created_at = created_at.replace('Z', '+00:00')
                        created_date = datetime.fromisoformat(created_at)
                    else:
                        created_date = created_at
                    
                    agora = datetime.now()
                    if created_date.tzinfo:
                        agora = agora.replace(tzinfo=created_date.tzinfo)
                    
                    diferenca = agora - created_date
                    dias = diferenca.days
                    
                    if dias == 0:
                        dias_aberto = "(aberto hoje)"
                    elif dias == 1:
                        dias_aberto = "(aberto há 1 dia)"
                    else:
                        dias_aberto = f"(aberto há {dias} dias)"
                except Exception:
                    pass
            
            # Determinar em qual grupo de prioridade colocar essa issue
            priority = str(priority_raw).lower() if priority_raw else None
            
            # Mapeamento de valores possíveis de prioridade
            if priority in ['high', 'alta', '3', 3]:
                priority_group = 'alta'
            elif priority in ['medium', 'media', 'média', '2', 2]:
                priority_group = 'media'
            elif priority in ['low', 'baixa', '1', 1]:
                priority_group = 'baixa'
            else:
                priority_group = 'sem_prioridade'
            
            # Armazenar a linha formatada no grupo correto
            issue_line = f"[#{issue_code}]({construflow_url}) – {issue_title} {dias_aberto}"
            issues_por_prioridade[priority_group].append(issue_line)
        
        # Construir o resultado final agrupado por prioridade
        result = ""
        
        # Prioridade Alta - Vermelho
        if issues_por_prioridade['alta']:
            result += "🔴 Prioridade Alta\n"
            for issue_line in issues_por_prioridade['alta']:
                result += f"- {issue_line}\n"
            result += "\n"
        
        # Prioridade Média - Laranja
        if issues_por_prioridade['media']:
            result += "🟠 Prioridade Média\n"
            for issue_line in issues_por_prioridade['media']:
                result += f"- {issue_line}\n"
            result += "\n"
        
        # Prioridade Baixa - Verde
        if issues_por_prioridade['baixa']:
            result += "🟢 Prioridade Baixa\n"
            for issue_line in issues_por_prioridade['baixa']:
                result += f"- {issue_line}\n"
            result += "\n"
        
        # Sem prioridade definida
        if issues_por_prioridade['sem_prioridade']:
            result += "⚪ Sem Prioridade Definida\n"
            for issue_line in issues_por_prioridade['sem_prioridade']:
                result += f"- {issue_line}\n"
            result += "\n"
        
        return result.strip() if result else "Sem apontamentos pendentes para o cliente nesta semana."

    def _gerar_tarefas_realizadas(self, data: Dict[str, Any]) -> str:
        """Gera a seção de tarefas realizadas no período."""
        # Verificar formato dos dados do Smartsheet
        smartsheet_data = data.get('smartsheet_data', {})
        
        # Verificar se smartsheet_data é um dicionário com chaves específicas
        if isinstance(smartsheet_data, dict) and 'completed_tasks' in smartsheet_data:
            # Usar diretamente a lista de tarefas concluídas
            completed_tasks = smartsheet_data.get('completed_tasks', [])
            logger.info(f"Usando {len(completed_tasks)} tarefas concluídas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            # Usar todas as tarefas e filtrar as concluídas
            all_tasks = smartsheet_data.get('all_tasks', [])
            completed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict):
                    status = task.get('Status', '').lower()
                    if 'conclu' in status or 'realiz' in status or 'feito' in status or 'done' in status or 'complete' in status:
                        completed_tasks.append(task)
            logger.info(f"Filtradas {len(completed_tasks)} tarefas concluídas de {len(all_tasks)} tarefas")
        elif isinstance(smartsheet_data, list):
            # Processar o formato antigo (lista direta de tarefas)
            all_tasks = smartsheet_data
            completed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict):
                    status = task.get('Status', '').lower()
                    if 'conclu' in status or 'realiz' in status or 'feito' in status or 'done' in status or 'complete' in status:
                        completed_tasks.append(task)
                elif isinstance(task, str):
                    # Se for uma string, adicionar diretamente
                    completed_tasks.append({'Nome da Tarefa': task})
            logger.info(f"Processadas {len(completed_tasks)} tarefas do formato antigo")
        else:
            logger.warning(f"Formato não reconhecido para smartsheet_data: {type(smartsheet_data)}")
            return "Sem tarefas concluídas no período."
            
        if not completed_tasks:
            return "Sem tarefas concluídas no período."
        
        # Formato da saída para tarefas realizadas
        result = ""
        for task in completed_tasks:
            if not isinstance(task, dict):
                continue
                
            # Formatar data
            task_date = task.get('Data Término', task.get('Data de Término', ''))
            if task_date:
                if isinstance(task_date, str):
                    formatted_date = task_date
                else:
                    try:
                        formatted_date = task_date.strftime("%d/%m")
                    except:
                        formatted_date = str(task_date)
            else:
                from datetime import datetime
                formatted_date = datetime.now().strftime("%d/%m")
            
            # Obter informações da tarefa
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            task_discipline = task.get('Disciplina', task.get('Discipline', ''))
            responsible = task.get('Responsável', task.get('Responsible', ''))
            
            # Formatar linha
            task_line = f"{formatted_date} - {task_discipline}: {task_name}"
            if responsible:
                task_line += f" (Responsável: {responsible})"
            result += f"{task_line}\n"
        
        return result if result else "Sem tarefas concluídas no período."

    def _gerar_atrasos_periodo(self, data: Dict[str, Any]) -> str:
        """Gera a seção de atrasos e desvios do período."""
        # Verificar formato dos dados do Smartsheet
        smartsheet_data = data.get('smartsheet_data', {})
        
        # Verificar se temos uma entrada específica para tarefas atrasadas
        if isinstance(smartsheet_data, dict) and 'delayed_tasks' in smartsheet_data:
            # Usar diretamente a lista de tarefas atrasadas
            delayed_tasks = smartsheet_data.get('delayed_tasks', [])
            logger.info(f"Usando {len(delayed_tasks)} tarefas atrasadas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            # Filtrar tarefas atrasadas da lista completa
            all_tasks = smartsheet_data.get('all_tasks', [])
            delayed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict) and (task.get('Categoria de atraso') or task.get('Delay Category')):
                    delayed_tasks.append(task)
            logger.info(f"Filtradas {len(delayed_tasks)} tarefas atrasadas de {len(all_tasks)} tarefas")
        elif isinstance(smartsheet_data, list):
            # Processar o formato antigo (lista direta de tarefas)
            all_tasks = smartsheet_data
            delayed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict) and (task.get('Categoria de atraso') or task.get('Delay Category')):
                    delayed_tasks.append(task)
            logger.info(f"Processadas {len(delayed_tasks)} tarefas atrasadas do formato antigo")
        else:
            logger.warning(f"Formato não reconhecido para smartsheet_data: {type(smartsheet_data)}")
            return "Não foram identificados atrasos no período."
            
        if not delayed_tasks:
            return "Não foram identificados atrasos no período."
        
        # Formato da saída para tarefas atrasadas
        result = ""
        for task in delayed_tasks:
            if not isinstance(task, dict):
                continue
                
            task_discipline = task.get('Disciplina', task.get('Discipline', ''))
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            
            # Tentar obter nova data
            new_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
            if new_date:
                if isinstance(new_date, str):
                    date_str = f" - Nova data para entrega: {new_date}"
                else:
                    try:
                        date_str = f" - Nova data para entrega: {new_date.strftime('%d/%m/%Y')}"
                    except:
                        date_str = ""
            else:
                date_str = ""
            
            result += f"* {task_discipline} – {task_name}{date_str}\n"
        
        return result if result else "Não foram identificados atrasos no período."
    
    def _gerar_programacao_semana(self, data: Dict[str, Any]) -> str:
        """Gera a seção de programação para as próximas duas semanas."""
        # Verificar formato dos dados do Smartsheet
        smartsheet_data = data.get('smartsheet_data', {})
        
        # Verificar se temos uma entrada específica para tarefas programadas
        if isinstance(smartsheet_data, dict) and 'scheduled_tasks' in smartsheet_data:
            # Usar diretamente a lista de tarefas programadas
            future_tasks = smartsheet_data.get('scheduled_tasks', [])
            logger.info(f"Usando {len(future_tasks)} tarefas programadas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            # Filtrar tarefas futuras da lista completa
            all_tasks = smartsheet_data.get('all_tasks', [])
            
            # Identificar tarefas para as próximas duas semanas
            from datetime import datetime, timedelta
            today = datetime.today()
            next_week_end = today + timedelta(days=14)  # Aumentado de 7 para 14 dias
            
            future_tasks = []
            for task in all_tasks:
                if not isinstance(task, dict):
                    continue
                    
                task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
                if task_date:
                    if isinstance(task_date, str):
                        # Se não puder converter, considerar como futura
                        future_tasks.append(task)
                    else:
                        # Se for data, verificar se está nas próximas duas semanas
                        try:
                            if today < task_date <= next_week_end:
                                future_tasks.append(task)
                        except:
                            # Se der erro na comparação, considerar como futura
                            future_tasks.append(task)
            
            # Se não encontrou tarefas futuras, pegar as 3 primeiras
            if not future_tasks and all_tasks:
                future_tasks = all_tasks[:min(3, len(all_tasks))]
                
            logger.info(f"Filtradas {len(future_tasks)} tarefas programadas de {len(all_tasks)} tarefas")
            
        elif isinstance(smartsheet_data, list):
            # Processar o formato antigo (lista direta de tarefas)
            from datetime import datetime, timedelta
            today = datetime.today()
            next_week_end = today + timedelta(days=14)  # Aumentado de 7 para 14 dias
            
            all_tasks = smartsheet_data
            future_tasks = []
            
            for task in all_tasks:
                if not isinstance(task, dict):
                    continue
                    
                task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
                if task_date:
                    if isinstance(task_date, str):
                        # Se não puder converter, considerar como futura
                        future_tasks.append(task)
                    else:
                        # Se for data, verificar se está nas próximas duas semanas
                        try:
                            if today < task_date <= next_week_end:
                                future_tasks.append(task)
                        except:
                            # Se der erro na comparação, considerar como futura
                            future_tasks.append(task)
            
            # Se não encontrou tarefas futuras, pegar as 3 primeiras
            if not future_tasks and all_tasks:
                valid_tasks = [t for t in all_tasks if isinstance(t, dict)]
                future_tasks = valid_tasks[:min(3, len(valid_tasks))]
                
            logger.info(f"Filtradas {len(future_tasks)} tarefas programadas do formato antigo")
        else:
            logger.warning(f"Formato não reconhecido para smartsheet_data: {type(smartsheet_data)}")
            return "Sem atividades programadas para as próximas duas semanas."
            
        if not future_tasks:
            return "Sem atividades programadas para as próximas duas semanas."
        
        # Formato da saída para tarefas programadas
        result = ""
        for task in future_tasks:
            if not isinstance(task, dict):
                continue
                
            # Formatar data
            task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
            if task_date:
                if isinstance(task_date, str):
                    formatted_date = task_date
                else:
                    try:
                        formatted_date = task_date.strftime("%d/%m")
                    except:
                        formatted_date = str(task_date)
            else:
                # Se não tiver data, usar data aproximada duas semanas à frente
                from datetime import datetime, timedelta
                future_date = datetime.now() + timedelta(days=14)  # Aumentado de 7 para 14 dias
                formatted_date = future_date.strftime("%d/%m")
            
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            task_discipline = task.get('Disciplina', task.get('Discipline', ''))
            
            # Formatar linha
            result += f"{formatted_date} - {task_discipline}: {task_name}\n"
        
        return result if result else "Sem atividades programadas para as próximas duas semanas."
        
    def _gerar_tabela_apontamentos(self, data: dict) -> str:
        """Gera uma tabela de apontamentos por disciplina mostrando apenas status 'todo' (A Fazer)."""
        issues = data.get('construflow_data', {}).get('all_issues', [])
        if not issues:
            return "Sem dados de apontamentos por disciplina."

        df = pd.DataFrame(issues)
        if df.empty or 'name' not in df.columns or 'status_y' not in df.columns:
            # Tentar alternativa da V2
            disciplines = data.get('construflow_data', {}).get('disciplines', {})
            if disciplines:
                # Formatar como tabela markdown
                discipline_rows = [
                    "| Disciplina | Quantidade de Apontamentos |",
                    "|------------|----------------------------|"
                ]
                
                for discipline, count in disciplines.items():
                    discipline_rows.append(f"| {discipline} | {count} |")
                
                return "\n".join(discipline_rows)
            
            return "Sem dados de apontamentos por disciplina."

        # Renomear colunas para facilitar
        df.rename(columns={
            'name': 'Disciplina',
            'status_y': 'Status'
        }, inplace=True)

        # Filtrar apenas os apontamentos com status 'todo'
        df_filtered = df[df['Status'] == 'todo']
        
        if df_filtered.empty:
            return "Sem apontamentos pendentes (A Fazer) no período."

        # Contar os apontamentos "A Fazer" por disciplina
        contagem_por_disciplina = df_filtered.groupby('Disciplina').size().reset_index(name='A Fazer')
        
        # Ordenar por quantidade de apontamentos (do maior para o menor)
        contagem_por_disciplina = contagem_por_disciplina.sort_values('A Fazer', ascending=False)
        
        # Criar a tabela markdown
        linhas = ["| Disciplina | A Fazer |",
                "|------------|---------|"]
        
        for _, row in contagem_por_disciplina.iterrows():
            linhas.append(f"| {row['Disciplina']} | {row['A Fazer']} |")
        
        return "\n".join(linhas)

    def save_report(self, report_text: str, project_name: str, 
                   format_type: str = 'md') -> str:
        """
        Salva o relatório em um arquivo local.
        
        Args:
            report_text: Texto do relatório
            project_name: Nome do projeto
            format_type: Formato do arquivo ('docx', 'txt' ou 'md')
            
        Returns:
            Caminho do arquivo salvo
        """        
        # Formatar nome do arquivo
        today_str = datetime.now().strftime("%Y-%m-%d")
        safe_project_name = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in project_name)
        safe_project_name = safe_project_name.replace(" ", "_")
        
        # Priorizar formato MD para melhor compatibilidade com Google Docs
        if format_type.lower() == 'md' or format_type.lower() == 'markdown':
            # Salvar como arquivo markdown
            file_name = f"Relatorio_{safe_project_name}_{today_str}.md"
            file_path = os.path.join(self.reports_dir, file_name)
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                logger.info(f"Relatório salvo como MD em {file_path}")
                return file_path
            except Exception as e:
                logger.error(f"Erro ao salvar relatório MD: {e}")
                
                # Tentar salvar em um local alternativo
                alt_path = os.path.join(os.getcwd(), file_name)
                try:
                    with open(alt_path, 'w', encoding='utf-8') as f:
                        f.write(report_text)
                    logger.info(f"Relatório MD salvo em local alternativo: '{alt_path}'")
                    return alt_path
                except Exception as e2:
                    logger.error(f"Erro ao salvar relatório MD em local alternativo: {e2}")
                    # Continuar com outros formatos
        
        # Formato DOCX se solicitado
        if format_type.lower() == 'docx':
            # Salvar como arquivo Word (.docx)
            try:
                from docx import Document
                from docx.shared import RGBColor, Pt
                from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
                
                doc = Document()
                
                # Adicionar título
                title = doc.add_heading(f"Relatório Semanal - {project_name}", level=1)
                title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                
                # Quebrar o relatório em parágrafos e adicioná-los ao documento
                paragraphs = report_text.split('\n')
                current_para = None
                in_priority_section = None
                
                for line in paragraphs:
                    # Verificar se é um cabeçalho de prioridade
                    if "🔴 Prioridade Alta" in line:
                        heading = doc.add_heading("🔴 Prioridade Alta", level=2)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(255, 0, 0)  # Vermelho
                        current_para = None
                        in_priority_section = "alta"
                        continue
                    elif "🟠 Prioridade Média" in line:
                        heading = doc.add_heading("🟠 Prioridade Média", level=2)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(255, 140, 0)  # Laranja
                        current_para = None
                        in_priority_section = "media"
                        continue
                    elif "🟢 Prioridade Baixa" in line:
                        heading = doc.add_heading("🟢 Prioridade Baixa", level=2)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(0, 180, 0)  # Verde
                        current_para = None
                        in_priority_section = "baixa"
                        continue
                    elif "⚪ Sem Prioridade" in line:
                        heading = doc.add_heading("⚪ Sem Prioridade Definida", level=2)
                        current_para = None
                        in_priority_section = "sem_prioridade"
                        continue
                    # Verificar se é um cabeçalho (de arquivo prompt_template.txt)
                    elif line.startswith('## '):
                        # Tratar como cabeçalho de seção (versão V2)
                        doc.add_heading(line.strip('#').strip(), level=2)
                        current_para = None
                        in_priority_section = None
                    elif line.startswith('#'):
                        # Tratar como cabeçalho de documento (versão V2)
                        doc.add_heading(line.strip('#').strip(), level=1)
                        current_para = None
                        in_priority_section = None
                    elif line.strip() == '':
                        # Linha em branco, finalizar parágrafo atual
                        current_para = None
                        in_priority_section = None
                    else:
                        # Para item de lista dentro de seção de prioridade
                        if line.strip().startswith('- ') and in_priority_section:
                            item_text = line.strip()[2:]  # Remover o "- " do início
                            item_para = doc.add_paragraph()
                            item_para.style = 'List Bullet'
                            
                            # Colorir o texto baseado na prioridade
                            item_run = item_para.add_run(item_text)
                            if in_priority_section == "alta":
                                item_run.font.color.rgb = RGBColor(180, 0, 0)  # Vermelho mais escuro para texto
                            elif in_priority_section == "media":
                                item_run.font.color.rgb = RGBColor(200, 100, 0)  # Laranja mais escuro para texto
                            
                            current_para = None  # Reset para não adicionar à seção atual
                        else:
                            # Linha normal
                            if current_para is None:
                                # Iniciar novo parágrafo
                                current_para = doc.add_paragraph()
                            
                            # Adicionar linha ao parágrafo atual
                            if current_para.text:
                                current_para.add_run('\n' + line)
                            else:
                                current_para.text = line
                
                # Salvar o documento
                file_name = f"Relatorio_{safe_project_name}_{today_str}.docx"
                file_path = os.path.join(self.reports_dir, file_name)
                doc.save(file_path)
                logger.info(f"Relatório salvo como DOCX em {file_path}")
                
                return file_path
                
            except ImportError:
                logger.warning("Módulo python-docx não encontrado. Salvando como TXT.")
                format_type = 'txt'
        
        # Padrão - salvar como TXT se nenhum dos outros formatos funcionou
        file_name = f"Relatorio_{safe_project_name}_{today_str}.txt"
        file_path = os.path.join(self.reports_dir, file_name)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"Relatório salvo como TXT em {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Erro ao salvar relatório TXT: {e}")
            
            # Tentar salvar em um local alternativo
            alt_path = os.path.join(os.getcwd(), file_name)
            try:
                with open(alt_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                logger.info(f"Relatório TXT salvo em local alternativo: '{alt_path}'")
                return alt_path
            except Exception as e2:
                logger.error(f"Erro ao salvar relatório TXT em local alternativo: {e2}")
                return ""