@echo off
chcp 65001 >nul
echo ============================================
echo   量化聚类选股系统 - 一键运行
echo ============================================

rem 检查虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [INFO] 未检测到虚拟环境，使用系统 Python
)

python main.py %*
if errorlevel 1 (
    echo.
    echo 请先安装依赖:
    echo   pip install -r requirements.txt
    pause
)
