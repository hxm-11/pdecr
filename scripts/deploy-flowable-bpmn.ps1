param(
    [string]$BaseUrl = "http://localhost:8081/flowable-rest/service",
    [string]$Username = "rest-admin",
    [string]$Password = "test",
    [string]$DeploymentKey = "pd_ecr_manager_approval",
    [string]$BpmnPath = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if ([string]::IsNullOrWhiteSpace($BpmnPath)) {
    $BpmnPath = Join-Path $RepoRoot "backend/app/integrations/flowable/processes/pd_ecr_manager_approval.bpmn20.xml"
}

$ResolvedBpmnPath = Resolve-Path $BpmnPath

Write-Host "Deploying BPMN to Flowable..."
Write-Host "Base URL: $BaseUrl"
Write-Host "BPMN: $ResolvedBpmnPath"

$DeployUrl = "$($BaseUrl.TrimEnd('/'))/repository/deployments"
$Auth = "${Username}:${Password}"

curl.exe -f -u $Auth `
    -F "deploymentKey=$DeploymentKey" `
    -F "file=@$ResolvedBpmnPath" `
    $DeployUrl

Write-Host ""
Write-Host "Flowable BPMN deployment completed."
