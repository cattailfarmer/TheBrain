param(
  [Parameter(Mandatory = $true)]
  [string]$RunLocalRoot,
  [Parameter(Mandatory = $true)]
  [string]$TargetWorkspaceRoot,
  [string]$EligibilityRef = "",
  [string]$SourceResultRef = "run_local_execution_result.sop",
  [string]$DraftId = "run-local-merge-draft-1",
  [string[]]$TargetPath = @()
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.run_local_merge_draft_cli",
  "--project-root", $ProjectRoot,
  "--run-local-root", $RunLocalRoot,
  "--target-workspace-root", $TargetWorkspaceRoot,
  "--source-result-ref", $SourceResultRef,
  "--draft-id", $DraftId
)
if ($EligibilityRef -ne "") { $argsList += @("--eligibility-ref", $EligibilityRef) }
foreach ($Path in $TargetPath) { $argsList += @("--target-path", $Path) }

& $Python @argsList
exit $LASTEXITCODE
