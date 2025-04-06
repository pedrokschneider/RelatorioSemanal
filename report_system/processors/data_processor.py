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
    
    def __init__(self, config: ConfigManager):
        """
        Inicializa o processador de dados.
        
        Args:
            config: Instância do ConfigManager
        """
        self.config = config
        self.smartsheet = SmartsheetConnector(config)
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
                result['smartsheet_data'] = tasks_df.to_dict('records')
                result['summary']['total_tasks'] = len(tasks_df)
                
                # Calcular estatísticas de status
                if 'Status' in tasks_df.columns:
                    status_counts = tasks_df['Status'].value_counts().to_dict()
                    result['summary']['status_counts'] = status_counts
        else:
            logger.warning(f"ID do Smartsheet não encontrado para projeto {project_id}")
        
        # Processar dados do Construflow
        issues_df = self.construflow.get_project_issues(project_id)
        
        if not issues_df.empty:
            # Filtrar issues ativas
            active_issues = issues_df[
                (issues_df['status_x'] == 'active') &
                (issues_df['status_y'] == 'todo')
            ] if 'status_x' in issues_df.columns and 'status_y' in issues_df.columns else pd.DataFrame()
            
            if not active_issues.empty:
                result['construflow_data'] = {
                    'active_issues': active_issues.to_dict('records'),
                    'issue_counts': len(active_issues),
                    'disciplines': {}
                }
                
                # Contagem por disciplina
                if 'name' in active_issues.columns:
                    discipline_counts = active_issues['name'].value_counts().to_dict()
                    result['construflow_data']['disciplines'] = discipline_counts
            else:
                # Inicializar estrutura vazia para evitar erros
                result['construflow_data'] = {
                    'active_issues': [],
                    'issue_counts': 0,
                    'disciplines': {}
                }
            
            # Adicionar todas as issues para processamento
            result['construflow_data']['all_issues'] = issues_df.to_dict('records')
        
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
                if not projects_df.empty and 'ID_Construflow' in projects_df.columns and 'Disciplinas_Cliente' in projects_df.columns:
                    project_row = projects_df[projects_df['ID_Construflow'] == project_id]
                    if not project_row.empty and pd.notna(project_row['Disciplinas_Cliente'].values[0]):
                        disciplinas_str = project_row['Disciplinas_Cliente'].values[0]
                        disciplinas_cliente = [d.strip() for d in disciplinas_str.split(';')]
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
