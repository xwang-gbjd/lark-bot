@echo off

REM ��� Python �Ƿ��Ѱ�װ / Check if Python is installed
where python >nul 2>nul
IF ERRORLEVEL 1 (
    echo "��ǰ�豸δ��װPython, �밲װ�����ԡ�/ Python not installed, please install Python before retrying."
    echo "�ɲο�./python-setup.md ��װPython��/ Please refer to./Python-setup.md to install Python."
    pause
    EXIT /b 1
) ELSE (
    echo Python �Ѱ�װ���汾��Ϣ:  / Python is already installed, version info:
    python --version
)
    

REM ��� pip �Ƿ��Ѱ�װ / Check if pip is installed
python -m pip --version >nul 2>nul
IF ERRORLEVEL 1 (
    echo pip δ��װ����ʼ��װ pip... / pip not installed, starting pip installation...
    python -m ensurepip --upgrade
    IF ERRORLEVEL 1 (
        echo pip ��װʧ�ܣ��������⡣ / pip installation failed, please check the issue.
        pause
        EXIT /b 1
    )
) ELSE (
    echo pip �Ѱ�װ���汾��Ϣ:  / pip is already installed, version info: 
    call python -m pip --version
)


REM ��װ��Ŀ���� / Install project dependencies
IF EXIST "requirements.txt" (
    echo ��ʼ��װ��Ŀ����... / Installing project dependencies...
    python -m pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo ������װʧ�ܣ����ֶ�������⡣ / Dependency installation failed, please check manually.
        pause
        EXIT /b 1
    )
) ELSE (
    echo δ��⵽ requirements.txt �ļ�������������װ�� / No requirements.txt file detected, skipping dependency installation.
)
    

REM ������Ŀ / Start the project
echo ������Ŀ... / Starting the project...
python main.py
