param(
    [string]$BaseUrl = "http://localhost:8081/flowable-rest/service",
    [string]$Username = "rest-admin",
    [string]$Password = "test",
    [string]$ProcessDefinitionKey = "pd_ecr_manager_approval"
)

$ErrorActionPreference = "Stop"

$RootUrl = $BaseUrl.TrimEnd("/")
$Auth = "${Username}:${Password}"

Write-Host "Checking Flowable REST endpoint..."
Write-Host "Base URL: $RootUrl"

$DefinitionsUrl = "$RootUrl/repository/process-definitions?key=$ProcessDefinitionKey"

$Response = curl.exe -f -s -u $Auth $DefinitionsUrl

if ($LASTEXITCODE -ne 0) {
    throw "Flowable REST is not reachable, authentication failed, or the URL is incorrect: $DefinitionsUrl"
}

if ([string]::IsNullOrWhiteSpace($Response)) {
    throw "Flowable responded with an empty response."
}

Write-Host "Flowable REST is reachable."

if ($Response -match '"size"\s*:\s*0') {
    Write-Host "Process definition '$ProcessDefinitionKey' is not deployed yet."
    Write-Host "Deploy it with:"
    Write-Host ".\scripts\deploy-flowable-bpmn.ps1 -BaseUrl `"$RootUrl`" -Username `"$Username`" -Password `"***`""
}
else {
    Write-Host "Process definition '$ProcessDefinitionKey' appears to be deployed."
}
