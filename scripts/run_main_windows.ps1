# Main study (confirmatory) from the Windows PC against the DGX Spark: docs/analysis_plan.md, tag prereg-v1.
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_main_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\run_main_windows.ps1 -Step analysis   # analysis only
#
# Needs the three servers of scripts/spark_main_up.sh (ports 8000-8002). Resumable: launch the same command
# again after an interruption. Pause Google Drive sync while it runs (Drive locks/reverts files).
# Order: main study (W1) -> wordings (W2/W3) -> one regeneration of truncated answers -> analysis.
param([ValidateSet("all", "analysis")][string]$Step = "all", [string]$SparkHost = "192.168.1.112")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$venv = Join-Path $env:USERPROFILE ".venvs\fgkb"
$py = "$venv\Scripts\python.exe"
$fgkb = "$venv\Scripts\fgkb.exe"

$tag = git describe --tags --always --dirty
Write-Host "code version: $tag"
if ($tag -like "*-dirty") { throw "uncommitted changes ($tag): commit them first, so the manifest identifies the code" }

$main = "configs\main_qwen_llama.yaml", "configs\main_olmo.yaml"
$word = "configs\main_wordings_qwen_llama.yaml", "configs\main_wordings_olmo.yaml"

if ($Step -eq "all") {
  & $py -m pip install -q -e ".[remote,analysis,controls,dense]"
  foreach ($f in "data\processed\fungramkb.json", "data\processed\fgkb_reason_main.jsonl",
                 "data\processed\fgkb_reason_main_wordings.jsonl") {
    if (-not (Test-Path $f)) { throw "Missing $f" }
  }
  New-Item -ItemType Directory -Force results | Out-Null
  $servers = @{}
  foreach ($port in 8000, 8001, 8002) {
    $m = Invoke-RestMethod "http://${SparkHost}:$port/v1/models" -TimeoutSec 10
    $v = try { Invoke-RestMethod "http://${SparkHost}:$port/version" -TimeoutSec 10 } catch { $null }
    $servers["$port"] = @{ model = $m.data[0].id; vllm = $v.version }
    Write-Host "port ${port}: $($m.data[0].id) (vLLM $($v.version))"
  }
  $servers | ConvertTo-Json | Out-File -Encoding utf8 results\main_servers.json

  foreach ($cfg in $main + $word) {
    Write-Host "=== $cfg"
    & $fgkb run --config $cfg
    if ($LASTEXITCODE -ne 0) { throw "run interrupted ($cfg): launch the same command again to resume" }
  }
  foreach ($cfg in $main + $word) {  # analysis plan, section 3: truncated answers regenerated once
    & $py scripts\rerun_truncated.py --config $cfg --max-tokens 1024
    if ($LASTEXITCODE -ne 0) { throw "rerun_truncated failed ($cfg)" }
  }
}

& $py scripts\main_analysis.py --results results\main.jsonl --bench data\processed\fgkb_reason_main.jsonl `
    --out results\main_analysis.json --report docs\main_report.md --long results\main_long.csv
if ($LASTEXITCODE -ne 0) { throw "main_analysis failed" }
& $py scripts\wording_analysis.py results\main.jsonl results\main_wordings.jsonl `
    --wordings data\processed\fgkb_reason_main_wordings.jsonl --report docs\main_wording_report.md `
    --out results\main_wording_analysis.json
if (Get-Command Rscript -ErrorAction SilentlyContinue) {
  Rscript scripts\main_glmm.R results\main_long.csv docs\main_glmm.txt
} else {
  Write-Warning "Rscript not found: mixed model with the Python fallback"
  & $py scripts\main_analysis.py --results results\main.jsonl --out results\main_analysis.json `
      --report docs\main_report.md --long results\main_long.csv --glmm-python | Out-Null
}
Write-Host "Done: docs\main_report.md, docs\main_wording_report.md, docs\main_glmm.txt"
