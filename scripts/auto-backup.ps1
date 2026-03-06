$ErrorActionPreference = "Stop"

function Write-Log([string]$Message) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Output "[$ts] $Message"
}

function Run-Git([Parameter(Mandatory=$true)][string[]]$Args) {
  & git @Args
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Args -join ' ') failed (exit $LASTEXITCODE)"
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

try {
  Run-Git @("rev-parse","--is-inside-work-tree")
} catch {
  Write-Log "Not a git repository: $repoRoot"
  exit 2
}

$name = (& git config user.name)
$email = (& git config user.email)
if ($LASTEXITCODE -ne 0 -or -not $name -or -not $email) {
  Write-Log "Git author identity is not set. Run:"
  Write-Log "  git config user.name \"Your Name\""
  Write-Log "  git config user.email \"you@example.com\""
  exit 3
}

$status = (& git status --porcelain)
if (-not $status) {
  Write-Log "No changes. Skip."
  exit 0
}

Write-Log "Changes detected. Staging..."
Run-Git @("add","-A")

$staged = (& git diff --cached --name-only)
if (-not $staged) {
  Write-Log "Nothing staged after add. Skip."
  exit 0
}

$msg = "auto-backup: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Write-Log "Committing: $msg"
Run-Git @("commit","-m",$msg) | Out-Null

Write-Log "Pushing to origin main..."
Run-Git @("push","origin","main")
Write-Log "Done."

