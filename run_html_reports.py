"""
Script para gerar relatórios HTML para múltiplos projetos.
Integra com Discord e Google Drive.
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
from report_system.storage import GoogleDriveManager

# Lista de projetos para processar
PROJECTS = [
    "1002",
    "1372",
    "1360",
    "1175",
    "1700",
    "2576",
    "2575",
    "2785",
    "3035",
    "3515",
    "3335",
    "3409",
    "3535",
    "5076",
    "3630",
    "4499",
    "2400",
]

def main():
    """Gera relatórios HTML para todos os projetos listados."""
    
    print(f"🚀 Iniciando geração de relatórios HTML para {len(PROJECTS)} projetos")
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
    
    # Inicializar Google Drive Manager
    try:
        gdrive = GoogleDriveManager(config)
        print("✅ GoogleDriveManager inicializado")
    except Exception as e:
        print(f"⚠️ GoogleDriveManager não disponível: {e}")
        gdrive = None
    
    # Inicializar Discord
    try:
        from report_system.discord_notification import DiscordNotificationManager
        discord = DiscordNotificationManager(config)
        print("✅ Discord inicializado")
    except Exception as e:
        print(f"⚠️ Discord não disponível: {e}")
        discord = None
    
    # Inicializar gerador HTML
    html_generator = HTMLReportGenerator(config)
    print("✅ HTMLReportGenerator inicializado")
    
    # Carregar configuração de projetos
    projects_df = None
    if gdrive:
        try:
            projects_df = gdrive.load_project_config_from_sheet()
            print(f"✅ Planilha de configuração carregada: {len(projects_df)} projetos")
        except Exception as e:
            print(f"⚠️ Erro ao carregar planilha: {e}")
    
    print("\n" + "=" * 60)
    
    # Processar cada projeto
    results = []
    for i, project_id in enumerate(PROJECTS, 1):
        print(f"\n📊 [{i}/{len(PROJECTS)}] Processando projeto {project_id}...")
        
        try:
            # Obter nome do projeto e smartsheet_id
            project_name = f"Projeto_{project_id}"
            client_name = None
            smartsheet_id = None
            discord_channel_id = None
            folder_id = None
            email_url_capa = None  # Link da imagem do projeto
            email_url_gant = None
            email_url_disciplina = None
            
            if projects_df is not None and not projects_df.empty:
                projects_df['construflow_id'] = projects_df['construflow_id'].astype(str)
                project_row = projects_df[projects_df['construflow_id'] == str(project_id)]
                
                if not project_row.empty:
                    if 'smartsheet_id' in project_row.columns:
                        smartsheet_id = str(project_row['smartsheet_id'].values[0])
                        if smartsheet_id == 'nan':
                            smartsheet_id = None
                    
                    if 'discord_id' in project_row.columns:
                        discord_channel_id = str(project_row['discord_id'].values[0])
                        if discord_channel_id == 'nan':
                            discord_channel_id = None
                    
                    if 'Projeto - PR' in project_row.columns:
                        project_name = project_row['Projeto - PR'].values[0]
                    
                    # Obter nome do cliente da planilha
                    if 'nome_cliente' in project_row.columns:
                        client_name = str(project_row['nome_cliente'].values[0])
                        if client_name == 'nan' or client_name == '':
                            client_name = None
                    
                    if 'pastaemails_id' in project_row.columns:
                        folder_id = str(project_row['pastaemails_id'].values[0])
                        if folder_id == 'nan' or folder_id == '':
                            folder_id = None
                    
                    # Obter link da imagem do projeto (email_url_capa)
                    if 'email_url_capa' in project_row.columns:
                        email_url_capa = str(project_row['email_url_capa'].values[0])
                        if email_url_capa == 'nan' or email_url_capa == '':
                            email_url_capa = None
                    
                    # Obter links dos botões
                    if 'email_url_gant' in project_row.columns:
                        email_url_gant = str(project_row['email_url_gant'].values[0])
                        if email_url_gant == 'nan' or email_url_gant == '':
                            email_url_gant = None
                    
                    if 'email_url_disciplina' in project_row.columns:
                        email_url_disciplina = str(project_row['email_url_disciplina'].values[0])
                        if email_url_disciplina == 'nan' or email_url_disciplina == '':
                            email_url_disciplina = None
            
            print(f"   Nome: {project_name}")
            print(f"   SmartSheet ID: {smartsheet_id}")
            print(f"   Discord Channel: {discord_channel_id}")
            print(f"   Pasta Drive: {folder_id}")
            if email_url_capa:
                print(f"   Imagem do Projeto: {email_url_capa[:50]}...")
            if email_url_gant:
                print(f"   Cronograma: {email_url_gant[:50]}...")
            if email_url_disciplina:
                print(f"   Relatório Disciplinas: {email_url_disciplina[:50]}...")
            
            # Processar dados do projeto
            project_data = processor.process_project_data(project_id, smartsheet_id)
            
            if not project_data or not project_data.get('project_name'):
                print(f"   ⚠️ Dados não encontrados para projeto {project_id}")
                results.append({
                    'project_id': project_id,
                    'project_name': project_name,
                    'success': False,
                    'error': 'Dados não encontrados'
                })
                continue
            
            # Atualizar nome do projeto
            project_name = project_data.get('project_name', project_name)
            
            # Adicionar nome do cliente aos dados do projeto
            if client_name:
                project_data['client_name'] = client_name
            
            # Buscar e processar imagem do projeto se email_url_capa estiver disponível
            project_image_base64 = None
            if gdrive and email_url_capa:
                try:
                    print(f"   🖼️ Processando imagem do projeto...")
                    # Extrair ID do arquivo do Google Drive da URL
                    file_id = None
                    if '/file/d/' in email_url_capa:
                        file_id = email_url_capa.split('/file/d/')[1].split('/')[0]
                    elif '/open?id=' in email_url_capa:
                        file_id = email_url_capa.split('/open?id=')[1].split('&')[0]
                    elif len(email_url_capa) == 33 and email_url_capa.isalnum():  # ID direto
                        file_id = email_url_capa
                    
                    if file_id:
                        project_image_base64 = gdrive.download_file_as_base64(file_id)
                    if project_image_base64:
                        print(f"   ✅ Imagem processada com sucesso")
                    else:
                        print(f"   ⚠️ Não foi possível processar a imagem")
                except Exception as e:
                    print(f"   ⚠️ Erro ao processar imagem: {e}")
            
            # Gerar e salvar relatórios HTML
            paths = html_generator.save_reports(
                data=project_data,
                project_name=project_name,
                project_id=project_id,
                project_image_base64=project_image_base64,
                email_url_gant=email_url_gant,
                email_url_disciplina=email_url_disciplina
            )
            
            print(f"   ✅ Relatórios HTML gerados:")
            
            client_url = None
            team_url = None
            
            # Upload para o Drive
            if gdrive and folder_id:
                try:
                    # Upload relatório do cliente
                    if 'client' in paths:
                        client_file_name = os.path.basename(paths['client'])
                        client_file_id = gdrive.upload_file(
                            file_path=paths['client'],
                            name=client_file_name,
                            parent_id=folder_id
                        )
                        if client_file_id:
                            client_url = f"https://drive.google.com/file/d/{client_file_id}/view"
                            print(f"      📤 Cliente: {client_url}")
                    
                    # Upload relatório da equipe
                    if 'team' in paths:
                        team_file_name = os.path.basename(paths['team'])
                        team_file_id = gdrive.upload_file(
                            file_path=paths['team'],
                            name=team_file_name,
                            parent_id=folder_id
                        )
                        if team_file_id:
                            team_url = f"https://drive.google.com/file/d/{team_file_id}/view"
                            print(f"      📤 Equipe: {team_url}")
                except Exception as e:
                    print(f"      ⚠️ Erro no upload: {e}")
            else:
                print(f"      📄 Cliente: {paths.get('client', 'N/A')}")
                print(f"      📄 Equipe: {paths.get('team', 'N/A')}")
            
            # Enviar notificação no Discord
            if discord and discord_channel_id:
                try:
                    message = f"📋 **Relatório Semanal - {project_name}**\n\n"
                    message += "✅ Relatórios HTML gerados com sucesso!\n\n"
                    
                    if client_url:
                        message += f"📄 [Relatório do Cliente]({client_url})\n"
                    if team_url:
                        message += f"📄 [Relatório da Equipe]({team_url})\n"
                    
                    # Adicionar link da pasta do Drive
                    if folder_id:
                        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
                        message += f"\n📁 [Abrir Pasta do Projeto]({folder_url})\n"
                    
                    discord.send_notification(discord_channel_id, message)
                    print(f"   📨 Notificação enviada para Discord")
                except Exception as e:
                    print(f"   ⚠️ Erro ao enviar notificação: {e}")
            
            results.append({
                'project_id': project_id,
                'project_name': project_name,
                'success': True,
                'client_path': paths.get('client'),
                'team_path': paths.get('team'),
                'client_url': client_url,
                'team_url': team_url
            })
            
            # Pequena pausa para não sobrecarregar as APIs
            time.sleep(2)
            
        except Exception as e:
            print(f"   ❌ Erro ao processar projeto {project_id}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'project_id': project_id,
                'project_name': project_name,
                'success': False,
                'error': str(e)
            })
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO FINAL")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(results) - success_count
    
    print(f"\n✅ Sucesso: {success_count}")
    print(f"❌ Falha: {fail_count}")
    
    if fail_count > 0:
        print("\nProjetos com falha:")
        for r in results:
            if not r['success']:
                print(f"   - {r['project_id']} ({r['project_name']}): {r.get('error', 'Erro desconhecido')}")
    
    print("\n🎉 Processo concluído!")

if __name__ == "__main__":
    main()

