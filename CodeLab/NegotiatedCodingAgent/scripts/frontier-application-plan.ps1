param(
  [string]$AdvancementRef = "",
  [switch]$ApplyPlan,
  [string]$PlanRef = "frontier_application_plan.sop",
  [string]$ResultId = "frontier-application-result-1",
  [string]$OutputDir = "",
  [string]$PlanId = "frontier-application-plan-1",
  [string]$CurrentFrontier = "",
  [string]$ConversationSurfaceRef = "",
  [string[]]$CompletedSliceRef = @(),
  [switch]$NarrativeUpdateRequired,
  [switch]$NarrativeUpdateDeferred
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.frontier_application_cli",
  "--project-root", $ProjectRoot,
  "--plan-id", $PlanId
)
if ($AdvancementRef -ne "") { $argsList += @("--advancement-ref", $AdvancementRef) }
if ($ApplyPlan) { $argsList += @("--apply-plan", "--plan-ref", $PlanRef, "--result-id", $ResultId) }
if ($OutputDir -ne "") { $argsList += @("--output-dir", $OutputDir) }
if ($CurrentFrontier -ne "") { $argsList += @("--current-frontier", $CurrentFrontier) }
if ($ConversationSurfaceRef -ne "") { $argsList += @("--conversation-surface-ref", $ConversationSurfaceRef) }
foreach ($Ref in $CompletedSliceRef) { $argsList += @("--completed-slice-ref", $Ref) }
if ($NarrativeUpdateRequired) { $argsList += "--narrative-update-required" }
if ($NarrativeUpdateDeferred) { $argsList += "--narrative-update-deferred" }

& $Python @argsList
exit $LASTEXITCODE
