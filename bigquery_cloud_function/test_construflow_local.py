# test_construflow_local.py
"""Teste local da conexão com Construflow"""
import os
import sys
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_construflow_connection():
    """Testa conexão básica com Construflow"""
    
    try:
        logger.info("�� Iniciando teste de conexão...")
        
        # Adicionar path do projeto
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_path = os.path.join(current_dir, 'report_system')
        sys.path.append(project_path)
        
        logger.info(f"�� Path do projeto: {project_path}")
        
        # Importar dependências
        from connectors.construflow_graphql import ConstruflowGraphQLConnector
        from config import ConfigManager
        
        logger.info("✅ Módulos importados com sucesso")
        
        # Inicializar configuração
        config = ConfigManager()
        logger.info("✅ Configuração carregada")
        
        # Inicializar conector
        connector = ConstruflowGraphQLConnector(config)
        logger.info("✅ Conector inicializado")
        
        # Teste 1: Verificar se consegue obter token
        logger.info("🔑 Testando autenticação...")
        token = connector._get_auth_token()
        if token:
            logger.info("✅ Autenticação OK - Token obtido")
        else:
            logger.warning("⚠️ Token não obtido")
        
        # Teste 2: Buscar projetos básicos
        logger.info("📊 Testando busca de projetos...")
        projects = connector.get_projects(force_refresh=True)
        
        if not projects.empty:
            logger.info(f"✅ Projetos encontrados: {len(projects)}")
            logger.info("📋 Lista de projetos:")
            for _, project in projects.head(3).iterrows():
                logger.info(f"   - ID: {project['id']}, Nome: {project['name']}")
        else:
            logger.warning("⚠️ Nenhum projeto encontrado")
        
        # Teste 3: Buscar issues de um projeto específico
        if not projects.empty:
            test_project_id = str(projects.iloc[0]['id'])
            logger.info(f"🎯 Testando busca de issues do projeto {test_project_id}...")
            
            issues = connector.get_project_issues(test_project_id, limit=5)
            
            if not issues.empty:
                logger.info(f"✅ Issues encontradas: {len(issues)}")
                logger.info("📋 Amostra de issues:")
                for _, issue in issues.head(2).iterrows():
                    logger.info(f"   - {issue['code']}: {issue['title'][:50]}...")
            else:
                logger.warning("⚠️ Nenhuma issue encontrada")
        
        logger.info("🎉 Teste de conexão concluído com sucesso!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Erro de importação: {e}")
        logger.error("Verifique se o path está correto e se todos os módulos estão disponíveis")
        return False
        
    except Exception as e:
        logger.error(f"❌ Erro geral: {e}")
        import traceback
        logger.error(f"Traceback completo:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("�� Iniciando teste de conexão com Construflow...")
    print("=" * 50)
    
    success = test_construflow_connection()
    
    print("=" * 50)
    if success:
        print("✅ Teste concluído com sucesso!")
    else:
        print("❌ Teste falhou. Verifique os logs acima.")
