param(
    [string]$TargetPath = ".",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$templateDir = Join-Path $scriptDir "templates"
$target = Resolve-Path -LiteralPath $TargetPath

if (-not (Test-Path -LiteralPath $templateDir)) {
    throw "Template klasoru bulunamadi: $templateDir"
}

$files = @(
    "agent.md",
    "todo.md",
    "architecture.md",
    "knowledge.md"
)

$created = @()
$skipped = @()

foreach ($name in $files) {
    $src = Join-Path $templateDir $name
    $dst = Join-Path $target $name

    if (-not (Test-Path -LiteralPath $src)) {
        throw "Template dosyasi bulunamadi: $src"
    }

    if ((Test-Path -LiteralPath $dst) -and (-not $Force)) {
        $skipped += $name
        continue
    }

    Copy-Item -LiteralPath $src -Destination $dst -Force
    $created += $name
}

Write-Host ""
Write-Host "Kurulum Tamamlandi" -ForegroundColor Green
Write-Host "Hedef klasor: $target"
Write-Host "Olusturulan/ezilen dosyalar: $($created.Count)"
foreach ($f in $created) { Write-Host "  + $f" }

Write-Host "Atlanan dosyalar: $($skipped.Count)"
foreach ($f in $skipped) { Write-Host "  - $f (zaten var, ezilmedi)" }

Write-Host ""
Write-Host "Ipuclari:"
Write-Host "  - Var olan dosyalari ezmek icin: -Force"
Write-Host "  - Farkli klasore kurmak icin: -TargetPath <klasor>"
