param(
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$exitCode = 1

try {
    $projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
    Set-Location -LiteralPath $projectRoot

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
    $npxCommand = Get-Command npx -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw "Node.js was not found." }
    if (-not $npmCommand) { throw "npm was not found." }
    if (-not $npxCommand) { throw "npx was not found." }

    $bootstrapScript = Join-Path $projectRoot "scripts\acceptance\programming_workbench_login_bootstrap.mjs"
    $acceptanceScript = Join-Path $projectRoot "scripts\acceptance\programming_workbench_online_acceptance.mjs"
    if (-not (Test-Path -LiteralPath $bootstrapScript -PathType Leaf)) {
        throw "Login bootstrap script was not found: $bootstrapScript"
    }
    if (-not (Test-Path -LiteralPath $acceptanceScript -PathType Leaf)) {
        throw "Acceptance script was not found: $acceptanceScript"
    }

    $authDirectory = Join-Path $projectRoot ".playwright\.auth"
    $authState = Join-Path $authDirectory "programming-workbench-online.json"
    New-Item -ItemType Directory -Force -Path $authDirectory | Out-Null

    $bootstrapCheck = & $nodeCommand.Source --check $bootstrapScript
    if ($LASTEXITCODE -ne 0) { throw "Bootstrap JavaScript syntax check failed." }
    $acceptanceCheck = & $nodeCommand.Source --check $acceptanceScript
    if ($LASTEXITCODE -ne 0) { throw "Acceptance JavaScript syntax check failed." }

    $chromiumPath = (& $nodeCommand.Source -e "const { chromium } = require('playwright'); process.stdout.write(chromium.executablePath());" | Out-String).Trim()
    $chromiumExitCode = $LASTEXITCODE
    if ($chromiumExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($chromiumPath) -or -not (Test-Path -LiteralPath $chromiumPath -PathType Leaf)) {
        if ($ValidateOnly) { throw "Playwright Chromium is unavailable." }
        Write-Host "Playwright Chromium was not found. Installing it now."
        & $npxCommand.Source playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed." }
        $chromiumPath = (& $nodeCommand.Source -e "const { chromium } = require('playwright'); process.stdout.write(chromium.executablePath());" | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($chromiumPath) -or -not (Test-Path -LiteralPath $chromiumPath -PathType Leaf)) {
            throw "Playwright Chromium is still unavailable after installation."
        }
    }

    if ($ValidateOnly) {
        Write-Output "ValidateOnly checks passed."
        exit 0
    }

    Write-Host "Opening the local headed Chromium login window."
    Write-Host "Sign in at http://101.32.190.42/ within 15 minutes."
    & $nodeCommand.Source $bootstrapScript --base-url "http://101.32.190.42/" --auth-state $authState --timeout-ms 900000
    if ($LASTEXITCODE -ne 0) { throw "Login bootstrap process failed with exit code $LASTEXITCODE." }

    if (-not (Test-Path -LiteralPath $authState -PathType Leaf)) {
        throw "Authentication state file was not created: $authState"
    }
    $authStateInfo = Get-Item -LiteralPath $authState
    if ($authStateInfo.Length -le 0) { throw "Authentication state file is empty: $authState" }

    & $nodeCommand.Source $acceptanceScript --base-url "http://101.32.190.42/" --auth-state $authState --auth-check-only
    if ($LASTEXITCODE -ne 0) {
        $exitCode = 20
        throw "Authentication state is invalid. Authentication probe failed with exit code $LASTEXITCODE."
    }

    Write-Output "Login completed."
    Write-Output "Authentication state saved."
    Write-Output "Authentication probe passed."
    Write-Output "You may close this PowerShell window."
    exit 0
}
catch {
    if ($exitCode -eq 20) {
        Write-Error ("Authentication state invalid.`n" + $_.Exception.Message)
    } else {
        Write-Error ("Login bootstrap failed.`n" + $_.Exception.Message)
    }
    exit $exitCode
}
