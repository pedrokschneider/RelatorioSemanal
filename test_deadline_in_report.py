"""
Script para verificar se o deadline está sendo incluído nos dados do relatório.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.processors.data_processor import DataProcessor

def test_deadline_in_report():
    """Testa se o deadline está sendo incluído nos dados do relatório."""
    
    config = ConfigManager()
    processor = DataProcessor(config)
    
    project_id = "1700"  # Planeta_ABV
    print(f"🔍 Testando deadline nos dados do relatório para projeto {project_id}...\n")
    
    try:
        # Processar dados do projeto
        data = processor.process_project_data(project_id)
        
        # Verificar client_issues
        construflow_data = data.get('construflow_data', {})
        client_issues = construflow_data.get('client_issues', [])
        
        print(f"✅ {len(client_issues)} issues do cliente encontradas")
        
        # Verificar se deadline está presente
        deadline_count = 0
        issues_with_deadline = []
        
        for issue in client_issues:
            deadline = issue.get('deadline')
            if deadline is not None:
                deadline_str = str(deadline).strip()
                if deadline_str and deadline_str.lower() not in ['nan', 'none', '', 'nat']:
                    deadline_count += 1
                    issues_with_deadline.append({
                        'code': issue.get('code', 'N/A'),
                        'title': issue.get('title', 'N/A')[:60],
                        'deadline': deadline,
                        'status': issue.get('status_y', 'N/A')
                    })
        
        print(f"\n📊 Deadline encontrado em {deadline_count} issues do cliente")
        
        if issues_with_deadline:
            print(f"\n📌 Issues com deadline:")
            for issue in issues_with_deadline[:5]:
                print(f"  - {issue['code']}: {issue['title']}...")
                print(f"    Status: {issue['status']}")
                print(f"    Deadline: {issue['deadline']}")
                print()
        else:
            print(f"\n⚠️ Nenhuma issue com deadline encontrada")
            print(f"   Verificando campos disponíveis na primeira issue...")
            if client_issues:
                first_issue = client_issues[0]
                print(f"   Campos: {list(first_issue.keys())}")
                if 'deadline' in first_issue:
                    print(f"   Deadline value: {first_issue['deadline']} (type: {type(first_issue['deadline'])})")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_deadline_in_report()

