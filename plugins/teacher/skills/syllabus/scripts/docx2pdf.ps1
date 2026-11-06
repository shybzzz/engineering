# Converts a .docx to PDF with Microsoft Word (Windows, Word installed) for a visual check.
# Works on a temporary copy opened read-only, in its own hidden Word instance, so a document
# the user has open is never touched.
# Usage: powershell -NoProfile -File docx2pdf.ps1 -In <file.docx> -Out <file.pdf>
param(
    [Parameter(Mandatory = $true)][string]$In,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$src = (Resolve-Path -LiteralPath $In).Path
$dst = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("docx2pdf_" + [guid]::NewGuid().ToString('N') + ".docx")
Copy-Item -LiteralPath $src -Destination $tmp -Force
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($tmp, $false, $true)
    $doc.ExportAsFixedFormat($dst, 17)          # 17 = wdExportFormatPDF
    Write-Output ("pages: " + $doc.ComputeStatistics(2))   # 2 = wdStatisticPages
    $doc.Close($false)
}
finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
Write-Output ("saved " + $dst)
