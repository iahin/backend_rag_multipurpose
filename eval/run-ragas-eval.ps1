param(
    [string]$BaseUrl = "",
    [string]$Username = "",
    [string]$Password = "",
    [int]$Limit = 10,
    [int]$TopK = 5,
    [switch]$ResetFirst,
    [switch]$ForceReingest,
    [string]$DatasetSource = "huggingface",
    [string]$DatasetPath = "",
    [string]$HfDataset = "explodinggradients/amnesty_qa",
    [string]$HfConfig = "english_v3",
    [string]$HfSplit = "eval",
    [string]$EmbeddingProfile = "",
    [string]$EmbeddingProvider = "",
    [string]$EmbeddingModel = "",
    [string]$GenerationProvider = "",
    [string]$GenerationModel = "",
    [string]$EvalLlmModel = "",
    [string]$EvalLlmBaseUrl = "",
    [string]$EvalLlmApiKey = "",
    [string]$EvalEmbeddingModel = "",
    [string]$EvalEmbeddingBaseUrl = "",
    [string]$EvalEmbeddingApiKey = "",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendEnvPath = Join-Path $repoRoot "backend\.env"

function Get-EnvMap {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        $values[$key] = $value
    }

    return $values
}

$backendEnv = Get-EnvMap -Path $backendEnvPath

if (-not $BaseUrl) {
    $port = if ($backendEnv.ContainsKey("APP_PORT")) { $backendEnv["APP_PORT"] } else { "9010" }
    $BaseUrl = "http://localhost:$port"
}

if (-not $Username) {
    $Username = if ($backendEnv.ContainsKey("AUTH_BOOTSTRAP_ADMIN_USERNAME")) {
        $backendEnv["AUTH_BOOTSTRAP_ADMIN_USERNAME"]
    }
    else {
        "admin"
    }
}

if (-not $Password -and $backendEnv.ContainsKey("AUTH_BOOTSTRAP_ADMIN_PASSWORD")) {
    $Password = $backendEnv["AUTH_BOOTSTRAP_ADMIN_PASSWORD"]
}

if (-not $Password) {
    throw "Password is required. Pass -Password or set AUTH_BOOTSTRAP_ADMIN_PASSWORD in backend\.env."
}

$arguments = @(
    (Join-Path $scriptDir "ragas_eval.py"),
    "--base-url", $BaseUrl,
    "--username", $Username,
    "--password", $Password,
    "--dataset-source", $DatasetSource,
    "--hf-dataset", $HfDataset,
    "--hf-config", $HfConfig,
    "--hf-split", $HfSplit,
    "--limit", $Limit.ToString(),
    "--top-k", $TopK.ToString()
)

if ($ResetFirst) {
    $arguments += "--reset-first"
}

if ($ForceReingest) {
    $arguments += "--force-reingest"
}

if ($DatasetPath) {
    $arguments += @("--dataset-path", $DatasetPath)
}

if ($EmbeddingProfile) {
    $arguments += @("--embedding-profile", $EmbeddingProfile)
}

if ($EmbeddingProvider) {
    $arguments += @("--embedding-provider", $EmbeddingProvider)
}

if ($EmbeddingModel) {
    $arguments += @("--embedding-model", $EmbeddingModel)
}

if ($GenerationProvider) {
    $arguments += @("--generation-provider", $GenerationProvider)
}

if ($GenerationModel) {
    $arguments += @("--generation-model", $GenerationModel)
}

if ($EvalLlmModel) {
    $arguments += @("--eval-llm-model", $EvalLlmModel)
}

if ($EvalLlmBaseUrl) {
    $arguments += @("--eval-llm-base-url", $EvalLlmBaseUrl)
}

if ($EvalLlmApiKey) {
    $arguments += @("--eval-llm-api-key", $EvalLlmApiKey)
}

if ($EvalEmbeddingModel) {
    $arguments += @("--eval-embedding-model", $EvalEmbeddingModel)
}

if ($EvalEmbeddingBaseUrl) {
    $arguments += @("--eval-embedding-base-url", $EvalEmbeddingBaseUrl)
}

if ($EvalEmbeddingApiKey) {
    $arguments += @("--eval-embedding-api-key", $EvalEmbeddingApiKey)
}

Write-Host "Running RAGAS evaluation against $BaseUrl"
& $PythonExe @arguments
exit $LASTEXITCODE
