"""
Conector GraphQL para a API do Construflow.
Versão otimizada que usa GraphQL como principal e REST como backup.
"""

import os
import pickle
import time
import logging
import pandas as pd
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import APIConnector
from ..config import ConfigManager

logger = logging.getLogger("ReportSystem")

class ConstruflowGraphQLConnector(APIConnector):
    """Conector GraphQL para a API do Construflow."""
    
    def __init__(self, config: ConfigManager):
        """Inicializa o conector GraphQL do Construflow."""
        super().__init__(config)
        self.graphql_url = "https://api.construflow.com.br/graphql"
        self.username = config.get_env_var("CONSTRUFLOW_USERNAME")
        self.password = config.get_env_var("CONSTRUFLOW_PASSWORD")
        self.api_key = config.get_env_var("CONSTRUFLOW_API_KEY")
        self.api_secret = config.get_env_var("CONSTRUFLOW_API_SECRET")
        
        # Cache para tokens flutuantes
        self.token_cache = {
            'access_token': None,
            'refresh_token': None,
            'expires_at': None
        }
        
        self.cache_dir = os.path.join(config.cache_dir, "construflow_graphql")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Fallback para REST API
        self.rest_connector = None
        try:
            from .construflow import ConstruflowConnector
            self.rest_connector = ConstruflowConnector(config)
            logger.info("Conector REST disponível como fallback")
        except ImportError:
            logger.warning("Conector REST não disponível para fallback")
    
    def _get_auth_token(self) -> str:
        """Obtém token de autenticação com sistema de tokens flutuantes."""
        try:
            # Verificar se já temos um token válido em cache
            if (self.token_cache['access_token'] and 
                self.token_cache['expires_at'] and 
                time.time() < self.token_cache['expires_at']):
                logger.debug("Usando token em cache")
                return self.token_cache['access_token']
            
            # Se temos refresh token, tentar renovar
            if self.token_cache['refresh_token']:
                try:
                    logger.debug("Renovando token com refresh token")
                    refresh_response = requests.post(
                        self.graphql_url,
                        headers={'Content-Type': 'application/json'},
                        json={
                            'query': '''
                                mutation RefreshToken {
                                    refreshToken {
                                        accessToken
                                        refreshToken
                                    }
                                }
                            '''
                        }
                    )
                    
                    refresh_data = refresh_response.json()
                    if refresh_data.get('data', {}).get('refreshToken', {}).get('accessToken'):
                        self.token_cache['access_token'] = refresh_data['data']['refreshToken']['accessToken']
                        self.token_cache['refresh_token'] = refresh_data['data']['refreshToken']['refreshToken']
                        self.token_cache['expires_at'] = time.time() + 3600  # 1 hora
                        logger.info("Token renovado com sucesso")
                        return self.token_cache['access_token']
                except Exception as e:
                    logger.warning(f"Falha ao renovar token: {e}")
                    # Limpar cache e fazer novo login
                    self.token_cache = {'access_token': None, 'refresh_token': None, 'expires_at': None}
            
            # Fazer novo login
            logger.info("Fazendo novo login")
            login_response = requests.post(
                self.graphql_url,
                headers={'Content-Type': 'application/json'},
                json={
                    'query': '''
                        mutation SignIn($username: String!, $password: String!) {
                            signIn(username: $username, password: $password) {
                                accessToken
                                refreshToken
                            }
                        }
                    ''',
                    'variables': {
                        'username': self.username,
                        'password': self.password
                    }
                }
            )
            
            login_data = login_response.json()
            if login_data.get('data', {}).get('signIn', {}).get('accessToken'):
                self.token_cache['access_token'] = login_data['data']['signIn']['accessToken']
                self.token_cache['refresh_token'] = login_data['data']['signIn']['refreshToken']
                self.token_cache['expires_at'] = time.time() + 3600  # 1 hora
                logger.info("Login realizado e tokens armazenados")
                return self.token_cache['access_token']
            else:
                raise Exception(f"Falha no login: {login_data}")
                
        except Exception as e:
            logger.error(f"Erro ao obter token: {e}")
            raise
    
    def _execute_graphql_query(self, query: str, variables: Dict = None) -> Dict:
        """Executa uma query GraphQL com retry automático."""
        try:
            token = self._get_auth_token()
            
            response = requests.post(
                self.graphql_url,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {token}',
                    'X-API-Key': self.api_key
                },
                json={
                    'query': query,
                    'variables': variables or {}
                }
            )
            
            data = response.json()
            
            # Verificar se o token expirou durante a requisição
            if data.get('errors') and any(
                'token' in error.get('message', '').lower() or 
                'unauthorized' in error.get('message', '').lower() or
                'expired' in error.get('message', '').lower()
                for error in data['errors']
            ):
                logger.info("Token expirou durante requisição, renovando...")
                # Limpar cache e tentar novamente
                self.token_cache = {'access_token': None, 'refresh_token': None, 'expires_at': None}
                token = self._get_auth_token()
                
                # Refazer a requisição com o novo token
                response = requests.post(
                    self.graphql_url,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {token}',
                        'X-API-Key': self.api_key
                    },
                    json={
                        'query': query,
                        'variables': variables or {}
                    }
                )
                data = response.json()
            
            return data
            
        except Exception as e:
            logger.error(f"Erro na requisição GraphQL: {e}")
            raise
    


    def get_projects(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtém lista de projetos usando GraphQL.
        CORREÇÃO: Busca projetos da planilha E também tenta buscar projetos específicos
        que podem estar compartilhados mas não na planilha.
        
        Args:
            force_refresh: Se deve forçar atualização do cache
            
        Returns:
            DataFrame com projetos
        """
        cache_file = os.path.join(self.cache_dir, "projects_graphql.pkl")
        
        # Verificar cache
        if not force_refresh and os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            if time.time() - cache_time < 86400:  # 24 horas
                try:
                    with open(cache_file, 'rb') as f:
                        logger.info("Usando cache para projetos GraphQL")
                        return pd.DataFrame(pickle.load(f))
                except Exception as e:
                    logger.warning(f"Erro ao carregar cache: {e}")
        
        # Buscar projetos usando GraphQL
        logger.info("Buscando projetos via GraphQL")
        
        # Obter IDs dos projetos da planilha
        try:
            from ..storage.google_drive import GoogleDriveManager
            gdrive = GoogleDriveManager(self.config)
            projects_df = gdrive.load_project_config_from_sheet()
            
            if projects_df.empty:
                logger.warning("Planilha de configuração vazia, usando lista padrão")
                # Fallback para lista padrão se a planilha estiver vazia
                known_project_ids = [1700, 2100, 2400, 2500, 3035, 4557, 4560]
            else:
                # Extrair IDs dos projetos da planilha
                if 'construflow_id' in projects_df.columns:
                    # Filtrar apenas projetos ativos se a coluna existir
                    if 'relatoriosemanal_status' in projects_df.columns:
                        active_projects = projects_df[projects_df['relatoriosemanal_status'].str.lower() == 'sim']
                    else:
                        active_projects = projects_df
                    
                    # Converter para lista de IDs
                    known_project_ids = []
                    for _, row in active_projects.iterrows():
                        if pd.notna(row['construflow_id']):
                            try:
                                project_id = int(row['construflow_id'])
                                known_project_ids.append(project_id)
                            except (ValueError, TypeError):
                                logger.warning(f"ID inválido na planilha: {row['construflow_id']}")
                    
                    logger.info(f"Encontrados {len(known_project_ids)} projetos ativos na planilha")
                else:
                    logger.warning("Coluna 'construflow_id' não encontrada na planilha, usando lista padrão")
                    known_project_ids = [1700, 2100, 2400, 2500, 3035, 4557, 4560]
                    
        except Exception as e:
            logger.warning(f"Erro ao carregar planilha: {e}, usando lista padrão")
            known_project_ids = [1700, 2100, 2400, 2500, 3035, 4557, 4560]
        
        all_projects = []
        
        # Primeiro, buscar projetos conhecidos da planilha
        for project_id in known_project_ids:
            try:
                query = '''
                    query getProject($projectId: Int!) {
                        project(projectId: $projectId) {
                            id
                            name
                            status
                        }
                    }
                '''
                
                result = self._execute_graphql_query(query, {'projectId': project_id})
                
                if result.get('data', {}).get('project'):
                    project = result['data']['project']
                    all_projects.append({
                        'id': str(project['id']),
                        'name': project['name'],
                        'status': project['status']
                    })
                    logger.debug(f"Projeto {project_id} encontrado: {project['name']}")
                else:
                    logger.warning(f"Projeto {project_id} não encontrado na API")
                
            except Exception as e:
                logger.warning(f"Erro ao buscar projeto {project_id}: {e}")
        
        # Agora buscar projetos compartilhados que podem não estar na planilha
        try:
            logger.info("Buscando projetos compartilhados adicionais...")
            query = '''
                query getSharedProjects {
                    projects {
                        id
                        name
                        status
                    }
                }
            '''
            
            result = self._execute_graphql_query(query)
            
            if result.get('data', {}).get('projects'):
                shared_projects = result['data']['projects']
                logger.info(f"Encontrados {len(shared_projects)} projetos totais na API")
                
                # Filtrar apenas projetos que não estão na lista conhecida
                known_ids_set = set(str(pid) for pid in known_project_ids)
                additional_projects = []
                
                for project in shared_projects:
                    project_id_str = str(project['id'])
                    if project_id_str not in known_ids_set:
                        additional_projects.append({
                            'id': project_id_str,
                            'name': project['name'],
                            'status': project['status']
                        })
                        logger.info(f"Projeto compartilhado encontrado: {project['name']} (ID: {project_id_str})")
                
                # Adicionar projetos compartilhados à lista
                all_projects.extend(additional_projects)
                logger.info(f"Adicionados {len(additional_projects)} projetos compartilhados")
            else:
                logger.warning("Não foi possível obter lista de projetos compartilhados")
                
        except Exception as e:
            logger.warning(f"Erro ao buscar projetos compartilhados: {e}")
        
        # Salvar em cache
        if all_projects:
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(all_projects, f)
                logger.info(f"Cache atualizado para {len(all_projects)} projetos (incluindo compartilhados)")
            except Exception as e:
                logger.warning(f"Erro ao salvar cache: {e}")
        
        return pd.DataFrame(all_projects)
    
    def get_project_issues(self, project_id: str, limit: int = None) -> pd.DataFrame:
        """
        Obtém issues/pendências de um projeto específico.
        CORRIGIDO: Agora cria uma linha separada para cada disciplina de cada issue.
        CORREÇÃO: Limpa o cache antes de buscar novos dados.
        
        Args:
            project_id: ID do projeto
            limit: Número máximo of issues (None para buscar todas)
            
        Returns:
            DataFrame com issues (uma linha por disciplina de cada issue)
        """
        cache_file = os.path.join(self.cache_dir, f"issues_{project_id}_graphql.pkl")
        
        # Verificar cache
        if os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            if time.time() - cache_time < 3600:  # 1 hora para issues
                try:
                    with open(cache_file, 'rb') as f:
                        logger.info(f"Usando cache para issues do projeto {project_id}")
                        return pd.DataFrame(pickle.load(f))
                except Exception as e:
                    logger.warning(f"Erro ao carregar cache: {e}")
        
        # CORREÇÃO: Limpar cache antigo antes de buscar novos dados
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info(f"Cache antigo removido para projeto {project_id}")
        except Exception as e:
            logger.warning(f"Erro ao remover cache antigo: {e}")
        
        # Buscar issues usando GraphQL com paginação
        logger.info(f"Buscando issues do projeto {project_id} via GraphQL")
        
        try:
            query = '''
                query getIssues($projectId: Int!, $first: Int, $after: String, $filter: JSON) {
                    project(projectId: $projectId) {
                        issues(first: $first, after: $after, filter: $filter) {
                            issues {
                                id
                                code
                                title
                                status
                                priority
                                createdAt
                                updatedAt
                                disciplines {
                                    discipline {
                                        id
                                        name
                                    }
                                    status
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            '''
            
            issues = []
            has_next_page = True
            after_cursor = None
            page_count = 0
            page_size = 100  # Tamanho da página para otimizar
            
            while has_next_page:
                page_count += 1
                logger.info(f"Buscando página {page_count} de issues do projeto {project_id}")
                
                variables = {
                    'projectId': int(project_id),
                    'first': page_size,
                    'filter': {'standard': 'pendencies'}
                }
                
                if after_cursor:
                    variables['after'] = after_cursor
                
                result = self._execute_graphql_query(query, variables)
                
                if result.get('data', {}).get('project', {}).get('issues', {}).get('issues'):
                    page_issues = result['data']['project']['issues']['issues']
                    logger.info(f"Página {page_count}: {len(page_issues)} issues encontradas")
                    
                    for issue in page_issues:
                        # CORREÇÃO: Criar uma linha para cada disciplina da issue
                        if issue.get('disciplines') and len(issue['disciplines']) > 0:
                            # Para cada disciplina da issue, criar uma linha separada
                            for discipline_data in issue['disciplines']:
                                discipline_name = discipline_data['discipline'].get('name', '')
                                discipline_status = discipline_data.get('status', '')
                                
                                issues.append({
                                    'id': str(issue['id']),
                                    'code': issue['code'],
                                    'title': issue['title'],
                                    'status_x': issue['status'],  # Status da issue (active, closed, etc.)
                                    'priority': issue.get('priority'),  # Prioridade da issue
                                    'projectId': project_id,
                                    'createdAt': issue.get('createdAt'),
                                    'updatedAt': issue.get('updatedAt'),
                                    'name': discipline_name,  # Nome da disciplina
                                    'status_y': discipline_status  # Status da disciplina (todo, done, etc.)
                                })
                        else:
                            # Se a issue não tem disciplinas, criar uma linha com valores vazios
                            issues.append({
                                'id': str(issue['id']),
                                'code': issue['code'],
                                'title': issue['title'],
                                'status_x': issue['status'],  # Status da issue (active, closed, etc.)
                                'priority': issue.get('priority'),  # Prioridade da issue
                                'projectId': project_id,
                                'createdAt': issue.get('createdAt'),
                                'updatedAt': issue.get('updatedAt'),
                                'name': '',  # Nome da disciplina vazio
                                'status_y': ''  # Status da disciplina vazio
                            })
                    
                    # Verificar se há mais páginas
                    page_info = result['data']['project']['issues']['pageInfo']
                    has_next_page = page_info.get('hasNextPage', False)
                    after_cursor = page_info.get('endCursor')
                    
                    # Verificar se atingiu o limite
                    if limit and len(issues) >= limit:
                        logger.info(f"Limite de {limit} issues atingido")
                        break
                else:
                    logger.warning(f"Página {page_count}: Nenhuma issue encontrada")
                    break
            
            logger.info(f"Total de {len(issues)} linhas de issues+disciplinas carregadas do projeto {project_id}")
            
            # Salvar em cache
            if issues:
                try:
                    with open(cache_file, 'wb') as f:
                        pickle.dump(issues, f)
                    logger.info(f"Cache atualizado para {len(issues)} linhas de issues+disciplinas do projeto {project_id}")
                except Exception as e:
                    logger.warning(f"Erro ao salvar cache: {e}")
            
            return pd.DataFrame(issues)
            
        except Exception as e:
            logger.error(f"Erro ao buscar issues do projeto {project_id}: {e}")
            # Fallback para REST API se disponível
            if self.rest_connector:
                logger.info("Usando fallback para REST API")
                return self.rest_connector.get_project_issues(project_id)
            return pd.DataFrame()
    
    def get_issue_comments(self, project_id: str, issue_id: str) -> List[Dict]:
        """
        Obtém comentários de uma issue específica.
        
        Args:
            project_id: ID do projeto
            issue_id: ID da issue
            
        Returns:
            Lista de comentários
        """
        try:
            query = '''
                query getIssueComments($issueId: Int!, $projectId: Int!) {
                    issue(issueId: $issueId, projectId: $projectId) {
                        id
                        code
                        title
                        comments {
                            id
                            message
                            visibility
                            createdAt
                            createdByUser {
                                id
                                name
                                email
                            }
                        }
                        history {
                            _id
                            user {
                                id
                                name
                            }
                            entityType
                            fields
                            dataTime
                        }
                    }
                }
            '''
            
            result = self._execute_graphql_query(query, {
                'projectId': int(project_id),
                'issueId': int(issue_id)
            })
            
            if result.get('data', {}).get('issue'):
                issue = result['data']['issue']
                return {
                    'issue': {
                        'id': issue['id'],
                        'code': issue['code'],
                        'title': issue['title']
                    },
                    'comments': issue.get('comments', []),
                    'history': issue.get('history', [])
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Erro ao buscar comentários da issue {issue_id}: {e}")
            return {}
    
    def get_data(self, endpoint: str, **kwargs) -> List[Dict]:
        """
        Método compatível com a interface REST para fallback.
        
        Args:
            endpoint: Tipo de dados ('projects', 'issues', etc.)
            **kwargs: Argumentos adicionais
            
        Returns:
            Lista de dados
        """
        if endpoint == 'projects':
            df = self.get_projects()
            return df.to_dict('records')
        elif endpoint == 'issues':
            project_id = kwargs.get('project_id')
            if project_id:
                df = self.get_project_issues(project_id)
                return df.to_dict('records')
            else:
                # Fallback para REST API se disponível
                if self.rest_connector:
                    return self.rest_connector.get_data(endpoint, **kwargs)
                return []
        else:
            # Fallback para REST API se disponível
            if self.rest_connector:
                return self.rest_connector.get_data(endpoint, **kwargs)
            return []
    
    def logout(self):
        """Faz logout e limpa tokens."""
        try:
            if self.token_cache['access_token']:
                self._execute_graphql_query('''
                    mutation SignOut {
                        signOut
                    }
                ''')
        except Exception as e:
            logger.warning(f"Erro no logout: {e}")
        finally:
            self.token_cache = {'access_token': None, 'refresh_token': None, 'expires_at': None}
            logger.info("Tokens limpos do cache") 

    def get_consolidated_project_data(self, project_id: str = None, limit: int = None) -> Dict[str, pd.DataFrame]:
        """
        Obtém todos os dados de um projeto em uma única query GraphQL otimizada.
        CORRIGIDO: Agora inclui disciplinas e cria uma linha separada para cada disciplina de cada issue.
        CORREÇÃO: Limpa o cache antes de buscar novos dados.
        
        Args:
            project_id: ID do projeto específico (obrigatório para otimização)
            limit: Limite de issues por projeto (None = infinito)
        
        Returns:
            Dicionário com DataFrames: {'projects', 'issues', 'disciplines', 'issue_disciplines'}
        """
        try:
            if not project_id:
                logger.warning("⚠️ project_id não fornecido, usando query para todos os projetos")
                return self.get_all_data_optimized()
            
            logger.info(f"🎯 Executando query consolidada GraphQL OTIMIZADA para projeto {project_id}")
            
            # CORREÇÃO: Limpar cache antigo antes de buscar novos dados
            cache_file = os.path.join(self.cache_dir, f"issues_{project_id}_graphql.pkl")
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    logger.info(f"Cache antigo removido para projeto {project_id}")
            except Exception as e:
                logger.warning(f"Erro ao remover cache antigo: {e}")
            
            # Query consolidada OTIMIZADA que inclui disciplinas
            query = """
            query GetProjectDataOptimized($projectId: Int!, $limit: Int) {
                project(projectId: $projectId) {
                    id
                    name
                    status
                    issues(first: $limit, filter: { standard: "pendencies" }) {
                        issues {
                            id
                            code
                            title
                            status
                            createdAt
                            updatedAt
                            disciplines {
                                discipline {
                                    id
                                    name
                                }
                                status
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
            }
            """
            
            # Se limit for None, usar um valor muito alto (ex: 1000000)
            query_limit = limit if limit is not None else 1000000
            variables = {
                "projectId": int(project_id),
                "limit": query_limit
            }
            
            # Executar query consolidada otimizada
            result = self._execute_graphql_query(query, variables)
            
            if not result.get('data'):
                logger.error("❌ Query consolidada otimizada falhou")
                return {}
            
            data = result['data']
            
            # Processar projeto específico
            projects_data = []
            if data.get('project'):
                project = data['project']
                projects_data.append({
                    'id': project['id'],
                    'name': project['name'],
                    'status': project.get('status', ''),
                    'description': '',  # Campo não disponível no schema
                    'createdAt': '',    # Campo não disponível no schema
                    'updatedAt': ''     # Campo não disponível no schema
                })
                logger.info(f"✅ Projeto {project['name']} obtido via GraphQL otimizado")
            
            # Processar issues do projeto específico (CORRIGIDO: uma linha por disciplina)
            issues_data = []
            
            if data.get('project', {}).get('issues', {}).get('issues'):
                for issue in data['project']['issues']['issues']:
                    # CORREÇÃO: Criar uma linha para cada disciplina da issue
                    if issue.get('disciplines') and len(issue['disciplines']) > 0:
                        # Para cada disciplina da issue, criar uma linha separada
                        for discipline_data in issue['disciplines']:
                            discipline_name = discipline_data['discipline'].get('name', '')
                            discipline_status = discipline_data.get('status', '')
                            
                            issue_data = {
                                'id': issue['id'],
                                'code': issue.get('code', ''),
                                'title': issue['title'],
                                'status_x': issue.get('status', ''),  # Status da issue
                                'projectId': str(project_id),
                                'createdAt': issue.get('createdAt', ''),
                                'updatedAt': issue.get('updatedAt', ''),
                                'name': discipline_name,  # Nome da disciplina
                                'status_y': discipline_status  # Status da disciplina
                            }
                            issues_data.append(issue_data)
                    else:
                        # Se a issue não tem disciplinas, criar uma linha com valores vazios
                        issue_data = {
                            'id': issue['id'],
                            'code': issue.get('code', ''),
                            'title': issue['title'],
                            'status_x': issue.get('status', ''),
                            'projectId': str(project_id),
                            'createdAt': issue.get('createdAt', ''),
                            'updatedAt': issue.get('updatedAt', ''),
                            'name': '',  # Nome da disciplina vazio
                            'status_y': ''  # Status da disciplina vazio
                        }
                        issues_data.append(issue_data)
            
            # Converter para DataFrames
            results = {}
            
            if projects_data:
                results['projects'] = pd.DataFrame(projects_data)
                logger.info(f"✅ 1 projeto específico obtido via GraphQL otimizado")
            
            if issues_data:
                results['issues'] = pd.DataFrame(issues_data)
                logger.info(f"🎯 {len(issues_data)} linhas de issues+disciplinas do projeto {project_id} obtidas via GraphQL otimizado")
            
            logger.info(f"🚀 Query otimizada concluída: 1 projeto + {len(issues_data)} linhas de issues+disciplinas específicas")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro na query consolidada: {e}")
            return {}

    def get_project_data_optimized(self, project_id: str) -> Dict[str, pd.DataFrame]:
        """
        Versão otimizada que obtém todos os dados de um projeto específico
        em uma única query GraphQL.
        
        Args:
            project_id: ID do projeto
            
        Returns:
            Dicionário com DataFrames dos dados do projeto
        """
        # Limite None = infinito
        return self.get_consolidated_project_data(project_id, limit=None)

    def get_all_data_optimized(self) -> Dict[str, pd.DataFrame]:
        """
        Versão otimizada que obtém todos os dados em uma única query GraphQL.
        CORRIGIDO: Agora inclui disciplinas e cria uma linha separada para cada disciplina de cada issue.
        
        Returns:
            Dicionário com todos os DataFrames
        """
        try:
            logger.info("🎯 Executando query consolidada GraphQL para TODOS os projetos")
            
            # Query para buscar todos os projetos e suas issues com disciplinas
            query = """
            query GetAllProjectsData($limit: Int) {
                projects(first: $limit) {
                    projects {
                        id
                        name
                        status
                        issues(first: 1000, filter: { standard: "pendencies" }) {
                            issues {
                                id
                                code
                                title
                                status
                                createdAt
                                updatedAt
                                disciplines {
                                    discipline {
                                        id
                                        name
                                    }
                                    status
                                }
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """
            
            variables = {
                "limit": 200  # Limite de projetos
            }
            
            # Executar query consolidada
            result = self._execute_graphql_query(query, variables)
            
            if not result.get('data'):
                logger.error("❌ Query consolidada para todos os projetos falhou")
                return {}
            
            data = result['data']
            
            # Processar projetos
            projects_data = []
            issues_data = []
            
            if data.get('projects', {}).get('projects'):
                for project in data['projects']['projects']:
                    # Dados do projeto
                    project_data = {
                        'id': project['id'],
                        'name': project['name'],
                        'status': project.get('status', ''),
                        'description': '',
                        'createdAt': '',
                        'updatedAt': ''
                    }
                    projects_data.append(project_data)
                    
                    # Issues do projeto (CORRIGIDO: uma linha por disciplina)
                    if project.get('issues', {}).get('issues'):
                        for issue in project['issues']['issues']:
                            # CORREÇÃO: Criar uma linha para cada disciplina da issue
                            if issue.get('disciplines') and len(issue['disciplines']) > 0:
                                # Para cada disciplina da issue, criar uma linha separada
                                for discipline_data in issue['disciplines']:
                                    discipline_name = discipline_data['discipline'].get('name', '')
                                    discipline_status = discipline_data.get('status', '')
                                    
                                    issue_data = {
                                        'id': issue['id'],
                                        'code': issue.get('code', ''),
                                        'title': issue['title'],
                                        'status_x': issue.get('status', ''),  # Status da issue
                                        'projectId': str(project['id']),
                                        'createdAt': issue.get('createdAt', ''),
                                        'updatedAt': issue.get('updatedAt', ''),
                                        'name': discipline_name,  # Nome da disciplina
                                        'status_y': discipline_status  # Status da disciplina
                                    }
                                    issues_data.append(issue_data)
                            else:
                                # Se a issue não tem disciplinas, criar uma linha com valores vazios
                                issue_data = {
                                    'id': issue['id'],
                                    'code': issue.get('code', ''),
                                    'title': issue['title'],
                                    'status_x': issue.get('status', ''),
                                    'projectId': str(project['id']),
                                    'createdAt': issue.get('createdAt', ''),
                                    'updatedAt': issue.get('updatedAt', ''),
                                    'name': '',  # Nome da disciplina vazio
                                    'status_y': ''  # Status da disciplina vazio
                                }
                                issues_data.append(issue_data)
            
            # Converter para DataFrames
            results = {}
            
            if projects_data:
                results['projects'] = pd.DataFrame(projects_data)
                logger.info(f"✅ {len(projects_data)} projetos obtidos via GraphQL consolidado")
            
            if issues_data:
                results['issues'] = pd.DataFrame(issues_data)
                logger.info(f"✅ {len(issues_data)} linhas de issues+disciplinas obtidas via GraphQL consolidado")
            
            logger.info(f"🚀 Query consolidada para todos os projetos concluída")
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter todos os dados: {e}")
            return {}

    def get_data_optimized(self, endpoint: str, **kwargs) -> List[Dict]:
        """
        Versão otimizada do get_data que usa queries consolidadas.
        
        Args:
            endpoint: Tipo de dados ('projects', 'issues', 'disciplines', 'issue_disciplines', 'all')
            **kwargs: Argumentos adicionais
            
        Returns:
            Lista de dicionários com os dados
        """
        try:
            # Se for 'all', usar query consolidada
            if endpoint == 'all':
                logger.info("🚀 Usando query consolidada GraphQL para todos os dados")
                consolidated_data = self.get_all_data_optimized()
                
                # Retornar dados baseado no que foi solicitado
                if 'projects' in consolidated_data:
                    return consolidated_data['projects'].to_dict('records')
                else:
                    return []
            
            # Para endpoints específicos, usar query consolidada e filtrar
            logger.info(f"🚀 Usando query consolidada GraphQL para {endpoint}")
            consolidated_data = self.get_all_data_optimized()
            
            if endpoint in consolidated_data:
                return consolidated_data[endpoint].to_dict('records')
            else:
                logger.warning(f"Endpoint {endpoint} não encontrado nos dados consolidados")
                return []
                
        except Exception as e:
            logger.error(f"❌ Erro no get_data_optimized: {e}")
            # Fallback para método original
            return self.get_data(endpoint, **kwargs) 

    def get_multiple_projects_data_optimized(self, project_ids: List[str], limit_per_project: int = 50) -> Dict[str, pd.DataFrame]:
        """
        Obtém dados de múltiplos projetos de forma otimizada.
        Executa queries paralelas para cada projeto em vez de carregar todas as issues.
        
        Args:
            project_ids: Lista de IDs dos projetos
            limit_per_project: Limite de issues por projeto
            
        Returns:
            Dicionário com DataFrames consolidados
        """
        try:
            logger.info(f"🚀 Executando queries otimizadas para {len(project_ids)} projetos")
            
            from concurrent.futures import ThreadPoolExecutor
            import time
            
            start_time = time.time()
            
            all_projects_data = []
            all_issues_data = []
            all_issue_disciplines_data = []
            
            # Função para buscar dados de um projeto
            def fetch_project_data(project_id: str) -> Dict:
                try:
                    logger.debug(f"🔍 Buscando dados do projeto {project_id}")
                    project_data = self.get_project_data_optimized(project_id)
                    return {
                        'project_id': project_id,
                        'data': project_data
                    }
                except Exception as e:
                    logger.error(f"❌ Erro ao buscar projeto {project_id}: {e}")
                    return {'project_id': project_id, 'data': {}}
            
            # Executar queries em paralelo
            with ThreadPoolExecutor(max_workers=min(5, len(project_ids))) as executor:
                futures = [executor.submit(fetch_project_data, pid) for pid in project_ids]
                
                for future in futures:
                    result = future.result()
                    project_id = result['project_id']
                    data = result['data']
                    
                    # Consolidar dados
                    if 'projects' in data and len(data['projects']) > 0:
                        all_projects_data.extend(data['projects'].to_dict('records'))
                    
                    if 'issues' in data and len(data['issues']) > 0:
                        all_issues_data.extend(data['issues'].to_dict('records'))
                    
                    if 'issue_disciplines' in data and len(data['issue_disciplines']) > 0:
                        all_issue_disciplines_data.extend(data['issue_disciplines'].to_dict('records'))
            
            # Buscar disciplinas uma única vez (são globais)
            disciplines_data = []
            try:
                query = """
                query GetDisciplines {
                    disciplines(first: 100) {
                        disciplines {
                            id
                            name
                            description
                        }
                    }
                }
                """
                result = self._execute_graphql_query(query)
                if result.get('data', {}).get('disciplines', {}).get('disciplines'):
                    for discipline in result['data']['disciplines']['disciplines']:
                        disciplines_data.append({
                            'id': discipline['id'],
                            'name': discipline['name'],
                            'description': discipline.get('description', '')
                        })
            except Exception as e:
                logger.warning(f"Erro ao buscar disciplinas: {e}")
            
            # Converter para DataFrames
            results = {}
            
            if all_projects_data:
                results['projects'] = pd.DataFrame(all_projects_data)
                logger.info(f"✅ {len(all_projects_data)} projetos obtidos via queries paralelas")
            
            if disciplines_data:
                results['disciplines'] = pd.DataFrame(disciplines_data)
                logger.info(f"✅ {len(disciplines_data)} disciplinas obtidas via GraphQL")
            
            if all_issues_data:
                results['issues'] = pd.DataFrame(all_issues_data)
                logger.info(f"🎯 {len(all_issues_data)} issues de {len(project_ids)} projetos obtidas via queries paralelas")
            
            if all_issue_disciplines_data:
                results['issue_disciplines'] = pd.DataFrame(all_issue_disciplines_data)
                logger.info(f"✅ {len(all_issue_disciplines_data)} relacionamentos issue-discipline obtidos")
            
            total_time = time.time() - start_time
            logger.info(f"🚀 Queries paralelas concluídas em {total_time:.2f}s: {len(project_ids)} projetos processados")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Erro nas queries paralelas: {e}")
            return {} 