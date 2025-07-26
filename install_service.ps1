# Script para instalar o serviço do Discord Bot
$ErrorActionPreference = "Stop"

# Configurações
$serviceName = "DiscordReportBot"
$displayName = "Discord Report Bot"
$description = "Bot Discord para Relatórios Semanais"
$pythonPath = (Get-Command python).Source
$scriptPath = "C:\GitHub\RelatorioSemanal\discord_bot.py"

# Verificar se o script existe
if (-not (Test-Path $scriptPath)) {
    Write-Host "Erro: Script não encontrado em $scriptPath"
    exit 1
}

# Remover serviço existente se houver
try {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Removendo serviço existente..."
        Stop-Service -Name $serviceName -Force
        sc.exe delete $serviceName
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "Nenhum serviço existente para remover"
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

# Configurar permissões
$acl = Get-Acl "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName"
$rule = New-Object System.Security.AccessControl.RegistryAccessRule("NT AUTHORITY\SYSTEM","FullControl","Allow")
$acl.SetAccessRule($rule)
Set-Acl "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName" $acl

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