"""
Script de teste para gerar relatórios HTML no estilo Otus.
"""

import os
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from report_system.config import ConfigManager
from report_system.processors.data_processor import DataProcessor
from report_system.generators.html_report_generator import HTMLReportGenerator

def main():
    """Gera relatórios HTML para um projeto específico."""
    
    # Projeto Planeta ABV
    project_id = "1700"
    print(f"🚀 Iniciando geração de relatórios HTML para projeto {project_id}")
    
    # Inicializar configuração
    config = ConfigManager()
    
    # Inicializar conector GraphQL
    try:
        from report_system.connectors.construflow_graphql import ConstruflowGraphQLConnector
        construflow = ConstruflowGraphQLConnector(config)
        print("✅ Conector GraphQL do Construflow inicializado")
    except Exception as e:
        print(f"❌ Erro ao inicializar conector GraphQL: {e}")
        return
    
    # Inicializar processador de dados
    processor = DataProcessor(config, construflow)
    print("✅ DataProcessor inicializado")
    
    # Obter ID do Smartsheet (se disponível)
    smartsheet_id = None
    try:
        from report_system.storage import GoogleDriveManager
        gdrive = GoogleDriveManager(config)
        projects_df = gdrive.load_project_config_from_sheet()
        
        if not projects_df.empty:
            projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
            project_row = projects_df[projects_df['construflow_id'] == project_id]
            
            if not project_row.empty and 'smartsheet_id' in project_row.columns:
                smartsheet_id = str(project_row['smartsheet_id'].values[0])
                print(f"✅ Smartsheet ID encontrado: {smartsheet_id}")
    except Exception as e:
        print(f"⚠️ Não foi possível obter Smartsheet ID: {e}")
    
    # Processar dados do projeto
    print(f"📊 Processando dados do projeto {project_id}...")
    try:
        project_data = processor.process_project_data(project_id, smartsheet_id)
        
        if not project_data:
            print("❌ Não foi possível obter dados do projeto")
            return
        
        print(f"✅ Dados do projeto obtidos: {project_data.get('project_name', 'Nome não encontrado')}")
        
        # Mostrar resumo dos dados
        construflow_data = project_data.get('construflow_data', {})
        smartsheet_data = project_data.get('smartsheet_data', {})
        
        if construflow_data:
            active_issues = construflow_data.get('active_issues', [])
            client_issues = construflow_data.get('client_issues', [])
            print(f"   - Issues ativas: {len(active_issues)}")
            print(f"   - Issues do cliente: {len(client_issues)}")
        
        if smartsheet_data:
            all_tasks = smartsheet_data.get('all_tasks', [])
            delayed_tasks = smartsheet_data.get('delayed_tasks', [])
            print(f"   - Tarefas totais: {len(all_tasks)}")
            print(f"   - Tarefas atrasadas: {len(delayed_tasks)}")
        
    except Exception as e:
        print(f"❌ Erro ao processar dados: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Inicializar gerador HTML
    html_generator = HTMLReportGenerator(config)
    print("✅ HTMLReportGenerator inicializado")
    
    # Gerar e salvar relatórios
    print(f"📝 Gerando relatórios HTML...")
    try:
        paths = html_generator.save_reports(
            data=project_data,
            project_name=project_data.get('project_name', 'Tarraf_Infinity'),
            project_id=project_id
        )
        
        print(f"\n✅ Relatórios gerados com sucesso!")
        
        if 'client' in paths:
            print(f"   📄 Cliente: {paths['client']}")
        
        if 'team' in paths:
            print(f"   📄 Equipe: {paths['team']}")
        
        print(f"\n💡 Abra os arquivos HTML em um navegador para visualizar.")
        
    except Exception as e:
        print(f"❌ Erro ao gerar relatórios: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

