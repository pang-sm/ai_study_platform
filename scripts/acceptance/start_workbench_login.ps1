$ErrorActionPreference = "Stop"

try {
    $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    Set-Location -LiteralPath $projectRoot

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw "未找到 Node.js，请先安装 Node.js 20 或更高版本。" }
    if (-not $npmCommand) { throw "未找到 npm，请确认 Node.js 安装包含 npm。" }

    $bootstrapScript = Join-Path $projectRoot "scripts\acceptance\programming_workbench_login_bootstrap.mjs"
    if (-not (Test-Path -LiteralPath $bootstrapScript -PathType Leaf)) {
        throw "登录引导脚本不存在：$bootstrapScript"
    }

    $playwrightEntry = & $nodeCommand.Source -e "const { chromium } = require('playwright'); process.stdout.write(chromium.executablePath());"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($playwrightEntry) -or -not (Test-Path -LiteralPath $playwrightEntry -PathType Leaf)) {
        Write-Host "未检测到 Playwright Chromium，正在安装..." -ForegroundColor Yellow
        & npx playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium 安装失败，退出码：$LASTEXITCODE" }
    }

    $authState = Join-Path $projectRoot ".playwright\.auth\programming-workbench-online.json"
    $authDirectory = Split-Path -Parent $authState
    New-Item -ItemType Directory -Force -Path $authDirectory | Out-Null
    Write-Host "正在打开正式站点登录窗口：http://101.32.190.42/" -ForegroundColor Cyan
    Write-Host "请仅在新打开的 Chromium 窗口中手动登录，最多等待 15 分钟。" -ForegroundColor Cyan

    & $nodeCommand.Source $bootstrapScript --base-url "http://101.32.190.42/" --auth-state $authState --timeout-ms 900000
    if ($LASTEXITCODE -ne 0) { throw "登录引导失败，退出码：$LASTEXITCODE。请查看 verification-results/programming-workbench-auth-bootstrap.json。" }
    if (-not (Test-Path -LiteralPath $authState -PathType Leaf)) { throw "登录引导结束但认证文件不存在：$authState" }

    Write-Host "登录成功" -ForegroundColor Green
    Write-Host "认证文件已保存：$authState" -ForegroundColor Green
    Write-Host "认证探针通过" -ForegroundColor Green
    Write-Host "现在可以关闭此窗口" -ForegroundColor Green
}
catch {
    Write-Error $_.Exception.Message
    exit 20
}
