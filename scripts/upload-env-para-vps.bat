@echo off
REM Envia .env e credencial do Google para o VPS.
REM Dê duplo clique neste arquivo.

cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "scripts\upload-env-para-vps.ps1"
pause
