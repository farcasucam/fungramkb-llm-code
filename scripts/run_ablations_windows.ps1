# Ablations S3 (lexicon-expanded KB) and S4 (G2 components, Qwen) of the main study (analysis plan, section 8).
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_ablations_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\run_ablations_windows.ps1 -Step analysis
#
# Same three servers as the main study (scripts/spark_main_up.sh). Resumable. If Google Drive locks the
# results files (Errno 22), launch the same command again, or run from a local clone (C:\fgkb\fungramkb-llm).
param([ValidateSet("all", "analysis")][string]$Step = "all")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$venv = Join-Path $env:USERPROFILE ".venvs\fgkb"
$py = "$venv\Scripts\python.exe"
$fgkb = "$venv\Scripts\fgkb.exe"

$tag = git describe --tags --always --dirty
Write-Host "code version: $tag"
if ($tag -like "*-dirty") { throw "uncommitted changes ($tag): commit them first, so the manifest identifies the code" }

$s3 = "configs\main_s3_lex_qwen_llama.yaml", "configs\main_s3_lex_olmo.yaml",
      "configs\main_s3_lex_wordings_qwen_llama.yaml", "configs\main_s3_lex_wordings_olmo.yaml"
$s4 = "configs\main_s4_noframes_only.yaml", "configs\main_s4_hedges_minus.yaml", "configs\main_s4_fillers_minus.yaml"

if ($Step -eq "all") {
  if (-not (Test-Path data\processed\fungramkb_lex.json)) { throw "Missing data\processed\fungramkb_lex.json (scripts\apply_lexicon_expansion.py)" }
  foreach ($cfg in $s4 + $s3) {
    Write-Host "=== $cfg"
    & $fgkb run --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "run interrupted ($cfg): launch the same command again to resume" }
  }
  foreach ($cfg in $s4 + $s3) {
    & $py scripts\rerun_truncated.py --config $cfg --max-tokens 1024
    if ($LASTEXITCODE -ne 0) { throw "rerun_truncated failed ($cfg)" }
  }
}

& $py scripts\ablation_analysis.py --base results\main.jsonl results\main_wordings.jsonl `
    --s3 results\main_s3_lex.jsonl results\main_s3_lex_wordings.jsonl --s4 results\main_s4.jsonl `
    --bench data\processed\fgkb_reason_main.jsonl --report docs\main_ablations_report.md --out results\main_ablations.json
if ($LASTEXITCODE -ne 0) { throw "ablation_analysis failed" }
Write-Host "Done: docs\main_ablations_report.md"
