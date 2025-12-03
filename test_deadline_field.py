"""
Script para verificar se o campo deadline está disponível na API REST
do Construflow no endpoint issues-disciplines.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.connectors.construflow import ConstruflowConnector

def test_deadline_field():
    """Testa se o campo deadline está disponível na API REST."""
    
    config = ConfigManager()
    connector = ConstruflowConnector(config)
    
    print("🔍 Verificando se o campo 'deadline' está disponível na API REST...\n")
    
    try:
        # Buscar dados de issue-disciplines via REST
        issue_disciplines = connector.get_data("issues-disciplines", force_refresh=True)
        
        if issue_disciplines and len(issue_disciplines) > 0:
            print(f"✅ {len(issue_disciplines)} registros encontrados")
            
            # Verificar campos disponíveis
            first_record = issue_disciplines[0]
            all_fields = set(first_record.keys())
            
            print(f"\n📋 Todos os campos disponíveis:")
            for field in sorted(all_fields):
                print(f"  - {field}")
            
            # Verificar especificamente o campo deadline
            if 'deadline' in all_fields:
                print(f"\n✅ Campo 'deadline' encontrado!")
                
                # Mostrar alguns exemplos
                print(f"\n📌 Exemplos de valores de deadline:")
                deadline_count = 0
                for record in issue_disciplines[:10]:
                    deadline = record.get('deadline')
                    if deadline:
                        deadline_count += 1
                        issue_id = record.get('issueId', 'N/A')
                        discipline_id = record.get('disciplineId', 'N/A')
                        status = record.get('status', 'N/A')
                        print(f"  Issue {issue_id} / Disciplina {discipline_id}:")
                        print(f"    Status: {status}")
                        print(f"    Deadline: {deadline}")
                        print()
                
                if deadline_count == 0:
                    print("  ⚠️ Campo existe mas está vazio nos primeiros registros")
            else:
                print(f"\n❌ Campo 'deadline' NÃO encontrado")
                print(f"   Campos disponíveis: {sorted(all_fields)}")
                
        else:
            print("⚠️ Nenhum dado retornado da API REST")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_deadline_field()


