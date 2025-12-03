"""
Script para testar se o deadline está sendo incluído para o projeto Planeta.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.connectors.construflow_graphql import ConstruflowGraphQLConnector

def test_planeta_deadline():
    """Testa se o deadline está sendo incluído para o projeto Planeta."""
    
    config = ConfigManager()
    connector = ConstruflowGraphQLConnector(config)
    
    project_id = "1700"  # Planeta_ABV
    print(f"🔍 Testando deadline para projeto {project_id} (Planeta_ABV)...\n")
    
    try:
        # Buscar issues do projeto
        issues_df = connector.get_project_issues(project_id, limit=10)
        
        if issues_df.empty:
            print("⚠️ Nenhuma issue encontrada")
            return
        
        print(f"✅ {len(issues_df)} issues encontradas")
        print(f"\n📋 Campos disponíveis:")
        print(f"  {list(issues_df.columns)}")
        
        # Verificar se deadline está presente
        if 'deadline' in issues_df.columns:
            print(f"\n✅ Campo 'deadline' encontrado!")
            
            deadline_count = issues_df['deadline'].notna().sum()
            print(f"  - Issues com deadline: {deadline_count} de {len(issues_df)}")
            
            if deadline_count > 0:
                print(f"\n📌 Exemplos de issues com deadline:")
                for idx, row in issues_df[issues_df['deadline'].notna()].head(5).iterrows():
                    print(f"\n  Issue #{row.get('code', 'N/A')}:")
                    print(f"    Título: {row.get('title', 'N/A')[:60]}...")
                    print(f"    Disciplina: {row.get('name', 'N/A')}")
                    print(f"    Deadline: {row.get('deadline', 'N/A')}")
                    print(f"    DisciplineId: {row.get('disciplineId', 'N/A')}")
            else:
                print(f"\n⚠️ Campo 'deadline' existe mas está vazio para todas as issues")
                print(f"   Isso pode significar que:")
                print(f"   1. As issues não têm deadline configurado no Construflow")
                print(f"   2. O merge não está funcionando corretamente")
                
                # Verificar se disciplineId está presente
                if 'disciplineId' in issues_df.columns:
                    print(f"\n   Verificando disciplineId:")
                    discipline_id_count = issues_df['disciplineId'].notna().sum()
                    print(f"   - Issues com disciplineId: {discipline_id_count} de {len(issues_df)}")
                    
                    if discipline_id_count > 0:
                        print(f"\n   Exemplo de disciplineId:")
                        example = issues_df[issues_df['disciplineId'].notna()].iloc[0]
                        print(f"     Issue: {example.get('code', 'N/A')}")
                        print(f"     DisciplineId: {example.get('disciplineId', 'N/A')}")
                        print(f"     Disciplina: {example.get('name', 'N/A')}")
        else:
            print(f"\n❌ Campo 'deadline' NÃO encontrado")
            print(f"   Campos disponíveis: {list(issues_df.columns)}")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_planeta_deadline()

