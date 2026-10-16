# Install/reinstall/remove only an explicitly checked disposable test copy.
# No first-run certificate trust, live Bluetooth, cameras, or existing app data.
param([string]$PreviousInstaller = '')
$ErrorActionPreference = 'Stop'
$buildRoot = Split-Path -Parent $PSScriptRoot
$setupFile = Join-Path $buildRoot 'dist\CricketBroadcastSystem-Setup.exe'
$productRegistry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{68A95CA1-D445-45D9-85AF-632D0411E3E4}_is1'
if (Test-Path -LiteralPath $productRegistry) { throw 'An installed copy already exists. Validation will not replace it.' }
if (-not (Test-Path -LiteralPath $setupFile)) { throw 'Build the installer first.' }
$testParent = [IO.Path]::GetFullPath((Join-Path $buildRoot '.installer-test'))
$testRoot = [IO.Path]::GetFullPath((Join-Path $testParent ('deployment-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))))
$testProgram = [IO.Path]::GetFullPath((Join-Path $testRoot 'program'))
if (-not $testProgram.StartsWith($testParent + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Test install path is outside its allowed folder.' }
if (Test-Path -LiteralPath $testRoot) { throw 'Test folder already exists. Choose a new test run.' }
New-Item -ItemType Directory -Path $testRoot | Out-Null
$savedFiles = Join-Path $testRoot 'saved-data'
$installed = $false

function Run-Installer([string]$LogName, [string]$InstallerPath = $setupFile) {
    $logFile = Join-Path $testRoot $LogName
    $parameters = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOICONS /TASKS="" /DIR="' + $testProgram + '" /LOG="' + $logFile + '"'
    $process = Start-Process -FilePath $InstallerPath -ArgumentList $parameters -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer failed with exit $($process.ExitCode). See $logFile" }
}

function Saved-Hashes {
    Get-ChildItem -LiteralPath $savedFiles -Recurse -File |
        Where-Object { $_.Extension -in @('.json', '.db', '.crt', '.pem') } |
        ForEach-Object { $_.FullName.Substring($savedFiles.Length) + ' ' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash } |
        Sort-Object
}

try {
    if ($PreviousInstaller) {
        $PreviousInstaller = [IO.Path]::GetFullPath($PreviousInstaller)
        if (-not $PreviousInstaller.StartsWith($testParent + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Previous candidate must be an archived test build inside .installer-test.' }
        if (-not (Test-Path -LiteralPath $PreviousInstaller)) { throw 'Previous installer archive is missing.' }
        Run-Installer 'previous-install.log' $PreviousInstaller
        $installed = $true
        $previousExe = Join-Path $testProgram 'CricketBroadcastSystem.exe'
        $previousTest = Start-Process -FilePath $previousExe -ArgumentList ('--self-test --data-dir "' + $savedFiles + '"') -WindowStyle Hidden -Wait -PassThru
        if ($previousTest.ExitCode -ne 0) { throw 'Previous candidate diagnostics failed; upgrade test stopped.' }
        $previousHashes = @(Saved-Hashes)
    }
    Run-Installer 'install.log'
    $installed = $true
    $programFile = Join-Path $testProgram 'CricketBroadcastSystem.exe'
    if (-not (Test-Path -LiteralPath $programFile)) { throw 'Installed app executable is missing' }
    $registered = Get-ItemProperty -LiteralPath $productRegistry
    if ($registered.DisplayVersion -ne '1.6.0-rc.3') { throw 'Installed product version is wrong' }
    if ($PreviousInstaller -and (Compare-Object $previousHashes @(Saved-Hashes))) { throw 'Upgrade changed saved matches/certificates before diagnostics.' }
    if ($PreviousInstaller) { Write-Output 'Previous candidate upgraded to rc.3; saved-file hashes unchanged.' }
    $testProcess = Start-Process -FilePath $programFile -ArgumentList ('--self-test --data-dir "' + $savedFiles + '"') -WindowStyle Hidden -Wait -PassThru
    if ($testProcess.ExitCode -ne 0) { throw 'Installed app self-test failed. Check its saved logs.' }
    $before = @(Saved-Hashes)
    Run-Installer 'reinstall.log'
    $after = @(Saved-Hashes)
    if (Compare-Object $before $after) { throw 'Reinstall changed saved matches/certificates' }
    Write-Output 'Install, installed-app diagnostics and same-version reinstall passed; saved-file hashes unchanged.'
} finally {
    if ($installed) {
        $uninstallFile = [IO.Path]::GetFullPath((Join-Path $testProgram 'uninstall\unins000.exe'))
        if (-not $uninstallFile.StartsWith($testProgram + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Uninstall target failed validation' }
        if (-not (Test-Path -LiteralPath $uninstallFile)) { throw 'The test copy uninstaller is missing; no broad cleanup was attempted.' }
        $uninstallProcess = Start-Process -FilePath $uninstallFile -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -WindowStyle Hidden -Wait -PassThru
        if ($uninstallProcess.ExitCode -ne 0) { throw "Test uninstall failed with exit $($uninstallProcess.ExitCode)" }
        if (Test-Path -LiteralPath (Join-Path $testProgram 'CricketBroadcastSystem.exe')) { throw 'Test executable remained after uninstall' }
        if (Test-Path -LiteralPath $productRegistry) { throw 'Test uninstall registry entry remained' }
        if (-not (Test-Path -LiteralPath (Join-Path $savedFiles 'certs\rootCA.key.pem'))) { throw 'Saved test certificate key was removed' }
        if ($before -and (Compare-Object $before @(Saved-Hashes))) { throw 'Uninstall changed saved test data' }
        Write-Output 'Disposable test program uninstalled; saved matches/certificates kept. Current .bat app was not changed.'
    }
}
