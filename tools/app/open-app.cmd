@echo off
rem Opens the tc-copilot operator app, working around the corporate PAC proxy
rem (which routes 127.0.0.1 through the Zscaler agent and breaks loopback in
rem normally-launched browsers). Starts the server if it is not already up.
setlocal
set PORT=8791

rem Start the server when nothing is listening on the port yet.
netstat -ano | findstr /r ":%PORT% .*LISTENING" >nul
if errorlevel 1 (
  echo Starting tc-copilot operator server on port %PORT% ...
  start "tc-copilot server" /min py -c "import sys; sys.path.insert(0, r'%~dp0.'); import server; server.serve(port=%PORT%, open_browser=False)"
  timeout /t 5 /nobreak >nul
)

rem Proxy-bypassed Edge window with its own profile (flags only apply to a new
rem browser process, so a dedicated user-data-dir is required).
start "" msedge --user-data-dir="%LOCALAPPDATA%\Temp\edge-tc-copilot" --no-proxy-server --no-first-run http://127.0.0.1:%PORT%/
endlocal
