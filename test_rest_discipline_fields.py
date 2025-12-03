"""
Script de teste para verificar se a API REST do Construflow retorna
campos de data limite para as disciplinas.
"""

import os
import sys
import json

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.connectors.construflow import ConstruflowConnector

def test_rest_discipline_fields():
    """Testa quais campos a API REST retorna para issue-disciplines."""
    
    config = ConfigManager()
    connector = ConstruflowConnector(config)
    
    print("🔍 Testando API REST para campos de data limite em issue-disciplines...\n")
    
    try:
        # Buscar dados de issue-disciplines via REST
        issue_disciplines = connector.get_data("issues-disciplines", force_refresh=True)
        
        if issue_disciplines:
            print(f"✅ {len(issue_disciplines)} relacionamentos issue-discipline encontrados")
            
            # Analisar o primeiro registro para ver os campos
            if len(issue_disciplines) > 0:
                first_record = issue_disciplines[0]
                print(f"\n📋 Campos disponíveis em issue-disciplines (REST):")
                print(f"  {sorted(first_record.keys())}")
                
                print(f"\n📌 Exemplo do primeiro registro:")
                for key, value in first_record.items():
                    print(f"  {key}: {value}")
                
                # Verificar se há campos relacionados a data
                date_fields = [k for k in first_record.keys() if any(word in k.lower() for word in ['date', 'data', 'due', 'deadline', 'limit', 'prazo', 'expected', 'target', 'completion'])]
                
                if date_fields:
                    print(f"\n✅ Campos relacionados a data encontrados:")
                    for field in date_fields:
                        print(f"  - {field}: {first_record.get(field)}")
                else:
                    print(f"\n⚠️ Nenhum campo relacionado a data encontrado nos campos disponíveis")
            else:
                print("⚠️ Nenhum registro encontrado")
        else:
            print("⚠️ Nenhum dado retornado da API REST")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rest_discipline_fields()


