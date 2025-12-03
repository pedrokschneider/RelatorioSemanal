"""
Script de teste para verificar se a API GraphQL do Construflow retorna
campos de data limite (deadline) para as disciplinas.
"""

import os
import sys
import json

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_system.config import ConfigManager
from report_system.connectors.construflow_graphql import ConstruflowGraphQLConnector

def test_discipline_fields():
    """Testa quais campos estão disponíveis para disciplinas na API GraphQL."""
    
    config = ConfigManager()
    connector = ConstruflowGraphQLConnector(config)
    
    # Primeiro, vamos tentar usar introspection do GraphQL para ver o schema
    introspection_query = '''
    query IntrospectionQuery {
        __type(name: "IssueDiscipline") {
            name
            fields {
                name
                type {
                    name
                    kind
                }
            }
        }
    }
    '''
    
    print("🔍 Tentando obter schema do tipo IssueDiscipline via introspection...\n")
    
    try:
        introspection_result = connector._execute_graphql_query(introspection_query, {})
        
        if introspection_result.get('data', {}).get('__type'):
            type_info = introspection_result['data']['__type']
            print(f"✅ Tipo encontrado: {type_info['name']}")
            print(f"\n📋 Campos disponíveis em IssueDiscipline:")
            
            if type_info.get('fields'):
                for field in type_info['fields']:
                    field_type = field['type']
                    type_name = field_type.get('name', field_type.get('kind', 'Unknown'))
                    print(f"  - {field['name']}: {type_name}")
            else:
                print("  ⚠️ Nenhum campo encontrado")
        else:
            print("⚠️ Introspection não retornou dados. Tentando query direta...")
    except Exception as e:
        print(f"⚠️ Erro na introspection: {e}")
        print("Tentando query direta...")
    
    # Query de teste com todos os campos possíveis da issue
    query = '''
    query getIssues($projectId: Int!, $first: Int) {
        project(projectId: $projectId) {
            issues(first: $first, filter: { standard: "pendencies" }) {
                issues {
                    id
                    code
                    title
                    status
                    priority
                    createdAt
                    updatedAt
                    dueDate
                    deadline
                    expectedDate
                    targetDate
                    completionDate
                    disciplines {
                        discipline {
                            id
                            name
                        }
                        status
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
    '''
    
    # Obter um projeto ID de teste
    # Vamos tentar obter projetos ativos primeiro
    try:
        projects_df = connector.get_projects()
        if not projects_df.empty:
            project_id = str(projects_df.iloc[0]['id'])
            print(f"📋 Usando projeto de teste: {project_id}")
        else:
            print("⚠️ Nenhum projeto encontrado, usando ID padrão")
            project_id = "1"
    except Exception as e:
        print(f"⚠️ Erro ao obter projetos: {e}")
        project_id = "1"
    
    variables = {
        "projectId": int(project_id),
        "first": 5  # Apenas 5 issues para teste
    }
    
    try:
        result = connector._execute_graphql_query(query, variables)
        
        # Verificar erros
        if result.get('errors'):
            print("❌ Erros na query:")
            for error in result['errors']:
                print(f"  - {error.get('message', 'Erro desconhecido')}")
                # Se houver detalhes sobre campos não disponíveis, mostrar
                if 'extensions' in error:
                    print(f"    Extensions: {json.dumps(error['extensions'], indent=2)}")
                # Se houver locations, mostrar
                if 'locations' in error:
                    print(f"    Locations: {error['locations']}")
        
        # Verificar dados retornados
        if result.get('data'):
            issues = result['data'].get('project', {}).get('issues', {}).get('issues', [])
            
            if issues:
                print(f"\n✅ {len(issues)} issues encontradas")
                print("\n📋 Campos disponíveis nas disciplinas:")
                
                # Analisar todas as issues com disciplinas
                found_fields = set()
                for issue in issues:
                    if issue.get('disciplines'):
                        for discipline_data in issue['disciplines']:
                            found_fields.update(discipline_data.keys())
                
                print(f"\n  Campos encontrados: {sorted(found_fields)}")
                
                # Mostrar exemplo detalhado da primeira disciplina
                for issue in issues:
                    if issue.get('disciplines'):
                        discipline_data = issue['disciplines'][0]
                        print(f"\n  📌 Exemplo - Disciplina da Issue #{issue.get('code', 'N/A')}:")
                        print(f"    Título: {issue.get('title', 'N/A')}")
                        
                        for key, value in discipline_data.items():
                            if value is not None:
                                print(f"      {key}: {value}")
                            else:
                                print(f"      {key}: null (campo existe mas está vazio)")
                        
                        break
            else:
                print("⚠️ Nenhuma issue encontrada para teste")
        else:
            print("⚠️ Nenhum dado retornado")
            
    except Exception as e:
        print(f"❌ Erro ao executar teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔍 Testando campos de data limite para disciplinas no Construflow...\n")
    test_discipline_fields()

