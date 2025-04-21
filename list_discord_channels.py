import os
import requests
import json
from dotenv import load_dotenv
import logging
import sys
import pandas as pd
from datetime import datetime
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

class DiscordChannelLister:
    def __init__(self):
        self.token = os.getenv('DISCORD_TOKEN')
        if not self.token:
            raise ValueError("Token do Discord não encontrado nas variáveis de ambiente")
        
        # Limpar o token de possíveis espaços ou caracteres inválidos
        self.token = self.token.strip()
        
        self.api_endpoint = 'https://discord.com/api/v10'
        
        # Tentar diferentes formatos de token
        self.headers_options = [
            {"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
            {"Authorization": self.token, "Content-Type": "application/json"},
            {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        ]
        
        # Validar o token antes de prosseguir
        if not self.validate_token():
            raise ValueError("Token do Discord inválido ou sem acesso")

    def validate_token(self):
        """Valida o token tentando obter informações do bot."""
        print("\nValidando token do Discord...")
        print(f"Token encontrado: {self.token[:20]}...{self.token[-5:]}")
        
        for headers in self.headers_options:
            try:
                print(f"\nTentando formato: {headers['Authorization'][:20]}...")
                url = f"{self.api_endpoint}/users/@me"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    bot_info = response.json()
                    print(f"\n✅ Token válido!")
                    print(f"Bot conectado como: {bot_info.get('username', 'N/A')}#{bot_info.get('discriminator', 'N/A')}")
                    self.headers = headers
                    return True
                else:
                    print(f"❌ Tentativa falhou (código {response.status_code})")
                    if response.text:
                        try:
                            error_info = response.json()
                            print(f"   Mensagem: {error_info.get('message', 'N/A')}")
                        except:
                            print(f"   Resposta: {response.text[:100]}")
            except Exception as e:
                print(f"❌ Erro ao validar token: {str(e)}")
        
        print("\n❌ Nenhum formato de token funcionou.")
        print("Verifique se:")
        print("1. O token está correto no arquivo .env")
        print("2. O bot está ativo e funcionando")
        print("3. O token não expirou ou foi revogado")
        print("\nToken atual no .env:")
        print(f"DISCORD_TOKEN={self.token}")
        return False

    def get_all_threads(self, channel_id, channel_name):
        """Obtém todos os tópicos de um canal, incluindo arquivados."""
        threads = []
        
        # Primeiro tenta obter tópicos ativos
        try:
            active_url = f"{self.api_endpoint}/channels/{channel_id}/threads/active"
            active_response = requests.get(active_url, headers=self.headers)
            
            if active_response.status_code == 200:
                active_data = active_response.json()
                threads.extend(active_data.get('threads', []))
                
            time.sleep(0.5)  # Pequeno delay entre requisições
            
            # Depois tenta obter tópicos arquivados públicos
            public_url = f"{self.api_endpoint}/channels/{channel_id}/threads/archived/public"
            public_response = requests.get(public_url, headers=self.headers)
            
            if public_response.status_code == 200:
                public_data = public_response.json()
                threads.extend(public_data.get('threads', []))
                
            time.sleep(0.5)  # Pequeno delay entre requisições
            
            # Por fim, tenta obter tópicos arquivados privados
            private_url = f"{self.api_endpoint}/channels/{channel_id}/threads/archived/private"
            private_response = requests.get(private_url, headers=self.headers)
            
            if private_response.status_code == 200:
                private_data = private_response.json()
                threads.extend(private_data.get('threads', []))
            
        except Exception as e:
            logger.error(f"Erro ao obter tópicos do canal {channel_name}: {str(e)}")
        
        return threads

    def get_bot_channels(self):
        """Obtém apenas os canais onde o bot está participando ativamente."""
        print("\nBuscando canais onde o bot está participando...")
        
        channels_data = []
        
        try:
            # Primeiro obtém os servidores
            guilds_url = f"{self.api_endpoint}/users/@me/guilds"
            guilds_response = requests.get(guilds_url, headers=self.headers)
            
            if guilds_response.status_code != 200:
                print("❌ Erro ao obter servidores")
                return []
                
            guilds = guilds_response.json()
            print(f"Encontrados {len(guilds)} servidores")
            
            for guild in guilds:
                print(f"\nVerificando servidor: {guild['name']}")
                
                # Obtém os canais do servidor
                channels_url = f"{self.api_endpoint}/guilds/{guild['id']}/channels"
                channels_response = requests.get(channels_url, headers=self.headers)
                
                if channels_response.status_code != 200:
                    print(f"❌ Sem acesso aos canais do servidor {guild['name']}")
                    continue
                
                channels = channels_response.json()
                text_channels = [c for c in channels if c['type'] == 0]  # 0 = canal de texto
                
                print(f"Encontrados {len(text_channels)} canais de texto")
                
                for channel in text_channels:
                    try:
                        # Tenta ler as últimas mensagens do canal para verificar acesso
                        messages_url = f"{self.api_endpoint}/channels/{channel['id']}/messages?limit=1"
                        messages_response = requests.get(messages_url, headers=self.headers)
                        
                        if messages_response.status_code == 200:
                            # Se conseguiu ler mensagens, adiciona o canal
                            channel_info = {
                                'servidor_nome': guild['name'],
                                'servidor_id': guild['id'],
                                'canal_nome': channel['name'],
                                'canal_id': channel['id'],
                                'tipo': 'canal',
                                'topico_nome': None,
                                'topico_id': None,
                                'topico_status': None,
                                'topico_tipo': None,
                                'ultima_atividade': None
                            }
                            channels_data.append(channel_info)
                            
                            print(f"Buscando tópicos do canal: {channel['name']}")
                            
                            # Busca todos os tipos de tópicos
                            threads = self.get_all_threads(channel['id'], channel['name'])
                            
                            if threads:
                                print(f"Encontrados {len(threads)} tópicos")
                                for thread in threads:
                                    # Determinar o status do tópico
                                    status = []
                                    if thread.get('archived'):
                                        status.append('arquivado')
                                    if thread.get('locked'):
                                        status.append('trancado')
                                    if not status:
                                        status.append('ativo')
                                        
                                    # Determinar o tipo do tópico
                                    thread_type = 'público'
                                    if thread.get('type') == 12:  # 12 = private thread
                                        thread_type = 'privado'
                                    
                                    thread_info = {
                                        'servidor_nome': guild['name'],
                                        'servidor_id': guild['id'],
                                        'canal_nome': channel['name'],
                                        'canal_id': channel['id'],
                                        'tipo': 'tópico',
                                        'topico_nome': thread['name'],
                                        'topico_id': thread['id'],
                                        'topico_status': ', '.join(status),
                                        'topico_tipo': thread_type,
                                        'ultima_atividade': thread.get('last_message_timestamp')
                                    }
                                    channels_data.append(thread_info)
                            else:
                                print("Nenhum tópico encontrado")
                            
                        # Pequeno delay para evitar rate limits
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar canal {channel['name']}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Erro ao obter canais: {str(e)}")
            
        return channels_data

    def create_channels_dataframe(self):
        """Cria um DataFrame com informações dos canais acessíveis."""
        print("\n=== Coletando dados dos canais e tópicos ===\n")
        
        channels_data = self.get_bot_channels()
        
        if not channels_data:
            print("❌ Nenhum canal acessível encontrado")
            return pd.DataFrame()
            
        # Criar DataFrame
        df = pd.DataFrame(channels_data)
        
        if not df.empty:
            # Reordenar as colunas
            columns_order = [
                'servidor_nome', 'servidor_id', 'canal_nome', 'canal_id',
                'tipo', 'topico_nome', 'topico_id', 'topico_status', 'topico_tipo',
                'ultima_atividade'
            ]
            df = df[columns_order]
            
            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = f"discord_channels_{timestamp}.xlsx"
            
            # Salvar em Excel
            df.to_excel(excel_file, index=False, sheet_name='Canais Discord')
            print(f"\n✅ Dados salvos em: {excel_file}")
            
            # Mostrar resumo
            print("\n=== Resumo dos Dados ===")
            print(f"Total de servidores: {df['servidor_nome'].nunique()}")
            print(f"Total de canais: {df[df['tipo'] == 'canal'].shape[0]}")
            
            topicos_df = df[df['tipo'] == 'tópico']
            total_topicos = len(topicos_df)
            print(f"Total de tópicos: {total_topicos}")
            
            if total_topicos > 0:
                print("\nStatus dos tópicos:")
                status_counts = topicos_df['topico_status'].value_counts()
                for status, count in status_counts.items():
                    print(f"- {status}: {count}")
                
                print("\nTipos de tópicos:")
                type_counts = topicos_df['topico_tipo'].value_counts()
                for tipo, count in type_counts.items():
                    print(f"- {tipo}: {count}")
            
            # Mostrar detalhes por servidor
            print("\n=== Detalhes por Servidor ===")
            for servidor in df['servidor_nome'].unique():
                servidor_df = df[df['servidor_nome'] == servidor]
                canais = servidor_df[servidor_df['tipo'] == 'canal'].shape[0]
                topicos = servidor_df[servidor_df['tipo'] == 'tópico'].shape[0]
                print(f"\n{servidor}:")
                print(f"- Canais: {canais}")
                print(f"- Tópicos: {topicos}")
                
                if topicos > 0:
                    status_counts = servidor_df[servidor_df['tipo'] == 'tópico']['topico_status'].value_counts()
                    print("  Status dos tópicos:")
                    for status, count in status_counts.items():
                        print(f"  - {status}: {count}")
        
        return df

def main():
    try:
        print("\n=== Verificador de Canais do Bot Discord ===")
        print("Iniciando verificação...")
        
        lister = DiscordChannelLister()
        df = lister.create_channels_dataframe()
        
        if not df.empty:
            # Mostrar preview do DataFrame
            print("\n=== Preview dos Dados ===")
            print(df.head())
        
        print("\n✅ Verificação concluída!")
        
    except Exception as e:
        logger.error(f"Erro ao listar canais: {e}")
        print(f"\n❌ Erro: {str(e)}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main()) 