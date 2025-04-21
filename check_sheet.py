import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# Carregar as variáveis de ambiente
load_dotenv()

# Configurar as credenciais do Google
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
PROJECTS_SHEET_ID = os.getenv("PROJECTS_SHEET_ID")
PROJECTS_SHEET_NAME = os.getenv("PROJECTS_SHEET_NAME")

print(f"Conectando à planilha {PROJECTS_SHEET_ID}, aba {PROJECTS_SHEET_NAME}")

# Autenticação do Google
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
    client = gspread.authorize(creds)
    
    # Acessar a planilha
    sheet = client.open_by_key(PROJECTS_SHEET_ID).worksheet(PROJECTS_SHEET_NAME)
    
    # Obter todas as abas da planilha
    spreadsheet = client.open_by_key(PROJECTS_SHEET_ID)
    print("Abas disponíveis na planilha:")
    for worksheet in spreadsheet.worksheets():
        print(f"- {worksheet.title}")
    
    # Obter os dados
    data = sheet.get_all_values()
    
    # Converter para DataFrame
    if data:
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        # Mostrar informações da planilha
        print(f"\nInformações da planilha:")
        print(f"Número de colunas: {len(headers)}")
        print(f"Número de linhas: {len(rows)}")
        print(f"\nCabeçalho da planilha:")
        for i, col in enumerate(headers):
            print(f"{i+1}. {col}")
        
        # Mostrar as primeiras linhas
        print("\nPrimeiras 3 linhas de dados:")
        for i in range(min(3, len(rows))):
            print(f"Linha {i+1}:")
            for j, col in enumerate(headers):
                if j < len(rows[i]):
                    print(f"  {col}: {rows[i][j] if rows[i][j] else 'VAZIO'}")
                else:
                    print(f"  {col}: DADOS AUSENTES")
    else:
        print("A planilha não possui dados.")
        
except Exception as e:
    print(f"Erro ao acessar a planilha: {e}") 