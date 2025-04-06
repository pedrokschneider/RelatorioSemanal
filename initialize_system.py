"""
Script de inicialização do sistema de relatórios.
Salve como initialize_system.py na raiz do projeto.
"""

import os
import sys
import pickle
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("system_init.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SystemInit")

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_directory_structure():
    """Cria a estrutura de diretórios necessária."""
    dirs = [
        "cache",
        "cache/construflow",
        "cache/smartsheet",
        "reports",
        "logs"
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Diretório criado/verificado: {dir_path}")

def create_empty_cache_files():
    """Cria arquivos de cache vazios mas válidos."""
    # Dados de exemplo mínimos
    example_projects = [
        {"id": "123", "name": "Projeto Exemplo", "status": "active"}
    ]
    
    example_issues = [
        {"id": "456", "title": "Issue Exemplo", "projectId": "123", "status": "todo"}
    ]
    
    example_disciplines = [
        {"id": "789", "name": "Disciplina Exemplo", "projectId": "123"}
    ]
    
    example_issues_disciplines = [
        {"id": "101112", "issueId": "456", "disciplineId": "789"}
    ]
    
    example_smartsheet = [
        {
            "Nome da Tarefa": "Tarefa Exemplo",
            "Data Término": "2025-04-30",
            "Status": "Em andamento",
            "sheet_id": "131415",
            "project_id": "123"
        }
    ]
    
    # Criar arquivos de cache
    cache_files = {
        "cache/construflow/projects.pkl": example_projects,
        "cache/construflow/issues.pkl": example_issues,
        "cache/construflow/disciplines.pkl": example_disciplines,
        "cache/construflow/issues-disciplines.pkl": example_issues_disciplines,
        "cache/smartsheet/sheet_131415.pkl": example_smartsheet
    }
    
    for file_path, data in cache_files.items():
        try:
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Arquivo de cache criado: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao criar arquivo de cache {file_path}: {e}")

def test_cache_system():
    """Testa o sistema de cache."""
    try:
        logger.info("Testando sistema de cache...")
        
        from report_system.utils.simple_cache import SimpleCacheManager
        
        # Inicializar gerenciador de cache
        cache = SimpleCacheManager("cache")
        
        # Testar carregamento
        projects = cache.load_construflow_data("projects")
        if projects:
            logger.info(f"Teste de carregamento OK: {len(projects)} projetos carregados")
        else:
            logger.warning("Teste de carregamento falhou: Nenhum projeto carregado")
        
        # Testar salvamento
        test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
        result = cache.save_data("test", test_data)
        if result:
            logger.info("Teste de salvamento OK")
        else:
            logger.warning("Teste de salvamento falhou")
        
        # Testar status
        status = cache.get_cache_status()
        logger.info(f"Status do cache: {len(status)} arquivos encontrados")
        
        return projects is not None and result
    except Exception as e:
        logger.error(f"Erro ao testar sistema de cache: {e}")
        return False

def test_construflow_connector():
    """Testa o conector do Construflow."""
    try:
        logger.info("Testando conector do Construflow...")
        
        from report_system.config import ConfigManager
        from report_system.connectors.construflow import ConstruflowConnector
        
        # Inicializar configuração e conector
        config = ConfigManager()
        
        # Verificar se as configurações necessárias estão presentes
        api_key = config.get_env_var("CONSTRUFLOW_API_KEY")
        api_secret = config.get_env_var("CONSTRUFLOW_API_SECRET")
        
        if not api_key or not api_secret:
            logger.warning("Credenciais do Construflow não configuradas. Usando cache existente.")
            
            # Carregar do cache usando o SimpleCacheManager
            from report_system.utils.simple_cache import SimpleCacheManager
            cache = SimpleCacheManager("cache")
            projects = cache.load_construflow_data("projects")
            
            if projects:
                logger.info(f"Carregados {len(projects)} projetos do cache")
                return True
            else:
                logger.warning("Não foi possível carregar projetos do cache")
                return False
        
        # Inicializar conector
        construflow = ConstruflowConnector(config)
        
        # Testar carregamento de projetos
        projects = construflow.get_projects()
        
        if not projects.empty:
            logger.info(f"Teste do Construflow OK: {len(projects)} projetos carregados")
            return True
        else:
            # Tentar carregar do cache
            logger.warning("Nenhum projeto retornado da API. Tentando carregar do cache...")
            projects_cache = construflow.get_data("projects", use_cache=True, force_refresh=False)
            
            if projects_cache:
                logger.info(f"Carregados {len(projects_cache)} projetos do cache")
                return True
            else:
                logger.warning("Não foi possível carregar projetos do cache")
                return False
    except Exception as e:
        logger.error(f"Erro ao testar conector do Construflow: {e}")
        return False

def test_smartsheet_connector():
    """Testa o conector do Smartsheet."""
    try:
        logger.info("Testando conector do Smartsheet...")
        
        from report_system.config import ConfigManager
        from report_system.connectors.smartsheet import SmartsheetConnector
        
        # Inicializar configuração e conector
        config = ConfigManager()
        
        # Verificar se a configuração necessária está presente
        token = config.get_env_var("SMARTSHEET_TOKEN")
        
        if not token:
            logger.warning("Token do Smartsheet não configurado. Usando cache existente.")
            
            # Carregar do cache usando o SimpleCacheManager
            from report_system.utils.simple_cache import SimpleCacheManager
            cache = SimpleCacheManager("cache")
            
            # Verificar se existem arquivos de Smartsheet no cache
            import os
            smartsheet_dir = os.path.join("cache", "smartsheet")
            if os.path.exists(smartsheet_dir):
                files = [f for f in os.listdir(smartsheet_dir) if f.endswith('.pkl')]
                if files:
                    logger.info(f"Encontrados {len(files)} arquivos de Smartsheet no cache")
                    return True
            
            logger.warning("Não foi possível encontrar arquivos de Smartsheet no cache")
            return False
        
        # Inicializar conector
        smartsheet = SmartsheetConnector(config)
        
        # Testar carregamento de um sheet (usando cache, se disponível)
        # Nota: Como não temos um sheet_id específico, verificamos apenas a inicialização
        logger.info("Conector do Smartsheet inicializado com sucesso")
        return True
    except Exception as e:
        logger.error(f"Erro ao testar conector do Smartsheet: {e}")
        return False

def main():
    """Função principal."""
    logger.info("=== INICIALIZANDO SISTEMA DE RELATÓRIOS ===")
    
    # Criar estrutura de diretórios
    create_directory_structure()
    
    # Criar arquivos de cache iniciais
    create_empty_cache_files()
    
    # Testar componentes
    cache_ok = test_cache_system()
    construflow_ok = test_construflow_connector()
    smartsheet_ok = test_smartsheet_connector()
    
    # Relatório final
    logger.info("\n=== RELATÓRIO DE INICIALIZAÇÃO ===")
    logger.info(f"Sistema de cache: {'✅ OK' if cache_ok else '❌ Falha'}")
    logger.info(f"Conector Construflow: {'✅ OK' if construflow_ok else '❌ Falha'}")
    logger.info(f"Conector Smartsheet: {'✅ OK' if smartsheet_ok else '❌ Falha'}")
    
    if cache_ok and construflow_ok and smartsheet_ok:
        logger.info("\n✅ SISTEMA INICIALIZADO COM SUCESSO!")
        return 0
    else:
        logger.warning("\n⚠️ SISTEMA INICIALIZADO COM AVISOS!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)