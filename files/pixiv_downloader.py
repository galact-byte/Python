#!/usr/bin/env python3
"""
Pixiv 图片下载器
从特定格式的文本中提取Pixiv作品ID并下载图片
"""

import re
import os
import time
import requests
from pathlib import Path

class PixivDownloader:
    def __init__(self, output_dir='pixiv_images'):
        """
        初始化下载器
        :param output_dir: 图片保存目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        
        # 设置请求头，模拟浏览器访问
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.pixiv.net/'
        })
    
    def extract_ids(self, text):
        """
        从文本中提取所有Pixiv作品ID
        :param text: 包含ID的文本
        :return: ID列表（去重）
        """
        # 使用正则表达式提取所有id后面的数字
        pattern = r'id：(\d+)'
        ids = re.findall(pattern, text)
        
        # 去重并保持顺序
        unique_ids = list(dict.fromkeys(ids))
        print(f"提取到 {len(unique_ids)} 个唯一ID（原始{len(ids)}个）")
        
        return unique_ids
    
    def get_artwork_info(self, artwork_id):
        """
        获取作品信息（需要登录才能访问完整API）
        注意：这个方法需要Pixiv账号cookies才能正常工作
        :param artwork_id: 作品ID
        :return: 作品信息字典
        """
        url = f'https://www.pixiv.net/ajax/illust/{artwork_id}'
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('error') is False:
                    return data.get('body')
            return None
        except Exception as e:
            print(f"获取作品 {artwork_id} 信息失败: {e}")
            return None
    
    def download_image(self, url, filename):
        """
        下载图片
        :param url: 图片URL
        :param filename: 保存文件名
        :return: 是否成功
        """
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                filepath = self.output_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"✓ 下载成功: {filename}")
                return True
            else:
                print(f"✗ 下载失败 (HTTP {response.status_code}): {filename}")
                return False
        except Exception as e:
            print(f"✗ 下载出错: {filename} - {e}")
            return False
    
    def save_id_list(self, ids, filename='pixiv_ids.txt'):
        """
        保存ID列表到文件
        :param ids: ID列表
        :param filename: 文件名
        """
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            for id in ids:
                f.write(f"{id}\n")
        print(f"\nID列表已保存到: {filepath}")
    
    def generate_urls(self, ids, url_file='pixiv_urls.txt'):
        """
        生成Pixiv作品页面URL列表
        :param ids: ID列表
        :param url_file: URL列表保存文件名
        """
        urls = [f"https://www.pixiv.net/artworks/{id}" for id in ids]
        filepath = self.output_dir / url_file
        with open(filepath, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")
        print(f"作品页面URL已保存到: {filepath}")
        return urls
    
    def download_simple(self, artwork_id, delay=1):
        """
        简单下载方法（直接尝试常见的图片URL格式）
        注意：这个方法可能不总是有效，因为Pixiv的图片URL需要正确的认证
        :param artwork_id: 作品ID
        :param delay: 延迟秒数
        """
        # 尝试常见的缩略图URL格式
        # 注意：实际下载原图需要登录和正确的cookies
        thumb_url = f"https://i.pximg.net/c/240x480/img-master/img/{artwork_id}_p0_master1200.jpg"
        
        filename = f"{artwork_id}.jpg"
        success = self.download_image(thumb_url, filename)
        
        if delay > 0:
            time.sleep(delay)
        
        return success


def main():
    # 示例文本数据
    sample_text = """id：100268677|||id：100333887|||id：100364267|||id：101385007 id：101385007|||id：102941645|||id：103298540|||id：103372416 id：103408763|||id：103967153|||id：105253351|||id：108907466"""
    
    print("=" * 60)
    print("Pixiv 作品ID提取和下载工具")
    print("=" * 60)
    print("\n请选择操作模式：")
    print("1. 从文本中提取ID并生成URL列表")
    print("2. 从文本中提取ID并尝试下载（需要配置cookies）")
    print("3. 从文件读取文本并处理")
    print()
    
    choice = input("请输入选项 (1/2/3): ").strip()
    
    downloader = PixivDownloader()
    
    if choice == '1':
        print("\n请粘贴包含ID的文本（输入END结束）：")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        text = '\n'.join(lines)
        
        ids = downloader.extract_ids(text)
        if ids:
            print(f"\n提取的ID列表：")
            for i, id in enumerate(ids, 1):
                print(f"{i}. {id}")
            
            downloader.save_id_list(ids)
            downloader.generate_urls(ids)
            print(f"\n✓ 处理完成！文件保存在 '{downloader.output_dir}' 目录")
    
    elif choice == '2':
        print("\n⚠️  注意：直接下载需要配置Pixiv登录cookies")
        print("推荐使用选项1生成URL列表，然后使用浏览器插件或专门的下载工具")
        proceed = input("是否继续? (y/n): ").strip().lower()
        if proceed == 'y':
            print("\n请粘贴包含ID的文本（输入END结束）：")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
            text = '\n'.join(lines)
            
            ids = downloader.extract_ids(text)
            if ids:
                downloader.save_id_list(ids)
                downloader.generate_urls(ids)
                
                print(f"\n开始下载...")
                for i, id in enumerate(ids, 1):
                    print(f"\n[{i}/{len(ids)}] 处理ID: {id}")
                    downloader.download_simple(id, delay=1)
    
    elif choice == '3':
        filename = input("请输入文本文件路径: ").strip()
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                text = f.read()
            
            ids = downloader.extract_ids(text)
            if ids:
                downloader.save_id_list(ids)
                downloader.generate_urls(ids)
                print(f"\n✓ 处理完成！文件保存在 '{downloader.output_dir}' 目录")
        else:
            print(f"文件不存在: {filename}")
    
    else:
        print("无效选项")


if __name__ == '__main__':
    main()
