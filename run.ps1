# PowerShell Helper for Agentic RAG
param (
    [Parameter(Position=0)]
    [string]$Command = "help",
    [Parameter(Position=1)]
    [string]$Query = "Summarize Project X"
)

$VenvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

switch ($Command) {
    "install" {
        & $VenvPython -m pip install -r requirements.txt
    }
    "lint" {
        & $VenvPython -m ruff check .
    }
    "test" {
        & $VenvPython -m pytest -v
    }
    "demo" {
        & $VenvPython -m apps.api.cli $Query
    }
    "api" {
        & $VenvPython -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
    }
    "web" {
        Set-Location apps/web
        npm run dev
    }
    "eval" {
        & $VenvPython -m eval.run_eval
    }
    default {
        Write-Host "Usage: .\run.ps1 [install|lint|test|demo|api|web|eval]"
        Write-Host "Example: .\run.ps1 demo 'What are the blockers for Project X?'"
    }
}
