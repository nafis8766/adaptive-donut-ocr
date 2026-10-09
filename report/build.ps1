# Builds report.tex -> report.pdf
#
# Usage, from a terminal in this folder:
#     .\build.ps1
#
# Two pdflatex passes are required, not one. The footer resolves \pageref{LastPage},
# and that reference is only correct on the second pass -- a single pass silently
# prints the wrong page count. Same reason as the CV's build script.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$pdflatex = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
if (-not (Test-Path $pdflatex)) {
    $pdflatex = "C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"
}
if (-not (Test-Path $pdflatex)) {
    Write-Host "Could not find pdflatex.exe. Is MiKTeX installed?" -ForegroundColor Red
    exit 1
}

foreach ($pass in 1, 2) {
    Write-Host "pass $pass ..." -ForegroundColor Cyan
    & $pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$here" "$here\report.tex" |
        Select-String -Pattern '^!|^l\.|Output written'
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Build FAILED on pass $pass. Full error is in report.log" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Built report.pdf" -ForegroundColor Green
