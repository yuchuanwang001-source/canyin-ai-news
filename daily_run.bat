@echo off
chcp 65001 >nul
cd /d "C:\Users\HUAWEI\Desktop"
cd "餐饮AI情报站"
set PYTHONIOENCODING=utf-8
echo [%date% %time%] Start update >> update_log.txt
"C:\Users\HUAWEI\AppData\Local\Programs\Python\Python311\python.exe" scraper.py >> update_log.txt 2>&1
echo [%date% %time%] Done >> update_log.txt
