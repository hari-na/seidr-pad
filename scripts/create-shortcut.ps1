# Creates a "Seidr Pad" desktop shortcut that starts the server and opens the test page.
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
  Write-Error "No .venv found. Run scripts\setup.bat first."
  exit 1
}
$path = Join-Path ([Environment]::GetFolderPath("Desktop")) "Seidr Pad.lnk"
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = "-m seidr_pad.launcher"
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = (Join-Path $root "seidr_pad\static\seidr-pad.ico") + ",0"
$shortcut.Description = "Start seidr-pad and open the test page"
$shortcut.Save()
Write-Host "Created $path"
