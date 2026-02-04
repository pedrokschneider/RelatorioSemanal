param(
  [string]$VpsHost = "72.60.60.117",
  [string]$VpsUser = "root",
  [int]$VpsPort = 22,
  [string]$SshKeyPath = "$env:USERPROFILE\.ssh\relatorio_github",
  [string]$RemoteDir = "/opt/relatorio-semanal",
  [string]$EnvPath = "",
  [string]$GoogleCredsPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $EnvPath) {
  $EnvPath = Resolve-Path (Join-Path $PSScriptRoot "..\.env")
}
if (-not $GoogleCredsPath) {
  $GoogleCredsPath = Resolve-Path (Join-Path $PSScriptRoot "..\config\google_credentials.json")
}

if (-not (Test-Path $SshKeyPath)) {
  throw "Chave SSH nao encontrada em: $SshKeyPath"
}
if (-not (Test-Path $EnvPath)) {
  throw ".env nao encontrado em: $EnvPath"
}
if (-not (Test-Path $GoogleCredsPath)) {
  throw "Credencial Google nao encontrada em: $GoogleCredsPath"
}

Write-Host "Enviando arquivos para $VpsUser@$VpsHost:$RemoteDir"

& ssh -i $SshKeyPath -p $VpsPort "$VpsUser@$VpsHost" "mkdir -p $RemoteDir/config"

& scp -i $SshKeyPath -P $VpsPort "$EnvPath" "$VpsUser@$VpsHost:$RemoteDir/.env"
& scp -i $SshKeyPath -P $VpsPort "$GoogleCredsPath" "$VpsUser@$VpsHost:$RemoteDir/config/google_credentials.json"

& ssh -i $SshKeyPath -p $VpsPort "$VpsUser@$VpsHost" "chmod 600 $RemoteDir/.env $RemoteDir/config/google_credentials.json"

Write-Host "Upload concluido."
