$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "CodexTokenUsageDashboard"
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$ScriptPath = Join-Path $RootDir "usage-static.py"
$ConfigPath = Join-Path $RootDir "config.yaml"
$LogPath = Join-Path $RootDir "usage-refresh.log"
$ErrLogPath = Join-Path $RootDir "usage-refresh.err.log"

try {
  $VersionOutput = & $PythonBin -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
} catch {
  Write-Error "Python 3.9+ is required. Set PYTHON_BIN to your Python executable if it is not on PATH."
  exit 1
}

$MajorMinor = $VersionOutput.Split(".")
if ([int]$MajorMinor[0] -lt 3 -or ([int]$MajorMinor[0] -eq 3 -and [int]$MajorMinor[1] -lt 9)) {
  Write-Error "Python 3.9+ is required. Detected $VersionOutput."
  exit 1
}

if (-not (Test-Path $ConfigPath)) {
  Write-Host "Creating $ConfigPath from Codex config..."
  & $PythonBin $ScriptPath sync-config --config $ConfigPath
} else {
  Write-Host "Using existing $ConfigPath"
}

$CollectArgs = "`"$ScriptPath`" collect --config `"$ConfigPath`""
& $PythonBin $ScriptPath collect --config $ConfigPath
$Command = "`"$PythonBin`" $CollectArgs >> `"$LogPath`" 2>> `"$ErrLogPath`""

$Action = New-ScheduledTaskAction `
  -Execute "cmd.exe" `
  -Argument "/d /c $Command" `
  -WorkingDirectory $RootDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes 5) `
  -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Installed Windows Scheduled Task: $TaskName"
Write-Host "Dashboard: $(Join-Path $RootDir 'daily-token-usage.html')"
Write-Host "Logs: $LogPath"
