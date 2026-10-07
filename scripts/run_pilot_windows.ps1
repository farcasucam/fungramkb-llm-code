# Go/no-go pilot from a Windows PC against the DGX Spark (192.168.1.112).
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_pilot_windows.ps1 -Mode vllm     # recommended
#   powershell -ExecutionPolicy Bypass -File scripts\run_pilot_windows.ps1 -Mode ollama
#
# vllm  : two `vllm serve` instances started on the Spark with scripts/spark_vllm_up.sh (ports 8000, 8001)
# ollama: Ollama (Docker) on the Spark, port 11434
#
# Needs Python >= 3.11 (e.g. Anaconda). The virtual environment is created OUTSIDE the project folder
# (it lives in Google Drive, where thousands of small files sync badly): %USERPROFILE%\.venvs\fgkb.
# The run is resumable: launch the same command again after an interruption.
# Do not press Ctrl+C in this window (it stops the run); to copy text, select it and press Enter.
param([ValidateSet("vllm", "ollama")][string]$Mode = "vllm", [string]$SparkHost = "192.168.1.112")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# 1. Python environment (client only: no torch, no GPU needed on the PC)
$venv = Join-Path $env:USERPROFILE ".venvs\fgkb"
if (-not (Test-Path "$venv\Scripts\python.exe")) { python -m venv $venv }
$py = "$venv\Scripts\python.exe"
& $py -m pip install -q --upgrade pip
& $py -m pip install -q -e ".[remote,analysis]"

# 2. Inputs and their fingerprints for the preregistration
foreach ($f in "data\processed\fungramkb.json", "data\processed\fgkb_reason.jsonl") {
  if (-not (Test-Path $f)) { throw "Missing $f" }
}
New-Item -ItemType Directory -Force results | Out-Null
Get-FileHash data\processed\fungramkb.json, data\processed\fgkb_reason.jsonl -Algorithm SHA256 |
  Format-Table -AutoSize | Out-File results\pilot_inputs.sha256

# 3. Servers
if ($Mode -eq "vllm") {
  $up = 0
  foreach ($port in 8000, 8001) {
    try {
      $m = Invoke-RestMethod "http://${SparkHost}:$port/v1/models" -TimeoutSec 10
      Write-Host "vLLM on port ${port}: $($m.data[0].id)"; $up++
    } catch {
      Write-Warning "no vLLM server on port $port yet: models served there will fail and can be resumed later"
    }
  }
  if ($up -eq 0) { throw "no vLLM server reachable on $SparkHost (start scripts/spark_vllm_up.sh on the Spark)" }
  $config = "configs\pilot_spark_vllm_remote.yaml"; $out = "results\pilot_spark_vllm.jsonl"
} else {
  $ollama = "http://${SparkHost}:11434"
  $v = Invoke-RestMethod "$ollama/api/version"
  Write-Host "Ollama $($v.version) at $ollama"
  & $py scripts\ollama_pull.py $ollama qwen2.5:7b-instruct-fp16 llama3.1:8b-instruct-fp16
  if ($LASTEXITCODE -ne 0) { throw "model download failed" }
  $config = "configs\pilot_spark_remote.yaml"; $out = "results\pilot_spark.jsonl"
}

# 4. Generations (resumable; progress with estimated time left every chunk) and preregistered analysis
& "$venv\Scripts\fgkb.exe" run --config $config
if ($LASTEXITCODE -ne 0) { throw "run interrupted: launch the same command again to resume" }
& $py scripts\pilot_analysis.py --results $out --bench data\processed\fgkb_reason.jsonl `
    --out ($out -replace "\.jsonl$", "_analysis.json") --report docs\pilot_report.md
Write-Host "Done: docs\pilot_report.md"
