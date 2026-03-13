# Install Windows shortcuts for Vociferous.
# Creates Desktop and Start Menu entries pointing to vociferous.bat.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$Target = Join-Path $ProjectDir "vociferous.bat"

if (-not (Test-Path $Target)) {
    throw "Launcher not found: $Target"
}

$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Vociferous.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartMenuShortcut = Join-Path $StartMenuDir "Vociferous.lnk"
$IconPath = Join-Path $ProjectDir "assets\icons\vociferous_icon.ico"

if (-not (Test-Path $StartMenuDir)) {
    New-Item -Path $StartMenuDir -ItemType Directory -Force | Out-Null
}

$Shell = New-Object -ComObject WScript.Shell

foreach ($Path in @($DesktopShortcut, $StartMenuShortcut)) {
    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $Target
    $Shortcut.WorkingDirectory = $ProjectDir
    $Shortcut.Description = "Vociferous - Offline speech-to-text"
    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = $IconPath
    }
    $Shortcut.Save()
}

Write-Host "Installed Windows shortcuts:" -ForegroundColor Green
Write-Host "  $DesktopShortcut"
Write-Host "  $StartMenuShortcut"
