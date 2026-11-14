<#
.SYNOPSIS
  Reads a board's serial port for a limited time and prints what arrived, decoded as UTF-8.

.DESCRIPTION
  Use after flashing to see the boot log. -Reset pulses RTS (wired to EN on ESP32 dev kits)
  so the log starts from power-on. With -Until the script stops 1.5 s after the pattern
  first appears and exits with code 2 if it never does.
  Keep this file ASCII-only: Windows PowerShell 5.1 misreads UTF-8 scripts without a BOM.
  Write non-ASCII characters in -Until as \uXXXX.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File serial_log.ps1 -Port COM5 -Reset -Seconds 20 -Until "\.local/"
#>
param(
  [Parameter(Mandatory = $true)][string]$Port,
  [int]$Baud = 115200,
  [int]$Seconds = 15,
  [switch]$Reset,
  [string]$Until = ''
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$serial = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
$serial.DtrEnable = $false
$serial.RtsEnable = $false
try {
  $serial.Open()
} catch {
  Write-Output "[serial_log] cannot open ${Port}: $($_.Exception.Message)"
  exit 1
}

$bytes = New-Object System.IO.MemoryStream
$seen = $false
$seenAt = 0
try {
  if ($Reset) {
    $serial.RtsEnable = $true
    Start-Sleep -Milliseconds 120
    $serial.RtsEnable = $false
  }
  $clock = [Diagnostics.Stopwatch]::StartNew()
  while ($clock.ElapsedMilliseconds -lt $Seconds * 1000) {
    $count = $serial.BytesToRead
    if ($count -gt 0) {
      $buffer = New-Object byte[] $count
      $read = $serial.Read($buffer, 0, $count)
      $bytes.Write($buffer, 0, $read)
      if ($Until -and -not $seen -and [System.Text.Encoding]::UTF8.GetString($bytes.ToArray()) -match $Until) {
        $seen = $true
        $seenAt = $clock.ElapsedMilliseconds
      }
    }
    if ($seen -and ($clock.ElapsedMilliseconds - $seenAt) -gt 1500) { break }
    Start-Sleep -Milliseconds 100
  }
} finally {
  $serial.Close()
}

[System.Text.Encoding]::UTF8.GetString($bytes.ToArray())

if ($Until) {
  if ($seen) {
    Write-Output "[serial_log] pattern seen after $seenAt ms"
  } else {
    Write-Output "[serial_log] pattern NOT seen in $Seconds s"
    exit 2
  }
}
