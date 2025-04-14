# Script para instalar o serviço do Discord Bot
$ErrorActionPreference = "Stop"

# Configurações
$serviceName = "DiscordReportBot"
$displayName = "Discord Report Bot"
$description = "Bot Discord para Relatórios Semanais"
$pythonPath = (Get-Command python).Source
$scriptPath = "C:\GitHub\RelatorioSemanal\discord_bot.pyw"

# Verificar se o script existe
if (-not (Test-Path $scriptPath)) {
    Write-Host "Erro: Script não encontrado em $scriptPath"
    exit 1
}

# Criar o serviço
Write-Host "Instalando novo serviço..."
$binPath = "`"$pythonPath`" `"$scriptPath`""
sc.exe create $serviceName binPath= $binPath DisplayName= $displayName start= auto
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erro ao criar serviço"
    exit 1
}

# Configurar descrição
sc.exe description $serviceName $description

# Iniciar o serviço
Write-Host "Iniciando serviço..."
Start-Service -Name $serviceName
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erro ao iniciar serviço"
    exit 1
}

Write-Host "Serviço instalado e iniciado com sucesso!"
Write-Host "Nome do serviço: $serviceName"
Write-Host "Status: $(Get-Service -Name $serviceName | Select-Object -ExpandProperty Status)"