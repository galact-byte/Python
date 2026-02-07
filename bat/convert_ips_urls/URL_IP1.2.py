# URL_IP1.2.py
# 功能概述：
# 该脚本用于从指定文本文件中提取并分类 URL 和 IP 地址。
# 主要任务包括：
# 1. 读取用户提供的文件内容。
# 2. 提取并展开形如 "192.168.1.1-5" 的 IP 范围。
# 3. 提取所有独立的 IPv4 地址。
# 4. 提取所有 HTTP/HTTPS URL。
# 5. 分离出 URL 中基于 IP 的条目，并将其归类到 IP 集合中。
# 6. 将纯 URL（不含 IP）和所有 IP 地址分别写入两个输出文件。
# 7. 对结果进行排序和去重后保存。

import re
import ipaddress

def expand_ip_range(match):
    """
    将形如 192.168.1.1-5 的 IP 范围展开成完整的 IP 列表。
    参数:
        match (re.Match): 正则匹配对象，包含基础 IP 和结束数字。
    返回:
        list: 展开后的 IP 字符串列表。
    """
    base_ip, end = match.group(1), int(match.group(2))
    start_ip = ipaddress.IPv4Address(base_ip)
    last_octet = int(base_ip.split('.')[-1])
    base_prefix = '.'.join(base_ip.split('.')[:-1])
    return [f"{base_prefix}.{i}" for i in range(last_octet, end + 1)]

# 正则表达式定义
url_pattern = r'https?://[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._~:/?#@!$&\'()*+,;=%-]*)*'  # 匹配 URL
ip_range_pattern = r'\b((?:\d{1,3}\.){3}\d{1,3})-(\d{1,3})\b'  # 匹配 IP 范围
ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'  # 匹配独立 IP

# 输入文件路径
file_path = input("请输入文件的路径: ")
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# 展开 IP 范围
expanded_ips = []
for match in re.finditer(ip_range_pattern, content):
    expanded_ips.extend(expand_ip_range(match))

# 提取所有独立IP（不包括 range 的）
ips = set(re.findall(ip_pattern, content))
ips.update(expanded_ips)

# 提取所有 URL
all_urls = set(re.findall(url_pattern, content))

# 分离出 URL 中带 IP 的条目
url_with_ip = set()
for url in all_urls:
    ip_match = re.match(r'https?://((\d{1,3}\.){3}\d{1,3})(?:[/:]|$)', url)
    if ip_match:
        ip_addr = ip_match.group(1)
        ips.add(ip_addr)           # 把 IP 加入 IP 集合
        url_with_ip.add(url)       # 后面用于从 URL 列表中移除

# 去除 URL 中的 IP 形式条目
pure_urls = all_urls - url_with_ip

# 写入 URL
url_output = input("请输入URL文本的输出路径: ")
with open(url_output, 'w', encoding='utf-8') as url_file:
    for url in sorted(pure_urls):
        url_file.write(url + '\n')

# 写入 IP
ip_output = input("请输入IP文本的输出路径: ")
with open(ip_output, 'w', encoding='utf-8') as ip_file:
    for ip in sorted(ips):
        ip_file.write(ip + '\n')

print("URL（非IP）和IP地址已正确分类和保存。")
import re
import ipaddress

def expand_ip_range(match):
    """将形如 192.168.1.1-5 的 IP 范围展开成列表"""
    base_ip, end = match.group(1), int(match.group(2))
    start_ip = ipaddress.IPv4Address(base_ip)
    last_octet = int(base_ip.split('.')[-1])
    base_prefix = '.'.join(base_ip.split('.')[:-1])
    return [f"{base_prefix}.{i}" for i in range(last_octet, end + 1)]

# 正则表达式定义
url_pattern = r'https?://[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._~:/?#@!$&\'()*+,;=%-]*)*'
ip_range_pattern = r'\b((?:\d{1,3}\.){3}\d{1,3})-(\d{1,3})\b'
ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

# 输入文件路径
file_path = input("请输入文件的路径: ")
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# 展开 IP 范围
expanded_ips = []
for match in re.finditer(ip_range_pattern, content):
    expanded_ips.extend(expand_ip_range(match))

# 提取所有独立IP（不包括 range 的）
ips = set(re.findall(ip_pattern, content))
ips.update(expanded_ips)

# 提取所有 URL
all_urls = set(re.findall(url_pattern, content))

# 分离出 URL 中带 IP 的条目
url_with_ip = set()
for url in all_urls:
    ip_match = re.match(r'https?://((\d{1,3}\.){3}\d{1,3})(?:[/:]|$)', url)
    if ip_match:
        ip_addr = ip_match.group(1)
        ips.add(ip_addr)           # 把 IP 加入 IP 集合
        url_with_ip.add(url)       # 后面用于从 URL 列表中移除

# 去除 URL 中的 IP 形式条目
pure_urls = all_urls - url_with_ip

# 写入 URL
url_output = input("请输入URL文本的输出路径: ")
with open(url_output, 'w', encoding='utf-8') as url_file:
    for url in sorted(pure_urls):
        url_file.write(url + '\n')

# 写入 IP
ip_output = input("请输入IP文本的输出路径: ")
with open(ip_output, 'w', encoding='utf-8') as ip_file:
    for ip in sorted(ips):
        ip_file.write(ip + '\n')

print("URL（非IP）和IP地址已正确分类和保存。")
