"""Small Windows installer payload embedded into published GMAPI archives."""

from __future__ import annotations

from collections.abc import Mapping


INSTALL_CMD = r"""@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0map-install.ps1" -Action Install
set "rc=%ERRORLEVEL%"
if not "%rc%"=="0" (
  echo.
  echo Installation failed. See the message above.
  pause
)
exit /b %rc%
"""


UNINSTALL_CMD = r"""@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0map-install.ps1" -Action Uninstall
set "rc=%ERRORLEVEL%"
if not "%rc%"=="0" (
  echo.
  echo Uninstall failed. See the message above.
  pause
)
exit /b %rc%
"""


INSTALL_PS1 = r"""param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Uninstall')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$maps = @(Get-ChildItem -LiteralPath $scriptDir -Directory | Where-Object { $_.Name -like '*.gmap' })

if ($maps.Count -ne 1) {
    throw "Expected exactly one .gmap directory next to this script, found $($maps.Count)."
}

$source = $maps[0]
if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
    throw 'APPDATA is not available for the current Windows user.'
}

$mapsRoot = Join-Path $env:APPDATA 'Garmin\Maps'
$target = Join-Path $mapsRoot $source.Name

if ($Action -eq 'Install') {
    New-Item -ItemType Directory -Force -Path $mapsRoot | Out-Null

    if (Get-Process -Name BaseCamp -ErrorAction SilentlyContinue) {
        Write-Warning 'Garmin BaseCamp is running. Close and reopen it after installation.'
    }

    $temporary = "$target.installing-$PID"
    try {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }

        # Copy the complete GMAPI product first. Only replace the installed map
        # after the new copy has succeeded, so an interrupted copy does not
        # destroy a previously working installation.
        Copy-Item -LiteralPath $source.FullName -Destination $temporary -Recurse -Force

        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        Move-Item -LiteralPath $temporary -Destination $target
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host "Map installed for Garmin BaseCamp:"
    Write-Host $target
    Write-Host 'Restart BaseCamp if it was already running.'
    Start-Process explorer.exe -ArgumentList $mapsRoot
    exit 0
}

if (Test-Path -LiteralPath $target) {
    if (Get-Process -Name BaseCamp -ErrorAction SilentlyContinue) {
        Write-Warning 'Garmin BaseCamp is running. Close and reopen it after uninstall.'
    }
    Remove-Item -LiteralPath $target -Recurse -Force
    Write-Host "Map removed:"
    Write-Host $target
} else {
    Write-Host "Map is not installed:"
    Write-Host $target
}

if (Test-Path -LiteralPath $mapsRoot) {
    Start-Process explorer.exe -ArgumentList $mapsRoot
}
exit 0
"""


README_TEMPLATE = """Установка карты в Garmin BaseCamp (Windows)

Карта: {gmap_name}

1. Полностью распакуйте этот ZIP-архив в обычную папку.
2. Запустите install-map.cmd двойным щелчком.
3. Если BaseCamp был открыт, закройте и запустите его снова.

Карта устанавливается только для текущего пользователя в:
%APPDATA%\\Garmin\\Maps\\{gmap_name}

Права администратора и изменение реестра Windows не требуются.
Повторный запуск install-map.cmd обновляет ранее установленную карту.

Удаление:
Запустите uninstall-map.cmd из распакованного архива.

Важно: не запускайте install-map.cmd прямо из окна ZIP-архива — сначала
полностью распакуйте архив, чтобы каталог {gmap_name} находился рядом со скриптом.
"""


def basecamp_installer_files(gmap_name: str) -> Mapping[str, bytes]:
    """Return fixed archive-root installer files for one GMAPI directory."""

    if not gmap_name.lower().endswith(".gmap") or "/" in gmap_name or "\\" in gmap_name:
        raise ValueError(f"invalid GMAPI directory name: {gmap_name!r}")
    return {
        "install-map.cmd": INSTALL_CMD.encode("ascii"),
        "uninstall-map.cmd": UNINSTALL_CMD.encode("ascii"),
        "map-install.ps1": INSTALL_PS1.encode("utf-8"),
        "README-INSTALL.txt": README_TEMPLATE.format(gmap_name=gmap_name).encode("utf-8"),
    }
