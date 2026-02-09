# generate_small_dictionaries.py
# 功能概述：
# 该脚本用于生成两个小型字典文件：
# 1. 包含常见弱口令的文本文件（weak_passwords_small.txt）。
# 2. 包含这些弱口令对应 MD5 哈希值的文本文件（weak_passwords_md5_small.txt）。
# 主要用途：安全测试、渗透测试或学习哈希算法。

import hashlib


def generate_small_weak_password_dictionaries():
    # 大约50个最常见的弱口令
    weak_passwords = [
        "123456",
        "password",
        "admin",
        "12345678",
        "qwerty",
        "111111",
        "test",
        "welcome",
        "root",
        "default",
        "admin123",
        "password123",
        "123456789",
        "abcdef",
        "adminadmin",
        "user",
        "guest",
        "pass",
        "master",
        "hello",
        "security",
        "changeit",
        "manager",
        "operator",
        "secret",
        "passwd",
        "12345",
        "654321",
        "000000",
        "1qaz@WSX",  # 常见但弱的键盘模式
        "P@ssword",  # 常见字符替换
        "Admin@",
        "Administrator",
        "Password!",
        "Admin!",
        "Test!",
        "User123",
        "Root123",
        "Welcome1",
        "Welcome!",
        "mima",  # 中文拼音 "密码"
        "yonghu",  # 中文拼音 "用户"
        "mima123",
        "admin2023",  # 结合年份
        "password2023",
        "2023",
        "2022",
        "changeme",
        "MyPassword",
        "Myadmin",
        "computer",
        "network",
        "system",
        "linux",
        "windows",
    ]

    # 移除空字符串（如果存在）并去重
    weak_passwords = list(set([p.strip() for p in weak_passwords if p.strip()]))
    weak_passwords.sort()  # 排序使字典更规整

    md5_hashes = []

    # 文件名加上 "_small" 以区分大字典
    with open("weak_passwords_small.txt", "w", encoding="utf-8") as pw_file, \
            open("weak_passwords_md5_small.txt", "w", encoding="utf-8") as md5_file:
        for password in weak_passwords:
            pw_file.write(password + "\n")

            md5_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
            md5_hashes.append(md5_hash)

            md5_file.write(md5_hash + "\n")

    print(f"生成了 {len(weak_passwords)} 个弱口令到 weak_passwords_small.txt")
    print(f"生成了 {len(md5_hashes)} 个MD5哈希到 weak_passwords_md5_small.txt")


if __name__ == "__main__":
    generate_small_weak_password_dictionaries()
