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

# Função utilitária para parse de datas flexível
from datetime import datetime

def parse_data_flex(date_str):
    if not date_str:
        return None
    formatos = ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d/%m"]
    for fmt in formatos:
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    return None

# 1. Ajustar formatação das listas (sem asteriscos, data sempre dd/mm)
def format_task_line(date_value, discipline, name, responsible=None):
    # Tenta converter para datetime
    dt = None
    if isinstance(date_value, str):
        dt = parse_data_flex(date_value)
        if not dt and len(date_value) >= 10:
            try:
                dt = datetime.strptime(date_value[:10], "%Y-%m-%d")
            except Exception:
                pass
    elif hasattr(date_value, 'strftime'):
        dt = date_value
    if dt:
        formatted_date = dt.strftime("%d/%m")
    else:
        formatted_date = str(date_value)[:5]  # fallback
    line = f"{formatted_date} | {discipline}:\n{name}"
    if responsible:
        line += f" (Responsável: {responsible})"
    return line

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
        """Carrega o template de prompt embutido no código, ignorando arquivo externo."""
        return """Bom dia a todos,

Segue o resumo semanal do projeto [NOME_PROJETO].

---

🛎️ Pontos que precisam de resposta ([NOME_CLIENTE]):
[APONTAMENTOS_CLIENTE]

---

✅ Realizados na semana:
[TAREFAS_REALIZADAS]

---

📅 Planejamento para a próxima semana (atividades a iniciar):
[ATIVIDADES_INICIADAS_PROXIMA_SEMANA]

---

⚠️ Atrasos e desvios do período:
[ATRASOS_PERIODO]

---

📦 Entregas previstas para as próximas semanas:
[PROGRAMACAO_SEMANA]

---

 📊 Apontamentos pendentes por disciplina:
[TABELA_APONTAMENTOS]

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
        
        # Obter nome do cliente corretamente
        project_name = data.get('project_name', 'Projeto')
        project_id = data.get('project_id', '')
        system = self._get_system_instance()  # Obtém instância do sistema
        client_names = system.get_client_names(project_id) if system else []
        if client_names and client_names[0]:
            client_name = client_names[0]
        else:
            client_name = "Cliente"
        
        # Preparar substituições básicas
        replacements = {
            "[NOME_PROJETO]": project_name,
            "[NOME_CLIENTE]": client_name,
            "[DATA_ATUAL]": datetime.now().strftime("%d/%m/%Y")

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
        
        # Gerar atividades que irão iniciar na próxima semana
        atividades_iniciadas_proxima_semana = self._gerar_atividades_iniciadas_proxima_semana(data)
        replacements["[ATIVIDADES_INICIADAS_PROXIMA_SEMANA]"] = atividades_iniciadas_proxima_semana
        
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
        
            # Calcular tempo desde a última atualização
            dias_sem_atualizacao = ""
            updated_at = issue.get('updatedAt')
            if updated_at:
                try:
                    from datetime import datetime
                    if isinstance(updated_at, str):
                        if 'Z' in updated_at:
                            updated_at = updated_at.replace('Z', '+00:00')
                        updated_date = datetime.fromisoformat(updated_at)
                    else:
                        updated_date = updated_at
                    agora = datetime.now()
                    if updated_date.tzinfo:
                        agora = agora.replace(tzinfo=updated_date.tzinfo)
                    diferenca = agora - updated_date
                    dias = diferenca.days
                    if dias == 0:
                        dias_sem_atualizacao = "(sem atualização hoje)"
                    elif dias == 1:
                        dias_sem_atualizacao = "(sem atualização há 1 dia)"
                    else:
                        dias_sem_atualizacao = f"(sem atualização há {dias} dias)"
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
            # issue_line = f"[#{issue_code}]({construflow_url}) – {issue_title} {dias_sem_atualizacao}"
            # issues_por_prioridade[priority_group].append(issue_line)
            if dias_sem_atualizacao and 'sem atualização' in dias_sem_atualizacao:
                issue_line = f"[#{issue_code}]({construflow_url}) – {issue_title}\n   ⏳ {dias_sem_atualizacao.strip('()')}"
            else:
                issue_line = f"[#{issue_code}]({construflow_url}) – {issue_title}"
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
        smartsheet_data = data.get('smartsheet_data', {})
        if isinstance(smartsheet_data, dict) and 'completed_tasks' in smartsheet_data:
            completed_tasks = smartsheet_data.get('completed_tasks', [])
            logger.info(f"Usando {len(completed_tasks)} tarefas concluídas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            all_tasks = smartsheet_data.get('all_tasks', [])
            completed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict):
                    status = task.get('Status', '').lower()
                    if 'conclu' in status or 'realiz' in status or 'feito' in status or 'done' in status or 'complete' in status:
                        completed_tasks.append(task)
            logger.info(f"Filtradas {len(completed_tasks)} tarefas concluídas de {len(all_tasks)} tarefas")
        elif isinstance(smartsheet_data, list):
            all_tasks = smartsheet_data
            completed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict):
                    status = task.get('Status', '').lower()
                    if 'conclu' in status or 'realiz' in status or 'feito' in status or 'done' in status or 'complete' in status:
                        completed_tasks.append(task)
                elif isinstance(task, str):
                    completed_tasks.append({'Nome da Tarefa': task})
            logger.info(f"Processadas {len(completed_tasks)} tarefas do formato antigo")
        else:
            logger.warning(f"Formato não reconhecido para smartsheet_data: {type(smartsheet_data)}")
            return "Sem tarefas concluídas no período."
        if not completed_tasks:
            return "Sem tarefas concluídas no período."
        from datetime import datetime
        def get_task_date(task):
            task_date = task.get('Data Término', task.get('Data de Término', ''))
            if isinstance(task_date, str):
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m"):
                    try:
                        return datetime.strptime(task_date, fmt)
                    except Exception:
                        continue
                return datetime.min
            elif hasattr(task_date, 'strftime'):
                return task_date
            return datetime.min
        completed_tasks.sort(key=get_task_date, reverse=True)
        # Agrupar tarefas realizadas por disciplina
        tarefas_por_disciplina = {}
        for task in completed_tasks:
            if not isinstance(task, dict):
                continue
            task_date = task.get('Data Término', task.get('Data de Término', ''))
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            task_discipline = task.get('Disciplina', task.get('Discipline', '')) or 'Sem Disciplina'
            # Formatar data SEM negrito, sempre dd/mm
            dt = parse_data_flex(task_date)
            if not dt and isinstance(task_date, str) and len(task_date) >= 10:
                try:
                    so_data = task_date[:10]
                    dt = datetime.strptime(so_data, "%Y-%m-%d")
                except Exception:
                    pass
            if dt:
                formatted_date = dt.strftime("%d/%m")
            else:
                import re
                match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', str(task_date))
                if match:
                    formatted_date = f"{match.group(3)}/{match.group(2)}"
                else:
                    match2 = re.search(r'(\d{2})/(\d{2})', str(task_date))
                    if match2:
                        formatted_date = f"{match2.group(1)}/{match2.group(2)}"
                    else:
                        formatted_date = str(task_date).strip()[:5]
            linha = f"{formatted_date} │ {task_name}"
            if task_discipline not in tarefas_por_disciplina:
                tarefas_por_disciplina[task_discipline] = []
            tarefas_por_disciplina[task_discipline].append(linha)
        # Montar resultado agrupado
        if not tarefas_por_disciplina:
            return "Sem tarefas concluídas no período."
        result = ""
        for disciplina, tarefas in tarefas_por_disciplina.items():
            result += f"{disciplina}\n"
            for tarefa in tarefas:
                result += f"{tarefa}\n"
            result += "\n"
        return result.strip()

    def _gerar_atividades_iniciadas_proxima_semana(self, data: Dict[str, Any]) -> str:
        """
        Gera a seção de atividades que irão iniciar na próxima semana (segunda a domingo).
        Se o relatório for solicitado antes de sexta-feira, considera atividades da semana atual e da próxima.
        """
        smartsheet_data = data.get('smartsheet_data', {})
        if isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            all_tasks = smartsheet_data.get('all_tasks', [])
        elif isinstance(smartsheet_data, list):
            all_tasks = smartsheet_data
        else:
            return "Sem atividades previstas para iniciar na próxima semana."
        from datetime import datetime, timedelta
        hoje = datetime.now()
        weekday = hoje.weekday()  # 0=segunda, 4=sexta
        # Calcular intervalo de datas
        if weekday < 4:  # Antes de sexta-feira
            # Segunda-feira desta semana
            segunda_atual = (hoje - timedelta(days=hoje.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            # Domingo da próxima semana
            domingo_proxima = segunda_atual + timedelta(days=13)
            intervalo_inicio = segunda_atual
            intervalo_fim = domingo_proxima
        else:
            # Próxima segunda-feira
            dias_ate_segunda = (7 - hoje.weekday()) % 7 or 7
            proxima_segunda = (hoje + timedelta(days=dias_ate_segunda)).replace(hour=0, minute=0, second=0, microsecond=0)
            proximo_domingo = proxima_segunda + timedelta(days=6)
            intervalo_inicio = proxima_segunda
            intervalo_fim = proximo_domingo
        # Agrupar atividades por disciplina
        atividades_por_disciplina = {}
        for task in all_tasks:
            if not isinstance(task, dict):
                continue
            data_inicio = task.get('Data Inicio', task.get('Data de Início', ''))
            data_termino = task.get('Data Término')
            try:
                if isinstance(data_inicio, str):
                    data_inicio_dt = parse_data_flex(data_inicio)
                else:
                    data_inicio_dt = data_inicio
            except Exception:
                continue
            if data_inicio_dt and intervalo_inicio <= data_inicio_dt <= intervalo_fim:
                # Formatar datas SEM ANO
                data_inicio_fmt = data_inicio_dt.strftime("%d/%m")
                if data_termino:
                    try:
                        if isinstance(data_termino, str):
                            data_termino_dt = parse_data_flex(data_termino)
                        else:
                            data_termino_dt = data_termino
                        data_termino_fmt = data_termino_dt.strftime("%d/%m")
                    except Exception:
                        data_termino_fmt = str(data_termino)[:5]
                else:
                    data_termino_fmt = "?"
                nome = task.get('Nome da Tarefa', task.get('Task Name', ''))
                disciplina = task.get('Disciplina', task.get('Discipline', '')) or 'Sem Disciplina'
                # Linha agrupada
                if data_inicio_fmt == data_termino_fmt or not data_termino:
                    linha = f"{data_inicio_fmt} │ {nome}"
                else:
                    linha = f"{data_inicio_fmt} a {data_termino_fmt} │ {nome}"
                if disciplina not in atividades_por_disciplina:
                    atividades_por_disciplina[disciplina] = []
                atividades_por_disciplina[disciplina].append(linha)
        # Montar resultado agrupado
        if not atividades_por_disciplina:
            return "Sem atividades previstas para iniciar na próxima semana."
        result = ""
        for disciplina, atividades in atividades_por_disciplina.items():
            result += f"{disciplina}\n"
            for atividade in atividades:
                result += f"{atividade}\n"
            result += "\n"
        return result.strip()

    def _gerar_atrasos_periodo(self, data: Dict[str, Any]) -> str:
        """Gera a seção de atrasos e desvios do período, incluindo baseline e motivo de atraso."""
        smartsheet_data = data.get('smartsheet_data', {})
        if isinstance(smartsheet_data, dict) and 'delayed_tasks' in smartsheet_data:
            delayed_tasks = smartsheet_data.get('delayed_tasks', [])
            logger.info(f"Usando {len(delayed_tasks)} tarefas atrasadas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            all_tasks = smartsheet_data.get('all_tasks', [])
            delayed_tasks = []
            for task in all_tasks:
                if isinstance(task, dict) and (task.get('Categoria de atraso') or task.get('Delay Category')):
                    delayed_tasks.append(task)
            logger.info(f"Filtradas {len(delayed_tasks)} tarefas atrasadas de {len(all_tasks)} tarefas")
        elif isinstance(smartsheet_data, list):
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
        result = ""
        for task in delayed_tasks:
            if not isinstance(task, dict):
                continue
            task_discipline = task.get('Disciplina', task.get('Discipline', ''))
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            nova_data = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
            # Buscar baseline mais recente
            import re
            baseline = task.get('Data de Fim - Baseline Otus')
            # Procurar todas as chaves que batem com o padrão
            baseline_keys = [k for k in task.keys() if re.match(r'^Data de Fim - Baseline Otus R\\d+$', k)]
            if baseline_keys:
                # Ordenar pelo número do R (maior para menor)
                baseline_keys.sort(key=lambda x: int(re.findall(r'R(\\d+)$', x)[0]), reverse=True)
                baseline = task.get(baseline_keys[0]) or baseline
            baseline_fmt = baseline if baseline else "-"
            motivo = task.get('Motivo de atraso')
            motivo_fmt = motivo if motivo else "-"
            # Formatar datas
            nova_data_fmt = ""
            if nova_data:
                nova_data_dt = parse_data_flex(nova_data)
                if not nova_data_dt and hasattr(nova_data, 'strftime'):
                    # Caso seja datetime já convertido
                    nova_data_dt = nova_data
                if nova_data_dt:
                    nova_data_fmt = nova_data_dt.strftime("%d/%m")
                else:
                    # Se for string, tentar extrair só a parte da data
                    if isinstance(nova_data, str) and len(nova_data) >= 10:
                        try:
                            so_data = nova_data[:10]
                            dt_tmp = datetime.strptime(so_data, "%Y-%m-%d")
                            nova_data_fmt = dt_tmp.strftime("%d/%m")
                        except Exception:
                            nova_data_fmt = str(nova_data)[:5]
                    else:
                        nova_data_fmt = str(nova_data)[:5]
            # Corrigir baseline para sempre dd/mm
            if baseline:
                baseline_dt = parse_data_flex(baseline)
                if baseline_dt:
                    baseline_fmt = baseline_dt.strftime("%d/%m")
                else:
                    baseline_fmt = str(baseline)[:5]
            else:
                baseline_fmt = "-"
            result += (f"* {task_discipline} – {task_name}\n"
                       f"    - Nova data programada: {nova_data_fmt}\n"
                       f"    - Data prevista inicial: {baseline_fmt}\n"
                       f"    - Motivo do atraso: {motivo_fmt}\n")
        return result if result else "Não foram identificados atrasos no período."
    
    def _gerar_programacao_semana(self, data: Dict[str, Any]) -> str:
        """Gera a seção de programação para as próximas duas semanas."""
        smartsheet_data = data.get('smartsheet_data', {})
        if isinstance(smartsheet_data, dict) and 'scheduled_tasks' in smartsheet_data:
            future_tasks = smartsheet_data.get('scheduled_tasks', [])
            logger.info(f"Usando {len(future_tasks)} tarefas programadas do dicionário")
        elif isinstance(smartsheet_data, dict) and 'all_tasks' in smartsheet_data:
            all_tasks = smartsheet_data.get('all_tasks', [])
            from datetime import datetime, timedelta
            today = datetime.today()
            next_week_end = today + timedelta(days=14)
            future_tasks = []
            for task in all_tasks:
                if not isinstance(task, dict):
                    continue
                task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
                if task_date:
                    if isinstance(task_date, str):
                        future_tasks.append(task)
                    else:
                        try:
                            if today < task_date <= next_week_end:
                                future_tasks.append(task)
                        except:
                            future_tasks.append(task)
            if not future_tasks and all_tasks:
                future_tasks = all_tasks[:min(3, len(all_tasks))]
            logger.info(f"Filtradas {len(future_tasks)} tarefas programadas de {len(all_tasks)} tarefas")
        elif isinstance(smartsheet_data, list):
            from datetime import datetime, timedelta
            today = datetime.today()
            next_week_end = today + timedelta(days=14)
            all_tasks = smartsheet_data
            future_tasks = []
            for task in all_tasks:
                if not isinstance(task, dict):
                    continue
                task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
                if task_date:
                    if isinstance(task_date, str):
                        future_tasks.append(task)
                    else:
                        try:
                            if today < task_date <= next_week_end:
                                future_tasks.append(task)
                        except:
                            future_tasks.append(task)
            if not future_tasks and all_tasks:
                valid_tasks = [t for t in all_tasks if isinstance(t, dict)]
                future_tasks = valid_tasks[:min(3, len(valid_tasks))]
            logger.info(f"Filtradas {len(future_tasks)} tarefas programadas do formato antigo")
        else:
            logger.warning(f"Formato não reconhecido para smartsheet_data: {type(smartsheet_data)}")
            return "Sem atividades programadas para as próximas duas semanas."
        if not future_tasks:
            return "Sem atividades programadas para as próximas duas semanas."
        def get_task_date(task):
            task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
            if isinstance(task_date, str):
                try:
                    return datetime.strptime(task_date, "%d/%m/%Y")
                except:
                    return datetime.now() + timedelta(days=14)
            return task_date if task_date else datetime.now() + timedelta(days=14)
        future_tasks.sort(key=get_task_date, reverse=False)
        # Agrupar entregas por disciplina
        entregas_por_disciplina = {}
        for task in future_tasks:
            if not isinstance(task, dict):
                continue
            task_date = task.get('Data Término', task.get('Data de Término', task.get('Due Date', '')))
            task_name = task.get('Nome da Tarefa', task.get('Task Name', ''))
            task_discipline = task.get('Disciplina', task.get('Discipline', '')) or 'Sem Disciplina'
            # Formatar data SEM negrito, sempre dd/mm
            dt = parse_data_flex(task_date)
            if not dt and isinstance(task_date, str) and len(task_date) >= 10:
                try:
                    so_data = task_date[:10]
                    dt = datetime.strptime(so_data, "%Y-%m-%d")
                except Exception:
                    pass
            if dt:
                formatted_date = dt.strftime("%d/%m")
            else:
                import re
                match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', str(task_date))
                if match:
                    formatted_date = f"{match.group(3)}/{match.group(2)}"
                else:
                    match2 = re.search(r'(\d{2})/(\d{2})', str(task_date))
                    if match2:
                        formatted_date = f"{match2.group(1)}/{match2.group(2)}"
                    else:
                        formatted_date = str(task_date).strip()[:5]
            linha = f"{formatted_date} │ {task_name}"
            if task_discipline not in entregas_por_disciplina:
                entregas_por_disciplina[task_discipline] = []
            entregas_por_disciplina[task_discipline].append(linha)
        # Montar resultado agrupado
        if not entregas_por_disciplina:
            return "Sem atividades programadas para as próximas duas semanas."
        result = ""
        for disciplina, entregas in entregas_por_disciplina.items():
            result += f"{disciplina}\n"
            for entrega in entregas:
                result += f"{entrega}\n"
            result += "\n"
        return result.strip()
        
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
            try:
                from docx import Document
                from docx.shared import RGBColor, Pt
                from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
                import re
                doc = Document()
                # Adicionar título principal
                title = doc.add_heading(f"Relatório Semanal - {project_name}", level=1)
                title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                # Quebrar o relatório em linhas
                paragraphs = report_text.split('\n')
                current_para = None
                # Mapear seções para Heading 2
                secoes_h2 = [
                    "Pontos que precisam de resposta",
                    "Realizados na semana:",
                    "Planejamento para a próxima semana (atividades a iniciar):",
                    "Atrasos e desvios do período:",
                    "Entregas previstas para as próximas semanas:",
                    "Apontamentos pendentes por disciplina:",
                    "🔴 Prioridade Alta",
                    "🟠 Prioridade Média",
                    "🟢 Prioridade Baixa",
                    "⚪ Sem Prioridade Definida"
                ]
                cor_prioridade = {
                    "🔴 Prioridade Alta": RGBColor(255, 0, 0),
                    "🟠 Prioridade Média": RGBColor(255, 140, 0),
                    "🟢 Prioridade Baixa": RGBColor(0, 180, 0),
                    "⚪ Sem Prioridade Definida": RGBColor(120, 120, 120)
                }
                for line in paragraphs:
                    l_strip = line.strip()
                    # Título de saudação
                    if l_strip == "Bom dia a todos,":
                        doc.add_paragraph(l_strip)
                        continue
                    # Título de fechamento
                    if l_strip == "Qualquer dúvida, estamos à disposição!":
                        doc.add_paragraph(l_strip)
                        continue
                    # Seção principal (Heading 2) ou prioridade
                    if l_strip in secoes_h2:
                        heading = doc.add_heading(l_strip, level=2)
                        if l_strip in cor_prioridade:
                            for run in heading.runs:
                                run.font.color.rgb = cor_prioridade[l_strip]
                        current_para = None
                        continue
                    # Linhas normais, listas, etc
                    if l_strip.startswith('- '):
                        item_para = doc.add_paragraph()
                        item_para.style = 'List Bullet'
                        item_para.add_run(l_strip[2:])
                    elif l_strip.startswith('* '):
                        item_para = doc.add_paragraph()
                        item_para.style = 'List Bullet'
                        item_para.add_run(l_strip[2:])
                    elif l_strip == '---' or l_strip == '':
                        continue
                    else:
                        doc.add_paragraph(l_strip)
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