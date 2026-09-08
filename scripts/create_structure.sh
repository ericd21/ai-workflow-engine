#!/bin/bash

folders=(
  app
  app/api
  app/core
  app/workflow
  app/workflow/steps
  app/llm
  app/llm/prompts
  app/llm/schemas
  app/rules
  app/models
  app/storage
  app/observability
  tests
  docker
  scripts
)

for folder in "${folders[@]}"; do
  mkdir -p "$folder"
done