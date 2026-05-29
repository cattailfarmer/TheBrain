param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("list", "claim", "advance", "claims", "rendezvous")]
  [string]$Command,
  [string]$Mailbox = "",
  [string]$MessageId = "",
  [string]$Claimant = "",
  [string]$Source = "",
  [string]$Target = "",
  [string]$Subject = "",
  [string]$Boundary = "",
  [switch]$Unread
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @("-m", "negotiated_agent.mailbox_cli", $Command, "--project-root", $ProjectRoot)
if ($Command -ne "rendezvous") {
  if ($Mailbox -eq "") {
    throw "$Command requires -Mailbox."
  }
  $argsList += @("--mailbox", $Mailbox)
}
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
if ($Command -eq "rendezvous") {
  if ($Source -eq "" -or $Target -eq "" -or $Subject -eq "" -or $Boundary -eq "") {
    throw "Rendezvous requires -Source, -Target, -Subject, and -Boundary."
  }
  $argsList += @("--source", $Source, "--target", $Target, "--subject", $Subject, "--boundary", $Boundary)
}

& $Python @argsList
exit $LASTEXITCODE
