$configPath = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'Chua co .env. Tao file theo .env.example va dien cau hinh provider/model/key.'
}

# Read assignments as data; never execute the contents of .env.
foreach ($line in Get-Content -LiteralPath $configPath -Encoding UTF8) {
    if ($line -match '^\s*(?:export\s+)?(PROVIDER|MODEL|OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|STATUS_USER_AGENT)\s*=\s*(.*)$') {
        $variableName = $Matches[1]
        $variableValue = $Matches[2].Trim()
        if ($variableValue.Length -ge 2 -and (
            ($variableValue.StartsWith('"') -and $variableValue.EndsWith('"')) -or
            ($variableValue.StartsWith("'") -and $variableValue.EndsWith("'"))
        )) {
            $variableValue = $variableValue.Substring(1, $variableValue.Length - 2)
        } else {
            $variableValue = ($variableValue -replace '\s+#.*$', '').Trim()
        }
        [Environment]::SetEnvironmentVariable($variableName, $variableValue, 'Process')
    }
}

$keyVariables = @{
    openai = 'OPENAI_API_KEY'
    gemini = 'GEMINI_API_KEY'
    anthropic = 'ANTHROPIC_API_KEY'
    openrouter = 'OPENROUTER_API_KEY'
}
if (-not $keyVariables.ContainsKey([string]$env:PROVIDER)) {
    throw 'PROVIDER phai la openai, gemini, anthropic hoac openrouter.'
}
if ([string]::IsNullOrWhiteSpace($env:MODEL) -or $env:MODEL -eq 'YOUR_TOOL_CALLING_MODEL') {
    throw 'Can dat MODEL la model ho tro tool calling.'
}
$keyVariable = $keyVariables[$env:PROVIDER]
$keyValue = [Environment]::GetEnvironmentVariable($keyVariable, 'Process')
if ([string]::IsNullOrWhiteSpace($keyValue) -or $keyValue -eq 'YOUR_KEY') {
    throw "Can dien $keyVariable trong .env."
}
Write-Host "Da nap cau hinh: PROVIDER=$env:PROVIDER, MODEL=$env:MODEL"
