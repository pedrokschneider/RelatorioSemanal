"""
Script para gerar relatório do Ceranium e verificar tarefas em atraso.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from report_system.config import ConfigManager
from report_system.storage.google_drive import GoogleDriveManager
from report_system.main import WeeklyReportSystem

def main():
    config = ConfigManager()
    gdrive = GoogleDriveManager(config)
    
    # Buscar projeto Ceranium
    print("🔍 Buscando projeto Ceranium...")
    projects_df = gdrive.load_project_config_from_sheet()
    
    if projects_df.empty:
        print("❌ Nenhum projeto encontrado na planilha")
        return
    
    # Buscar por "Ceranium" no nome do projeto
    if 'Projeto - PR' in projects_df.columns:
        ceranium_row = projects_df[projects_df['Projeto - PR'].str.contains('Ceranium', case=False, na=False)]
        
        if ceranium_row.empty:
            print("❌ Projeto Ceranium não encontrado")
            print(f"Projetos disponíveis: {projects_df['Projeto - PR'].tolist()[:10]}...")
            return
        
        project_id = str(ceranium_row['construflow_id'].iloc[0])
        project_name = ceranium_row['Projeto - PR'].iloc[0]
        smartsheet_id = ceranium_row['smartsheet_id'].iloc[0] if 'smartsheet_id' in ceranium_row.columns else None
        
        print(f"✅ Projeto encontrado: {project_name} (ID: {project_id})")
        if smartsheet_id:
            print(f"   Smartsheet ID: {smartsheet_id}")
        
        # Gerar relatório
        print(f"\n🚀 Gerando relatório para {project_name}...")
        system = WeeklyReportSystem()
        
        # Processar dados primeiro para verificar tarefas em atraso
        from report_system.processors.data_processor import DataProcessor
        from report_system.generators.html_report_generator import HTMLReportGenerator
        
        processor = DataProcessor(config, HTMLReportGenerator(config))
        project_data = processor.process_project_data(project_id, smartsheet_id)
        
        # Verificar tarefas em atraso
        delayed_tasks = project_data.get('smartsheet_data', {}).get('delayed_tasks', [])
        print(f"\n📊 Tarefas em atraso encontradas: {len(delayed_tasks)}")
        
        if delayed_tasks:
            print("\n📋 Detalhes das tarefas em atraso:")
            for i, task in enumerate(delayed_tasks[:10], 1):  # Mostrar até 10
                task_name = task.get('Task Name', task.get('Nome da Tarefa', 'N/A'))
                status = task.get('Status', 'N/A')
                categoria = task.get('Categoria de atraso', task.get('Delay Category', ''))
                end_date = task.get('Data Término', task.get('Data de Término', task.get('End Date', 'N/A')))
                disciplina = task.get('Disciplina', task.get('Discipline', 'N/A'))
                
                print(f"\n  {i}. {task_name}")
                print(f"     Status: {status}")
                print(f"     Disciplina: {disciplina}")
                print(f"     Data Término: {end_date}")
                if categoria:
                    print(f"     Categoria de atraso: {categoria}")
            
            if len(delayed_tasks) > 10:
                print(f"\n  ... e mais {len(delayed_tasks) - 10} tarefas")
        else:
            print("⚠️ Nenhuma tarefa em atraso encontrada!")
        
        # Gerar relatório completo
        print(f"\n📄 Gerando relatórios HTML...")
        result = system.run_for_project(
            project_id, 
            quiet_mode=False, 
            skip_notifications=True, 
            hide_dashboard=False,
            schedule_days=15
        )
        
        if result[0]:
            print(f"\n✅ Relatório gerado com sucesso!")
            print(f"   Arquivo local: {result[1]}")
            if result[2]:
                print(f"   Link: https://drive.google.com/file/d/{result[2]}/view")
        else:
            print(f"\n❌ Falha ao gerar relatório: {result[1] if len(result) > 1 else 'Erro desconhecido'}")
    else:
        print("❌ Coluna 'Projeto - PR' não encontrada na planilha")

if __name__ == "__main__":
    main()


