$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
$env:OPENROUTER_API_KEY = [System.Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY","User")
Set-Location "C:\Users\sarth\Desktop\297\CMPE297\assignment2\partC"
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --profile partc --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml --port 3081 --no-open
