@echo off
chcp 65001 >nul

echo 正在清理中间文件...

:: 中间文件
del /f /q merged_translation.json 2>nul
del /f /q merged_translation_new_entries.json 2>nul
del /f /q translated_new_entries.json 2>nul

:: 最终输出
del /f /q final_translation.json 2>nul

:: 报告/日志
del /f /q quality_report.txt 2>nul
del /f /q cleanup_log.txt 2>nul

echo 清理完成！配置文件不会被删除
pause
