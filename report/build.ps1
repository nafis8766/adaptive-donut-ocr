# Builds report.tex -> report.pdf
#
# Usage, from a terminal in this folder:
#     .\build.ps1
#
# FOUR passes, not two, and the order matters:
#
#   1. pdflatex  writes report.bcf, listing the \cite keys and the reference context
#   2. biber     reads report.bcf + references.bib and writes report.bbl
#   3. pdflatex  pulls report.bbl in, so the bibliography and [n] citation labels appear
#   4. pdflatex  resolves the now-correct labels -- a \ref to a section, table or equation
#                that moved when the bibliography changed the page layout
#
# BIBER, not bibtex. The journal template ships biblatex with backend=bibtex; that builds
# a correct PDF but warns "Please (re)run BibTeX" on every pass forever, because biblatex
# checks whether a requested rerun happened by diffing the .bbl's md5 and bibtex rewrites
# it byte-identically. See the comment in report.tex. Dropping pass 2 entirely does not
# fail the build -- it silently produces a PDF with no references and [?] for every
# citation, which is why pass 4's exit check below reads the .bbl rather than trusting
# the exit codes.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$bin = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64"
if (-not (Test-Path "$bin\pdflatex.exe")) {
    $bin = "C:\Program Files\MiKTeX\miktex\bin\x64"
}
$pdflatex = "$bin\pdflatex.exe"
$biber    = "$bin\biber.exe"
if (-not (Test-Path $pdflatex)) {
    Write-Host "Could not find pdflatex.exe. Is MiKTeX installed?" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $biber)) {
    Write-Host "Could not find biber.exe next to pdflatex." -ForegroundColor Red
    exit 1
}

function Invoke-Pdflatex([int]$pass) {
    Write-Host "pdflatex pass $pass ..." -ForegroundColor Cyan
    & $pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$here" "$here\report.tex" |
        Select-String -Pattern '^!|^l\.|Output written'
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Build FAILED on pdflatex pass $pass. Full error is in report.log" -ForegroundColor Red
        exit 1
    }
}

Invoke-Pdflatex 1

Write-Host "biber ..." -ForegroundColor Cyan
Push-Location $here
& $biber --quiet "report"
$biberExit = $LASTEXITCODE
Pop-Location
if ($biberExit -ne 0) {
    Write-Host ""
    Write-Host "biber FAILED. Full error is in report.blg" -ForegroundColor Red
    exit 1
}

Invoke-Pdflatex 2
Invoke-Pdflatex 3

# Three content checks on the finished build. A LaTeX run exits 0 while leaving [?] in the
# PDF, so the exit codes above are necessary and not sufficient -- read the artifacts.
$log = Get-Content "$here\report.log" -Raw
$bad = $false

if (-not (Test-Path "$here\report.bbl")) {
    Write-Host "PROBLEM: report.bbl is missing -- the bibliography did not build." -ForegroundColor Red
    $bad = $true
} else {
    $entries = ([regex]'\\entry\{').Matches((Get-Content "$here\report.bbl" -Raw)).Count
    if ($entries -lt 1) {
        Write-Host "PROBLEM: report.bbl has no entries." -ForegroundColor Red
        $bad = $true
    } else {
        Write-Host "  bibliography entries : $entries" -ForegroundColor DarkGray
    }
}

if ($log -match 'There were undefined references' -or $log -match 'Citation .* undefined') {
    Write-Host "PROBLEM: undefined references or citations -- the PDF will show ?? or [?]." -ForegroundColor Red
    $bad = $true
}

$overfull = ([regex]'Overfull \\[hv]box').Matches($log).Count
Write-Host "  overfull boxes       : $overfull" -ForegroundColor DarkGray

if ($bad) { exit 1 }

Write-Host ""
Write-Host "Built report.pdf" -ForegroundColor Green
