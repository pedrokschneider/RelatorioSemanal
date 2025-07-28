#!/usr/bin/env python3
"""
Script para corrigir a sincronização do cache com a planilha de configuração.
"""

import os
import sys
import logging
import shutil
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_cache_sync():
    """Corrige a sincronização do cache com a planilha."""
    
    try:
        logger.info("=== Correção de Sincronização do Cache ===")
        
        # Importar o sistema
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))
        
        from report_system.main import WeeklyReportSystem
        
        # Inicializar o sistema
        logger.info("Inicializando sistema...")
        system = WeeklyReportSystem()
        
        # Carregar configuração da planilha
        logger.info("Carregando configuração da planilha...")
        projects_df = system._load_project_config()
        
        if projects_df is None or projects_df.empty:
            logger.error("❌ Não foi possível carregar a planilha de configuração")
            return False
        
        # Obter projetos da planilha
        planilha_projetos = projects_df['construflow_id'].dropna().astype(str).tolist()
        logger.info(f"Projetos na planilha: {len(planilha_projetos)}")
        
        # Verificar cache atual
        cache_dir = "cache/construflow"
        if os.path.exists(f"{cache_dir}/projects.pkl"):
            logger.info("Cache de projetos encontrado")
        else:
            logger.warning("Cache de projetos não encontrado")
        
        # Opção 1: Limpar cache completamente
        logger.info("Opção 1: Limpar cache completamente")
        if os.path.exists(cache_dir):
            backup_dir = f"cache/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(cache_dir, backup_dir)
            logger.info(f"Cache movido para backup: {backup_dir}")
        
        # Criar novo diretório de cache
        os.makedirs(cache_dir, exist_ok=True)
        logger.info("Novo diretório de cache criado")
        
        # Opção 2: Forçar atualização completa
        logger.info("Opção 2: Forçar atualização completa do cache")
        
        try:
            # Atualizar cache para todos os projetos
            logger.info("Atualizando cache para todos os projetos...")
            system.update_cache_for_all_projects()
            logger.info("✅ Cache atualizado com sucesso")
            
            # Verificar se o projeto CFL_NSC (2400) está agora no cache
            logger.info("Verificando se o projeto 2400 está no cache...")
            
            # Tentar carregar o projeto específico
            project_data = system.processor.process_project_data("2400", None)
            
            if project_data and project_data.get('project_name'):
                logger.info(f"✅ Projeto 2400 encontrado: {project_data['project_name']}")
                return True
            else:
                logger.error("❌ Projeto 2400 ainda não encontrado após atualização")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao atualizar cache: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Erro geral: {e}")
        return False

def test_project_2400():
    """Testa especificamente o projeto 2400."""
    
    try:
        logger.info("=== Teste Específico do Projeto 2400 ===")
        
        # Importar o sistema
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))
        
        from report_system.main import WeeklyReportSystem
        
        # Inicializar o sistema
        system = WeeklyReportSystem()
        
        # Testar processamento do projeto 2400
        logger.info("Testando processamento do projeto 2400...")
        
        try:
            project_data = system.processor.process_project_data("2400", None)
            
            if project_data and project_data.get('project_name'):
                logger.info(f"✅ Projeto 2400 processado com sucesso: {project_data['project_name']}")
                logger.info(f"   - Issues: {len(project_data.get('issues', []))}")
                logger.info(f"   - Disciplinas: {len(project_data.get('disciplines', []))}")
                return True
            else:
                logger.error("❌ Projeto 2400 não retornou dados válidos")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar projeto 2400: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
        return False

def main():
    """Função principal."""
    logger.info("=== Correção de Cache para CFL_NSC ===")
    
    # Passo 1: Corrigir sincronização
    step1_passed = fix_cache_sync()
    
    # Passo 2: Testar projeto 2400
    step2_passed = test_project_2400()
    
    # Resultado final
    logger.info("\n=== Resultados ===")
    logger.info(f"Correção de cache: {'✅ PASSOU' if step1_passed else '❌ FALHOU'}")
    logger.info(f"Teste projeto 2400: {'✅ PASSOU' if step2_passed else '❌ FALHOU'}")
    
    if step1_passed and step2_passed:
        logger.info("🎉 Correção concluída! O projeto CFL_NSC deve funcionar agora.")
        return 0
    else:
        logger.error("❌ Alguns passos falharam. Verifique os logs acima.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 