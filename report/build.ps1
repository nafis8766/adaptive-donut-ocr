# Builds report.tex -> report.pdf
#
# Usage, from a terminal in this folder:
#     .\build.ps1
#
# FOUR passes, and the order matters:
#
#   1. pdflatex  writes report.aux, including the \citation{} keys and \bibstyle{IEEEtran}
#   2. bibtex    reads report.aux + references.bib and writes report.bbl in IEEE style
#   3. pdflatex  pulls report.bbl in, so the bibliography and [n] citation labels appear
#   4. pdflatex  resolves the now-correct labels -- a \ref to a numbered section, table or
#                equation that moved when the bibliography changed the page layout
#
# BIBTEX, not biber. The report moved from a biblatex template to IEEE's conference
# template, which uses plain BibTeX with IEEEtran.bst. Note this is NOT a return to the
# arrangement that produced the permanent "Please (re)run BibTeX" warning -- that bug is
# biblatex's rerun-detection comparing .bbl checksums, and biblatex is no longer loaded at
# all. Plain BibTeX with IEEEtran.bst has no such check. Verified: 0 warnings after pass 4.
#
# Dropping pass 2 does not fail the build -- it silently produces a PDF with no references
# and [?] for every citation, which is why the checks after pass 4 read the artifacts
# instead of trusting the exit codes.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$bin = "$env:LOCALAPPDATA\Programs\MiKTeX\miktex\bin\x64"
if (-not (Test-Path "$bin\pdflatex.exe")) {
    $bin = "C:\Program Files\MiKTeX\miktex\bin\x64"
}
$pdflatex = "$bin\pdflatex.exe"
$bibtex   = "$bin\bibtex.exe"
if (-not (Test-Path $pdflatex)) {
    Write-Host "Could not find pdflatex.exe. Is MiKTeX installed?" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $bibtex)) {
    Write-Host "Could not find bibtex.exe next to pdflatex." -ForegroundColor Red
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

Write-Host "bibtex ..." -ForegroundColor Cyan
Push-Location $here
& $bibtex "report" | Select-String -Pattern "Warning|error|I couldn't|I found no|repeated entry"
$bibtexExit = $LASTEXITCODE
Pop-Location
# bibtex exits 1 on warnings alone (e.g. an empty field), so only a hard failure (2+) stops
# the build. A missing .bib or an unresolved \cite is a hard error and does stop it.
if ($bibtexExit -ge 2) {
    Write-Host ""
    Write-Host "bibtex FAILED. Full error is in report.blg" -ForegroundColor Red
    exit 1
}

Invoke-Pdflatex 2
Invoke-Pdflatex 3

# Content checks on the finished build. A LaTeX run exits 0 while leaving [?] in the PDF,
# so the exit codes above are necessary and not sufficient -- read the artifacts.
$log = Get-Content "$here\report.log" -Raw
$bad = $false

if (-not (Test-Path "$here\report.bbl")) {
    Write-Host "PROBLEM: report.bbl is missing -- the bibliography did not build." -ForegroundColor Red
    $bad = $true
} else {
    $entries = ([regex]'\\bibitem').Matches((Get-Content "$here\report.bbl" -Raw)).Count
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

# IEEEtran is two-column, so an over-wide table or an unbreakable URL overflows a 3.4in
# column rather than a 6in page. These are far more likely here than they were on a
# single-column template, which is why the count is printed on every build.
$overfull = ([regex]'Overfull \\[hv]box').Matches($log).Count
Write-Host "  overfull boxes       : $overfull" -ForegroundColor DarkGray

# IEEE's own guidance text must not survive into the PDF. The template says so explicitly:
# "Failure to remove the template text from your paper may result in your paper not being
# published." Cheap to assert, and it cannot be assumed -- report.tex is a full rewrite but
# a future edit could paste a block back in.
$tex = Get-Content "$here\report.tex" -Raw
foreach ($needle in @('Given Name Surname', 'dept. name of organization',
                      'This document is a model and instructions',
                      'IEEE conference templates contain guidance text',
                      'Identify applicable funding agency here')) {
    if ($tex -match [regex]::Escape($needle)) {
        Write-Host "PROBLEM: IEEE template boilerplate still in report.tex: '$needle'" -ForegroundColor Red
        $bad = $true
    }
}

if ($bad) { exit 1 }

Write-Host ""
Write-Host "Built report.pdf" -ForegroundColor Green
