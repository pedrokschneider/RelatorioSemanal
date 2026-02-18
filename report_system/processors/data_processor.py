"""
Módulo para processamento de dados de fontes externas.
"""

import logging
import pandas as pd
import inspect
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    
    def process_project_data(self, project_id: str, smartsheet_id: Optional[str] = None, reference_date: Optional[datetime] = None, since_date: Optional[datetime] = None) -> Dict[str, Any]:
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
        'timestamp': (reference_date if reference_date else datetime.now()).isoformat(),
        'smartsheet_data': None,
        'construflow_data': None,
        'summary': {},
        'reference_date': reference_date,  # Armazenar data de referência para uso nos geradores
        'since_date': since_date  # Armazenar data inicial para atividades concluídas
        }
        
        # Obter nome do projeto
        projects_df = self.construflow.get_projects()
        # Conversão forçada de ID para string
        if not projects_df.empty and 'id' in projects_df.columns:
            projects_df['id'] = projects_df['id'].astype(str)
        else:
            projects_df = pd.DataFrame(columns=['id', 'name'])
        # Filtrar projeto
        project_row = projects_df[projects_df['id'] == project_id]
        
        # Verificar se o projeto foi encontrado
        if project_row.empty:
            # Tentar buscar diretamente o projeto via GraphQL otimizado (cobre casos fora da planilha/ativos)
            logger.warning(f"Projeto {project_id} não encontrado na lista padrão. Tentando buscar diretamente na API...")
            try:
                optimized = self.construflow.get_project_data_optimized(project_id)
                if optimized and 'projects' in optimized and not optimized['projects'].empty:
                    project_row = optimized['projects']
                    # Normalizar tipos
                    if 'id' in project_row.columns:
                        project_row['id'] = project_row['id'].astype(str)
                    project_row = project_row[project_row['id'] == project_id]
                else:
                    logger.warning(f"API não retornou dados para o projeto {project_id}")
            except Exception as e:
                logger.warning(f"Falha ao buscar projeto {project_id} diretamente na API: {e}")
        
        if project_row.empty:
            logger.error(f"Projeto {project_id} não encontrado")
            if not projects_df.empty and 'id' in projects_df.columns:
                logger.error("IDs disponíveis:")
                logger.error(projects_df['id'].tolist())
            return result
        
        # Obter nomes do Supabase - SEM fallback para Construflow
        project_name = None
        client_name = None
        config_df = None
        try:
            config_df = self.gdrive.load_project_config_from_sheet()
            if not config_df.empty and 'construflow_id' in config_df.columns:
                config_df['construflow_id'] = config_df['construflow_id'].astype(str)
                planilha_row = config_df[config_df['construflow_id'] == str(project_id)]
                if not planilha_row.empty:
                    # Project name: nome_comercial > Projeto - PR (projects.name)
                    if 'nome_comercial' in planilha_row.columns:
                        val = planilha_row['nome_comercial'].values[0]
                        if pd.notna(val) and str(val).strip() and str(val).strip() != '-':
                            project_name = str(val).strip()
                            logger.info(f"Usando nome comercial para projeto {project_id}: {project_name}")
                    if not project_name and 'Projeto - PR' in planilha_row.columns:
                        val = planilha_row['Projeto - PR'].values[0]
                        if pd.notna(val) and str(val).strip():
                            project_name = str(val).strip()
                            logger.info(f"Usando nome do Supabase (projects.name) para projeto {project_id}: {project_name}")
                    # Client name: companies.name
                    if 'nome_cliente' in planilha_row.columns:
                        val = planilha_row['nome_cliente'].values[0]
                        if pd.notna(val) and str(val).strip():
                            client_name = str(val).strip()
                            logger.info(f"Nome do cliente para projeto {project_id}: {client_name}")
                else:
                    logger.warning(f"Projeto {project_id} não encontrado na config Supabase. "
                                  f"construflow_ids disponíveis: {config_df['construflow_id'].tolist()[:10]}")
            else:
                logger.warning(f"Config sheet vazia ou sem coluna construflow_id")
        except Exception as e:
            logger.warning(f"Erro ao obter nomes do Supabase: {e}")

        if not project_name:
            logger.error(f"Nome do projeto {project_id} não encontrado no Supabase! "
                        f"Verifique project_features e projects no Supabase.")
            project_name = str(project_id)

        result['project_name'] = project_name
        result['client_name'] = client_name
    
        
        # Buscar ID do Smartsheet se não fornecido
        if not smartsheet_id:
            projects_df = self.gdrive.load_project_config_from_sheet()
            
            if not projects_df.empty and 'ID_Construflow' in projects_df.columns and 'ID_Smartsheet' in projects_df.columns:
                # Buscar na planilha
                project_row = projects_df[projects_df['ID_Construflow'] == project_id]
                
                if not project_row.empty and pd.notna(project_row['ID_Smartsheet'].values[0]):
                    smartsheet_id = project_row['ID_Smartsheet'].values[0]
                    logger.info(f"ID do Smartsheet obtido da planilha: {smartsheet_id}")
        
        # Paralelizar busca de dados do Smartsheet e Construflow
        logger.info(f"🚀 Iniciando busca paralela de dados para projeto {project_id}")
        
        def fetch_smartsheet_data():
            """Busca dados do Smartsheet em thread separada."""
            if smartsheet_id:
                try:
                    logger.info(f"📊 Buscando dados do Smartsheet {smartsheet_id}...")
                    tasks_df = self.smartsheet.get_recent_tasks(smartsheet_id, force_refresh=True)
                    return tasks_df
                except Exception as e:
                    logger.error(f"Erro ao buscar dados do Smartsheet: {e}")
                    return None
            return None
        
        def fetch_construflow_data():
            """Busca dados do Construflow em thread separada."""
            try:
                logger.info(f"🔍 Buscando issues do Construflow para projeto {project_id}...")
                issues_df = self.construflow.get_project_issues(project_id)
                return issues_df if issues_df is not None else pd.DataFrame()
            except Exception as e:
                logger.error(f"Erro ao buscar issues do Construflow: {e}")
                return pd.DataFrame()
        
        # Executar buscas em paralelo
        tasks_df = None
        issues_df = pd.DataFrame()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submeter ambas as tarefas
            smartsheet_future = executor.submit(fetch_smartsheet_data) if smartsheet_id else None
            construflow_future = executor.submit(fetch_construflow_data)
            
            # Aguardar resultados
            if smartsheet_future:
                try:
                    tasks_df = smartsheet_future.result(timeout=120)  # Timeout de 2 minutos
                    logger.info(f"✅ Dados do Smartsheet obtidos: {len(tasks_df) if tasks_df is not None and not tasks_df.empty else 0} tarefas")
                except Exception as e:
                    logger.error(f"Erro ao obter dados do Smartsheet: {e}")
                    tasks_df = None
            
            try:
                issues_df = construflow_future.result(timeout=300)  # Timeout de 5 minutos
                logger.info(f"✅ Issues do Construflow obtidas: {len(issues_df)} issues")
            except Exception as e:
                logger.error(f"Erro ao obter issues do Construflow: {e}")
                issues_df = pd.DataFrame()
        
        # Processar dados do Smartsheet
        if tasks_df is not None and not tasks_df.empty:
            # Processar dados do Smartsheet
            # Forçar atualização do cache para garantir dados mais recentes
            tasks_df = self.smartsheet.get_recent_tasks(smartsheet_id, force_refresh=True)
            if not tasks_df.empty:
                # Filtrar tarefas que devem ser removidas do relatório
                # Procurar por coluna "Caminho crítico - Marco" (com variações possíveis)
                # Excluir tarefas com "INT - Remover Relatório" ou variações similares
                
                # Função para normalizar valores (remover espaços extras, converter para lowercase, remover acentos)
                def normalize_remove_value(val):
                    if pd.isna(val):
                        return None
                    import unicodedata
                    import re
                    text = str(val).strip()
                    # Normalizar unicode (remover acentos)
                    text = unicodedata.normalize('NFD', text)
                    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
                    # Converter para lowercase e remover espaços múltiplos
                    text = re.sub(r'\s+', ' ', text.lower().strip())
                    return text
                
                # Procurar coluna com nome similar (case-insensitive, tolerante a espaços)
                critical_path_column = None
                possible_names = [
                    'Caminho crítico - Marco',
                    'Caminho Critico - Marco',
                    'Caminho crítico-Marco',
                    'Caminho Critico-Marco',
                    'Caminho crítico Marco',
                    'Caminho Critico Marco'
                ]
                
                # Normalizar nomes de colunas para comparação
                def normalize_column_name(name):
                    import unicodedata
                    import re
                    text = str(name).strip()
                    text = unicodedata.normalize('NFD', text)
                    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
                    text = re.sub(r'\s+', ' ', text.lower().strip())
                    return text
                
                # Procurar coluna correspondente
                for col in tasks_df.columns:
                    normalized_col = normalize_column_name(col)
                    for possible_name in possible_names:
                        if normalized_col == normalize_column_name(possible_name):
                            critical_path_column = col
                            break
                    if critical_path_column:
                        break
                
                # Se não encontrou exata, procurar por coluna que contenha "caminho" e "critico" ou "critico" e "marco"
                if not critical_path_column:
                    for col in tasks_df.columns:
                        normalized_col = normalize_column_name(col)
                        if 'caminho' in normalized_col and ('critico' in normalized_col or 'critico' in normalized_col) and 'marco' in normalized_col:
                            critical_path_column = col
                            logger.info(f"Coluna encontrada por busca parcial: '{col}' (normalizada: '{normalized_col}')")
                            break
                
                if critical_path_column:
                    logger.info(f"Usando coluna '{critical_path_column}' para filtrar tarefas a remover")
                    
                    # Valores possíveis para remoção (case-insensitive, com/sem acentos)
                    remove_values = [
                        'int - remover relatório',
                        'int - remover relatorio',
                        'int-remover relatório',
                        'int-remover relatorio',
                        'remover relatório',
                        'remover relatorio',
                        'remover relatorios',
                        'remover relatórios'
                    ]
                    
                    # Contar tarefas antes do filtro
                    total_before = len(tasks_df)
                    
                    # Filtrar tarefas que NÃO têm nenhum dos valores de remoção
                    def should_keep_task(val):
                        normalized = normalize_remove_value(val)
                        if normalized is None:
                            return True  # Manter tarefas sem valor
                        # Verificar se corresponde a algum valor de remoção
                        for remove_val in remove_values:
                            if normalized == remove_val or normalized.startswith(remove_val) or remove_val in normalized:
                                return False  # Remover esta tarefa
                        return True  # Manter esta tarefa
                    
                    mask = tasks_df[critical_path_column].apply(should_keep_task)
                    tasks_df = tasks_df[mask]
                    
                    removed_count = total_before - len(tasks_df)
                    logger.info(f"Filtradas {removed_count} tarefas com tag de remoção. Tarefas restantes: {len(tasks_df)} de {total_before}")
                    
                    # Log de debug: mostrar alguns valores únicos encontrados na coluna (após filtro)
                    if len(tasks_df) > 0 and critical_path_column in tasks_df.columns:
                        sample_values = tasks_df[critical_path_column].dropna().unique()[:5]
                        if len(sample_values) > 0:
                            logger.debug(f"Valores de exemplo na coluna '{critical_path_column}' (após filtro): {list(sample_values)}")
                else:
                    logger.warning(f"Coluna 'Caminho crítico - Marco' não encontrada. Colunas disponíveis: {', '.join(tasks_df.columns.tolist()[:10])}")
                    logger.warning("Tarefas não serão filtradas por tag de remoção.")
                
                # Manter todas as tarefas para o gerador decidir o que é concluído
                all_tasks = [row._asdict() if hasattr(row, '_asdict') else row.to_dict() for _, row in tasks_df.iterrows()]

                # Log diagnóstico: disciplinas e status disponíveis
                if 'Disciplina' in tasks_df.columns:
                    disciplinas = tasks_df['Disciplina'].dropna().unique().tolist()
                    logger.info(f"Disciplinas encontradas no Smartsheet ({len(disciplinas)}): {sorted(disciplinas)}")
                else:
                    logger.warning(f"Coluna 'Disciplina' não encontrada no Smartsheet. Colunas: {tasks_df.columns.tolist()[:15]}")
                if 'Status' in tasks_df.columns:
                    status_dist = tasks_df['Status'].value_counts().to_dict()
                    logger.info(f"Distribuição de status: {status_dist}")

                # Construir lista de atrasadas:
                # - Status = 'não feito' (com/sem acento)
                # - OU categoria/motivo de atraso preenchidos
                # - OU data de término anterior a hoje e status != 'feito'
                delayed_tasks = []
                # Usar data de referência se fornecida, senão usar data atual
                today = (reference_date if reference_date else datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)

                def normalize_status(value: Any) -> str:
                    if value is None:
                        return ""
                    import unicodedata
                    import re
                    text = str(value).strip().lower()
                    text = unicodedata.normalize('NFD', text)
                    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
                    text = re.sub(r'\s+', ' ', text)
                    return text

                def has_delay_info(task_row: pd.Series) -> bool:
                    delay_keys = [
                        'Categoria de atraso',
                        'Delay Category',
                        'Motivo de atraso',
                        'Motivo do atraso',
                        'Delay Reason'
                    ]
                    for key in delay_keys:
                        val = task_row.get(key)
                        if val is not None and str(val).strip() not in ['', 'nan', 'None']:
                            return True
                    return False
                
                for _, task in tasks_df.iterrows():
                    task_dict = task.to_dict()
                    status_norm = normalize_status(task.get('Status', ''))
                    tem_info_atraso = has_delay_info(task)

                    # Verificar se está atrasada pela data (término antes de hoje e não concluída)
                    atrasada_por_data = False
                    if status_norm != 'feito':
                        end_date = task.get('Data Término') or task.get('Data de Término') or task.get('End Date')
                        if end_date and not pd.isna(end_date):
                            try:
                                if isinstance(end_date, str):
                                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                                        try:
                                            end_dt = datetime.strptime(end_date.split('T')[0], fmt)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        end_dt = None
                                else:
                                    end_dt = pd.to_datetime(end_date).to_pydatetime()

                                if end_dt and end_dt.replace(hour=0, minute=0, second=0, microsecond=0) < today:
                                    atrasada_por_data = True
                            except Exception as e:
                                logger.debug(f"Erro ao processar data de término '{end_date}': {e}")

                    # Status padronizados do Smartsheet: 'a fazer', 'em progresso', 'feito', 'não feito'
                    if status_norm == 'nao feito' or tem_info_atraso or atrasada_por_data:
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
        elif smartsheet_id:
            logger.warning(f"Smartsheet ID={smartsheet_id} fornecido para projeto {project_id}, mas get_recent_tasks retornou vazio ou None. Relatório terá seções de Smartsheet vazias.")
        else:
            logger.warning(f"Nenhum smartsheet_id encontrado para projeto {project_id}. Verifique a coluna smartsheet_id no Supabase.")
        
        # Processar dados do Construflow (já obtidos em paralelo acima)
        # Se não conseguiu obter dados do Construflow ou DataFrame está vazio, 
        # manter construflow_data como None para que a notificação seja enviada
        if issues_df is None or issues_df.empty:
            logger.warning(f"Nenhuma issue encontrada no Construflow para projeto {project_id} - construflow_data permanecerá None para notificação")
            # Manter construflow_data como None para que o sistema notifique sobre a falta de dados
            return result
        
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
                # Se não há issues ativas mas há issues no total, inicializar estrutura vazia
                # Isso indica que há issues mas nenhuma está ativa
                result['construflow_data'] = {
                    'active_issues': [],
                    'issue_counts': 0,
                    'disciplines': {},
                    'all_issues': issues_df.to_dict('records'),
                    'client_issues': []
                }
                logger.warning("Nenhuma issue ativa encontrada, mas há issues no projeto")
            
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
                if not projects_df.empty and 'construflow_disciplinasclientes' in projects_df.columns:
                    # Tentar diferentes nomes de coluna para o ID do Construflow
                    id_column = None
                    for col_name in ['construflow_id', 'flow_id', 'ID_Construflow', 'construflowid']:
                        if col_name in projects_df.columns:
                            id_column = col_name
                            break
                    
                    if id_column:
                        # Converter para string para comparação
                        projects_df[id_column] = projects_df[id_column].astype(str)
                        project_row = projects_df[projects_df[id_column] == str(project_id)]
                        
                        if not project_row.empty and pd.notna(project_row['construflow_disciplinasclientes'].values[0]):
                            disciplinas_str = str(project_row['construflow_disciplinasclientes'].values[0])
                            # Suportar tanto vírgula quanto ponto e vírgula como separadores
                            if ';' in disciplinas_str:
                                disciplinas_cliente = [d.strip() for d in disciplinas_str.split(';') if d.strip()]
                            else:
                                disciplinas_cliente = [d.strip() for d in disciplinas_str.split(',') if d.strip()]
                            logger.info(f"Disciplinas do cliente carregadas para projeto {project_id}: {disciplinas_cliente}")
                    else:
                        logger.warning(f"Coluna de ID do Construflow não encontrada na planilha para projeto {project_id}")
            except Exception as e:
                logger.warning(f"Erro ao obter disciplinas do cliente da planilha: {e}")
        
        import re
        import unicodedata
        
        def normalize_text(text):
            """Normaliza texto removendo acentos, espaços extras e convertendo para lowercase."""
            if not text or pd.isna(text):
                return ""
            # Converter para string e remover espaços extras
            text = str(text).strip()
            # Normalizar unicode (NFD = decomposed form)
            text = unicodedata.normalize('NFD', text)
            # Remover acentos
            text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
            # Converter para lowercase e remover espaços múltiplos
            text = re.sub(r'\s+', ' ', text.lower().strip())
            return text
        
        if not disciplinas_cliente or 'name' not in df_issues.columns:
            logger.warning(f"Não foi possível filtrar issues para o cliente. Disciplinas: {disciplinas_cliente}")
            return df_issues

        # Filtrar por visibilidade (apenas coordenação ou público)
        visibility_cols = [c for c in df_issues.columns if 'visibility' in str(c).lower() or 'visibilidade' in str(c).lower()]
        if visibility_cols:
            allowed_visibility = {
                'publico', 'público', 'public',
                'coordenacao', 'coordenação', 'coordination'
            }

            def is_allowed_visibility(value) -> bool:
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    return True
                norm = normalize_text(value)
                if not norm:
                    return True
                return any(norm == v or v in norm for v in allowed_visibility)

            def row_visibility_ok(row) -> bool:
                # Usar o primeiro valor de visibilidade preenchido
                for col in visibility_cols:
                    val = row.get(col)
                    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == '':
                        continue
                    return is_allowed_visibility(val)
                return True

            before_count = len(df_issues)
            df_issues = df_issues[df_issues.apply(row_visibility_ok, axis=1)]
            filtered_count = before_count - len(df_issues)
            logger.info(f"Filtradas {filtered_count} issues por visibilidade (permitidas: coordenação/público)")
        
        # Normalizar disciplinas do cliente (remover acentos, espaços, case-insensitive)
        disciplinas_cliente_normalized = [normalize_text(d) for d in disciplinas_cliente if d and str(d).strip()]
        logger.info(f"Filtrando por disciplinas do cliente (originais): {disciplinas_cliente}")
        logger.info(f"Filtrando por disciplinas do cliente (normalizadas): {disciplinas_cliente_normalized}")
        
        # Verificar quais disciplinas únicas existem nas issues
        if not df_issues.empty and 'name' in df_issues.columns:
            disciplinas_issues = df_issues['name'].dropna().unique()
            disciplinas_issues_normalized = [normalize_text(d) for d in disciplinas_issues]
            logger.info(f"Disciplinas encontradas nas issues (originais): {list(disciplinas_issues)}")
            logger.info(f"Disciplinas encontradas nas issues (normalizadas): {disciplinas_issues_normalized}")
        
        # Filtrar pelas disciplinas do cliente (comparação normalizada com correspondência parcial)
        if df_issues['name'].dtype == 'object':
            # Normalizar nomes das issues para comparação
            df_issues_normalized = df_issues['name'].astype(str).apply(normalize_text)
            
            # Primeiro tentar correspondência exata
            mask = df_issues_normalized.isin(disciplinas_cliente_normalized)
            
            # Se não encontrou correspondência exata, tentar correspondência parcial (contém)
            if not mask.any() and disciplinas_cliente_normalized:
                logger.info(f"Tentando correspondência parcial para disciplinas do cliente...")
                # Criar máscara para cada disciplina do cliente
                partial_masks = []
                for disc_cliente in disciplinas_cliente_normalized:
                    if disc_cliente:  # Ignorar strings vazias
                        partial_mask = df_issues_normalized.str.contains(disc_cliente, case=False, na=False, regex=False)
                        partial_masks.append(partial_mask)
                        if partial_mask.any():
                            logger.info(f"  ✅ Encontrada correspondência parcial: '{disc_cliente}' em {partial_mask.sum()} issues")
                
                # Combinar todas as máscaras parciais
                if partial_masks:
                    mask = pd.concat(partial_masks, axis=1).any(axis=1)
        else:
            mask = df_issues['name'].isin(disciplinas_cliente)
        
        filtered_df = df_issues[mask]
        
        logger.info(f"Filtradas {len(filtered_df)} issues de cliente de um total de {len(df_issues)}")
        if len(filtered_df) == 0 and len(df_issues) > 0:
            logger.warning(f"⚠️ NENHUMA ISSUE FILTRADA! Verifique se os nomes das disciplinas na planilha correspondem aos nomes no Construflow")
            logger.warning(f"   Disciplinas configuradas: {disciplinas_cliente}")
            if 'name' in df_issues.columns:
                disciplinas_disponiveis = df_issues['name'].dropna().unique().tolist()
                logger.warning(f"   Disciplinas disponíveis nas issues: {disciplinas_disponiveis}")
        
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
