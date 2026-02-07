#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游戏翻译工作流 - 图形化界面
整合合并、翻译、回写三个步骤
"""

import sys
import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QProgressBar,
    QFileDialog, QComboBox, QGroupBox, QTabWidget, QMessageBox,
    QCheckBox, QSpinBox, QInputDialog, QSplitter
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QTextCursor

# 导入我们的模块
from merge_translations import merge_translations as do_merge
from api_translator import create_translator, translate_json_file, merge_translated_back
from quality_checker import check_translation_quality, check_with_ai, generate_report, fix_with_ai, apply_fixes


class WorkerThread(QThread):
    """工作线程基类"""
    progress = pyqtSignal(str)  # 日志消息
    finished = pyqtSignal(bool, str)  # 是否成功，结果消息
    progress_value = pyqtSignal(int, int)  # 当前值，总数


class MergeWorker(WorkerThread):
    """合并工作线程"""
    
    def __init__(self, new_file, old_file, output_file):
        super().__init__()
        self.new_file = new_file
        self.old_file = old_file
        self.output_file = output_file
    
    def run(self):
        try:
            self.progress.emit("🔄 开始合并翻译文件...")
            
            # 调用原有的合并函数
            # 由于原函数会打印到控制台，我们需要捕获或重定向输出
            import io
            from contextlib import redirect_stdout
            
            f = io.StringIO()
            with redirect_stdout(f):
                do_merge(self.new_file, self.old_file, self.output_file)
            
            output = f.getvalue()
            for line in output.split('\n'):
                if line.strip():
                    self.progress.emit(line)
            
            # 检查是否生成了新条目文件
            new_entries_file = self.output_file.replace('.json', '_new_entries.json')
            if Path(new_entries_file).exists():
                with open(new_entries_file, 'r', encoding='utf-8') as f:
                    new_entries = json.load(f)
                
                msg = f"✅ 合并完成！\n"
                msg += f"📝 生成文件: {self.output_file}\n"
                msg += f"🆕 新增条目: {len(new_entries)} 条\n"
                msg += f"📄 新条目文件: {new_entries_file}"
                
                self.finished.emit(True, msg)
            else:
                self.finished.emit(True, "✅ 合并完成！没有新增条目需要翻译。")
                
        except Exception as e:
            self.finished.emit(False, f"❌ 合并失败: {str(e)}")


class TranslateWorker(WorkerThread):
    """翻译工作线程"""
    
    def __init__(self, input_file, output_file, provider, api_key, model, base_url):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    def run(self):
        try:
            self.progress.emit("🤖 正在初始化翻译器...")
            
            # 创建翻译器
            translator = create_translator(
                self.provider, 
                self.api_key, 
                self.model if self.model else None,
                self.base_url if self.base_url else None
            )
            
            self.progress.emit(f"📖 正在加载文件: {self.input_file}")
            
            # 定义进度回调
            def progress_callback(current, total, text):
                self.progress.emit(f"翻译进度: {current}/{total} - {text}...")
                self.progress_value.emit(current, total)
            
            # 执行翻译
            success_count, total_count = translate_json_file(
                self.input_file,
                self.output_file,
                translator,
                progress_callback
            )
            
            msg = f"✅ 翻译完成！\n"
            msg += f"📝 总条目数: {total_count}\n"
            msg += f"✅ 成功翻译: {success_count}\n"
            msg += f"💾 输出文件: {self.output_file}"
            
            self.finished.emit(True, msg)
            
        except Exception as e:
            self.finished.emit(False, f"❌ 翻译失败: {str(e)}")


class MergeBackWorker(WorkerThread):
    """回写合并工作线程"""
    
    def __init__(self, merged_file, translated_file, output_file):
        super().__init__()
        self.merged_file = merged_file
        self.translated_file = translated_file
        self.output_file = output_file
    
    def run(self):
        try:
            self.progress.emit("🔄 正在合并翻译结果...")
            
            update_count = merge_translated_back(
                self.merged_file,
                self.translated_file,
                self.output_file
            )
            
            msg = f"✅ 回写完成！\n"
            msg += f"📝 更新条目数: {update_count}\n"
            msg += f"💾 最终文件: {self.output_file}"
            
            self.finished.emit(True, msg)
            
        except Exception as e:
            self.finished.emit(False, f"❌ 回写失败: {str(e)}")


class QualityCheckWorker(WorkerThread):
    """质量检查工作线程"""
    
    def __init__(self, original_file, translated_file, check_missing, check_order, 
                 check_ai=False, translator=None):
        super().__init__()
        self.original_file = original_file
        self.translated_file = translated_file
        self.check_missing = check_missing
        self.check_order = check_order
        self.check_ai = check_ai
        self.translator = translator
        self.results = None
    
    def run(self):
        try:
            self.progress.emit("🔍 正在检查翻译质量...")
            
            # 执行质量检查
            self.results = check_translation_quality(
                self.original_file,
                self.translated_file,
                self.check_missing,
                self.check_order
            )
            
            # AI检查（可选）
            if self.check_ai and self.translator:
                self.progress.emit("🤖 正在进行AI辅助检查...")
                import json
                with open(self.translated_file, 'r', encoding='utf-8') as f:
                    translated_data = json.load(f)
                with open(self.original_file, 'r', encoding='utf-8') as f:
                    original_data = json.load(f)
                
                entries = []
                for key, translated in translated_data.items():
                    original = original_data.get(key, key)
                    entries.append({"key": key, "original": original, "translated": translated})
                
                # 只取前100条进行AI检查
                ai_issues = check_with_ai(self.translator, entries[:100])
                self.results["ai_issues"] = ai_issues
                self.results["summary"]["ai_issue_count"] = len(ai_issues)
            
            msg = f"✅ 检查完成！\n"
            msg += f"📊 漏翻: {self.results['summary']['missing_count']} 条\n"
            msg += f"📊 语序问题: {self.results['summary']['order_error_count']} 条"
            if self.check_ai:
                msg += f"\n📊 AI标记: {self.results['summary'].get('ai_issue_count', 0)} 条"
            
            self.finished.emit(True, msg)
            
        except Exception as e:
            self.finished.emit(False, f"❌ 检查失败: {str(e)}")


class TranslationGUI(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.config_file = Path("translation_config.json")
        self.presets_file = Path("api_presets.json")
        self.quality_config_file = Path("quality_config.json")
        self.presets = {}  # 预设存储
        self.env_keys = self.load_env_keys()  # 从.env加载的密钥
        self.init_ui()
        self.load_presets()
        self.load_config()
        self.load_quality_config()
    
    def load_env_keys(self):
        """从.env文件加载API密钥"""
        keys = {}
        env_file = Path(".env")
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if value.strip():
                                keys[key.strip()] = value.strip()
            except Exception:
                pass
        return keys
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("游戏翻译工作流 v2.0")
        self.setGeometry(100, 100, 1000, 700)
        
        # 主部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 使用QSplitter让日志区域可拖动
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)  # 1表示拉伸比例
        
        # 标签页
        tabs = QTabWidget()
        
        # 第一步：合并文件
        tab1 = self.create_merge_tab()
        tabs.addTab(tab1, "1️⃣ 合并文件")
        
        # 第二步：API翻译
        tab2 = self.create_translate_tab()
        tabs.addTab(tab2, "2️⃣ API翻译")
        
        # 第三步：回写结果
        tab3 = self.create_mergeback_tab()
        tabs.addTab(tab3, "3️⃣ 回写结果")
        
        # 第四步：质量检查
        tab4 = self.create_quality_tab()
        tabs.addTab(tab4, "4️⃣ 质量检查")
        
        # 标签页放入splitter
        splitter.addWidget(tabs)
        
        # 日志区域
        log_group = QGroupBox("📋 运行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)  # 最小高度
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        splitter.addWidget(log_group)
        
        # 设置初始比例 (70% 标签页, 30% 日志)
        splitter.setSizes([500, 200])
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def create_merge_tab(self):
        """创建合并文件标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info = QLabel("📖 说明：比对新旧版本JSON文件，提取需要翻译的新条目")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        # 新文件
        new_layout = QHBoxLayout()
        new_layout.addWidget(QLabel("新文件（原文）:"))
        self.merge_new_file = QLineEdit()
        new_layout.addWidget(self.merge_new_file)
        btn_new = QPushButton("浏览...")
        btn_new.clicked.connect(lambda: self.browse_file(self.merge_new_file))
        new_layout.addWidget(btn_new)
        file_layout.addLayout(new_layout)
        
        # 旧文件
        old_layout = QHBoxLayout()
        old_layout.addWidget(QLabel("旧文件（已翻译）:"))
        self.merge_old_file = QLineEdit()
        old_layout.addWidget(self.merge_old_file)
        btn_old = QPushButton("浏览...")
        btn_old.clicked.connect(lambda: self.browse_file(self.merge_old_file))
        old_layout.addWidget(btn_old)
        file_layout.addLayout(old_layout)
        
        # 输出文件
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("输出文件:"))
        self.merge_output_file = QLineEdit("merged_translation.json")
        out_layout.addWidget(self.merge_output_file)
        btn_out = QPushButton("浏览...")
        btn_out.clicked.connect(lambda: self.browse_save_file(self.merge_output_file))
        out_layout.addWidget(btn_out)
        file_layout.addLayout(out_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 执行按钮
        btn_merge = QPushButton("🚀 开始合并")
        btn_merge.clicked.connect(self.do_merge_step)
        btn_merge.setMinimumHeight(40)
        layout.addWidget(btn_merge)
        
        layout.addStretch()
        return widget
    
    def create_translate_tab(self):
        """创建翻译标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info = QLabel("🤖 说明：使用AI大模型API翻译新增的日文条目")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # API配置
        api_group = QGroupBox("API配置")
        api_layout = QVBoxLayout()
        
        # 预设选择（新增）
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(200)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        btn_save_preset = QPushButton("💾 保存预设")
        btn_save_preset.clicked.connect(self.save_preset)
        preset_layout.addWidget(btn_save_preset)
        btn_delete_preset = QPushButton("🗑️ 删除")
        btn_delete_preset.clicked.connect(self.delete_preset)
        preset_layout.addWidget(btn_delete_preset)
        preset_layout.addStretch()
        api_layout.addLayout(preset_layout)
        
        # 提供商选择
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("API提供商:"))
        self.api_provider = QComboBox()
        self.api_provider.addItems([
            "OpenAI", 
            "Anthropic (Claude)", 
            "DeepSeek", 
            "Sakura (本地模型)",
            "自定义OpenAI格式"
        ])
        self.api_provider.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(self.api_provider)
        api_layout.addLayout(provider_layout)
        
        # API Key
        self.key_layout_widget = QWidget()  # 包装器，方便隐藏
        key_layout = QHBoxLayout(self.key_layout_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(QLabel("API Key:"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        key_layout.addWidget(self.api_key)
        self.show_key_check = QCheckBox("显示")
        self.show_key_check.stateChanged.connect(self.toggle_api_key_visibility)
        key_layout.addWidget(self.show_key_check)
        api_layout.addWidget(self.key_layout_widget)
        
        # 模型名称
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        self.api_model = QLineEdit()
        self.api_model.setPlaceholderText("留空使用默认模型")
        model_layout.addWidget(self.api_model)
        api_layout.addLayout(model_layout)
        
        # Base URL（自定义时显示）
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Base URL:"))
        self.api_base_url = QLineEdit()
        self.api_base_url.setPlaceholderText("例如: https://api.openai.com/v1")
        url_layout.addWidget(self.api_base_url)
        api_layout.addLayout(url_layout)
        self.api_base_url.setVisible(False)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_save_config = QPushButton("💾 保存API配置")
        btn_save_config.clicked.connect(self.save_config)
        btn_layout.addWidget(btn_save_config)
        
        btn_test = QPushButton("🔗 测试连接")
        btn_test.clicked.connect(self.test_api_connection)
        btn_layout.addWidget(btn_test)
        api_layout.addLayout(btn_layout)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        # 输入文件
        in_layout = QHBoxLayout()
        in_layout.addWidget(QLabel("输入文件:"))
        self.trans_input_file = QLineEdit()
        self.trans_input_file.setPlaceholderText("通常是第一步生成的 _new_entries.json")
        in_layout.addWidget(self.trans_input_file)
        btn_in = QPushButton("浏览...")
        btn_in.clicked.connect(lambda: self.browse_file(self.trans_input_file))
        in_layout.addWidget(btn_in)
        file_layout.addLayout(in_layout)
        
        # 输出文件
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("输出文件:"))
        self.trans_output_file = QLineEdit("translated_new_entries.json")
        out_layout.addWidget(self.trans_output_file)
        btn_out = QPushButton("浏览...")
        btn_out.clicked.connect(lambda: self.browse_save_file(self.trans_output_file))
        out_layout.addWidget(btn_out)
        file_layout.addLayout(out_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 执行按钮
        btn_translate = QPushButton("🤖 开始翻译")
        btn_translate.clicked.connect(self.do_translate_step)
        btn_translate.setMinimumHeight(40)
        layout.addWidget(btn_translate)
        
        layout.addStretch()
        return widget
    
    def create_mergeback_tab(self):
        """创建回写结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info = QLabel("📝 说明：将翻译好的新条目合并回主文件，生成最终版本")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        # 合并文件
        merged_layout = QHBoxLayout()
        merged_layout.addWidget(QLabel("合并文件:"))
        self.back_merged_file = QLineEdit()
        self.back_merged_file.setPlaceholderText("第一步生成的 merged_translation.json")
        merged_layout.addWidget(self.back_merged_file)
        btn_merged = QPushButton("浏览...")
        btn_merged.clicked.connect(lambda: self.browse_file(self.back_merged_file))
        merged_layout.addWidget(btn_merged)
        file_layout.addLayout(merged_layout)
        
        # 翻译文件
        trans_layout = QHBoxLayout()
        trans_layout.addWidget(QLabel("翻译文件:"))
        self.back_trans_file = QLineEdit()
        self.back_trans_file.setPlaceholderText("第二步生成的翻译结果")
        trans_layout.addWidget(self.back_trans_file)
        btn_trans = QPushButton("浏览...")
        btn_trans.clicked.connect(lambda: self.browse_file(self.back_trans_file))
        trans_layout.addWidget(btn_trans)
        file_layout.addLayout(trans_layout)
        
        # 输出文件
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("最终文件:"))
        self.back_output_file = QLineEdit("final_translation.json")
        out_layout.addWidget(self.back_output_file)
        btn_out = QPushButton("浏览...")
        btn_out.clicked.connect(lambda: self.browse_save_file(self.back_output_file))
        out_layout.addWidget(btn_out)
        file_layout.addLayout(out_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 执行按钮
        btn_back = QPushButton("🔄 合并回写")
        btn_back.clicked.connect(self.do_mergeback_step)
        btn_back.setMinimumHeight(40)
        layout.addWidget(btn_back)
        
        layout.addStretch()
        return widget
    
    def create_quality_tab(self):
        """创建质量检查标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        info = QLabel("🔍 说明：检查翻译文件中的漏翻和语序问题")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()
        
        # 原文文件
        orig_layout = QHBoxLayout()
        orig_layout.addWidget(QLabel("原文文件:"))
        self.quality_orig_file = QLineEdit()
        self.quality_orig_file.setPlaceholderText("需要翻译的原文JSON文件")
        orig_layout.addWidget(self.quality_orig_file)
        btn_orig = QPushButton("浏览...")
        btn_orig.clicked.connect(lambda: self.browse_file(self.quality_orig_file))
        orig_layout.addWidget(btn_orig)
        file_layout.addLayout(orig_layout)
        
        # 译文文件
        trans_layout = QHBoxLayout()
        trans_layout.addWidget(QLabel("译文文件:"))
        self.quality_trans_file = QLineEdit()
        self.quality_trans_file.setPlaceholderText("翻译后的JSON文件")
        trans_layout.addWidget(self.quality_trans_file)
        btn_trans = QPushButton("浏览...")
        btn_trans.clicked.connect(lambda: self.browse_file(self.quality_trans_file))
        trans_layout.addWidget(btn_trans)
        file_layout.addLayout(trans_layout)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # 检查选项
        options_group = QGroupBox("检查选项")
        options_layout = QVBoxLayout()
        
        self.check_missing = QCheckBox("检测漏翻（原文未翻译、日文残留）")
        self.check_missing.setChecked(True)
        options_layout.addWidget(self.check_missing)
        
        self.check_order = QCheckBox("检测语序错误（数字单位分离等）")
        self.check_order.setChecked(True)
        options_layout.addWidget(self.check_order)
        
        self.check_ai = QCheckBox("AI辅助检测（更全面，消耗API额度）")
        self.check_ai.setChecked(False)
        options_layout.addWidget(self.check_ai)
        
        # AI检测提示
        ai_hint = QLabel("⚠️ AI检测建议用DeepSeek/GPT等通用模型，Sakura翻译专用不擅长分析")
        ai_hint.setStyleSheet("color: #888; font-size: 11px;")
        options_layout.addWidget(ai_hint)
        
        # AI选择
        ai_select_layout = QHBoxLayout()
        ai_select_layout.addWidget(QLabel("AI来源:"))
        self.quality_ai_source = QComboBox()
        self.quality_ai_source.addItems([
            "使用翻译标签页的API配置",
            "DeepSeek",
            "OpenAI", 
            "Google Gemini",
            "Anthropic (Claude)",
            "Sakura (本地模型)",
            "自定义OpenAI格式"
        ])
        ai_select_layout.addWidget(self.quality_ai_source)
        options_layout.addLayout(ai_select_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_check = QPushButton("🔍 开始检查")
        btn_check.clicked.connect(self.do_quality_check)
        btn_check.setMinimumHeight(40)
        btn_layout.addWidget(btn_check)
        
        btn_export = QPushButton("📄 导出报告")
        btn_export.clicked.connect(self.export_quality_report)
        btn_export.setMinimumHeight(40)
        btn_layout.addWidget(btn_export)
        
        btn_fix = QPushButton("🪄 AI自动修复")
        btn_fix.clicked.connect(self.do_ai_fix)
        btn_fix.setMinimumHeight(40)
        btn_layout.addWidget(btn_fix)
        layout.addLayout(btn_layout)
        
        # 结果显示区域
        result_group = QGroupBox("检查结果")
        result_layout = QVBoxLayout()
        self.quality_result = QTextEdit()
        self.quality_result.setReadOnly(True)
        self.quality_result.setPlaceholderText("检查结果将显示在这里...")
        result_layout.addWidget(self.quality_result)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)
        
        return widget
    
    def browse_file(self, line_edit):
        """浏览选择文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择JSON文件", "", "JSON文件 (*.json);;所有文件 (*)"
        )
        if filename:
            line_edit.setText(filename)
    
    def browse_save_file(self, line_edit):
        """浏览保存文件"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存JSON文件", line_edit.text(), "JSON文件 (*.json);;所有文件 (*)"
        )
        if filename:
            line_edit.setText(filename)
    
    def on_provider_changed(self, provider):
        """API提供商变化时的处理"""
        # 自定义或Sakura时显示Base URL
        is_custom = "自定义" in provider
        is_sakura = "Sakura" in provider
        
        self.api_base_url.setVisible(is_custom or is_sakura)
        
        # Sakura模型时，隐藏API Key输入框
        if is_sakura:
            self.key_layout_widget.setVisible(False)
            self.api_key.setText("")  # 清空key
            self.api_model.setPlaceholderText("模型名称，如: sakura")
            self.api_base_url.setText("http://localhost:11434")  # Ollama默认
            self.api_base_url.setPlaceholderText("Ollama: http://localhost:11434 | LM Studio: http://localhost:1234/v1")
        else:
            self.key_layout_widget.setVisible(True)
            
            # 设置其他提供商的默认模型提示
            if "OpenAI" in provider:
                self.api_model.setPlaceholderText("例如: gpt-3.5-turbo, gpt-4, gpt-4o")
            elif "Claude" in provider:
                self.api_model.setPlaceholderText("例如: claude-sonnet-4-5-20250929")
            elif "DeepSeek" in provider:
                self.api_model.setPlaceholderText("例如: deepseek-chat")
            else:
                self.api_model.setPlaceholderText("输入模型名称")
            
            # 自定义OpenAI格式时显示正确的URL格式
            if is_custom:
                self.api_base_url.setPlaceholderText("例如: https://api.example.com/v1 (需要加/v1)")
    
    def toggle_api_key_visibility(self, state):
        """切换API Key显示/隐藏"""
        if state == Qt.CheckState.Checked.value:
            self.api_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
    
    def test_api_connection(self):
        """测试API连接"""
        provider_text = self.api_provider.currentText()
        api_key = self.api_key.text().strip()
        model = self.api_model.text().strip()
        base_url = self.api_base_url.text().strip() if self.api_base_url.isVisible() else None
        
        # 确定provider
        is_sakura = "Sakura" in provider_text
        
        if not is_sakura and not api_key:
            QMessageBox.warning(self, "警告", "请先填写API Key！")
            return
        
        if "OpenAI" in provider_text:
            provider = "openai"
        elif "Claude" in provider_text:
            provider = "anthropic"
        elif "DeepSeek" in provider_text:
            provider = "deepseek"
        elif is_sakura:
            provider = "sakura"
        else:
            provider = "custom"
        
        self.log("🔗 正在测试API连接...")
        self.statusBar().showMessage("测试连接中...")
        
        try:
            translator = create_translator(provider, api_key or "dummy", model or None, base_url)
            
            # 发送一个简单的测试请求
            test_text = "こんにちは"
            result = translator.translate_single(test_text)
            
            self.log(f"✅ 连接成功！")
            self.log(f"   测试翻译: {test_text} → {result}")
            self.statusBar().showMessage("连接测试成功")
            QMessageBox.information(self, "成功", f"API连接成功！\n\n测试翻译:\n{test_text} → {result}")
        except Exception as e:
            self.log(f"❌ 连接失败: {str(e)}")
            self.statusBar().showMessage("连接测试失败")
            QMessageBox.critical(self, "失败", f"API连接失败:\n{str(e)}")
    
    def log(self, message):
        """添加日志"""
        self.log_text.append(message)
        # 滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def do_merge_step(self):
        """执行合并步骤"""
        new_file = self.merge_new_file.text().strip()
        old_file = self.merge_old_file.text().strip()
        output_file = self.merge_output_file.text().strip()
        
        if not new_file or not old_file or not output_file:
            QMessageBox.warning(self, "警告", "请填写所有文件路径！")
            return
        
        if not Path(new_file).exists():
            QMessageBox.warning(self, "警告", f"新文件不存在: {new_file}")
            return
        
        if not Path(old_file).exists():
            QMessageBox.warning(self, "警告", f"旧文件不存在: {old_file}")
            return
        
        self.log("=" * 60)
        self.log("开始执行第一步：合并文件")
        self.statusBar().showMessage("正在合并文件...")
        
        self.worker = MergeWorker(new_file, old_file, output_file)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_merge_finished)
        self.worker.start()
    
    def on_merge_finished(self, success, message):
        """合并完成"""
        self.log(message)
        self.statusBar().showMessage("就绪")
        
        if success:
            # 自动填充第二步的输入文件
            new_entries_file = self.merge_output_file.text().replace('.json', '_new_entries.json')
            if Path(new_entries_file).exists():
                self.trans_input_file.setText(new_entries_file)
            
            # 自动填充第三步的合并文件
            self.back_merged_file.setText(self.merge_output_file.text())
            
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "失败", message)
    
    def do_translate_step(self):
        """执行翻译步骤"""
        input_file = self.trans_input_file.text().strip()
        output_file = self.trans_output_file.text().strip()
        api_key = self.api_key.text().strip()
        
        if not input_file or not output_file:
            QMessageBox.warning(self, "警告", "请填写输入和输出文件路径！")
            return
        
        # 获取API配置
        provider_text = self.api_provider.currentText()
        
        # Sakura本地模型不需要API Key
        if "Sakura" not in provider_text:
            if not api_key:
                QMessageBox.warning(self, "警告", "请填写API Key！")
                return
        else:
            # Sakura可以没有API Key
            if not api_key:
                api_key = "dummy"
        
        if not Path(input_file).exists():
            QMessageBox.warning(self, "警告", f"输入文件不存在: {input_file}")
            return
        
        # 确定provider
        if "OpenAI" in provider_text:
            provider = "openai"
        elif "Claude" in provider_text:
            provider = "anthropic"
        elif "DeepSeek" in provider_text:
            provider = "deepseek"
        elif "Sakura" in provider_text:
            provider = "sakura"
        else:
            provider = "custom"
        
        model = self.api_model.text().strip()
        base_url = self.api_base_url.text().strip() if self.api_base_url.isVisible() else None
        
        self.log("=" * 60)
        self.log("开始执行第二步：API翻译")
        if provider == "sakura":
            self.log(f"使用本地Sakura模型: {model or 'sakura'}")
            self.log(f"服务地址: {base_url or 'http://localhost:11434'}")
        self.statusBar().showMessage("正在翻译...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = TranslateWorker(input_file, output_file, provider, api_key, model, base_url)
        self.worker.progress.connect(self.log)
        self.worker.progress_value.connect(self.update_progress)
        self.worker.finished.connect(self.on_translate_finished)
        self.worker.start()
    
    def update_progress(self, current, total):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def on_translate_finished(self, success, message):
        """翻译完成"""
        self.log(message)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("就绪")
        
        if success:
            # 自动填充第三步的翻译文件
            self.back_trans_file.setText(self.trans_output_file.text())
            
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.critical(self, "失败", message)
    
    def do_mergeback_step(self):
        """执行回写步骤"""
        merged_file = self.back_merged_file.text().strip()
        trans_file = self.back_trans_file.text().strip()
        output_file = self.back_output_file.text().strip()
        
        if not merged_file or not trans_file or not output_file:
            QMessageBox.warning(self, "警告", "请填写所有文件路径！")
            return
        
        if not Path(merged_file).exists():
            QMessageBox.warning(self, "警告", f"合并文件不存在: {merged_file}")
            return
        
        if not Path(trans_file).exists():
            QMessageBox.warning(self, "警告", f"翻译文件不存在: {trans_file}")
            return
        
        self.log("=" * 60)
        self.log("开始执行第三步：回写合并")
        self.statusBar().showMessage("正在合并...")
        
        self.worker = MergeBackWorker(merged_file, trans_file, output_file)
        self.worker.progress.connect(self.log)
        self.worker.finished.connect(self.on_mergeback_finished)
        self.worker.start()
    
    def on_mergeback_finished(self, success, message):
        """回写完成"""
        self.log(message)
        self.statusBar().showMessage("就绪")
        
        if success:
            QMessageBox.information(self, "完成", 
                f"{message}\n\n🎉 所有步骤已完成！\n最终翻译文件可以直接用于游戏。")
        else:
            QMessageBox.critical(self, "失败", message)
    
    def do_quality_check(self):
        """执行质量检查"""
        orig_file = self.quality_orig_file.text().strip()
        trans_file = self.quality_trans_file.text().strip()
        
        if not orig_file or not trans_file:
            QMessageBox.warning(self, "警告", "请填写原文文件和译文文件路径！")
            return
        
        if not Path(orig_file).exists():
            QMessageBox.warning(self, "警告", f"原文文件不存在: {orig_file}")
            return
        
        if not Path(trans_file).exists():
            QMessageBox.warning(self, "警告", f"译文文件不存在: {trans_file}")
            return
        
        self.log("=" * 60)
        self.log("开始执行质量检查")
        self.statusBar().showMessage("正在检查...")
        self.quality_result.clear()
        
        # 保存质量检查配置
        self.save_quality_config()
        
        # 准备翻译器（如果需要AI检查）
        translator = None
        if self.check_ai.isChecked():
            translator = self.get_quality_translator()
            if translator is None:
                return
        
        self.quality_worker = QualityCheckWorker(
            orig_file, trans_file,
            self.check_missing.isChecked(),
            self.check_order.isChecked(),
            self.check_ai.isChecked(),
            translator
        )
        self.quality_worker.progress.connect(self.log)
        self.quality_worker.finished.connect(self.on_quality_finished)
        self.quality_worker.start()
    
    def on_quality_finished(self, success, message):
        """质量检查完成"""
        self.log(message)
        self.statusBar().showMessage("就绪")
        
        if success and hasattr(self, 'quality_worker') and self.quality_worker.results:
            results = self.quality_worker.results
            
            # 显示结果
            text_lines = []
            text_lines.append(f"📊 检查结果汇总")
            text_lines.append(f"漏翻: {results['summary']['missing_count']} 条")
            text_lines.append(f"语序问题: {results['summary']['order_error_count']} 条")
            if 'ai_issue_count' in results['summary']:
                text_lines.append(f"AI标记: {results['summary']['ai_issue_count']} 条")
            text_lines.append("")
            
            if results["missing_translations"]:
                text_lines.append("=" * 50)
                text_lines.append("📋 漏翻条目:")
                for item in results["missing_translations"][:20]:
                    text_lines.append(f"\n原: {item['original'][:80]}")
                    text_lines.append(f"译: {item['translated'][:80]}")
                    text_lines.append(f"原因: {item['reason']}")
                if len(results["missing_translations"]) > 20:
                    text_lines.append(f"\n... 还有 {len(results['missing_translations']) - 20} 条 ...")
            
            if results["word_order_errors"]:
                text_lines.append("\n" + "=" * 50)
                text_lines.append("⚠️ 语序问题:")
                for item in results["word_order_errors"][:20]:
                    text_lines.append(f"\n原: {item['original'][:80]}")
                    text_lines.append(f"译: {item['translated'][:80]}")
                    text_lines.append(f"问题: {item['error_type']} (检测到: {item['matched']})")
                if len(results["word_order_errors"]) > 20:
                    text_lines.append(f"\n... 还有 {len(results['word_order_errors']) - 20} 条 ...")
            
            if "ai_issues" in results and results["ai_issues"]:
                text_lines.append("\n" + "=" * 50)
                text_lines.append("🤖 AI检测问题:")
                for item in results["ai_issues"][:20]:
                    text_lines.append(f"\n原: {item['original'][:80]}")
                    text_lines.append(f"译: {item['translated'][:80]}")
                    text_lines.append(f"AI意见: {item['ai_reason']}")
            
            self.quality_result.setPlainText("\n".join(text_lines))
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.critical(self, "失败", message)
    
    def export_quality_report(self):
        """导出质量检查报告"""
        if not hasattr(self, 'quality_worker') or not self.quality_worker.results:
            QMessageBox.warning(self, "警告", "请先执行质量检查！")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "quality_report.txt", "文本文件 (*.txt);;所有文件 (*)"
        )
        
        if filename:
            report = generate_report(self.quality_worker.results, filename)
            self.log(f"✅ 报告已导出: {filename}")
            QMessageBox.information(self, "成功", f"报告已导出到:\n{filename}")
    
    def get_quality_translator(self):
        """获取质量检查/修复使用的翻译器"""
        ai_source = self.quality_ai_source.currentText()
        
        if "使用翻译标签页" in ai_source:
            # 使用翻译标签页的配置
            provider_text = self.api_provider.currentText()
            api_key = self.api_key.text().strip()
            model = self.api_model.text().strip()
            # 对于Sakura，始终读取base_url
            base_url = self.api_base_url.text().strip()
            
            if "OpenAI" in provider_text:
                provider = "openai"
            elif "Claude" in provider_text:
                provider = "anthropic"
            elif "DeepSeek" in provider_text:
                provider = "deepseek"
            elif "Sakura" in provider_text:
                provider = "sakura"
            else:
                provider = "custom"
            
            if "Sakura" not in provider_text and not api_key:
                QMessageBox.warning(self, "警告", "请先在API翻译标签页配置API！")
                return None
        else:
            # 使用选择的独立API，优先从.env获取key
            if "DeepSeek" in ai_source:
                provider = "deepseek"
                api_key = self.env_keys.get("DEEPSEEK_API_KEY", "")
                if not api_key:
                    api_key, ok = QInputDialog.getText(self, "DeepSeek API Key", "请输入DeepSeek API Key:")
                    if not ok or not api_key:
                        return None
                model = "deepseek-chat"
                base_url = "https://api.deepseek.com"
            elif "OpenAI" in ai_source:
                provider = "openai"
                api_key = self.env_keys.get("OPENAI_API_KEY", "")
                if not api_key:
                    api_key, ok = QInputDialog.getText(self, "OpenAI API Key", "请输入OpenAI API Key:")
                    if not ok or not api_key:
                        return None
                model = "gpt-4o-mini"
                base_url = "https://api.openai.com/v1"
            elif "Claude" in ai_source:
                provider = "anthropic"
                api_key = self.env_keys.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    api_key, ok = QInputDialog.getText(self, "Anthropic API Key", "请输入Anthropic API Key:")
                    if not ok or not api_key:
                        return None
                model = "claude-3-haiku-20240307"
                base_url = "https://api.anthropic.com"
            elif "Gemini" in ai_source:
                provider = "openai"  # Gemini uses OpenAI-compatible API
                api_key = self.env_keys.get("GEMINI_API_KEY", "")
                if not api_key:
                    api_key, ok = QInputDialog.getText(self, "Gemini API Key", "请输入Gemini API Key:")
                    if not ok or not api_key:
                        return None
                model = "gemini-2.0-flash"
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            elif "Sakura" in ai_source:
                provider = "sakura"
                api_key = "dummy"
                model = "sakura"
                base_url = self.env_keys.get("SAKURA_BASE_URL", "http://127.0.0.1:8080")
            else:
                # 自定义
                api_key, ok = QInputDialog.getText(self, "API Key", "请输入API Key:")
                if not ok:
                    return None
                base_url, ok = QInputDialog.getText(self, "Base URL", "请输入API Base URL:")
                if not ok:
                    return None
                model, ok = QInputDialog.getText(self, "模型", "请输入模型名称:")
                if not ok:
                    return None
                provider = "custom"
        
        try:
            return create_translator(provider, api_key or "dummy", model or None, base_url)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"创建翻译器失败: {e}")
            return None
    
    def do_ai_fix(self):
        """使用AI自动修复检测到的问题"""
        if not hasattr(self, 'quality_worker') or not self.quality_worker.results:
            QMessageBox.warning(self, "警告", "请先执行质量检查！")
            return
        
        results = self.quality_worker.results
        all_issues = results.get("missing_translations", []) + results.get("word_order_errors", [])
        
        if not all_issues:
            QMessageBox.information(self, "提示", "没有检测到需要修复的问题！")
            return
        
        # 确认修复
        reply = QMessageBox.question(self, "确认修复",
            f"检测到 {len(all_issues)} 个问题，是否使用AI自动修复？\n\n"
            f"注意：这将调用API并消耗额度。\n"
            f"修复后会更新译文文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 获取翻译器
        translator = self.get_quality_translator()
        if translator is None:
            return
        
        self.log("🪄 开始AI自动修复...")
        self.statusBar().showMessage("正在修复...")
        
        try:
            
            # 调用修复
            fixes = fix_with_ai(translator, all_issues)
            
            if fixes:
                # 应用修复
                trans_file = self.quality_trans_file.text().strip()
                count = apply_fixes(trans_file, fixes)
                
                self.log(f"✅ AI修复完成！有效修复 {count}/{len(all_issues)} 个条目")
                self.log(f"📝 已更新文件: {trans_file}")
                if count < len(all_issues):
                    self.log(f"⚠️ {len(all_issues) - count} 个条目因修复结果无效而跳过")
                QMessageBox.information(self, "成功", 
                    f"AI修复完成！\n\n有效修复 {count}/{len(all_issues)} 个条目\n已更新文件: {trans_file}")
            else:
                self.log("⚠️ AI未返回有效修复结果")
                self.log("💡 提示: Sakura翻译模型不擅长修复任务，建议换用DeepSeek/GPT")
                QMessageBox.warning(self, "警告", 
                    "AI未返回有效修复结果\n\n"
                    "Sakura是翻译专用模型,不擅长修复任务。\n"
                    "建议切换到DeepSeek/GPT等通用模型进行修复。")
                
        except Exception as e:
            self.log(f"❌ AI修复失败: {str(e)}")
            QMessageBox.critical(self, "失败", f"AI修复失败:\n{str(e)}")
        
        self.statusBar().showMessage("就绪")
    
    def save_config(self):
        """保存API配置"""
        config = {
            "provider": self.api_provider.currentText(),
            "api_key": self.api_key.text(),
            "model": self.api_model.text(),
            "base_url": self.api_base_url.text()
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log("✅ API配置已保存")
            QMessageBox.information(self, "成功", "API配置已保存！")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存配置失败: {e}")
    
    def load_config(self):
        """加载API配置"""
        if not self.config_file.exists():
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 恢复配置
            if "provider" in config:
                index = self.api_provider.findText(config["provider"])
                if index >= 0:
                    self.api_provider.setCurrentIndex(index)
            
            if "api_key" in config:
                self.api_key.setText(config["api_key"])
            
            if "model" in config:
                self.api_model.setText(config["model"])
            
            if "base_url" in config:
                self.api_base_url.setText(config["base_url"])
            
            self.log("✅ 已加载保存的API配置")
        except Exception as e:
            self.log(f"⚠️ 加载配置失败: {e}")
    
    def load_quality_config(self):
        """加载质量检查配置"""
        if not self.quality_config_file.exists():
            return
        
        try:
            with open(self.quality_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 恢复AI来源选择
            if "ai_source" in config:
                index = self.quality_ai_source.findText(config["ai_source"])
                if index >= 0:
                    self.quality_ai_source.setCurrentIndex(index)
            
            # 恢复检查选项
            if "check_missing" in config:
                self.check_missing.setChecked(config["check_missing"])
            if "check_order" in config:
                self.check_order.setChecked(config["check_order"])
            if "check_ai" in config:
                self.check_ai.setChecked(config["check_ai"])
                
        except Exception:
            pass
    
    def save_quality_config(self):
        """保存质量检查配置"""
        config = {
            "ai_source": self.quality_ai_source.currentText(),
            "check_missing": self.check_missing.isChecked(),
            "check_order": self.check_order.isChecked(),
            "check_ai": self.check_ai.isChecked()
        }
        try:
            with open(self.quality_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def load_presets(self):
        """加载API预设列表"""
        self.presets = {}
        if self.presets_file.exists():
            try:
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.presets = data.get("presets", {})
            except Exception as e:
                self.log(f"⚠️ 加载预设失败: {e}")
        
        # 更新下拉框
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("-- 选择预设 --")
        for name in self.presets.keys():
            self.preset_combo.addItem(name)
        self.preset_combo.blockSignals(False)
    
    def save_preset(self):
        """保存当前配置为预设"""
        name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # 保存当前配置到预设
        self.presets[name] = {
            "provider": self.api_provider.currentText(),
            "api_key": self.api_key.text(),
            "model": self.api_model.text(),
            "base_url": self.api_base_url.text()
        }
        
        # 保存到文件
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump({"presets": self.presets}, f, ensure_ascii=False, indent=2)
            
            # 更新下拉框
            self.load_presets()
            # 选中刚保存的预设
            index = self.preset_combo.findText(name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            
            self.log(f"✅ 预设 '{name}' 已保存")
            QMessageBox.information(self, "成功", f"预设 '{name}' 已保存！")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存预设失败: {e}")
    
    def delete_preset(self):
        """删除当前选中的预设"""
        name = self.preset_combo.currentText()
        if name == "-- 选择预设 --" or name not in self.presets:
            QMessageBox.warning(self, "警告", "请先选择一个预设！")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
            f"确定要删除预设 '{name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            del self.presets[name]
            try:
                with open(self.presets_file, 'w', encoding='utf-8') as f:
                    json.dump({"presets": self.presets}, f, ensure_ascii=False, indent=2)
                self.load_presets()
                self.log(f"✅ 预设 '{name}' 已删除")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"删除预设失败: {e}")
    
    def on_preset_changed(self, preset_name):
        """切换预设时加载配置"""
        if preset_name == "-- 选择预设 --" or preset_name not in self.presets:
            return
        
        config = self.presets[preset_name]
        
        # 恢复配置
        if "provider" in config:
            index = self.api_provider.findText(config["provider"])
            if index >= 0:
                self.api_provider.setCurrentIndex(index)
        
        if "api_key" in config:
            self.api_key.setText(config["api_key"])
        
        if "model" in config:
            self.api_model.setText(config["model"])
        
        if "base_url" in config:
            self.api_base_url.setText(config["base_url"])
        
        self.log(f"✅ 已加载预设: {preset_name}")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    window = TranslationGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
