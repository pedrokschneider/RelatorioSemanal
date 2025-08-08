"""
Módulo para processamento de dados de fontes externas.
"""

import logging
import pandas as pd
import inspect
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..config import ConfigManager
from ..connectors import SmartsheetConnector, ConstruflowConnector
from ..storage import GoogleDriveManager

logger = logging.getLogger("ReportSystem")

class DataProcessor:
    """Processa dados de várias fontes para gerar relatórios."""
    
    def __init__(self, config: ConfigManager, construflow_connector=None):
        """
        Inicializa o processador de dados.
        
        Args:
            config: Instância do ConfigManager
            construflow_connector: Conector do Construflow (opcional, se não fornecido cria um novo)
        """
        self.config = config
        self.smartsheet = SmartsheetConnector(config)
        
        # Usar o conector fornecido ou criar um novo
        if construflow_connector:
            self.construflow = construflow_connector
        else:
            # Tentar usar GraphQL primeiro, fallback para REST
            try:
                from ..connectors.construflow_graphql import ConstruflowGraphQLConnector
                self.construflow = ConstruflowGraphQLConnector(config)
            except ImportError:
                self.construflow = ConstruflowConnector(config)
        
        self.gdrive = GoogleDriveManager(config)
    
    def process_project_data(self, project_id: str, smartsheet_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Processa todos os dados para um projeto específico.
        
        Args:
            project_id: ID do projeto no Construflow
            smartsheet_id: ID opcional do Smartsheet (se não for fornecido, busca na planilha)
            
        Returns:
            Dicionário com dados processados
        """
        logger.info(f"Processando dados para projeto {project_id}")
        project_id = str(project_id)
        result = {
        'project_id': project_id,
        'timestamp': datetime.now().isoformat(),
        'smartsheet_data': None,
        'construflow_data': None,
        'summary': {}
        }
        
        # Obter nome do projeto
        projects_df = self.construflow.get_projects()
        # Conversão forçada de ID para string
        projects_df['id'] = projects_df['id'].astype(str)
        # Filtrar projeto
        project_row = projects_df[projects_df['id'] == project_id]
        
        # Verificar se o projeto foi encontrado
        if project_row.empty:
            logger.error(f"Projeto {project_id} não encontrado")
            logger.error("IDs disponíveis:")
            logger.error(projects_df['id'].tolist())
            return result
        
        # Obter nome do projeto
        project_name = project_row['name'].values[0]
        result['project_name'] = project_name
    
        
        # Buscar dados do Smartsheet (restante do método permanece igual)
        if not smartsheet_id:
            projects_df = self.gdrive.load_project_config_from_sheet()
            
            if not projects_df.empty and 'ID_Construflow' in projects_df.columns and 'ID_Smartsheet' in projects_df.columns:
                # Buscar na planilha
                project_row = projects_df[projects_df['ID_Construflow'] == project_id]
                
                if not project_row.empty and pd.notna(project_row['ID_Smartsheet'].values[0]):
                    smartsheet_id = project_row['ID_Smartsheet'].values[0]
                    logger.info(f"ID do Smartsheet obtido da planilha: {smartsheet_id}")
            
        if smartsheet_id:
            # Processar dados do Smartsheet
            tasks_df = self.smartsheet.get_recent_tasks(smartsheet_id)
            if not tasks_df.empty:
                # Manter todas as tarefas para o gerador decidir o que é concluído
                all_tasks = [row._asdict() if hasattr(row, '_asdict') else row.to_dict() for _, row in tasks_df.iterrows()]

                # Construir apenas a lista de atrasadas conforme regra: Status = 'não feito' OU Categoria de atraso preenchida
                delayed_tasks = []
                for _, task in tasks_df.iterrows():
                    task_dict = task.to_dict()
                    status = str(task.get('Status', '')).lower().strip()
                    categoria_atraso = task.get('Categoria de atraso') or task.get('Delay Category')
                    tem_categoria_atraso = categoria_atraso and str(categoria_atraso).strip() not in ['', 'nan', 'None']

                    # Status padronizados do Smartsheet: 'a fazer', 'em progresso', 'feito', 'não feito'
                    if status == 'não feito' or tem_categoria_atraso:
                        delayed_tasks.append(task_dict)

                # Organizar dados (sem completed_tasks/scheduled_tasks para evitar sobrepor lógica do gerador)
                result['smartsheet_data'] = {
                    'all_tasks': all_tasks,
                    'delayed_tasks': delayed_tasks
                }

                result['summary']['total_tasks'] = len(all_tasks)
                result['summary']['delayed_tasks'] = len(delayed_tasks)

                # Estatísticas de status puramente descritivas
                if 'Status' in tasks_df.columns:
                    status_counts = tasks_df['Status'].value_counts().to_dict()
                    result['summary']['status_counts'] = status_counts

                logger.info(f"Smartsheet: {len(all_tasks)} tarefas carregadas; {len(delayed_tasks)} marcadas como atrasadas (não feito/categoria atraso)")
        else:
            logger.warning(f"ID do Smartsheet não encontrado para projeto {project_id}")
        
        # Processar dados do Construflow
        issues_df = self.construflow.get_project_issues(project_id)
        
        if not issues_df.empty:
            # Filtrar issues ativas - adaptado para GraphQL
            # GraphQL: status = status da issue, status_y = status da disciplina
            if 'status' in issues_df.columns and 'status_y' in issues_df.columns:
                # Para GraphQL: issues com status 'active' E disciplina com status 'todo' OU 'follow'
                active_issues = issues_df[
                    (issues_df['status'] == 'active') &
                    (issues_df['status_y'].isin(['todo', 'follow']))
                ]
                logger.info(f"Filtradas {len(active_issues)} issues ativas com disciplina 'todo' ou 'follow' de {len(issues_df)} total")
            elif 'status' in issues_df.columns:
                # Fallback: apenas verificar status da issue
                active_issues = issues_df[issues_df['status'] == 'active']
                logger.info(f"Filtradas {len(active_issues)} issues ativas (sem filtro de disciplina) de {len(issues_df)} total")
            else:
                # Fallback para formato REST (status_x e status_y)
                active_issues = issues_df[
                    (issues_df['status_x'] == 'active') &
                    (issues_df['status_y'].isin(['todo', 'follow']))
                ] if 'status_x' in issues_df.columns and 'status_y' in issues_df.columns else pd.DataFrame()
                logger.info(f"Usando filtro REST: {len(active_issues)} issues ativas")
            
            if not active_issues.empty:
                result['construflow_data'] = {
                    'active_issues': active_issues.to_dict('records'),
                    'issue_counts': len(active_issues),
                    'disciplines': {}
                }
                
                # Contagem por disciplina (se disponível)
                if 'name' in active_issues.columns:
                    discipline_counts = active_issues['name'].value_counts().to_dict()
                    result['construflow_data']['disciplines'] = discipline_counts
                    logger.info(f"Disciplinas encontradas: {list(discipline_counts.keys())}")
            else:
                # Inicializar estrutura vazia para evitar erros
                result['construflow_data'] = {
                    'active_issues': [],
                    'issue_counts': 0,
                    'disciplines': {}
                }
                logger.warning("Nenhuma issue ativa encontrada")
            
            # Adicionar todas as issues para processamento
            result['construflow_data']['all_issues'] = issues_df.to_dict('records')
            logger.info(f"Total de issues processadas: {len(issues_df)}")
            
            # Filtrar apontamentos do cliente
            try:
                client_issues_df = self.filter_client_issues(issues_df, project_id)
                if not client_issues_df.empty:
                    result['construflow_data']['client_issues'] = client_issues_df.to_dict('records')
                    logger.info(f"Filtrados {len(client_issues_df)} apontamentos do cliente")
                else:
                    result['construflow_data']['client_issues'] = []
                    logger.info("Nenhum apontamento do cliente encontrado")
            except Exception as e:
                logger.warning(f"Erro ao filtrar apontamentos do cliente: {e}")
                result['construflow_data']['client_issues'] = []
        
        return result
    
    def filter_client_issues(self, df_issues: pd.DataFrame, project_id: str) -> pd.DataFrame:
        """
        Filtra issues do Construflow relacionadas às disciplinas do cliente.
        
        Args:
            df_issues: DataFrame com todas as issues do projeto
            project_id: ID do projeto
            
        Returns:
            DataFrame com issues filtradas pelas disciplinas do cliente
        """
        # Obter disciplinas relacionadas ao cliente
        system = self._get_system_instance()
        
        if system:
            disciplinas_cliente = system.get_client_disciplines(project_id)
        else:
            # Se não conseguir obter do sistema, usar uma abordagem genérica
            disciplinas_cliente = []
            
            # Tentar carregar da planilha
            try:
                projects_df = self.gdrive.load_project_config_from_sheet()
                if not projects_df.empty and 'construflow_id' in projects_df.columns and 'construflow_disciplinasclientes' in projects_df.columns:
                    project_row = projects_df[projects_df['construflow_id'] == project_id]
                    if not project_row.empty and pd.notna(project_row['construflow_disciplinasclientes'].values[0]):
                        disciplinas_str = project_row['construflow_disciplinasclientes'].values[0]
                        disciplinas_cliente = [d.strip() for d in disciplinas_str.split(',')]
            except Exception as e:
                logger.warning(f"Erro ao obter disciplinas do cliente da planilha: {e}")
        
        if not disciplinas_cliente or 'name' not in df_issues.columns:
            logger.warning(f"Não foi possível filtrar issues para o cliente. Disciplinas: {disciplinas_cliente}")
            return df_issues
        
        # Filtrar pelas disciplinas do cliente
        mask = df_issues['name'].isin(disciplinas_cliente)
        filtered_df = df_issues[mask]
        
        logger.info(f"Filtradas {len(filtered_df)} issues de cliente de um total de {len(df_issues)}")
        return filtered_df
    
    def _get_system_instance(self):
        """
        Tenta obter uma instância do sistema WeeklyReportSystem.
        Necessário para acessar métodos como get_client_disciplines.
        """
        # Procurar classes WeeklyReportSystem no módulo atual
        for name, obj in inspect.getmembers(sys.modules['__main__']):
            if inspect.isclass(obj) and name == 'WeeklyReportSystem':
                # Procurar instâncias dessa classe
                for frame in inspect.stack():
                    for var in frame[0].f_locals.values():
                        if isinstance(var, obj):
                            return var
        
        # Se não encontrou, retornar None
        return None
