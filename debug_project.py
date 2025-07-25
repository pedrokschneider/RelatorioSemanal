#!/usr/bin/env python3
"""
Script para debugar problemas com projetos baseados no canal do Discord.
"""

import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Adicionar diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_system"))

# Carregar variáveis de ambiente
load_dotenv()

def debug_project_by_discord_channel(channel_id):
    """Debuga um projeto baseado no ID do canal do Discord."""
    
    print(f"🔍 Investigando projeto para canal Discord: {channel_id}")
    
    try:
        from report_system.main import WeeklyReportSystem
        
        # Inicializar sistema
        system = WeeklyReportSystem(verbose_init=False)
        
        # Buscar projeto pelo canal Discord
        project_id = system.get_project_by_discord_channel(channel_id)
        
        if not project_id:
            print(f"❌ Projeto não encontrado para o canal Discord {channel_id}")
            return
        
        print(f"✅ Projeto encontrado: {project_id}")
        
        # Obter informações do projeto
        projects_df = system._load_project_config()
        project_row = projects_df[projects_df['construflow_id'] == project_id]
        
        if not project_row.empty:
            project_name = project_row['Projeto - PR'].iloc[0] if 'Projeto - PR' in project_row.columns else "Nome não encontrado"
            print(f"📋 Nome do projeto: {project_name}")
            
            # Verificar disciplinas do cliente
            if 'construflow_disciplinasclientes' in project_row.columns:
                disciplinas_str = project_row['construflow_disciplinasclientes'].iloc[0]
                if pd.notna(disciplinas_str):
                    disciplinas = [d.strip() for d in str(disciplinas_str).split(',')]
                    print(f"🎯 Disciplinas do cliente configuradas: {disciplinas}")
                else:
                    print("⚠️ Disciplinas do cliente não configuradas na planilha")
            else:
                print("⚠️ Coluna 'construflow_disciplinasclientes' não encontrada na planilha")
        
        # Obter todas as issues do projeto
        print(f"\n📊 Buscando issues do projeto {project_id}...")
        
        # Usar o conector GraphQL para obter issues
        construflow = system.processor.construflow
        
        if hasattr(construflow, 'get_project_issues'):
            issues_df = construflow.get_project_issues(project_id)
        else:
            # Fallback para método genérico
            issues_df = system.processor.construflow.get_project_issues(project_id)
        
        if issues_df.empty:
            print("❌ Nenhuma issue encontrada para o projeto")
            return
        
        print(f"📈 Total de issues encontradas: {len(issues_df)}")
        
        # Mostrar colunas disponíveis
        print(f"📋 Colunas disponíveis: {list(issues_df.columns)}")
        
        # Mostrar todas as issues da disciplina Contratante
        print(f"\n🔍 Todas as issues da disciplina 'Contratante':")
        contratante_issues = issues_df[issues_df['name'] == 'Contratante']
        print(f"📊 Total de issues 'Contratante': {len(contratante_issues)}")
        
        for i, (_, issue) in enumerate(contratante_issues.iterrows()):
            status_issue = issue.get('status_x', 'N/A')
            status_disciplina = issue.get('status_y', 'N/A')
            print(f"  {i+1}. {issue.get('title', 'Sem título')} (Code: {issue.get('code', 'N/A')})")
            print(f"     Status Issue: {status_issue}, Status Disciplina: {status_disciplina}")
        
        # Filtrar issues ativas
        if 'status' in issues_df.columns and 'status_y' in issues_df.columns:
            # Formato GraphQL
            active_issues = issues_df[
                (issues_df['status'] == 'active') &
                (issues_df['status_y'].isin(['todo', 'follow']))
            ]
            print(f"✅ Issues ativas com disciplina 'todo' ou 'follow': {len(active_issues)}")
        elif 'status' in issues_df.columns:
            # Apenas status da issue
            active_issues = issues_df[issues_df['status'] == 'active']
            print(f"✅ Issues ativas (sem filtro de disciplina): {len(active_issues)}")
        else:
            # Formato REST
            active_issues = issues_df[
                (issues_df['status_x'] == 'active') &
                (issues_df['status_y'].isin(['todo', 'follow']))
            ] if 'status_x' in issues_df.columns and 'status_y' in issues_df.columns else issues_df
            print(f"✅ Issues ativas (formato REST): {len(active_issues)}")
        
        # Mostrar issues ativas da disciplina Contratante
        print(f"\n🔍 Issues ativas da disciplina 'Contratante':")
        contratante_ativas = active_issues[active_issues['name'] == 'Contratante']
        print(f"📊 Issues 'Contratante' ativas: {len(contratante_ativas)}")
        
        for i, (_, issue) in enumerate(contratante_ativas.iterrows()):
            status_issue = issue.get('status_x', 'N/A')
            status_disciplina = issue.get('status_y', 'N/A')
            print(f"  {i+1}. {issue.get('title', 'Sem título')} (Code: {issue.get('code', 'N/A')})")
            print(f"     Status Issue: {status_issue}, Status Disciplina: {status_disciplina}")
        
        # Mostrar disciplinas encontradas
        if 'name' in active_issues.columns:
            discipline_counts = active_issues['name'].value_counts()
            print(f"\n📊 Disciplinas encontradas nas issues ativas:")
            for discipline, count in discipline_counts.items():
                print(f"  - {discipline}: {count} issues")
        
        # Filtrar issues do cliente
        print(f"\n🎯 Filtrando issues do cliente...")
        client_issues = system.filter_client_issues(active_issues, project_id)
        print(f"📊 Issues do cliente encontradas: {len(client_issues)}")
        
        if not client_issues.empty and 'name' in client_issues.columns:
            client_discipline_counts = client_issues['name'].value_counts()
            print(f"📋 Issues do cliente por disciplina:")
            for discipline, count in client_discipline_counts.items():
                print(f"  - {discipline}: {count} issues")
        
        # Mostrar algumas issues do cliente como exemplo
        if not client_issues.empty:
            print(f"\n📝 Exemplos de issues do cliente:")
            for i, (_, issue) in enumerate(client_issues.head(3).iterrows()):
                print(f"  {i+1}. {issue.get('title', 'Sem título')} (Code: {issue.get('code', 'N/A')})")
        
        # Verificar se há issues que deveriam estar sendo filtradas
        if 'name' in active_issues.columns:
            disciplinas_cliente = system.get_client_disciplines(project_id)
            print(f"\n🔍 Verificando disciplinas do cliente: {disciplinas_cliente}")
            
            # Mostrar todas as disciplinas nas issues ativas
            todas_disciplinas = active_issues['name'].unique()
            print(f"📋 Todas as disciplinas nas issues ativas: {list(todas_disciplinas)}")
            
            # Verificar se há issues de disciplinas do cliente que não estão sendo filtradas
            issues_perdidas = active_issues[active_issues['name'].isin(disciplinas_cliente)]
            print(f"🎯 Issues de disciplinas do cliente (deveriam ser {len(disciplinas_cliente)} disciplinas): {len(issues_perdidas)}")
            
            if len(issues_perdidas) != len(client_issues):
                print(f"⚠️ DISCREPÂNCIA: {len(issues_perdidas)} issues deveriam ser do cliente, mas apenas {len(client_issues)} estão sendo filtradas")
                
                # Mostrar diferença
                perdidas_codes = set(issues_perdidas['code'].astype(str))
                filtradas_codes = set(client_issues['code'].astype(str))
                nao_filtradas = perdidas_codes - filtradas_codes
                
                if nao_filtradas:
                    print(f"❌ Issues não filtradas: {list(nao_filtradas)}")
        
        # Verificar se há issues com status diferente que deveriam ser incluídas
        print(f"\n🔍 Verificando todas as issues da disciplina 'Contratante' (independente do status):")
        todas_contratante = issues_df[issues_df['name'] == 'Contratante']
        print(f"📊 Total de issues 'Contratante' (todas): {len(todas_contratante)}")
        
        # Mostrar status das issues
        if 'status_x' in todas_contratante.columns and 'status_y' in todas_contratante.columns:
            status_counts = todas_contratante.groupby(['status_x', 'status_y']).size()
            print(f"📋 Contagem por status:")
            for (status_issue, status_disciplina), count in status_counts.items():
                print(f"  - Issue: {status_issue}, Disciplina: {status_disciplina} -> {count} issues")
        
        # Verificar se há issues que não estão sendo consideradas "ativas"
        print(f"\n🔍 Issues 'Contratante' que não estão sendo consideradas ativas:")
        nao_ativas = todas_contratante[
            ~((todas_contratante['status_x'] == 'active') & (todas_contratante['status_y'] == 'todo'))
        ]
        print(f"📊 Issues 'Contratante' não ativas: {len(nao_ativas)}")
        
        for i, (_, issue) in enumerate(nao_ativas.iterrows()):
            status_issue = issue.get('status_x', 'N/A')
            status_disciplina = issue.get('status_y', 'N/A')
            print(f"  {i+1}. {issue.get('title', 'Sem título')} (Code: {issue.get('code', 'N/A')})")
            print(f"     Status Issue: {status_issue}, Status Disciplina: {status_disciplina}")
        
    except Exception as e:
        print(f"❌ Erro ao debugar projeto: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Função principal."""
    if len(sys.argv) != 2:
        print("Uso: python debug_project.py <canal_discord_id>")
        print("Exemplo: python debug_project.py 1290649572372123678")
        return
    
    channel_id = sys.argv[1]
    debug_project_by_discord_channel(channel_id)

if __name__ == "__main__":
    main() 