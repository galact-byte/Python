# main.py
import sys
import json
import os
import re
import csv
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, asdict, field
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QSplitter,
    QGroupBox, QComboBox, QSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QTabWidget, QListWidget, QDialog, QDialogButtonBox,
    QFormLayout, QProgressBar, QPlainTextEdit, QScrollArea,
    QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QTextCursor, QPixmap

import aiohttp
import pandas as pd
from fuzzywuzzy import fuzz, process
from PIL import Image
import io


class MatchMode(Enum):
    EXACT_ONLY = "exact_only"
    FUZZY_ONLY = "fuzzy_only"
    EXACT_THEN_FUZZY = "exact_then_fuzzy"

class ImageProcessMode(Enum):
    SINGLE = "single"
    BATCH = "batch"

class ImageAnalysisStep(Enum):
    EXTRACT_WORDS = "extract_words"
    MATCH_TAGS = "match_tags"
    VERIFY_MATCHES = "verify_matches"
    GENERATE_FINAL = "generate_final"


@dataclass
class PromptTemplates:
    """提示词模板配置"""
    # 生成基础词汇
    base_words_system: str = "你是一个专业的图像标签生成助手，精通将自然语言描述转换为精确的英文标签。"
    base_words_user: str = """请将以下描述转换为详细的英文标签词汇列表。
要求：
1. 提取所有关键元素，包括人物、动作、表情、服装、场景等
2. 不要包含颜色形容词
3. 每个词汇用逗号分隔
4. 必须在回复开头使用 WORDS: 标记词汇列表

用户描述: {user_input}

示例格式:
WORDS: girl, smile, long_hair, school_uniform, classroom, standing"""

    # 重新生成词汇
    regenerate_system: str = "你是一个专业的同义词生成助手，精通英文词汇的多种表达方式。"
    regenerate_user: str = """以下词汇未找到标准标签，请为每个词提供多个相似的英文表达：
未匹配词汇: {unmatched_words}

要求：
1. 为每个词提供3-5个同义词或相近表达
2. 使用下划线连接多词组合
3. 必须在回复开头使用 WORDS: 标记词汇列表

示例格式:
WORDS: beautiful_girl, pretty_woman, lovely_lady"""

    # 验证模糊匹配
    verify_fuzzy_system: str = "你是一个专业的语义分析专家，精通判断词汇的语义相似度。"
    verify_fuzzy_user: str = """请根据用户的原始描述，判断以下模糊匹配的标签是否符合原意。

用户原始描述: {user_input}
需要验证的词汇: {original_word}
模糊匹配到的标签候选（按相似度排序）:
{candidates}

要求：
1. 如果有候选标签符合原始描述的含义，选择最符合的一个
2. 如果所有候选都不符合，返回 NONE
3. 必须使用 SELECTED: 标记你选择的标签

示例格式:
SELECTED: long_hair 或 SELECTED: NONE"""

    # 生成最终提示词
    final_prompt_system: str = "你是一个专业的AI绘画提示词生成专家，精通Stable Diffusion提示词的编写。"
    final_prompt_user: str = """请根据用户的原始描述生成一个完整的图像生成提示词。

用户原始描述: {user_input}

已匹配的标准标签（按权重排序）: {matched_tags}
未匹配的词汇: {unmatched_words}

要求：
1. 严格基于用户的原始描述意图
2. 将标签按重要性和逻辑顺序排列
3. 为未匹配的词汇添加适当的颜色或修饰词
4. 未匹配的词汇用括号()标注
5. 必须在回复开头使用 PROMPT: 标记最终提示词

示例格式:
PROMPT: 1girl, beautiful, long_hair, blue_eyes, (fantasy_costume), smile, standing, outdoor"""

    # 图片词汇提取系统提示词
    image_extract_system: str = "你是一个专业的图像分析专家，精通从图像中提取关键词汇和标签。"
    image_extract_user: str = """请仔细分析这张图片，提取出所有可见的元素和特征。

要求：
1. 提取人物特征（性别、年龄、发型、表情等）
2. 提取服装和配饰
3. 提取动作和姿态
4. 提取背景和环境
5. 提取艺术风格和技法特征
6. 只提取英文词汇，用逗号分隔
7. 使用下划线连接多词组合
8. 必须在回复开头使用 WORDS: 标记提取的词汇

请分析图片并提取词汇："""

    # 图片最终提示词生成
    image_final_system: str = "你是一个专业的AI绘画提示词生成专家，精通将图像分析结果组合成完整的Stable Diffusion提示词。"
    image_final_user: str = """基于这张图片和提供的标准标签，生成一个完整的Stable Diffusion提示词。

图片信息：请参考提供的图片内容

已匹配的标准标签: {matched_tags}
未匹配的词汇: {unmatched_words}

要求：
1. 基于图片的实际内容生成提示词
2. 优先使用已匹配的标准标签
3. 将标签按重要性和逻辑顺序排列
4. 未匹配的词汇可以保留但用括号()标注
5. 确保提示词能够重現图片的主要特征
6. 必须在回复开头使用 PROMPT: 标记最终提示词

请生成提示词："""

@dataclass
class Config:
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4-vision-preview"
    temperature: float = 0.7
    max_tokens: int = 2000
    models_cache: List[str] = None
    last_project_path: str = ""
    fuzzy_threshold: int = 80
    max_fuzzy_candidates: int = 5
    match_mode: str = MatchMode.EXACT_THEN_FUZZY.value
    support_image_formats: List[str] = None
    max_image_size: int = 1024
    batch_delay: float = 1.0
    prompt_templates: PromptTemplates = field(default_factory=PromptTemplates)
    
    def __post_init__(self):
        if self.support_image_formats is None:
            self.support_image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    
    def save(self, filepath: str = "config.json"):
        data = asdict(self)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str = "config.json"):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'prompt_templates' in data:
                    data['prompt_templates'] = PromptTemplates(**data['prompt_templates'])
                return cls(**data)
        return cls()

@dataclass
class Project:
    name: str = "未命名项目"
    created_at: str = ""
    modified_at: str = ""
    user_input: str = ""
    generated_prompt: str = ""
    history: List[Dict] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.modified_at:
            self.modified_at = datetime.now().isoformat()
        if self.history is None:
            self.history = []
    
    def save(self, filepath: str):
        self.modified_at = datetime.now().isoformat()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return cls(**data)

class ImageUtils:
    @staticmethod
    def resize_image(image_path: str, max_size: int = 1024) -> Image.Image:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            return img
    
    @staticmethod
    def image_to_base64(image: Image.Image, format: str = 'JPEG') -> str:
        buffer = io.BytesIO()
        image.save(buffer, format=format, quality=85)
        image_bytes = buffer.getvalue()
        return base64.b64encode(image_bytes).decode('utf-8')
    
    @staticmethod
    def get_images_from_folder(folder_path: str, supported_formats: List[str]) -> List[str]:
        image_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if any(file.lower().endswith(fmt.lower()) for fmt in supported_formats):
                    image_files.append(os.path.join(root, file))
        return sorted(image_files)

class TagManager:
    def __init__(self, csv_path: str = None):
        self.tags_df = None
        self.tags_dict = {}  
        self.synonyms_dict = {}  
        self.blacklist = set()
        if csv_path and os.path.exists(csv_path):
            self.load_tags(csv_path)
    
    def load_tags(self, csv_path: str):
        try:
            # 读取CSV文件，假设格式为：tag,category,weight,synonyms
            self.tags_df = pd.read_csv(csv_path, header=None, encoding='utf-8')
            self.tags_df.columns = ['tag', 'category', 'weight', 'synonyms']
            
            # 构建标签字典和同义词字典
            for _, row in self.tags_df.iterrows():
                tag = row['tag']
                weight = row['weight']
                synonyms = str(row['synonyms']).split(',') if pd.notna(row['synonyms']) else []
                
                self.tags_dict[tag] = weight
                
                # 构建同义词映射
                for synonym in synonyms:
                    synonym = synonym.strip()
                    if synonym:
                        self.synonyms_dict[synonym.lower()] = tag
                        
            return True
        except Exception as e:
            print(f"加载标签库失败: {e}")
            return False
    
    def search_tags(self, words: List[str], match_mode: MatchMode, threshold: int = 80) -> Dict[str, Tuple[str, int, float]]:
        """
        搜索标签
        返回: {原词: (匹配的标准tag, 权重, 相似度分数)}
        """
        results = {}
        
        for word in words:
            word_lower = word.lower().strip()
            
            if match_mode == MatchMode.EXACT_ONLY:
                result = self._exact_match(word_lower)
                if result:
                    results[word] = result
                else:
                    results[word] = (None, 0, 0.0)
                    
            elif match_mode == MatchMode.FUZZY_ONLY:
                candidates = self.fuzzy_match(word_lower, threshold)
                if candidates:
                    results[word] = candidates
                else:
                    results[word] = (None, 0, 0.0)
                    
            elif match_mode == MatchMode.EXACT_THEN_FUZZY:
                result = self._exact_match(word_lower)
                if result:
                    results[word] = result
                else:
                    candidates = self.fuzzy_match(word_lower, threshold)
                    if candidates:
                        results[word] = candidates
                    else:
                        results[word] = (None, 0, 0.0)
        
        return results
    
    def _exact_match(self, word: str) -> Optional[Tuple[str, int, float]]:
        if word in self.tags_dict and word not in self.blacklist:
            return (word, self.tags_dict[word], 100.0)
        
        if word in self.synonyms_dict and self.synonyms_dict[word] not in self.blacklist:
            standard_tag = self.synonyms_dict[word]
            return (standard_tag, self.tags_dict[standard_tag], 95.0)
        
        return None
    
    def fuzzy_match(self, word: str, threshold: int = 80, max_candidates: int = 5) -> List[Tuple[str, int, float]]:
        candidates = []
        
        for tag in self.tags_dict.keys():
            if tag in self.blacklist:
                continue
                
            score = fuzz.ratio(word, tag)
            if score >= threshold:
                candidates.append((tag, self.tags_dict[tag], score))
        
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[:max_candidates]
    
    def add_to_blacklist(self, tag: str):
        self.blacklist.add(tag)
    
    def clear_blacklist(self):
        self.blacklist.clear()

class OpenAIClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            async with self.session.get(
                f"{self.config.api_base}/models",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model['id'] for model in data.get('data', [])]
                    return models
                else:
                    return []
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []
    
    async def chat_completion(self, messages: List[Dict], stream: bool = True):
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": stream
        }
        
        try:
            async with self.session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if stream:
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            if line == "data: [DONE]":
                                break
                            try:
                                data = json.loads(line[6:])
                                if 'choices' in data and data['choices']:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
                else:
                    data = await response.json()
                    if 'choices' in data and data['choices']:
                        yield data['choices'][0]['message']['content']
        except Exception as e:
            yield f"错误: {str(e)}"
    
    async def extract_image_words(self, image_base64: str) -> str:
        """从图片中提取词汇"""
        messages = [
            {
                "role": "system",
                "content": self.config.prompt_templates.image_extract_system
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.config.prompt_templates.image_extract_user},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        response_text = ""
        async for chunk in self.chat_completion(messages, stream=True):
            response_text += chunk
        
        return response_text
    
    async def generate_final_image_prompt(self, image_base64: str, matched_tags: List[str], unmatched_words: List[str]) -> str:
        """基于图片和标签生成最终提示词"""
        prompt = self.config.prompt_templates.image_final_user.format(
            matched_tags=', '.join(matched_tags),
            unmatched_words=', '.join(unmatched_words) if unmatched_words else '无'
        )
        
        messages = [
            {
                "role": "system",
                "content": self.config.prompt_templates.image_final_system
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        response_text = ""
        async for chunk in self.chat_completion(messages, stream=True):
            response_text += chunk
        
        return response_text

class ImageWorkerThread(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str, str)  # (image_path, prompt)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    batch_progress_signal = pyqtSignal(int, int)  # (current, total)
    step_progress_signal = pyqtSignal(str, int)  # (step_name, progress)
    
    def __init__(self, config: Config, tag_manager: TagManager):
        super().__init__()
        self.config = config
        self.tag_manager = tag_manager
        self.image_paths = []
        self.is_running = False
        self.process_mode = ImageProcessMode.SINGLE
        self.match_mode = MatchMode.EXACT_THEN_FUZZY
        
    def run(self):
        self.is_running = True
        self.tag_manager.clear_blacklist()
        asyncio.run(self.process_images())
    
    async def process_images(self):
        try:
            total_images = len(self.image_paths)
            self.log_signal.emit(f"开始处理 {total_images} 张图片")
            
            async with OpenAIClient(self.config) as client:
                for i, image_path in enumerate(self.image_paths):
                    if not self.is_running:
                        break
                    
                    self.log_signal.emit(f"正在处理图片: {os.path.basename(image_path)}")
                    self.batch_progress_signal.emit(i + 1, total_images)
                    
                    try:
                        # 处理单张图片
                        result = await self.process_single_image(client, image_path)
                        
                        self.result_signal.emit(image_path, result)
                        self.log_signal.emit(f"✓ {os.path.basename(image_path)} 处理完成")
                        
                        # 批量处理时添加延迟
                        if self.process_mode == ImageProcessMode.BATCH and i < total_images - 1:
                            await asyncio.sleep(self.config.batch_delay)
                            
                    except Exception as e:
                        self.log_signal.emit(f"✗ {os.path.basename(image_path)} 处理失败: {str(e)}")
                        self.result_signal.emit(image_path, f"处理失败: {str(e)}")
                
                self.log_signal.emit(f"图片处理完成，共处理 {len(self.image_paths)} 张图片")
                
        except Exception as e:
            self.log_signal.emit(f"图片处理错误: {str(e)}")
        finally:
            self.finished_signal.emit()
            self.is_running = False
    
    async def process_single_image(self, client: OpenAIClient, image_path: str) -> str:
        """处理单张图片的完整流程"""
        try:
            # 加载和处理图片
            self.step_progress_signal.emit("加载图片", 10)
            image = ImageUtils.resize_image(image_path, self.config.max_image_size)
            image_base64 = ImageUtils.image_to_base64(image)
            
            # 提取词汇
            self.step_progress_signal.emit("提取词汇", 25)
            self.log_signal.emit("  正在提取图片词汇...")
            words_response = await client.extract_image_words(image_base64)
            
            # 解析提取的词汇
            words = self.extract_words_from_response(words_response)
            if words:
                self.log_signal.emit(f"  提取到词汇: {', '.join(words)}")
            else:
                self.log_signal.emit("  未能提取到有效词汇")
                return "无法从图片中提取出有效的词汇"
            
            # 标签库匹配
            self.step_progress_signal.emit("匹配标签", 50)
            self.log_signal.emit("  正在匹配标签库...")
            
            # 搜索标签（最多3次）
            final_tags = {}
            unmatched_words = []
            
            for attempt in range(3):
                self.log_signal.emit(f"    第{attempt + 1}次匹配...")
                
                search_results = self.tag_manager.search_tags(
                    words, 
                    self.match_mode,
                    threshold=self.config.fuzzy_threshold
                )
                
                # 处理搜索结果
                matched_tags = {}
                fuzzy_candidates = {}
                unmatched = []
                
                for word, result in search_results.items():
                    if isinstance(result, list):  # 模糊匹配候选
                        if self.match_mode != MatchMode.EXACT_ONLY:
                            fuzzy_candidates[word] = result
                        else:
                            unmatched.append(word)
                    elif result[0]:  # 精确匹配
                        matched_tags[result[0]] = result[1]
                        self.log_signal.emit(f"    ✓ '{word}' -> '{result[0]}' (权重: {result[1]})")
                    else:  # 未匹配
                        unmatched.append(word)
                        self.log_signal.emit(f"    ✗ '{word}' 未找到匹配")
                
                # 验证模糊匹配
                if fuzzy_candidates and self.match_mode != MatchMode.EXACT_ONLY:
                    self.log_signal.emit(f"    验证{len(fuzzy_candidates)}个模糊匹配...")
                    verified_tags = await self.verify_fuzzy_matches_for_image(
                        client, image_path, fuzzy_candidates
                    )
                    
                    for word, (tag, weight) in verified_tags.items():
                        if tag:
                            matched_tags[tag] = weight
                            self.log_signal.emit(f"    ✓ '{word}' -> '{tag}' (模糊匹配，权重: {weight})")
                        else:
                            unmatched.append(word)
                            self.log_signal.emit(f"    ✗ '{word}' 模糊匹配验证失败")
                
                # 更新最终标签
                final_tags.update(matched_tags)
                
                if not unmatched or attempt == 2:
                    unmatched_words = unmatched
                    break
                
                # 重新生成未匹配词汇
                self.log_signal.emit(f"    重新生成未匹配词汇: {', '.join(unmatched)}")
                words = await self.regenerate_words_for_image(client, unmatched)
            
            # 生成最终提示词
            self.step_progress_signal.emit("生成提示词", 75)
            self.log_signal.emit("  正在生成最终提示词...")
            
            # 按权重排序标签
            sorted_tags = sorted(final_tags.items(), key=lambda x: x[1], reverse=True)
            tags_list = [tag for tag, _ in sorted_tags]
            
            # 使用图片和标签生成最终提示词
            final_response = await client.generate_final_image_prompt(
                image_base64, tags_list, unmatched_words
            )
            
            # 提取最终提示词
            match = re.search(r'PROMPT:\s*(.+)', final_response, re.IGNORECASE | re.DOTALL)
            if match:
                final_prompt = match.group(1).strip()
            else:
                # 如果没有找到标记，手动组合
                all_tags = tags_list.copy()
                for word in unmatched_words:
                    all_tags.append(f"({word})")
                final_prompt = ', '.join(all_tags)
            
            self.step_progress_signal.emit("完成", 100)
            return final_prompt
            
        except Exception as e:
            self.log_signal.emit(f"  处理图片时发生错误: {str(e)}")
            return f"处理失败: {str(e)}"
    
    def extract_words_from_response(self, response: str) -> List[str]:
        """从AI响应中提取词汇列表"""
        match = re.search(r'WORDS:\s*(.+)', response, re.IGNORECASE)
        if match:
            words_str = match.group(1).strip()
            words = [w.strip() for w in words_str.split(',') if w.strip()]
            return words
        return []
    
    async def verify_fuzzy_matches_for_image(self, client: OpenAIClient, image_path: str,
                                           fuzzy_candidates: Dict[str, List[Tuple[str, int, float]]]) -> Dict[str, Tuple[str, int]]:
        """为图片验证模糊匹配的标签"""
        verified = {}
        
        for word, candidates in fuzzy_candidates.items():
            # 格式化候选列表
            candidates_str = "\n".join([
                f"{i+1}. {tag} (相似度: {score:.1f}%, 权重: {weight})"
                for i, (tag, weight, score) in enumerate(candidates)
            ])
            
            # 使用图片名称作为上下文
            image_context = f"图片文件: {os.path.basename(image_path)}"
            
            prompt = self.config.prompt_templates.verify_fuzzy_user.format(
                user_input=image_context,
                original_word=word,
                candidates=candidates_str
            )
            
            messages = [
                {"role": "system", "content": self.config.prompt_templates.verify_fuzzy_system},
                {"role": "user", "content": prompt}
            ]
            
            response_text = ""
            async for chunk in client.chat_completion(messages, stream=True):
                response_text += chunk
            
            # 提取选择结果
            match = re.search(r'SELECTED:\s*(.+)', response_text, re.IGNORECASE)
            if match:
                selected = match.group(1).strip()
                
                if selected.upper() != 'NONE':
                    # 在候选中找到选中的标签
                    for tag, weight, _ in candidates:
                        if tag == selected:
                            verified[word] = (tag, weight)
                            break
                    else:
                        # 如果没找到，将标签加入黑名单
                        for tag, _, _ in candidates:
                            self.tag_manager.add_to_blacklist(tag)
                        verified[word] = (None, 0)
                else:
                    # AI判定所有候选都不符合，加入黑名单
                    for tag, _, _ in candidates:
                        self.tag_manager.add_to_blacklist(tag)
                    verified[word] = (None, 0)
            else:
                verified[word] = (None, 0)
        
        return verified
    
    async def regenerate_words_for_image(self, client: OpenAIClient, unmatched: List[str]) -> List[str]:
        """为图片重新生成未匹配的词汇"""
        prompt = self.config.prompt_templates.regenerate_user.format(
            unmatched_words=', '.join(unmatched)
        )
        
        messages = [
            {"role": "system", "content": self.config.prompt_templates.regenerate_system},
            {"role": "user", "content": prompt}
        ]
        
        response_text = ""
        async for chunk in client.chat_completion(messages, stream=True):
            response_text += chunk
            
        match = re.search(r'WORDS:\s*(.+)', response_text, re.IGNORECASE)
        if match:
            words_str = match.group(1).strip()
            words = [w.strip() for w in words_str.split(',') if w.strip()]
            return words
        
        return []
    
    def stop(self):
        self.is_running = False

class AIWorkerThread(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    
    def __init__(self, config: Config, tag_manager: TagManager):
        super().__init__()
        self.config = config
        self.tag_manager = tag_manager
        self.user_input = ""
        self.is_running = False
        self.match_mode = MatchMode.EXACT_THEN_FUZZY
        
    def run(self):
        self.is_running = True
        self.tag_manager.clear_blacklist()
        asyncio.run(self.process_ai_request())
        
    async def process_ai_request(self):
        try:
            self.log_signal.emit(f"[{datetime.now().strftime('%H:%M:%S')}] 开始处理用户输入: {self.user_input}")
            self.log_signal.emit(f"匹配模式: {self.match_mode.value}")
            self.progress_signal.emit(10)
            
            async with OpenAIClient(self.config) as client:
                # 生成基础词汇
                self.log_signal.emit("正在生成基础词汇...")
                base_words = await self.generate_base_words(client, self.user_input)
                self.progress_signal.emit(20)
                
                if not self.is_running:
                    return
                
                # 查询和验证标签（最多3次）
                final_tags = {}
                unmatched_words = []
                
                for attempt in range(3):
                    self.log_signal.emit(f"第{attempt + 1}次查询标签...")
                    
                    # 搜索标签
                    search_results = self.tag_manager.search_tags(
                        base_words, 
                        self.match_mode,
                        threshold=self.config.fuzzy_threshold
                    )
                    
                    # 处理搜索结果
                    matched_tags = {}
                    fuzzy_candidates = {}
                    unmatched = []
                    
                    for word, result in search_results.items():
                        if isinstance(result, list):  # 模糊匹配候选
                            if self.match_mode != MatchMode.EXACT_ONLY:
                                fuzzy_candidates[word] = result
                            else:
                                unmatched.append(word)
                        elif result[0]:  # 精确匹配
                            matched_tags[result[0]] = result[1]
                            self.log_signal.emit(f"✓ '{word}' -> '{result[0]}' (权重: {result[1]})")
                        else:  # 未匹配
                            unmatched.append(word)
                            self.log_signal.emit(f"✗ '{word}' 未找到匹配")
                    
                    # 验证模糊匹配
                    if fuzzy_candidates and self.match_mode != MatchMode.EXACT_ONLY:
                        self.log_signal.emit(f"正在验证{len(fuzzy_candidates)}个模糊匹配...")
                        verified_tags = await self.verify_fuzzy_matches(
                            client, self.user_input, fuzzy_candidates
                        )
                        
                        for word, (tag, weight) in verified_tags.items():
                            if tag:
                                matched_tags[tag] = weight
                                self.log_signal.emit(f"✓ '{word}' -> '{tag}' (模糊匹配，权重: {weight})")
                            else:
                                unmatched.append(word)
                                self.log_signal.emit(f"✗ '{word}' 模糊匹配验证失败")
                    
                    # 更新最终标签
                    final_tags.update(matched_tags)
                    
                    if not unmatched or attempt == 2:
                        unmatched_words = unmatched
                        break
                    
                    # 重新生成未匹配的词汇
                    self.log_signal.emit(f"重新生成未匹配词汇: {', '.join(unmatched)}")
                    base_words = await self.regenerate_words(client, unmatched)
                    self.progress_signal.emit(20 + (attempt + 1) * 20)
                
                if not self.is_running:
                    return
                
                # 生成最终提示词
                self.log_signal.emit("正在生成最终提示词...")
                
                # 按权重排序标签
                sorted_tags = sorted(final_tags.items(), key=lambda x: x[1], reverse=True)
                tags_list = [tag for tag, _ in sorted_tags]
                
                final_prompt = await self.generate_final_prompt(
                    client, self.user_input, tags_list, unmatched_words
                )
                self.progress_signal.emit(100)
                
                self.result_signal.emit(final_prompt)
                self.log_signal.emit(f"[{datetime.now().strftime('%H:%M:%S')}] 处理完成")
                
        except Exception as e:
            self.log_signal.emit(f"错误: {str(e)}")
        finally:
            self.finished_signal.emit()
            self.is_running = False
    
    async def generate_base_words(self, client: OpenAIClient, user_input: str) -> List[str]:
        prompt = self.config.prompt_templates.base_words_user.format(user_input=user_input)
        
        messages = [
            {"role": "system", "content": self.config.prompt_templates.base_words_system},
            {"role": "user", "content": prompt}
        ]
        
        response_text = ""
        async for chunk in client.chat_completion(messages, stream=True):
            response_text += chunk
            
        match = re.search(r'WORDS:\s*(.+)', response_text, re.IGNORECASE)
        if match:
            words_str = match.group(1).strip()
            words = [w.strip() for w in words_str.split(',') if w.strip()]
            self.log_signal.emit(f"生成词汇: {', '.join(words)}")
            return words
        
        return []
    
    async def verify_fuzzy_matches(self, client: OpenAIClient, user_input: str, 
                                  fuzzy_candidates: Dict[str, List[Tuple[str, int, float]]]) -> Dict[str, Tuple[str, int]]:
        verified = {}
        
        for word, candidates in fuzzy_candidates.items():
            candidates_str = "\n".join([
                f"{i+1}. {tag} (相似度: {score:.1f}%, 权重: {weight})"
                for i, (tag, weight, score) in enumerate(candidates)
            ])
            
            prompt = self.config.prompt_templates.verify_fuzzy_user.format(
                user_input=user_input,
                original_word=word,
                candidates=candidates_str
            )
            
            messages = [
                {"role": "system", "content": self.config.prompt_templates.verify_fuzzy_system},
                {"role": "user", "content": prompt}
            ]
            
            response_text = ""
            async for chunk in client.chat_completion(messages, stream=True):
                response_text += chunk
            
            match = re.search(r'SELECTED:\s*(.+)', response_text, re.IGNORECASE)
            if match:
                selected = match.group(1).strip()
                
                if selected.upper() != 'NONE':
                    for tag, weight, _ in candidates:
                        if tag == selected:
                            verified[word] = (tag, weight)
                            break
                    else:
                        for tag, _, _ in candidates:
                            self.tag_manager.add_to_blacklist(tag)
                        verified[word] = (None, 0)
                else:
                    for tag, _, _ in candidates:
                        self.tag_manager.add_to_blacklist(tag)
                    verified[word] = (None, 0)
            else:
                verified[word] = (None, 0)
        
        return verified
    
    async def regenerate_words(self, client: OpenAIClient, unmatched: List[str]) -> List[str]:
        prompt = self.config.prompt_templates.regenerate_user.format(
            unmatched_words=', '.join(unmatched)
        )
        
        messages = [
            {"role": "system", "content": self.config.prompt_templates.regenerate_system},
            {"role": "user", "content": prompt}
        ]
        
        response_text = ""
        async for chunk in client.chat_completion(messages, stream=True):
            response_text += chunk
            
        match = re.search(r'WORDS:\s*(.+)', response_text, re.IGNORECASE)
        if match:
            words_str = match.group(1).strip()
            words = [w.strip() for w in words_str.split(',') if w.strip()]
            return words
        
        return []
    
    async def generate_final_prompt(self, client: OpenAIClient, user_input: str,
                                   matched_tags: List[str], unmatched_words: List[str]) -> str:
        prompt = self.config.prompt_templates.final_prompt_user.format(
            user_input=user_input,
            matched_tags=', '.join(matched_tags),
            unmatched_words=', '.join(unmatched_words) if unmatched_words else '无'
        )
        
        messages = [
            {"role": "system", "content": self.config.prompt_templates.final_prompt_system},
            {"role": "user", "content": prompt}
        ]
        
        response_text = ""
        async for chunk in client.chat_completion(messages, stream=True):
            response_text += chunk
            
        match = re.search(r'PROMPT:\s*(.+)', response_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        
        all_tags = matched_tags.copy()
        for word in unmatched_words:
            all_tags.append(f"({word})")
        return ', '.join(all_tags)
    
    def stop(self):
        self.is_running = False

class ImageBatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片批量处理结果")
        self.setModal(True)
        self.resize(1000, 600)
        self.results = {}
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["图片路径", "生成的提示词", "操作"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table)
        
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_results)
        
        self.copy_all_btn = QPushButton("复制所有提示词")
        self.copy_all_btn.clicked.connect(self.copy_all_prompts)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.copy_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def add_result(self, image_path: str, prompt: str):
        self.results[image_path] = prompt
        
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(image_path)))
        self.table.setItem(row, 1, QTableWidgetItem(prompt))
        
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(lambda: self.copy_prompt(prompt))
        self.table.setCellWidget(row, 2, copy_btn)
    
    def copy_prompt(self, prompt: str):
        QApplication.clipboard().setText(prompt)
        QMessageBox.information(self, "提示", "提示词已复制到剪贴板")
    
    def copy_all_prompts(self):
        all_prompts = []
        for image_path, prompt in self.results.items():
            all_prompts.append(f"# {os.path.basename(image_path)}\n{prompt}\n")
        
        combined_text = "\n".join(all_prompts)
        QApplication.clipboard().setText(combined_text)
        QMessageBox.information(self, "提示", f"已复制 {len(self.results)} 个提示词到剪贴板")
    
    def export_results(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出批量处理结果",
            "batch_results.txt",
            "Text Files (*.txt);;JSON Files (*.json)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.results, f, indent=2, ensure_ascii=False)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        for image_path, prompt in self.results.items():
                            f.write(f"# {os.path.basename(image_path)}\n")
                            f.write(f"{prompt}\n\n")
                
                QMessageBox.information(self, "成功", f"结果已导出到: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

class PromptEditorDialog(QDialog):
    def __init__(self, prompt_templates: PromptTemplates, parent=None):
        super().__init__(parent)
        self.prompt_templates = prompt_templates
        self.setWindowTitle("提示词模板编辑器")
        self.setModal(True)
        self.resize(800, 600)
        
        self.inputs = {}
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tab_widget = QTabWidget()
        
        # 基础词汇生成标签页
        base_tab = self.create_prompt_tab(
            "base_words",
            "基础词汇生成",
            self.prompt_templates.base_words_system,
            self.prompt_templates.base_words_user
        )
        
        # 重新生成词汇标签页
        regenerate_tab = self.create_prompt_tab(
            "regenerate",
            "重新生成词汇",
            self.prompt_templates.regenerate_system,
            self.prompt_templates.regenerate_user
        )
        
        # 验证模糊匹配标签页
        verify_tab = self.create_prompt_tab(
            "verify_fuzzy",
            "验证模糊匹配",
            self.prompt_templates.verify_fuzzy_system,
            self.prompt_templates.verify_fuzzy_user
        )
        
        # 最终提示词生成标签页
        final_tab = self.create_prompt_tab(
            "final_prompt",
            "最终提示词生成",
            self.prompt_templates.final_prompt_system,
            self.prompt_templates.final_prompt_user
        )
        
        # 图片词汇提取标签页
        image_extract_tab = self.create_prompt_tab(
            "image_extract",
            "图片词汇提取",
            self.prompt_templates.image_extract_system,
            self.prompt_templates.image_extract_user
        )
        
        # 图片最终生成标签页
        image_final_tab = self.create_prompt_tab(
            "image_final",
            "图片最终生成",
            self.prompt_templates.image_final_system,
            self.prompt_templates.image_final_user
        )
        
        self.tab_widget.addTab(base_tab, "基础词汇")
        self.tab_widget.addTab(regenerate_tab, "重新生成")
        self.tab_widget.addTab(verify_tab, "模糊验证")
        self.tab_widget.addTab(final_tab, "最终生成")
        self.tab_widget.addTab(image_extract_tab, "图片提取")
        self.tab_widget.addTab(image_final_tab, "图片生成")
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.save_templates)
        buttons.rejected.connect(self.reject)
        
        restore_btn = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        restore_btn.clicked.connect(self.restore_defaults)
        
        layout.addWidget(self.tab_widget)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def create_prompt_tab(self, name: str, title: str, system_prompt: str, user_prompt: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 系统提示词组
        system_group = QGroupBox("系统提示词")
        system_layout = QVBoxLayout()
        system_input = QPlainTextEdit()
        system_input.setPlainText(system_prompt)
        system_input.setMinimumHeight(120)
        system_layout.addWidget(system_input)
        system_group.setLayout(system_layout)
        
        # 用户提示词组
        user_group = QGroupBox("用户提示词")
        user_layout = QVBoxLayout()
        user_input = QPlainTextEdit()
        user_input.setPlainText(user_prompt)
        user_input.setMinimumHeight(200)
        
        # 变量说明标签
        variables_label = QLabel()
        variables_label.setStyleSheet("color: #666; font-style: italic;")
        if "base_words" in name:
            variables_label.setText("可用变量: {user_input}")
        elif "regenerate" in name:
            variables_label.setText("可用变量: {unmatched_words}")
        elif "verify_fuzzy" in name:
            variables_label.setText("可用变量: {user_input}, {original_word}, {candidates}")
        elif "final_prompt" in name:
            variables_label.setText("可用变量: {user_input}, {matched_tags}, {unmatched_words}")
        elif "image_extract" in name:
            variables_label.setText("图片词汇提取模板，配合图片输入使用")
        elif "image_final" in name:
            variables_label.setText("可用变量: {matched_tags}, {unmatched_words}，配合图片输入使用")
        
        user_layout.addWidget(variables_label)
        user_layout.addWidget(user_input)
        user_group.setLayout(user_layout)
        
        # 保存输入框引用
        self.inputs[f"{name}_system"] = system_input
        self.inputs[f"{name}_user"] = user_input
        
        layout.addWidget(system_group)
        layout.addWidget(user_group)
        widget.setLayout(layout)
        
        return widget
    
    def save_templates(self):
        """保存模板"""
        try:
            self.prompt_templates.base_words_system = self.inputs["base_words_system"].toPlainText()
            self.prompt_templates.base_words_user = self.inputs["base_words_user"].toPlainText()
            
            self.prompt_templates.regenerate_system = self.inputs["regenerate_system"].toPlainText()
            self.prompt_templates.regenerate_user = self.inputs["regenerate_user"].toPlainText()
            
            self.prompt_templates.verify_fuzzy_system = self.inputs["verify_fuzzy_system"].toPlainText()
            self.prompt_templates.verify_fuzzy_user = self.inputs["verify_fuzzy_user"].toPlainText()
            
            self.prompt_templates.final_prompt_system = self.inputs["final_prompt_system"].toPlainText()
            self.prompt_templates.final_prompt_user = self.inputs["final_prompt_user"].toPlainText()
            
            self.prompt_templates.image_extract_system = self.inputs["image_extract_system"].toPlainText()
            self.prompt_templates.image_extract_user = self.inputs["image_extract_user"].toPlainText()
            
            self.prompt_templates.image_final_system = self.inputs["image_final_system"].toPlainText()
            self.prompt_templates.image_final_user = self.inputs["image_final_user"].toPlainText()
            
            self.accept()
        except KeyError as e:
            QMessageBox.critical(self, "错误", f"保存模板时出错: 未找到输入框 {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存模板时出错: {str(e)}")
    
    def restore_defaults(self):
        """恢复默认值"""
        try:
            default_templates = PromptTemplates()
            
            self.inputs["base_words_system"].setPlainText(default_templates.base_words_system)
            self.inputs["base_words_user"].setPlainText(default_templates.base_words_user)
            
            self.inputs["regenerate_system"].setPlainText(default_templates.regenerate_system)
            self.inputs["regenerate_user"].setPlainText(default_templates.regenerate_user)
            
            self.inputs["verify_fuzzy_system"].setPlainText(default_templates.verify_fuzzy_system)
            self.inputs["verify_fuzzy_user"].setPlainText(default_templates.verify_fuzzy_user)
            
            self.inputs["final_prompt_system"].setPlainText(default_templates.final_prompt_system)
            self.inputs["final_prompt_user"].setPlainText(default_templates.final_prompt_user)
            
            self.inputs["image_extract_system"].setPlainText(default_templates.image_extract_system)
            self.inputs["image_extract_user"].setPlainText(default_templates.image_extract_user)
            
            self.inputs["image_final_system"].setPlainText(default_templates.image_final_system)
            self.inputs["image_final_user"].setPlainText(default_templates.image_final_user)
            
            QMessageBox.information(self, "提示", "已恢复默认提示词模板")
            
        except KeyError as e:
            QMessageBox.critical(self, "错误", f"恢复默认值时出错: 未找到输入框 {e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复默认值时出错: {str(e)}")

class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(700, 650)
        
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        tab_widget = QTabWidget()
        
        # API设置标签页
        api_tab = QWidget()
        api_layout = QVBoxLayout()
        
        api_group = QGroupBox("API设置")
        api_form = QFormLayout()
        
        self.api_base_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        api_form.addRow("API地址:", self.api_base_input)
        api_form.addRow("API密钥:", self.api_key_input)
        
        model_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.refresh_models_btn = QPushButton("刷新模型列表")
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.refresh_models_btn)
        api_form.addRow("模型:", model_layout)
        
        api_group.setLayout(api_form)
        
        params_group = QGroupBox("生成参数")
        params_form = QFormLayout()
        
        self.temperature_spin = QSpinBox()
        self.temperature_spin.setRange(0, 100)
        self.temperature_spin.setSuffix(" %")
        
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8000)
        self.max_tokens_spin.setSingleStep(100)
        
        params_form.addRow("Temperature:", self.temperature_spin)
        params_form.addRow("Max Tokens:", self.max_tokens_spin)
        
        params_group.setLayout(params_form)
        
        api_layout.addWidget(api_group)
        api_layout.addWidget(params_group)
        api_layout.addStretch()
        api_tab.setLayout(api_layout)
        
        # 匹配设置标签页
        match_tab = QWidget()
        match_layout = QVBoxLayout()
        
        match_mode_group = QGroupBox("匹配模式")
        match_mode_layout = QVBoxLayout()
        
        self.match_mode_group = QButtonGroup()
        
        self.exact_only_radio = QRadioButton("仅精确匹配")
        self.exact_only_radio.setToolTip("只进行精确匹配和同义词匹配")
        
        self.fuzzy_only_radio = QRadioButton("仅模糊匹配")
        self.fuzzy_only_radio.setToolTip("只进行模糊匹配，不进行精确匹配")
        
        self.exact_then_fuzzy_radio = QRadioButton("精确匹配优先")
        self.exact_then_fuzzy_radio.setToolTip("先尝试精确匹配，失败后进行模糊匹配")
        
        self.match_mode_group.addButton(self.exact_only_radio)
        self.match_mode_group.addButton(self.fuzzy_only_radio)
        self.match_mode_group.addButton(self.exact_then_fuzzy_radio)
        
        match_mode_layout.addWidget(self.exact_only_radio)
        match_mode_layout.addWidget(self.fuzzy_only_radio)
        match_mode_layout.addWidget(self.exact_then_fuzzy_radio)
        match_mode_group.setLayout(match_mode_layout)
        
        match_params_group = QGroupBox("匹配参数")
        match_params_form = QFormLayout()
        
        self.fuzzy_threshold_spin = QSpinBox()
        self.fuzzy_threshold_spin.setRange(50, 100)
        self.fuzzy_threshold_spin.setSuffix(" %")
        
        self.max_candidates_spin = QSpinBox()
        self.max_candidates_spin.setRange(1, 10)
        
        match_params_form.addRow("模糊匹配阈值:", self.fuzzy_threshold_spin)
        match_params_form.addRow("最大候选数:", self.max_candidates_spin)
        
        match_params_group.setLayout(match_params_form)
        
        match_layout.addWidget(match_mode_group)
        match_layout.addWidget(match_params_group)
        match_layout.addStretch()
        match_tab.setLayout(match_layout)
        
        # 图像设置标签页
        image_tab = QWidget()
        image_layout = QVBoxLayout()
        
        image_group = QGroupBox("图像处理设置")
        image_form = QFormLayout()
        
        self.max_image_size_spin = QSpinBox()
        self.max_image_size_spin.setRange(256, 2048)
        self.max_image_size_spin.setSingleStep(64)
        self.max_image_size_spin.setSuffix(" px")
        
        self.batch_delay_spin = QSpinBox()
        self.batch_delay_spin.setRange(0, 10)
        self.batch_delay_spin.setSuffix(" 秒")
        
        image_form.addRow("最大图片尺寸:", self.max_image_size_spin)
        image_form.addRow("批量处理延迟:", self.batch_delay_spin)
        
        formats_label = QLabel("支持的图片格式:")
        formats_text = QLabel(", ".join(self.config.support_image_formats))
        image_form.addRow(formats_label, formats_text)
        
        image_group.setLayout(image_form)
        
        image_layout.addWidget(image_group)
        image_layout.addStretch()
        image_tab.setLayout(image_layout)
        
        tab_widget.addTab(api_tab, "API设置")
        tab_widget.addTab(match_tab, "匹配设置")
        tab_widget.addTab(image_tab, "图像设置")
        
        prompt_btn_layout = QHBoxLayout()
        self.edit_prompts_btn = QPushButton("编辑提示词模板")
        self.edit_prompts_btn.clicked.connect(self.edit_prompts)
        prompt_btn_layout.addWidget(self.edit_prompts_btn)
        prompt_btn_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_config)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(tab_widget)
        layout.addLayout(prompt_btn_layout)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def load_config(self):
        self.api_base_input.setText(self.config.api_base)
        self.api_key_input.setText(self.config.api_key)
        self.temperature_spin.setValue(int(self.config.temperature * 100))
        self.max_tokens_spin.setValue(self.config.max_tokens)
        self.fuzzy_threshold_spin.setValue(self.config.fuzzy_threshold)
        self.max_candidates_spin.setValue(self.config.max_fuzzy_candidates)
        self.max_image_size_spin.setValue(self.config.max_image_size)
        self.batch_delay_spin.setValue(int(self.config.batch_delay))
        
        match_mode = MatchMode(self.config.match_mode)
        if match_mode == MatchMode.EXACT_ONLY:
            self.exact_only_radio.setChecked(True)
        elif match_mode == MatchMode.FUZZY_ONLY:
            self.fuzzy_only_radio.setChecked(True)
        else:
            self.exact_then_fuzzy_radio.setChecked(True)
        
        if self.config.models_cache:
            self.model_combo.addItems(self.config.models_cache)
            if self.config.model in self.config.models_cache:
                self.model_combo.setCurrentText(self.config.model)
    
    def refresh_models(self):
        async def fetch_models():
            self.config.api_base = self.api_base_input.text()
            self.config.api_key = self.api_key_input.text()
            
            async with OpenAIClient(self.config) as client:
                models = await client.get_models()
                if models:
                    self.model_combo.clear()
                    self.model_combo.addItems(models)
                    self.config.models_cache = models
                    QMessageBox.information(self, "成功", f"获取到 {len(models)} 个模型")
                else:
                    QMessageBox.warning(self, "失败", "无法获取模型列表")
        
        asyncio.run(fetch_models())
    
    def edit_prompts(self):
        dialog = PromptEditorDialog(self.config.prompt_templates, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "成功", "提示词模板已更新")
    
    def save_config(self):
        self.config.api_base = self.api_base_input.text()
        self.config.api_key = self.api_key_input.text()
        self.config.model = self.model_combo.currentText()
        self.config.temperature = self.temperature_spin.value() / 100.0
        self.config.max_tokens = self.max_tokens_spin.value()
        self.config.fuzzy_threshold = self.fuzzy_threshold_spin.value()
        self.config.max_fuzzy_candidates = self.max_candidates_spin.value()
        self.config.max_image_size = self.max_image_size_spin.value()
        self.config.batch_delay = self.batch_delay_spin.value()
        
        if self.exact_only_radio.isChecked():
            self.config.match_mode = MatchMode.EXACT_ONLY.value
        elif self.fuzzy_only_radio.isChecked():
            self.config.match_mode = MatchMode.FUZZY_ONLY.value
        else:
            self.config.match_mode = MatchMode.EXACT_THEN_FUZZY.value
        
        self.config.save()
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config.load()
        self.current_project = Project()
        self.current_project_path = None
        self.tag_manager = TagManager()
        self.ai_worker = None
        self.image_worker = None
        self.batch_results_dialog = None
        
        self.init_ui()
        self.load_tag_library()
    
    def init_ui(self):
        self.setWindowTitle("SD绘画Tag生成工具 v1.0")
        self.resize(1400, 900)
        
        self.create_menu_bar()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        self.new_project_btn = QPushButton("新建项目")
        self.new_project_btn.clicked.connect(self.new_project)
        
        self.open_project_btn = QPushButton("打开项目")
        self.open_project_btn.clicked.connect(self.open_project)
        
        self.save_project_btn = QPushButton("保存项目")
        self.save_project_btn.clicked.connect(self.save_project)
        
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self.open_settings)
        
        toolbar_layout.addWidget(self.new_project_btn)
        toolbar_layout.addWidget(self.open_project_btn)
        toolbar_layout.addWidget(self.save_project_btn)
        toolbar_layout.addWidget(self.settings_btn)
        toolbar_layout.addStretch()
        
        # 内容区域
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧功能区域
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        self.function_tabs = QTabWidget()
        
        text_tab = self.create_text_generation_tab()
        image_tab = self.create_image_generation_tab()
        
        self.function_tabs.addTab(text_tab, "文本生成")
        self.function_tabs.addTab(image_tab, "图片分析")
        
        left_layout.addWidget(self.function_tabs)
        left_widget.setLayout(left_layout)
        
        # 右侧日志区域
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        
        log_buttons_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        
        log_buttons_layout.addWidget(self.clear_log_btn)
        log_buttons_layout.addStretch()
        
        log_layout.addWidget(self.log_text)
        log_layout.addLayout(log_buttons_layout)
        log_group.setLayout(log_layout)
        
        right_layout.addWidget(log_group)
        right_widget.setLayout(right_layout)
        
        content_splitter.addWidget(left_widget)
        content_splitter.addWidget(right_widget)
        content_splitter.setSizes([900, 500])
        
        # 状态栏
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()
        
        self.batch_progress_label = QLabel()
        self.status_bar.addPermanentWidget(self.batch_progress_label)
        self.batch_progress_label.hide()
        
        # 步骤进度标签
        self.step_progress_label = QLabel()
        self.status_bar.addPermanentWidget(self.step_progress_label)
        self.step_progress_label.hide()
        
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(content_splitter)
        
        central_widget.setLayout(main_layout)
        
        self.update_status("就绪")
    
    def create_text_generation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        
        input_group = QGroupBox("输入描述")
        input_layout = QVBoxLayout()
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入您想要生成的图像描述...")
        self.input_text.setMaximumHeight(150)
        
        match_mode_layout = QHBoxLayout()
        match_mode_label = QLabel("匹配模式:")
        
        self.text_match_mode_group = QButtonGroup()
        self.text_exact_radio = QRadioButton("仅精确")
        self.text_fuzzy_radio = QRadioButton("仅模糊")
        self.text_hybrid_radio = QRadioButton("混合模式")
        self.text_hybrid_radio.setChecked(True)
        
        self.text_match_mode_group.addButton(self.text_exact_radio)
        self.text_match_mode_group.addButton(self.text_fuzzy_radio)
        self.text_match_mode_group.addButton(self.text_hybrid_radio)
        
        match_mode_layout.addWidget(match_mode_label)
        match_mode_layout.addWidget(self.text_exact_radio)
        match_mode_layout.addWidget(self.text_fuzzy_radio)
        match_mode_layout.addWidget(self.text_hybrid_radio)
        match_mode_layout.addStretch()
        
        input_buttons_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成Tag")
        self.generate_btn.clicked.connect(self.generate_tags)
        
        self.stop_text_btn = QPushButton("停止")
        self.stop_text_btn.clicked.connect(self.stop_text_generation)
        self.stop_text_btn.setEnabled(False)
        
        input_buttons_layout.addWidget(self.generate_btn)
        input_buttons_layout.addWidget(self.stop_text_btn)
        input_buttons_layout.addStretch()
        
        input_layout.addWidget(self.input_text)
        input_layout.addLayout(match_mode_layout)
        input_layout.addLayout(input_buttons_layout)
        input_group.setLayout(input_layout)
        
        result_group = QGroupBox("生成结果")
        result_layout = QVBoxLayout()
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        
        result_buttons_layout = QHBoxLayout()
        self.copy_result_btn = QPushButton("复制结果")
        self.copy_result_btn.clicked.connect(self.copy_result)
        
        result_buttons_layout.addWidget(self.copy_result_btn)
        result_buttons_layout.addStretch()
        
        result_layout.addWidget(self.result_text)
        result_layout.addLayout(result_buttons_layout)
        result_group.setLayout(result_layout)
        
        layout.addWidget(input_group)
        layout.addWidget(result_group)
        widget.setLayout(layout)
        
        return widget
    
    def create_image_generation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 图片选择区域
        image_input_group = QGroupBox("图片选择")
        image_input_layout = QVBoxLayout()
        
        # 处理模式选择
        mode_layout = QHBoxLayout()
        mode_label = QLabel("处理模式:")
        
        self.image_mode_group = QButtonGroup()
        self.single_image_radio = QRadioButton("单张图片")
        self.batch_image_radio = QRadioButton("批量处理")
        self.single_image_radio.setChecked(True)
        
        self.image_mode_group.addButton(self.single_image_radio)
        self.image_mode_group.addButton(self.batch_image_radio)
        
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.single_image_radio)
        mode_layout.addWidget(self.batch_image_radio)
        mode_layout.addStretch()
        
        # 匹配模式选择
        image_match_mode_layout = QHBoxLayout()
        image_match_mode_label = QLabel("匹配模式:")
        
        self.image_match_mode_group = QButtonGroup()
        self.image_exact_radio = QRadioButton("仅精确")
        self.image_fuzzy_radio = QRadioButton("仅模糊")
        self.image_hybrid_radio = QRadioButton("混合模式")
        self.image_hybrid_radio.setChecked(True)
        
        self.image_match_mode_group.addButton(self.image_exact_radio)
        self.image_match_mode_group.addButton(self.image_fuzzy_radio)
        self.image_match_mode_group.addButton(self.image_hybrid_radio)
        
        image_match_mode_layout.addWidget(image_match_mode_label)
        image_match_mode_layout.addWidget(self.image_exact_radio)
        image_match_mode_layout.addWidget(self.image_fuzzy_radio)
        image_match_mode_layout.addWidget(self.image_hybrid_radio)
        image_match_mode_layout.addStretch()
        
        # 文件选择
        file_layout = QHBoxLayout()
        
        self.select_image_btn = QPushButton("选择图片")
        self.select_image_btn.clicked.connect(self.select_image_file)
        
        self.select_folder_btn = QPushButton("选择文件夹")
        self.select_folder_btn.clicked.connect(self.select_image_folder)
        self.select_folder_btn.setEnabled(False)
        
        self.selected_path_label = QLabel("未选择文件")
        
        self.single_image_radio.toggled.connect(self.on_image_mode_changed)
        
        file_layout.addWidget(self.select_image_btn)
        file_layout.addWidget(self.select_folder_btn)
        file_layout.addWidget(self.selected_path_label)
        file_layout.addStretch()
        
        # 处理按钮
        image_buttons_layout = QHBoxLayout()
        
        self.analyze_image_btn = QPushButton("分析图片")
        self.analyze_image_btn.clicked.connect(self.analyze_images)
        self.analyze_image_btn.setEnabled(False)
        
        self.stop_image_btn = QPushButton("停止")
        self.stop_image_btn.clicked.connect(self.stop_image_analysis)
        self.stop_image_btn.setEnabled(False)
        
        image_buttons_layout.addWidget(self.analyze_image_btn)
        image_buttons_layout.addWidget(self.stop_image_btn)
        image_buttons_layout.addStretch()
        
        image_input_layout.addLayout(mode_layout)
        image_input_layout.addLayout(image_match_mode_layout)
        image_input_layout.addLayout(file_layout)
        image_input_layout.addLayout(image_buttons_layout)
        image_input_group.setLayout(image_input_layout)
        
        # 图片结果显示区域
        image_result_group = QGroupBox("分析结果")
        image_result_layout = QVBoxLayout()
        
        self.image_result_text = QTextEdit()
        self.image_result_text.setReadOnly(True)
        self.image_result_text.setPlaceholderText("图片分析结果将显示在这里...")
        
        image_result_buttons_layout = QHBoxLayout()
        
        self.copy_image_result_btn = QPushButton("复制结果")
        self.copy_image_result_btn.clicked.connect(self.copy_image_result)
        
        self.show_batch_results_btn = QPushButton("查看批量结果")
        self.show_batch_results_btn.clicked.connect(self.show_batch_results)
        self.show_batch_results_btn.setEnabled(False)
        
        image_result_buttons_layout.addWidget(self.copy_image_result_btn)
        image_result_buttons_layout.addWidget(self.show_batch_results_btn)
        image_result_buttons_layout.addStretch()
        
        image_result_layout.addWidget(self.image_result_text)
        image_result_layout.addLayout(image_result_buttons_layout)
        image_result_group.setLayout(image_result_layout)
        
        layout.addWidget(image_input_group)
        layout.addWidget(image_result_group)
        widget.setLayout(layout)
        
        return widget
        
    def get_current_image_match_mode(self) -> MatchMode:
        """获取当前图片匹配模式"""
        if self.image_exact_radio.isChecked():
            return MatchMode.EXACT_ONLY
        elif self.image_fuzzy_radio.isChecked():
            return MatchMode.FUZZY_ONLY
        else:
            return MatchMode.EXACT_THEN_FUZZY
    
    def on_image_mode_changed(self):
        is_single = self.single_image_radio.isChecked()
        self.select_image_btn.setEnabled(is_single)
        self.select_folder_btn.setEnabled(not is_single)
        
        self.selected_path_label.setText("未选择文件")
        self.analyze_image_btn.setEnabled(False)
    
    def select_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片文件",
            "",
            "Image Files (*.jpg *.jpeg *.png *.bmp *.webp)"
        )
        
        if file_path:
            self.selected_path_label.setText(os.path.basename(file_path))
            self.selected_path_label.setProperty("file_path", file_path)
            self.analyze_image_btn.setEnabled(True)
    
    def select_image_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择图片文件夹",
            ""
        )
        
        if folder_path:
            image_files = ImageUtils.get_images_from_folder(
                folder_path, 
                self.config.support_image_formats
            )
            
            if image_files:
                self.selected_path_label.setText(f"{folder_path} ({len(image_files)} 张图片)")
                self.selected_path_label.setProperty("folder_path", folder_path)
                self.analyze_image_btn.setEnabled(True)
            else:
                QMessageBox.warning(self, "警告", "所选文件夹中没有找到支持的图片文件")
                self.selected_path_label.setText("未选择文件")
                self.analyze_image_btn.setEnabled(False)
    
    def analyze_images(self):
        if not self.config.api_key:
            QMessageBox.warning(self, "警告", "请先在设置中配置API密钥")
            self.open_settings()
            return
        
        if "vision" not in self.config.model.lower() and "gpt-4" not in self.config.model.lower():
            reply = QMessageBox.question(
                self,
                "模型警告",
                f"当前模型 '{self.config.model}' 可能不支持图像分析。\n建议使用支持视觉的模型（如 gpt-4-vision-preview）。\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # 获取图片路径
        image_paths = []
        
        if self.single_image_radio.isChecked():
            file_path = self.selected_path_label.property("file_path")
            if file_path:
                image_paths = [file_path]
        else:
            folder_path = self.selected_path_label.property("folder_path")
            if folder_path:
                image_paths = ImageUtils.get_images_from_folder(
                    folder_path,
                    self.config.support_image_formats
                )
        
        if not image_paths:
            QMessageBox.warning(self, "警告", "请先选择图片或文件夹")
            return
        
        # 创建并启动图片处理线程
        self.image_worker = ImageWorkerThread(self.config, self.tag_manager)
        self.image_worker.image_paths = image_paths
        self.image_worker.process_mode = ImageProcessMode.SINGLE if len(image_paths) == 1 else ImageProcessMode.BATCH
        self.image_worker.match_mode = self.get_current_image_match_mode()
        
        # 连接信号
        self.image_worker.log_signal.connect(self.log)
        self.image_worker.result_signal.connect(self.on_image_result_received)
        self.image_worker.progress_signal.connect(self.update_progress)
        self.image_worker.batch_progress_signal.connect(self.update_batch_progress)
        self.image_worker.step_progress_signal.connect(self.update_step_progress)
        self.image_worker.finished_signal.connect(self.on_image_analysis_finished)
        
        # 更新UI状态
        self.analyze_image_btn.setEnabled(False)
        self.stop_image_btn.setEnabled(True)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.step_progress_label.show()
        
        # 如果是批量处理，创建结果对话框
        if len(image_paths) > 1:
            self.batch_results_dialog = ImageBatchDialog(self)
            self.batch_progress_label.show()
            self.show_batch_results_btn.setEnabled(True)
        else:
            self.image_result_text.clear()
        
        # 启动线程
        self.image_worker.start()
        self.update_status(f"正在分析 {len(image_paths)} 张图片...")
    
    def stop_image_analysis(self):
        if self.image_worker and self.image_worker.isRunning():
            self.image_worker.stop()
            self.log("用户中止了图片分析过程")
    
    def on_image_result_received(self, image_path: str, prompt: str):
        if self.batch_results_dialog:
            self.batch_results_dialog.add_result(image_path, prompt)
        else:
            self.image_result_text.setText(f"# {os.path.basename(image_path)}\n{prompt}")
    
    def update_batch_progress(self, current: int, total: int):
        self.batch_progress_label.setText(f"进度: {current}/{total}")
    
    def update_step_progress(self, step_name: str, progress: int):
        self.step_progress_label.setText(f"{step_name}: {progress}%")
        self.progress_bar.setValue(progress)
    
    def on_image_analysis_finished(self):
        self.analyze_image_btn.setEnabled(True)
        self.stop_image_btn.setEnabled(False)
        self.progress_bar.hide()
        self.batch_progress_label.hide()
        self.step_progress_label.hide()
        self.update_status("图片分析完成")
        
        if self.batch_results_dialog and self.batch_results_dialog.table.rowCount() > 0:
            self.batch_results_dialog.show()
    
    def show_batch_results(self):
        if self.batch_results_dialog:
            self.batch_results_dialog.show()
    
    def copy_image_result(self):
        result = self.image_result_text.toPlainText()
        if result:
            QApplication.clipboard().setText(result)
            self.update_status("已复制到剪贴板")
    
    def get_current_match_mode(self) -> MatchMode:
        if self.text_exact_radio.isChecked():
            return MatchMode.EXACT_ONLY
        elif self.text_fuzzy_radio.isChecked():
            return MatchMode.FUZZY_ONLY
        else:
            return MatchMode.EXACT_THEN_FUZZY
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件")
        
        new_action = QAction("新建项目", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_project)
        
        open_action = QAction("打开项目", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_project)
        
        save_action = QAction("保存项目", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        
        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_action.triggered.connect(self.save_project_as)
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        tools_menu = menubar.addMenu("工具")
        
        load_tags_action = QAction("加载标签库", self)
        load_tags_action.triggered.connect(self.load_tag_library_dialog)
        
        edit_prompts_action = QAction("编辑提示词模板", self)
        edit_prompts_action.triggered.connect(self.edit_prompt_templates)
        
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.open_settings)
        
        tools_menu.addAction(load_tags_action)
        tools_menu.addAction(edit_prompts_action)
        tools_menu.addSeparator()
        tools_menu.addAction(settings_action)
    
    def load_tag_library(self):
        default_path = "tags.csv"
        if os.path.exists(default_path):
            self.tag_manager.load_tags(default_path)
            self.log(f"已加载标签库: {len(self.tag_manager.tags_dict)} 个标签")
        else:
            self.log("未找到默认标签库文件 tags.csv")
    
    def load_tag_library_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择标签库CSV文件",
            "",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            if self.tag_manager.load_tags(file_path):
                self.log(f"已加载标签库: {len(self.tag_manager.tags_dict)} 个标签")
                QMessageBox.information(self, "成功", f"已加载 {len(self.tag_manager.tags_dict)} 个标签")
            else:
                QMessageBox.warning(self, "失败", "加载标签库失败")
    
    def edit_prompt_templates(self):
        dialog = PromptEditorDialog(self.config.prompt_templates, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config.save()
            self.log("提示词模板已更新")
    
    def new_project(self):
        if self.current_project.user_input or self.current_project.generated_prompt:
            reply = QMessageBox.question(
                self,
                "新建项目",
                "当前项目未保存，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.current_project = Project()
        self.current_project_path = None
        self.input_text.clear()
        self.result_text.clear()
        self.image_result_text.clear()
        self.log("已创建新项目")
        self.update_title()
    
    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目",
            "",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                self.current_project = Project.load(file_path)
                self.current_project_path = file_path
                
                self.input_text.setText(self.current_project.user_input)
                self.result_text.setText(self.current_project.generated_prompt)
                
                for item in self.current_project.history:
                    self.log(item.get('message', ''))
                
                self.log(f"已打开项目: {os.path.basename(file_path)}")
                self.update_title()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法打开项目: {str(e)}")
    
    def save_project(self):
        if not self.current_project_path:
            self.save_project_as()
        else:
            self.save_current_project()
    
    def save_project_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存项目",
            f"{self.current_project.name}.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            self.current_project_path = file_path
            self.save_current_project()
    
    def save_current_project(self):
        try:
            self.current_project.user_input = self.input_text.toPlainText()
            self.current_project.generated_prompt = self.result_text.toPlainText()
            self.current_project.save(self.current_project_path)
            
            self.log(f"项目已保存: {os.path.basename(self.current_project_path)}")
            self.update_status("项目已保存")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存项目失败: {str(e)}")
    
    def open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.log("设置已更新")
    
    def generate_tags(self):
        user_input = self.input_text.toPlainText().strip()
        
        if not user_input:
            QMessageBox.warning(self, "警告", "请输入描述内容")
            return
        
        if not self.config.api_key:
            QMessageBox.warning(self, "警告", "请先在设置中配置API密钥")
            self.open_settings()
            return
        
        if not self.tag_manager.tags_dict:
            reply = QMessageBox.question(
                self,
                "提示",
                "未加载标签库，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.ai_worker = AIWorkerThread(self.config, self.tag_manager)
        self.ai_worker.user_input = user_input
        self.ai_worker.match_mode = self.get_current_match_mode()
        
        self.ai_worker.log_signal.connect(self.log)
        self.ai_worker.result_signal.connect(self.on_result_received)
        self.ai_worker.progress_signal.connect(self.update_progress)
        self.ai_worker.finished_signal.connect(self.on_generation_finished)
        
        self.generate_btn.setEnabled(False)
        self.stop_text_btn.setEnabled(True)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        
        self.ai_worker.start()
        self.update_status("正在生成标签...")
    
    def stop_text_generation(self):
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.log("用户中止了生成过程")
    
    def on_result_received(self, result: str):
        self.result_text.setText(result)
        self.current_project.generated_prompt = result
        
        self.current_project.history.append({
            'timestamp': datetime.now().isoformat(),
            'input': self.input_text.toPlainText(),
            'output': result
        })
    
    def on_generation_finished(self):
        self.generate_btn.setEnabled(True)
        self.stop_text_btn.setEnabled(False)
        self.progress_bar.hide()
        self.update_status("生成完成")
    
    def copy_result(self):
        result = self.result_text.toPlainText()
        if result:
            QApplication.clipboard().setText(result)
            self.update_status("已复制到剪贴板")
    
    def clear_log(self):
        self.log_text.clear()
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        
        if self.current_project:
            self.current_project.history.append({
                'timestamp': datetime.now().isoformat(),
                'message': message
            })
    
    def update_status(self, message: str):
        self.status_bar.showMessage(message)
    
    def update_progress(self, value: int):
        self.progress_bar.setValue(value)
    
    def update_title(self):
        title = "SD绘画Tag生成工具 v3.1 - 优化图片分析"
        if self.current_project_path:
            title += f" - {os.path.basename(self.current_project_path)}"
        elif self.current_project.name != "未命名项目":
            title += f" - {self.current_project.name}"
        self.setWindowTitle(title)
    
    def closeEvent(self, event):
        if self.current_project.user_input or self.current_project.generated_prompt:
            reply = QMessageBox.question(
                self,
                "退出",
                "当前项目未保存，是否退出？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.ai_worker.wait()
        
        if self.image_worker and self.image_worker.isRunning():
            self.image_worker.stop()
            self.image_worker.wait()
        
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
