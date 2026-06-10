$action = New-ScheduledTaskAction -Execute "C:\Users\HUAWEI\AppData\Local\Programs\Python\Python311\python.exe" -Argument "C:\Users\HUAWEI\Desktop\餐饮AI情报站\scraper.py" -WorkingDirectory "C:\Users\HUAWEI\Desktop\餐饮AI情报站"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "HUAWEI" -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName "canyin_update" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "Task created. Daily 8:00 AM."
