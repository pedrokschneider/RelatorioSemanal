#!/usr/bin/env python3
"""
Script para verificar se as variáveis de ambiente do arquivo .env estão sendo carregadas corretamente.
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Carregar o arquivo .env
load_dotenv()

def check_env_var(var_name):
    """Verifica se uma variável de ambiente está definida e mostra seu valor."""
    value = os.getenv(var_name)
    if value:
        print(f"✅ {var_name}: {value}")
    else:
        print(f"❌ {var_name}: não definida")
    return value

def main():
    """Função principal."""
    print("\n=== Verificando variáveis de ambiente ===\n")
    
    # Verificar variáveis relacionadas à planilha
    sheet_id = check_env_var("sheet_id")
    sheet_name = check_env_var("sheet_name")
    sheet_api_key = check_env_var("sheet_api_key")
    projects_sheet_id = check_env_var("PROJECTS_SHEET_ID")
    projects_sheet_name = check_env_var("PROJECTS_SHEET_NAME")
    
    print("\n=== Verificação concluída ===\n")
    
    # Carregar classe de configuração do sistema para verificar como ela processa as variáveis
    print("\n=== Verificando ConfigManager ===\n")
    
    try:
        from report_system.config import ConfigManager
        
        config = ConfigManager()
        
        print(f"ConfigManager.projects_sheet_id: {config.projects_sheet_id}")
        print(f"ConfigManager.projects_sheet_name: {config.projects_sheet_name}")
        
        print("\n=== ConfigManager verificado ===\n")
        
    except Exception as e:
        print(f"Erro ao inicializar ConfigManager: {e}")
    
    # Sugestões baseadas na verificação
    print("\n=== Sugestões ===\n")
    
    if sheet_id and projects_sheet_id and sheet_id != projects_sheet_id:
        print(f"⚠️ As variáveis sheet_id e PROJECTS_SHEET_ID têm valores diferentes.")
        print(f"   Isso pode causar problemas. Considere usar o mesmo valor.")
    
    if sheet_name and projects_sheet_name and sheet_name != projects_sheet_name:
        print(f"⚠️ As variáveis sheet_name e PROJECTS_SHEET_NAME têm valores diferentes.")
        print(f"   Isso pode causar problemas. Considere usar o mesmo valor.")
    
    print("\nO ID correto da planilha deve ser: 1Qgm6U3EsNdTYFJAQ00M4U0YELrajsmXpjDf7g3yqyq8")
    print("Nome correto da aba deve ser: Port - Links")
    
    if (sheet_id and sheet_id != "1Qgm6U3EsNdTYFJAQ00M4U0YELrajsmXpjDf7g3yqyq8") or \
       (projects_sheet_id and projects_sheet_id != "1Qgm6U3EsNdTYFJAQ00M4U0YELrajsmXpjDf7g3yqyq8"):
        print("\n⚠️ O ID da planilha não corresponde ao valor esperado!")
        
    if (sheet_name and sheet_name != "Port - Links") or \
       (projects_sheet_name and projects_sheet_name != "Port - Links"):
        print("\n⚠️ O nome da aba não corresponde ao valor esperado!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 