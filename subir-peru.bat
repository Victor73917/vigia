@echo off
rem Baja las fuentes que solo responden desde el Peru (avisos y quebradas del SENAMHI, ENFEN)
rem y las sube a la rama datos-peru de GitHub. GitHub Actions las toma de ahi y vuelve a publicar la pagina.
rem La rama se reescribe cada vez (un solo commit), asi no acumula historial.
rem La corre cada hora la tarea programada "VIGIA datos Peru".
cd /d "%~dp0"
echo ==== %date% %time% >> datos\peru.log
py -X utf8 recolectar.py --peru avisos quebradas enfen >> datos\peru.log 2>&1
if not exist datos\peru.json exit /b 1
set GIT_INDEX_FILE=.git\peru.index
for /f %%i in ('git hash-object -w datos\peru.json') do set BLOB=%%i
git read-tree --empty
git update-index --add --cacheinfo 100644,%BLOB%,peru.json
for /f %%i in ('git write-tree') do set ARBOL=%%i
set GIT_INDEX_FILE=
for /f %%i in ('git commit-tree %ARBOL% -m "Datos del Peru (SENAMHI y ENFEN)"') do set COMMIT=%%i
git push -f -q origin %COMMIT%:refs/heads/datos-peru >> datos\peru.log 2>&1
echo subido %COMMIT% >> datos\peru.log
