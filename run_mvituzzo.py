"""Script para executar relatório do projeto MVituzzo_Tênis Club"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.storage.google_drive import GoogleDriveManager
from report_system.main import WeeklyReportSystem

# Buscar projeto
config = ConfigManager()
gdrive = GoogleDriveManager(config)
df = gdrive.load_project_config_from_sheet()

if not df.empty:
    # Procurar por MVituzzo_Tênis Club
    df_filtered = df[df['Projeto - PR'].str.contains('MVituzzo.*Tênis|MVituzzo.*Tenis', case=False, na=False)]
    
    if not df_filtered.empty:
        project_row = df_filtered.iloc[0]
        project_id = str(project_row['construflow_id'])
        project_name = project_row['Projeto - PR']
        disciplinas = project_row.get('construflow_disciplinasclientes', 'N/A')
        
        print(f"✅ Projeto encontrado:")
        print(f"   Nome: {project_name}")
        print(f"   ID: {project_id}")
        print(f"   Disciplinas configuradas: {disciplinas}")
        print(f"\n🚀 Executando relatório com filtro corrigido...")
        
        # Executar relatório
        system = WeeklyReportSystem()
        result = system.run_for_project(project_id, quiet_mode=True, skip_notifications=False, hide_dashboard=False)
        
        if result[0]:
            print(f"\n✅ Relatório gerado com sucesso!")
            if result[2]:
                print(f"   Link: {result[2]}")
        else:
            print(f"\n❌ Erro ao gerar relatório: {result[3] if len(result) > 3 else 'Erro desconhecido'}")
    else:
        print("❌ Projeto não encontrado na planilha")
else:
    print("❌ Planilha vazia ou não acessível")













