param([switch]$Preview)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$workspace = Split-Path (Split-Path $project -Parent) -Parent
$data = Join-Path $workspace 'work\tcg-pc-runtime'
$settings = Get-Content (Join-Path $data 'settings.json') -Raw | ConvertFrom-Json
$mutex = New-Object System.Threading.Mutex($false, 'Local\TCGDealWatchPC')
$locked = $false
try {
    $locked = $mutex.WaitOne(0)
    if (-not $locked) { exit 0 }
    $secure = (Get-Content (Join-Path $data 'discord.dpapi') -Raw).Trim() | ConvertTo-SecureString
    $credential = New-Object System.Management.Automation.PSCredential('discord', $secure)
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $settings.python
    $start.WorkingDirectory = $project
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $reportName = if ($Preview) { 'preview.json' } else { 'report.json' }
    $start.Arguments = '-m tcg_bot --state "' + (Join-Path $data 'state.json') + '" --report "' + (Join-Path $data $reportName) + '"'
    if (-not $Preview) { $start.Arguments += ' --send' }
    $start.EnvironmentVariables['DISCORD_WEBHOOK_URL'] = $credential.GetNetworkCredential().Password
    $start.EnvironmentVariables['PYTHONUTF8'] = '1'
    $start.EnvironmentVariables['TCG_BROWSER'] = '0'
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    $began = Get-Date
    $null = $process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(840000)) { $process.Kill(); throw 'Scan timeout' }
    $log = $stdout.Result + "`r`n" + $stderr.Result
    $log | Set-Content (Join-Path $data 'last-run.log') -Encoding UTF8
    @{ started=$began.ToString('o'); finished=(Get-Date).ToString('o'); exit_code=$process.ExitCode; preview=[bool]$Preview } | ConvertTo-Json | Set-Content (Join-Path $data 'last-run.json') -Encoding UTF8
    # Source failures remain visible in report/log; fatal errors retain their exit code.
    exit $process.ExitCode
} catch {
    @{ finished=(Get-Date).ToString('o'); error_type=$_.Exception.GetType().Name } | ConvertTo-Json | Set-Content (Join-Path $data 'last-run.json') -Encoding UTF8
    exit 2
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
