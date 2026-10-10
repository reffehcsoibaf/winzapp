@echo off
rem Diagnostico da aba Privacidade: copia para C:\logs\privacidade.txt as linhas
rem de log que falam de privacidade (do app e do servidor WPPConnect).
rem Pode ser executado de qualquer lugar: ele procura a pasta "data" na raiz do
rem projeto (a pasta acima de "scripts") e em "client".
setlocal
if not exist C:\logs mkdir C:\logs
set "OUT=C:\logs\privacidade.txt"
set "RAIZ=%~dp0.."
echo Diagnostico da aba Privacidade > "%OUT%"
echo Raiz do projeto: %RAIZ% >> "%OUT%"
set ACHOU=0
for %%B in ("%RAIZ%\data" "%RAIZ%\client\data") do (
  if exist "%%~B\accounts" (
    for /d %%A in ("%%~B\accounts\*") do (
      for %%L in (log.log wppconnect.log) do (
        if exist "%%A\logs\%%L" (
          set ACHOU=1
          echo. >> "%OUT%"
          echo ===== %%A\logs\%%L >> "%OUT%"
          findstr /i /c:"privacy" "%%A\logs\%%L" >> "%OUT%"
        )
      )
    )
  )
)
if "%ACHOU%"=="0" echo Nenhum log encontrado em data\accounts\*\logs >> "%OUT%"
echo Pronto. Resultado gravado em %OUT%
pause
