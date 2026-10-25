[CmdletBinding()]
param([Parameter(Mandatory)][string]$OutputRoot)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

# This entrypoint deliberately cannot run on Calvin's workstation or a self-hosted runner.
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'Run only through the manual GitHub-hosted Windows workflow. No local installer or build is supported.'
}
$root = [IO.Path]::GetFullPath($OutputRoot)
$runnerRoot = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if (-not $root.StartsWith($runnerRoot, [StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $root)) {
    throw 'Build root must be a fresh directory under RUNNER_TEMP'
}
New-Item -ItemType Directory -Path "$root/evidence/logs" -Force | Out-Null
$logRoot = "$root/evidence/logs"
$outcome = 'failed'

function Invoke-Logged {
    param([string]$Name, [string]$Command, [string[]]$Arguments)
    & $Command @Arguments 2>&1 | Tee-Object -FilePath "$logRoot/$Name.log"
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

try {
    Invoke-Logged 'prepare' 'python' @("$PSScriptRoot/prepare.py", '--output', $root)
    $manifest = Get-Content "$PSScriptRoot/manifest.json" -Raw | ConvertFrom-Json
    $vswhere = "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe"
    if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Hosted VS discovery tool is missing; do not install it' }
    $instances = @((& $vswhere -products '*' -version '[17.0,18.0)' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | ConvertFrom-Json))
    if ($LASTEXITCODE -ne 0 -or $instances.Count -lt 1) { throw 'Existing VS2022 C++ compiler required; no installer fallback' }
    $vs = $instances | Sort-Object installationVersion -Descending | Select-Object -First 1
    $msvc = (Get-Content "$($vs.installationPath)/VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt" -Raw).Trim()
    $compiler = "$($vs.installationPath)/VC/Tools/MSVC/$msvc/bin/Hostx64/x64/cl.exe"
    if (-not (Test-Path -LiteralPath $compiler)) { throw 'Hosted x64 compiler missing' }
    $cmake = (Get-Command cmake -ErrorAction Stop).Source
    $cmakeVersion = (& $cmake --version | Select-Object -First 1)
    if ($cmakeVersion -notmatch 'cmake version (\d+\.\d+\.\d+)' -or [version]$Matches[1] -lt [version]'3.23') { throw 'Existing CMake >=3.23 is required' }
    $identity = [ordered]@{
        source_revision = $env:GITHUB_SHA; run_id = $env:GITHUB_RUN_ID; run_attempt = $env:GITHUB_RUN_ATTEMPT
        repository = $env:GITHUB_REPOSITORY; runner_os = $env:RUNNER_OS; runner_arch = $env:RUNNER_ARCH
        runner_image = $env:ImageOS; runner_image_version = $env:ImageVersion
        powershell = $PSVersionTable.PSVersion.ToString(); python = (& python --version)
        cmake = $cmakeVersion; cmake_sha256 = (Get-FileHash $cmake -Algorithm SHA256).Hash
        visual_studio = $vs; msvc_version = $msvc; compiler_sha256 = (Get-FileHash $compiler -Algorithm SHA256).Hash
        vcpkg_commit = $manifest.vcpkg.commit; vcpkg_tool_sha256 = $manifest.vcpkg.tool_sha256
        upstream_commit = $manifest.upstream.commit; variant = 'upstream-unchanged'
        runtime_qualified = $false; byte_identical_rebuild_verified = $false
    }
    $identity | ConvertTo-Json -Depth 12 | Set-Content "$root/evidence/build-identity.json"
    $env:VCPKG_ROOT = "$root/vcpkg"
    $env:VCPKG_DOWNLOADS = "$root/downloads"
    $env:VCPKG_BINARY_SOURCES = 'clear'
    $env:VCPKG_DISABLE_METRICS = '1'
    $env:VCPKG_VISUAL_STUDIO_PATH = $vs.installationPath
    # No bootstrap script: prepare.py verified the exact tool executable before this first execution.
    Invoke-Logged 'vcpkg-version' "$root/vcpkg/vcpkg.exe" @('version', '--disable-metrics')
    $configure = @('-S', "$root/upstream", '-B', "$root/build", '-G', 'Visual Studio 17 2022', '-A', 'x64',
        "-DCMAKE_GENERATOR_INSTANCE=$($vs.installationPath)", '-DBUILD_AS_SHARED=ON', "-DOUTPUT_PATH=$root/stage",
        '-DCMAKE_POLICY_VERSION_MINIMUM=3.5', '-DCMAKE_SHARED_LINKER_FLAGS_RELEASE=/INCREMENTAL:NO /DEBUG /OPT:REF /OPT:ICF')
    # Source remains unchanged. /DEBUG requests a matching linker PDB for the diagnostic artifact.
    $configure | ConvertTo-Json | Set-Content "$root/evidence/configure-arguments.json"
    Invoke-Logged 'configure' $cmake $configure
    Invoke-Logged 'compile' $cmake @('--build', "$root/build", '--config', 'Release', '--target', 'NirnLabUIPlatform', '--parallel', '4')
    $dll = "$root/stage/Data/NirnLabUIPlatform/NirnLabUIPlatform.dll"
    if (-not (Test-Path -LiteralPath $dll)) { throw 'Expected DLL missing after build' }
    $pdb = "$root/stage/Data/NirnLabUIPlatform/NirnLabUIPlatform.pdb"
    if (-not (Test-Path -LiteralPath $pdb)) { throw 'Matching linker PDB missing beside the DLL after build' }
    New-Item -ItemType Directory -Path "$root/evidence/artifacts", "$root/evidence/licenses" -Force | Out-Null
    Copy-Item -LiteralPath $dll -Destination "$root/evidence/artifacts/NirnLabUIPlatform.dll"
    Copy-Item -LiteralPath $pdb -Destination "$root/evidence/artifacts/NirnLabUIPlatform.pdb"
    $pdb | Set-Content "$root/evidence/pdb-source.txt"
    Copy-Item "$root/upstream/LICENSE" "$root/evidence/licenses/NirnLabUIPlatform-MIT.txt"
    Copy-Item "$root/vcpkg/LICENSE.txt" "$root/evidence/licenses/vcpkg-MIT.txt"
    $installed = "$root/build/vcpkg_installed"
    Get-ChildItem "$installed/*/share/*/copyright" -File | ForEach-Object {
        $triplet = $_.Directory.Parent.Parent.Name
        Copy-Item -LiteralPath $_.FullName -Destination "$root/evidence/licenses/$triplet-$($_.Directory.Name).txt"
    }
    if (-not (Get-ChildItem "$root/evidence/licenses" -Filter '*cef-prebuilt*')) { throw 'CEF license missing' }
    if (-not (Get-ChildItem "$root/evidence/licenses" -Filter '*commonlibsse-ng*')) { throw 'CommonLib license missing' }
    $outcome = 'compiled-unqualified'
}
finally {
    # Retain failure evidence without uploading dependency executables, game assets, or all environment variables.
    foreach ($pair in @(
        @("$root/build/CMakeCache.txt", 'CMakeCache.txt'),
        @("$root/build/vcpkg-manifest-install.log", 'vcpkg-manifest-install.log'),
        @("$root/build/vcpkg_installed/vcpkg/status", 'vcpkg-status.txt'),
        @("$root/vcpkg/scripts/vcpkg-tool-metadata.txt", 'vcpkg-tool-metadata.txt')
    )) { if (Test-Path -LiteralPath $pair[0]) { Copy-Item -LiteralPath $pair[0] -Destination "$root/evidence/$($pair[1])" } }
    if (Test-Path "$root/build/CMakeFiles") {
        Get-ChildItem "$root/build/CMakeFiles" -Recurse -Filter CMakeCXXCompiler.cmake -File | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination "$root/evidence/CMakeCXXCompiler-$($_.Directory.Name).cmake"
        }
    }
    if (Test-Path "$root/vcpkg/buildtrees") {
        $dependencyLogs = @(Get-ChildItem "$root/vcpkg/buildtrees" -Recurse -File -Filter '*.log')
        $included = 0
        $omitted = @()
        foreach ($file in $dependencyLogs) {
            if ($included -ge 100 -or $file.Length -gt 5MB) { $omitted += $file.FullName; continue }
            $relative = [IO.Path]::GetRelativePath("$root/vcpkg/buildtrees", $file.FullName)
            $target = Join-Path "$root/evidence/dependency-logs" $relative
            New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
            Copy-Item -LiteralPath $file.FullName -Destination $target
            $included++
        }
        @{ included=$included; omitted=$omitted; max_files=100; max_bytes_per_file=5MB } | ConvertTo-Json | Set-Content "$root/evidence/dependency-log-coverage.json"
    }
    if (Test-Path "$root/build/vcpkg_installed") {
        Get-ChildItem "$root/build/vcpkg_installed/*/share/*/vcpkg.spdx.json" -File | ForEach-Object {
            New-Item -ItemType Directory -Path "$root/evidence/dependency-sbom" -Force | Out-Null
            $triplet = $_.Directory.Parent.Parent.Name
            Copy-Item -LiteralPath $_.FullName -Destination "$root/evidence/dependency-sbom/$triplet-$($_.Directory.Name).json"
        }
    }
    [ordered]@{ status=$outcome; native_input_fixed=$false; runtime_qualified=$false; patches=@(); warning='Unchanged upstream lacks the lab save-compatibility flag. Do not deploy this baseline artifact.' } |
        ConvertTo-Json | Set-Content "$root/evidence/result.json"
    Get-ChildItem "$root/evidence" -File -Recurse | ForEach-Object {
        [ordered]@{ path=[IO.Path]::GetRelativePath("$root/evidence", $_.FullName); bytes=$_.Length; sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    } | ConvertTo-Json -Depth 4 | Set-Content "$root/evidence/artifact-hashes.json"
}
