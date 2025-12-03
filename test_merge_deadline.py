"""
Script para testar se o campo deadline está sendo incluído no merge
entre issues_disciplines e disciplines.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.connectors.construflow import ConstruflowConnector

def test_merge_with_deadline():
    """Testa se o deadline está sendo incluído no merge."""
    
    config = ConfigManager()
    connector = ConstruflowConnector(config)
    
    print("🔍 Testando merge de issues_disciplines com disciplines incluindo deadline...\n")
    
    try:
        # Obter um projeto de teste
        projects = connector.get_projects()
        if projects.empty:
            print("⚠️ Nenhum projeto encontrado")
            return
        
        project_id = str(projects.iloc[0]['id'])
        print(f"📋 Testando com projeto: {project_id}\n")
        
        # Obter dados separados
        df_issues = connector.get_issues()
        df_disciplines = connector.get_disciplines()
        df_issue_disciplines = connector.get_issue_disciplines()
        
        print(f"✅ Dados obtidos:")
        print(f"  - Issues: {len(df_issues)}")
        print(f"  - Disciplines: {len(df_disciplines)}")
        print(f"  - Issue-Disciplines: {len(df_issue_disciplines)}")
        
        # Verificar se deadline está em issue_disciplines
        if 'deadline' in df_issue_disciplines.columns:
            print(f"\n✅ Campo 'deadline' encontrado em issue_disciplines")
            deadline_count = df_issue_disciplines['deadline'].notna().sum()
            print(f"  - Registros com deadline: {deadline_count} de {len(df_issue_disciplines)}")
        else:
            print(f"\n❌ Campo 'deadline' NÃO encontrado em issue_disciplines")
            print(f"  Campos disponíveis: {list(df_issue_disciplines.columns)}")
            return
        
        # Filtrar por projeto
        df_filtered = df_issues[df_issues['projectId'] == project_id]
        
        if df_filtered.empty:
            print(f"⚠️ Nenhuma issue encontrada para projeto {project_id}")
            return
        
        # Fazer o merge como no código atual
        df_issue_disciplines['disciplineId'] = df_issue_disciplines['disciplineId'].astype(str)
        df_disciplines['id'] = df_disciplines['id'].astype(str)
        
        df_merged_disciplines = df_issue_disciplines.merge(
            df_disciplines,
            left_on='disciplineId',
            right_on='id',
            how='left'
        )
        
        # Verificar se deadline está no merge
        if 'deadline' in df_merged_disciplines.columns:
            print(f"\n✅ Campo 'deadline' preservado após merge com disciplines")
            deadline_count_after = df_merged_disciplines['deadline'].notna().sum()
            print(f"  - Registros com deadline após merge: {deadline_count_after}")
        else:
            print(f"\n❌ Campo 'deadline' perdido após merge com disciplines")
        
        # Fazer merge final com issues
        df_filtered = df_filtered.copy()
        df_filtered['id'] = df_filtered['id'].astype(str)
        df_merged_disciplines['issueId'] = df_merged_disciplines['issueId'].astype(str)
        
        df_result = df_filtered.merge(
            df_merged_disciplines,
            left_on='id',
            right_on='issueId',
            how='left'
        )
        
        # Verificar se deadline está no resultado final
        if 'deadline' in df_result.columns:
            print(f"\n✅ Campo 'deadline' presente no resultado final")
            deadline_count_final = df_result['deadline'].notna().sum()
            print(f"  - Registros com deadline no resultado: {deadline_count_final}")
            
            # Mostrar exemplo
            if deadline_count_final > 0:
                example = df_result[df_result['deadline'].notna()].iloc[0]
                print(f"\n📌 Exemplo:")
                print(f"  Issue: {example.get('code', 'N/A')} - {example.get('title', 'N/A')[:50]}")
                print(f"  Disciplina: {example.get('name', 'N/A')}")
                print(f"  Deadline: {example.get('deadline', 'N/A')}")
        else:
            print(f"\n❌ Campo 'deadline' perdido no resultado final")
            print(f"  Campos no resultado: {list(df_result.columns)}")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_merge_with_deadline()


