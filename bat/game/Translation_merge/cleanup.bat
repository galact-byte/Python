@echo off
chcp 65001
whoami
del /f /q final_translation.json
del /f /q merged_translation.json
del /f /q merged_translation_new_entries.json
del /f /q translated_new_entries.json
del /f /q quality_report.txt
del /f /q translation_config.json
del /f /q quality_config.json
del /f /q api_presets.json
del /f /q cleanup_log.txt
echo Cleanup completed.
