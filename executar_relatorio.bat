@echo off
:: Garantir que estamos no diretório do script
cd /d "%~dp0"

:: Criar pasta de logs se não existir
if not exist logs mkdir logs

:: Registrar início da execução
echo Iniciando execucao de relatorios semanais - %date% %time% >> logs\execucao.log

:: Executar o script Python com a opção force
python run.py --force >> logs\execucao.log 2>&1

:: Registrar conclusão
echo Execucao finalizada - %date% %time% >> logs\execucao.log 