$folders = @(
    "app",
    "app/api",
    "app/core",
    "app/workflow",
    "app/workflow/steps",
    "app/llm",
    "app/llm/prompts",
    "app/llm/schemas",
    "app/rules",
    "app/models",
    "app/storage",
    "app/observability",
    "tests",
    "docker",
    "scripts"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder
}