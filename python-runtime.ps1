$ErrorActionPreference='Stop'
$pythonPaths = @($env:ORGAINSE_PYTHON)
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notmatch '\\Microsoft\\WindowsApps\\python.exe$') { $pythonPaths += $pythonCommand.Source }
$pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyLauncher) { $pythonPaths += (& $pyLauncher.Source -3 -c "import sys;print(sys.executable)" 2>$null) }
$bundles = Get-AppxPackage -Name 'OpenAI.CodexPrimaryRuntime*' -ErrorAction SilentlyContinue | Sort-Object Version -Descending
foreach ($bundle in $bundles) { $pythonPaths += Join-Path $bundle.InstallLocation 'dependencies\python\python.exe' }
$pythonBin = $pythonPaths | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $pythonBin) { throw 'Install Python 3.10+ or set ORGAINSE_PYTHON to its python.exe.' }
$pythonBin
