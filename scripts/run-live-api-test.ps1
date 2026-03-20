param(
    [string]$BaseUrl = "http://localhost:9010",
    [string]$Username = "admin",
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [string]$IngestText = "The SIT Centre for AI offers comprehensive end-to-end services with co-supervision by experts from both SIT and NVIDIA It serves as a gateway for increased AI adoption across industries, better development of students’ competency in AI and a boost in the AI talent pipeline",
    [string]$IngestTitle = "SNAIC Overview",
    [string]$ChatMessage = "what is snaic",
    [string]$GenerationProvider = "openai",
    [string]$GenerationModel = "gpt-4.1-mini",
    [string]$EmbeddingProfile = "openai_small_1536",
    [string]$EmbeddingProvider,
    [string]$EmbeddingModel
)

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

$pytestArgs = @(
    "backend/tests/test_live_api_flow.py",
    "--live-api-base-url", $BaseUrl,
    "--live-api-username", $Username,
    "--live-api-password", $Password,
    "--live-api-ingest-text", $IngestText,
    "--live-api-ingest-title", $IngestTitle,
    "--live-api-chat-message", $ChatMessage,
    "--live-api-generation-provider", $GenerationProvider,
    "--live-api-generation-model", $GenerationModel,
    "--live-api-embedding-profile", $EmbeddingProfile
)

if ($EmbeddingProvider) {
    $pytestArgs += @("--live-api-embedding-provider", $EmbeddingProvider)
}

if ($EmbeddingModel) {
    $pytestArgs += @("--live-api-embedding-model", $EmbeddingModel)
}

python -m pytest @pytestArgs
exit $LASTEXITCODE
