param(
    [string]$Python = "python",
    # Keep this as OneFile so the built EXE stays portable by itself.
    # If you switch back to OneDir, moving only the EXE out of its folder will break the app.
    [ValidateSet("OneFile")]
    [string]$Mode = "OneFile"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"

if ($Python -eq "python" -and (Test-Path $venvPython)) {
    $Python = $venvPython
}

Push-Location $scriptDir
try {
    $cleanupTargets = @(
        (Join-Path $scriptDir "build\Bi-Clicker"),
        (Join-Path $scriptDir "dist\Bi-Clicker"),
        (Join-Path $scriptDir "dist\Bi-Clicker.exe"),
        (Join-Path $scriptDir "Bi-Clicker.spec")
    )

    foreach ($target in $cleanupTargets) {
        if (Test-Path $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }

    if ($Mode -ne "OneFile") {
        throw "Bi-Clicker must be built as OneFile so the EXE works as a standalone app outside its folder."
    }

    $customTkinterPath = & $Python -c "import customtkinter, pathlib; print(pathlib.Path(customtkinter.__file__).resolve().parent)"
    if (-not $customTkinterPath) {
        throw "Could not resolve the customtkinter install path."
    }

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --noconsole `
        --name "Bi-Clicker" `
        --icon "ACLib\playback.ico" `
        --add-data "ACLib\playback.ico;ACLib" `
        --add-data "${customTkinterPath};customtkinter/" `
        --hidden-import "bi_clicker_ui" `
        --hidden-import "customtkinter" `
        --hidden-import "pydirectinput" `
        auto_clicker.py
}
finally {
    Pop-Location
}
