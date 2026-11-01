@echo off
rem ============================================================================
rem  Loan Intelligence - local launcher for Windows
rem  Double-click this file, or run it from a terminal in the project folder.
rem  It finds Python, creates a virtual environment (outside this folder), installs the
rem  dependencies when needed, creates the first accounts on the first run,
rem  and starts the application at http://localhost:8501
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Loan Intelligence (local)

rem --- optional settings from .env (KEY=value lines; lines starting with # are ignored)
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
  )
)
if not defined LOAN_APP_PORT set "LOAN_APP_PORT=8501"

rem --- 1. find Python 3.10 or newer
set "PYCMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
  )
)
if not defined PYCMD (
  echo.
  echo ERROR: Python 3.10 or newer was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this file again.
  goto :fail
)
echo Using Python: %PYCMD%

rem --- 2. virtual environment. It lives OUTSIDE the project folder (the project's own test suite scans every .py file under the project root,
rem     so a virtual-environment folder inside it would make an original test fail). Override with LOAN_APP_VENV.
if not defined LOAN_APP_VENV (
  if defined LOCALAPPDATA ( set "LOAN_APP_VENV=%LOCALAPPDATA%\LoanIntelligence\venv" ) else ( set "LOAN_APP_VENV=%USERPROFILE%\LoanIntelligence\venv" )
)
if not exist "%LOAN_APP_VENV%\Scripts\python.exe" (
  echo Creating virtual environment in %LOAN_APP_VENV% ...
  %PYCMD% -m venv "%LOAN_APP_VENV%"
  if errorlevel 1 (
    echo ERROR: could not create the virtual environment.
    goto :fail
  )
)
set "VPY=%LOAN_APP_VENV%\Scripts\python.exe"

rem --- 3. dependencies (re-installed only when requirements.txt changed)
fc /b requirements.txt "%LOAN_APP_VENV%\requirements.installed" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies. The first run takes several minutes ...
  "%VPY%" -m pip install --upgrade pip
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERROR: dependency installation failed. Check your internet connection and the messages above.
    goto :fail
  )
  copy /y requirements.txt "%LOAN_APP_VENV%\requirements.installed" >nul
)

rem --- 4. first run: create the database and the two accounts, and show the passwords once
if not exist "data\app\loan_app.db" (
  if not defined LOAN_APP_DATA_DIR (
    echo.
    echo First run: creating the database and the administrator / officer accounts.
    "%VPY%" -m app.bootstrap
    if errorlevel 1 (
      echo ERROR: first-run setup failed.
      goto :fail
    )
    echo.
    echo ^>^>^> Write down the passwords above now. They are not stored anywhere in plain text. ^<^<^<
    pause
  )
)

rem --- 5. port check
netstat -ano | findstr /R /C:":%LOAN_APP_PORT% .*LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo.
  echo ERROR: port %LOAN_APP_PORT% is already in use. Close the other program, or set LOAN_APP_PORT to another number and run again.
  goto :fail
)

rem --- 6. launch (the browser is opened shortly after the server starts)
echo.
echo Starting the application at http://localhost:%LOAN_APP_PORT%   (press Ctrl+C in this window to stop it)
if not defined RUN_LOCAL_NO_LAUNCH start "" /b cmd /c "timeout /t 6 /nobreak >nul & start http://localhost:%LOAN_APP_PORT%"
if defined RUN_LOCAL_NO_LAUNCH (
  echo RUN_LOCAL_NO_LAUNCH is set: setup finished, not launching.
  exit /b 0
)
"%VPY%" -m streamlit run app\streamlit_app.py --server.address localhost --server.port %LOAN_APP_PORT%
if errorlevel 1 (
  echo.
  echo ERROR: the application stopped with an error. See the messages above.
  goto :fail
)
exit /b 0

:fail
echo.
echo Startup failed.
pause
exit /b 1
