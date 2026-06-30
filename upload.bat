@echo off
REM BatchHelm - one-step upload to GitHub (Windows).
REM Double-click, or run: upload.bat "optional commit message"
setlocal
cd /d "%~dp0"

set "MSG=%~1"
if "%MSG%"=="" set "MSG=feat: complete Qwen hackathon build - agent orchestration, Qwen-driven workflow, memory, deployment, docs"

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%b"
echo Branch: %BRANCH%
echo.

git add -A

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "%MSG%"
) else (
  echo No new changes to commit (pushing any pending commits).
)

git push -u origin %BRANCH%

echo.
echo Uploaded. View it at: https://github.com/ankitranjan-dsai/batchhelm-ai
pause
