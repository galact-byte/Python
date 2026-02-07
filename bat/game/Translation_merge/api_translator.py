#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API翻译模块
支持多种大模型API进行日文到中文的翻译
"""

import json
import time
from typing import Dict, List, Tuple
import requests
from pathlib import Path


class APITranslator:
    """API翻译器基类"""
    
    def __init__(self, api_key: str, model: str, base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.request_delay = 0.5  # 请求间隔（秒）
        
    def translate_batch(self, texts: List[str], progress_callback=None) -> List[str]:
        """
        批量翻译文本
        
        Args:
            texts: 待翻译的文本列表
            progress_callback: 进度回调函数 callback(current, total, text)
            
        Returns:
            翻译后的文本列表
        """
        results = []
        total = len(texts)
        
        for idx, text in enumerate(texts, 1):
            try:
                translation = self.translate_single(text)
                results.append(translation)
                
                if progress_callback:
                    progress_callback(idx, total, text[:50])
                    
                # 延迟以避免请求过快
                if idx < total:
                    time.sleep(self.request_delay)
                    
            except Exception as e:
                print(f"❌ 翻译失败 [{idx}/{total}]: {e}")
                results.append(text)  # 失败时保留原文
                
        return results
    
    def translate_single(self, text: str) -> str:
        """翻译单条文本（子类实现）"""
        raise NotImplementedError


class OpenAITranslator(APITranslator):
    """OpenAI API翻译器（也兼容其他OpenAI格式的API）"""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo", base_url: str = None):
        super().__init__(api_key, model, base_url)
        if not base_url:
            self.base_url = "https://api.openai.com/v1"
    
    def translate_single(self, text: str) -> str:
        """使用OpenAI API翻译单条文本"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = """你是一个专业的日语到中文游戏翻译专家。请将用户提供的日文文本翻译成中文。
要求：
1. 保持游戏术语的准确性
2. 符合中文游戏玩家的阅读习惯
3. 只输出翻译结果，不要有任何解释或额外内容
4. 保持原文的格式（如有换行、空格等）"""
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            raise Exception(f"API请求失败: {e}")


class AnthropicTranslator(APITranslator):
    """Anthropic Claude API翻译器"""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", base_url: str = None):
        super().__init__(api_key, model, base_url)
        if not base_url:
            self.base_url = "https://api.anthropic.com/v1"
    
    def translate_single(self, text: str) -> str:
        """使用Anthropic API翻译单条文本"""
        url = f"{self.base_url}/messages"
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        system_prompt = """你是一个专业的日语到中文游戏翻译专家。请将用户提供的日文文本翻译成中文。
要求：
1. 保持游戏术语的准确性
2. 符合中文游戏玩家的阅读习惯
3. 只输出翻译结果，不要有任何解释或额外内容
4. 保持原文的格式（如有换行、空格等）"""
        
        data = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": text}
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text'].strip()
        except Exception as e:
            raise Exception(f"API请求失败: {e}")


class DeepSeekTranslator(APITranslator):
    """DeepSeek API翻译器"""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = None):
        super().__init__(api_key, model, base_url)
        if not base_url:
            self.base_url = "https://api.deepseek.com/v1"
    
    def translate_single(self, text: str) -> str:
        """使用DeepSeek API翻译单条文本"""
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = """你是一个专业的日语到中文游戏翻译专家。请将用户提供的日文文本翻译成中文。
要求：
1. 保持游戏术语的准确性
2. 符合中文游戏玩家的阅读习惯
3. 只输出翻译结果，不要有任何解释或额外内容
4. 保持原文的格式（如有换行、空格等）"""
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.3
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            raise Exception(f"API请求失败: {e}")


class SakuraTranslator(APITranslator):
    """Sakura本地模型翻译器（支持Ollama/LM Studio/llama.cpp）"""
    
    def __init__(self, api_key: str = "dummy", model: str = "sakura", base_url: str = None):
        super().__init__(api_key, model, base_url)
        if not base_url:
            self.base_url = "http://localhost:11434"  # 默认Ollama地址
        
        # Sakura专用的prompt格式
        self.use_sakura_format = True
    
    def translate_single(self, text: str) -> str:
        """使用Sakura模型翻译单条文本"""
        
        # Sakura模型的专用prompt格式
        if self.use_sakura_format:
            prompt = f"将下面的日文文本翻译成中文：{text}"
        else:
            prompt = text
        
        # 检测是Ollama还是其他格式
        if "11434" in self.base_url:  # Ollama
            return self._translate_ollama(prompt)
        elif "1234" in self.base_url:  # LM Studio
            return self._translate_openai_format(prompt)
        else:  # llama.cpp或其他OpenAI兼容格式
            return self._translate_openai_format(prompt)
    
    def _translate_ollama(self, prompt: str) -> str:
        """Ollama格式API调用"""
        url = f"{self.base_url}/api/generate"
        
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.3,
                "top_k": 40,
                "repeat_penalty": 1.0
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result['response'].strip()
        except Exception as e:
            raise Exception(f"Ollama API请求失败: {e}")
    
    def _translate_openai_format(self, prompt: str) -> str:
        """OpenAI格式API调用（适用于LM Studio、llama.cpp server等）"""
        url = f"{self.base_url}/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # 如果需要API key（某些服务）
        if self.api_key and self.api_key != "dummy":
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            raise Exception(f"本地模型API请求失败: {e}")


def create_translator(provider: str, api_key: str, model: str = None, base_url: str = None) -> APITranslator:
    """
    创建翻译器实例
    
    Args:
        provider: API提供商 ('openai', 'anthropic', 'deepseek', 'sakura', 'custom')
        api_key: API密钥
        model: 模型名称
        base_url: 自定义API地址
        
    Returns:
        翻译器实例
    """
    provider = provider.lower()
    
    if provider == 'openai':
        return OpenAITranslator(api_key, model or "gpt-3.5-turbo", base_url)
    elif provider == 'anthropic':
        return AnthropicTranslator(api_key, model or "claude-sonnet-4-5-20250929", base_url)
    elif provider == 'deepseek':
        return DeepSeekTranslator(api_key, model or "deepseek-chat", base_url)
    elif provider == 'sakura':
        # Sakura本地模型，不需要真实API key
        sakura_url = base_url if base_url else "http://127.0.0.1:8080"
        return SakuraTranslator("dummy", model or "sakura", sakura_url)
    elif provider == 'custom':
        # 自定义API，使用OpenAI格式
        return OpenAITranslator(api_key, model or "default", base_url)
    else:
        raise ValueError(f"不支持的API提供商: {provider}")


def translate_json_file(input_file: str, output_file: str, translator: APITranslator, 
                       progress_callback=None) -> Tuple[int, int]:
    """
    翻译JSON文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        translator: 翻译器实例
        progress_callback: 进度回调函数
        
    Returns:
        (成功数, 总数)
    """
    # 加载JSON文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取需要翻译的文本
    keys = list(data.keys())
    texts = [data[key] for key in keys]
    
    # 批量翻译
    translations = translator.translate_batch(texts, progress_callback)
    
    # 构建翻译结果
    translated_data = {}
    success_count = 0
    
    for key, original, translation in zip(keys, texts, translations):
        translated_data[key] = translation
        if translation != original:
            success_count += 1
    
    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)
    
    return success_count, len(keys)


def merge_translated_back(merged_file: str, translated_new_file: str, output_file: str) -> int:
    """
    将翻译好的新条目合并回主文件
    
    Args:
        merged_file: 合并后的主文件
        translated_new_file: 翻译好的新条目文件
        output_file: 输出文件路径
        
    Returns:
        更新的条目数
    """
    # 加载两个文件
    with open(merged_file, 'r', encoding='utf-8') as f:
        merged_data = json.load(f)
    
    with open(translated_new_file, 'r', encoding='utf-8') as f:
        translated_data = json.load(f)
    
    # 合并翻译
    update_count = 0
    for key, value in translated_data.items():
        if key in merged_data:
            # 只有当翻译不同于原文时才更新
            if value != merged_data[key]:
                merged_data[key] = value
                update_count += 1
    
    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    
    return update_count
