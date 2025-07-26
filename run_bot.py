#!/usr/bin/env python3
"""
Script para executar o bot Discord.
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def show_menu():
    """Mostra o menu de opções."""
    print("🤖 BOT DISCORD")
    print("=" * 50)
    print()
    print("1. Executar Bot Discord")
    print("   • Monitora canais configurados na planilha")
    print("   • Usa polling para verificar mensagens")
    print("   • Interface de menu interativo")
    print()
    print("2. Verificar Configuração")
    print("   • Testa se tudo está configurado corretamente")
    print()
    print("0. Sair")
    print()

def check_configuration():
    """Verifica se a configuração está correta."""
    print("🔧 VERIFICANDO CONFIGURAÇÃO")
    print("=" * 50)
    
    # Verificar arquivo .env
    env_file = ".env"
    if os.path.exists(env_file):
        print("✅ Arquivo .env encontrado")
    else:
        print("❌ Arquivo .env não encontrado")
        return False
    
    # Verificar token do Discord
    discord_token = os.getenv('DISCORD_TOKEN')
    if discord_token:
        print("✅ Token do Discord configurado")
    else:
        print("❌ Token do Discord não configurado")
        return False
    
    # Verificar canal admin
    admin_channel = os.getenv('DISCORD_ADMIN_CHANNEL_ID')
    if admin_channel:
        print("✅ Canal admin configurado")
    else:
        print("⚠️  Canal admin não configurado (opcional)")
    
    # Verificar dependências
    try:
        import discord
        print("✅ Discord.py instalado")
    except ImportError:
        print("❌ Discord.py não instalado")
        print("   Execute: pip install discord.py")
        return False
    
    try:
        import pandas
        print("✅ Pandas instalado")
    except ImportError:
        print("❌ Pandas não instalado")
        print("   Execute: pip install pandas")
        return False
    
    # Verificar arquivos do sistema
    required_files = [
        "discord_bot.py",
        "report_system/main.py",
        "report_queue.py"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} encontrado")
        else:
            print(f"❌ {file_path} não encontrado")
            return False
    
    print("\n✅ Configuração verificada com sucesso!")
    return True

def run_bot():
    """Executa o bot Discord."""
    print("🚀 Iniciando Bot Discord...")
    print("   Pressione Ctrl+C para parar")
    print()
    
    try:
        subprocess.run([sys.executable, "discord_bot.py"], check=True)
    except KeyboardInterrupt:
        print("\n⏹️  Bot interrompido pelo usuário")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao executar bot: {e}")

def main():
    """Função principal."""
    while True:
        show_menu()
        
        try:
            choice = input("Escolha uma opção: ").strip()
            
            if choice == "0":
                print("👋 Encerrando...")
                break
                
            elif choice == "1":
                if check_configuration():
                    run_bot()
                else:
                    print("\n❌ Configuração incompleta. Verifique os erros acima.")
                    input("Pressione Enter para continuar...")
                
            elif choice == "2":
                check_configuration()
                input("\nPressione Enter para continuar...")
                
            else:
                print("❌ Opção inválida")
                input("Pressione Enter para continuar...")
                
        except KeyboardInterrupt:
            print("\n👋 Encerrando...")
            break
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            input("Pressione Enter para continuar...")

if __name__ == "__main__":
    main() 