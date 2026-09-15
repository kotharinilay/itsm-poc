<#
.SYNOPSIS
  Local development commands (Windows). Thin wrapper over dev.sh so both platforms run the
  identical gate set — a gate that exists on only one platform is a gate that drifts.
#>
[CmdletBinding()]
param([Parameter(Position = 0)][string]$Command = 'validate')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($null -eq $bash) {
    Write-Error 'bash not found. Git for Windows supplies it; it ships with Git.'
    exit 1
}

& $bash.Source (Join-Path $root 'build/scripts/dev.sh') $Command
exit $LASTEXITCODE
