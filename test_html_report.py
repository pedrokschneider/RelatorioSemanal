"""
Script de teste para gerar relatórios HTML no estilo Otus.
"""

import os
import sys
import time

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from report_system.config import ConfigManager
from report_system.processors.data_processor import DataProcessor
from report_system.generators.html_report_generator import HTMLReportGenerator

def main():
    """Gera relatórios HTML para um projeto específico."""
    
    # Iniciar cronômetro
    start_time = time.time()
    
    # Projeto Planeta_ABV
    # Buscar ID do projeto na planilha
    project_id = None
    project_name_to_find = "Planeta_ABV"
    
    try:
        from report_system.storage import GoogleDriveManager
        gdrive_temp = GoogleDriveManager(config)
        projects_df_temp = gdrive_temp.load_project_config_from_sheet()
        
        if not projects_df_temp.empty and 'Projeto - PR' in projects_df_temp.columns:
            project_row_temp = projects_df_temp[projects_df_temp['Projeto - PR'].str.contains(project_name_to_find, case=False, na=False)]
            if not project_row_temp.empty and 'construflow_id' in project_row_temp.columns:
                project_id = str(project_row_temp['construflow_id'].values[0])
                print(f"✅ ID do projeto encontrado: {project_id}")
    except Exception as e:
        print(f"⚠️ Erro ao buscar ID do projeto: {e}")
    
    if not project_id:
        # Fallback: tentar ID conhecido (você pode ajustar se necessário)
        project_id = "1700"  # ID padrão caso não encontre na planilha
        print(f"⚠️ Usando ID padrão: {project_id}")
    
    print(f"🚀 Iniciando geração de relatórios HTML para projeto {project_id} ({project_name_to_find})")
    print("=" * 60)
    
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
    
    # Obter ID do Smartsheet, nome do cliente e imagem do projeto (se disponível)
    smartsheet_id = None
    client_name = None
    email_url_capa = None
    email_url_gant = None
    email_url_disciplina = None
    gdrive = None
    try:
        from report_system.storage import GoogleDriveManager
        gdrive = GoogleDriveManager(config)
        projects_df = gdrive.load_project_config_from_sheet()
        
        if not projects_df.empty:
            projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
            project_row = projects_df[projects_df['construflow_id'] == project_id]
            
            # Debug: mostrar colunas disponíveis
            if not project_row.empty:
                print(f"📋 Colunas disponíveis na planilha: {', '.join(project_row.columns.tolist())}")
            
            if not project_row.empty:
                if 'smartsheet_id' in project_row.columns:
                    smartsheet_id = str(project_row['smartsheet_id'].values[0])
                    if smartsheet_id == 'nan':
                        smartsheet_id = None
                    else:
                        print(f"✅ Smartsheet ID encontrado: {smartsheet_id}")
                
                # Obter nome do cliente da planilha
                if 'nome_cliente' in project_row.columns:
                    client_name = str(project_row['nome_cliente'].values[0])
                    if client_name == 'nan' or client_name == '':
                        client_name = None
                    else:
                        print(f"✅ Nome do cliente encontrado: {client_name}")
                
                # Obter link da imagem do projeto (email_url_capa)
                if 'email_url_capa' in project_row.columns:
                    email_url_capa = str(project_row['email_url_capa'].values[0])
                    if email_url_capa == 'nan' or email_url_capa == '':
                        email_url_capa = None
                        print(f"⚠️ Campo email_url_capa está vazio na planilha")
                    else:
                        print(f"✅ Link da imagem encontrado: {email_url_capa[:50]}...")
                else:
                    print(f"⚠️ Coluna 'email_url_capa' não encontrada na planilha")
                
                # Obter links dos botões
                if 'email_url_gant' in project_row.columns:
                    email_url_gant = str(project_row['email_url_gant'].values[0])
                    if email_url_gant == 'nan' or email_url_gant == '':
                        email_url_gant = None
                    else:
                        print(f"✅ Link do cronograma encontrado: {email_url_gant[:50]}...")
                
                if 'email_url_disciplina' in project_row.columns:
                    email_url_disciplina = str(project_row['email_url_disciplina'].values[0])
                    if email_url_disciplina == 'nan' or email_url_disciplina == '':
                        email_url_disciplina = None
                    else:
                        print(f"✅ Link do relatório de disciplinas encontrado: {email_url_disciplina[:50]}...")
    except Exception as e:
        print(f"⚠️ Não foi possível obter dados da planilha: {e}")
    
    # Processar dados do projeto
    print(f"📊 Processando dados do projeto {project_id}...")
    try:
        project_data = processor.process_project_data(project_id, smartsheet_id)
        
        if not project_data:
            print("❌ Não foi possível obter dados do projeto")
            return
        
        print(f"✅ Dados do projeto obtidos: {project_data.get('project_name', 'Nome não encontrado')}")
        
        # Adicionar nome do cliente aos dados do projeto
        if client_name:
            project_data['client_name'] = client_name
        
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
    
    # Buscar e processar imagem do projeto se email_url_capa estiver disponível
    project_image_base64 = None
    if not gdrive:
        print(f"⚠️ GoogleDriveManager não foi inicializado")
    elif not email_url_capa:
        print(f"⚠️ email_url_capa não está disponível para este projeto")
    else:
        try:
            print(f"🖼️ Processando imagem do projeto...")
            print(f"   📎 URL: {email_url_capa[:80]}...")
            # Extrair ID do arquivo do Google Drive da URL usando o método do GoogleDriveManager
            file_id = gdrive.extract_file_id_from_url(email_url_capa)
            
            if file_id:
                print(f"   🔑 File ID extraído: {file_id}")
                project_image_base64 = gdrive.download_file_as_base64(file_id)
                if project_image_base64:
                    print(f"✅ Imagem processada com sucesso")
                else:
                    print(f"⚠️ Não foi possível processar a imagem (download retornou None)")
            else:
                print(f"⚠️ Não foi possível extrair o File ID da URL")
        except Exception as e:
            print(f"⚠️ Erro ao processar imagem: {e}")
            import traceback
            traceback.print_exc()
    
    # Gerar e salvar relatórios
    print(f"📝 Gerando relatórios HTML...")
    try:
        paths = html_generator.save_reports(
            data=project_data,
            project_name=project_data.get('project_name', 'Tarraf_Infinity'),
            project_id=project_id,
            project_image_base64=project_image_base64,
            email_url_gant=email_url_gant,
            email_url_disciplina=email_url_disciplina
        )
        
        print(f"\n✅ Relatórios gerados com sucesso!")
        
        if 'client' in paths:
            print(f"   📄 Cliente: {paths['client']}")
        
        if 'team' in paths:
            print(f"   📄 Equipe: {paths['team']}")
        
        print(f"\n💡 Abra os arquivos HTML em um navegador para visualizar.")
        
        # Calcular tempo total
        elapsed_time = time.time() - start_time
        print(f"\n⏱️ Tempo total de execução: {elapsed_time:.2f} segundos ({elapsed_time/60:.2f} minutos)")
        
    except Exception as e:
        print(f"❌ Erro ao gerar relatórios: {e}")
        import traceback
        traceback.print_exc()
        
        # Calcular tempo mesmo em caso de erro
        elapsed_time = time.time() - start_time
        print(f"\n⏱️ Tempo até o erro: {elapsed_time:.2f} segundos")

if __name__ == "__main__":
    main()

