param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("list", "claim", "advance")]
  [string]$Command,
  [Parameter(Mandatory = $true)]
  [string]$Mailbox,
  [string]$MessageId = "",
  [string]$Claimant = "",
  [switch]$Unread
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @("-m", "negotiated_agent.mailbox_cli", $Command, "--project-root", $ProjectRoot, "--mailbox", $Mailbox)
if ($Unread) {
  $argsList += "--unread"
}
if ($Command -eq "claim" -or $Command -eq "advance") {
  if ($MessageId -eq "") {
    throw "$Command requires -MessageId."
  }
  $argsList += @("--message-id", $MessageId)
}
if ($Command -eq "claim") {
  if ($Claimant -eq "") {
    throw "Claim requires -Claimant."
  }
  $argsList += @("--claimant", $Claimant)
}

& $Python @argsList
exit $LASTEXITCODE
