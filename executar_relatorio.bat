@echo off
echo Iniciando execucao de relatorios semanais - %date% %time% >> logs\execucao.log
cd /d "%~dp0"
python run.py >> logs\execucao.log 2>&1
echo Execucao finalizada - %date% %time% >> logs\execucao.log 