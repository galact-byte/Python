import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import os
import time
import re
from urllib.parse import urlparse

from tiqu import output_dir


class FanboxScraper:
    def __init__(self, session_id, creator_name):
        """
        初始化爬虫
        :param session_id: 你的Fanbox登录cookie (FANBOXSESSID)
        :param creator_name:创作者名称（例如：liyoosa）
        """
        self.creator_name = creator_name
        self.base_url = "https://liyoosa.fanbox.cc"
        self.session_id = session_id

        # 配置Chrome选项
        options = uc.ChromeOptions()
        options.add_argument('--window-size=1920,1080')

        # 使用 undetected_chromedriver 绕过检测
        print("正在启动浏览器...")
        self.driver = uc.Chrome(options=options, version_main=143)
        self.wait = WebDriverWait(self.driver, 20)

        # 用于下载图片的session
        self.download_session = requests.Session()
        self.download_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.fanbox.cc/'
        })

        # 设置cookie
        self.set_cookies()

    def set_cookies(self):
        """设置cookies到浏览器"""
        print("设置登录状态...")
        self.driver.get("https://www.fanbox.cc")
        time.sleep(2)

        # 添加cookie
        self.driver.add_cookie({
            'name': 'FANBOXSESSID',
            'value': self.session_id,
            'domain': '.fanbox.cc',
            'path': '/'
        })

        # 刷新以应用cookie
        self.driver.refresh()
        time.sleep(3)

        # ===== 新增：等待手动验证 =====
        print("\n" + "=" * 60)
        print("⚠️  如果出现人机验证，请手动完成")
        print("    完成后请在控制台按 Enter 继续...")
        print("=" * 60)
        input()  # 暂停，等待你手动完成验证
        # =============================

        print("✓ 登录状态设置完成")

    def sanitize_filename(self, filename):
        """清理文件名中的非法字符"""
        if not filename:
            return "untitled"
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        return filename.strip()[:200]

    def get_post_urls_from_page(self, page):
        """从列表页获取所有post的URL"""
        url = f"{self.base_url}/posts?page={page}&sort=newest"
        print(f"\n正在获取第 {page} 页...")

        try:
            self.driver.get(url)
            time.sleep(4)

            # 滚动页面
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # 查找所有post链接
            post_urls = []
            links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="/posts/"]')

            for link in links:
                href = link.get_attribute('href')
                if href and '/posts/' in href and re.match(r'.*/posts/\d+$', href):
                    if href not in post_urls:
                        post_urls.append(href)

            print(f"  找到 {len(post_urls)} 个posts")
            return post_urls

        except Exception as e:
            print(f"  获取失败: {e}")
            return []

    def get_post_images(self, post_url):
        """获取post的标题和所有图片URL"""
        print(f"\n{'=' * 60}")
        print(f"处理: {post_url}")

        try:
            self.driver.get(post_url)

            # 智能等待 - 等待图片出现
            print("  等待内容加载...", end='', flush=True)

            max_wait = 30
            start_time = time.time()

            while time.time() - start_time < max_wait:
                # 检查图片
                img_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                         'img[src*="downloads.fanbox.cc"], img[src*="pixiv.pximg.net"]')

                if len(img_elements) > 0:
                    print(f" ✓ ({len(img_elements)} 个图片)")
                    break

                time.sleep(1)
            else:
                print(" ⚠️ 超时")

            # 额外等待并滚动
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # 获取标题
            title = "untitled"
            try:
                # 方法1: 查找 h1 标签
                title_element = self.driver.find_element(By.TAG_NAME, 'h1')
                title_text = title_element.text.strip()

                # 如果 h1 有文本，使用它
                if title_text:
                    title = title_text
                else:
                    # 方法2: 通过 JavaScript 获取 h1 的 textContent（排除子元素）
                    title = self.driver.execute_script("""
                        let h1 = document.querySelector('h1');
                        if (h1) {
                            // 获取 h1 的直接文本内容，不包括子元素
                            let text = '';
                            for (let node of h1.childNodes) {
                                if (node.nodeType === Node.TEXT_NODE) {
                                    text += node.textContent;
                                }
                            }
                            return text.trim();
                        }
                        return '';
                    """)

                if not title:
                    # 方法3: 查找包含 PostTitle 类的元素
                    title_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="PostTitle"]')
                    if title_elements:
                        title = title_elements[0].text.strip()

            except Exception as e:
                print(f"  ⚠️ 获取标题失败: {e}")

            title = self.sanitize_filename(title) if title else "untitled"
            post_id = post_url.split('/')[-1]

            print(f"  标题: {title}")

            # 获取所有图片URL
            images = []

            # 优先获取原图链接
            link_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="downloads.fanbox.cc"]')
            for link in link_elements:
                href = link.get_attribute('href')
                if href and href not in images:
                    images.append(href)

            # 如果没有原图链接，从img获取
            if not images:
                img_elements = self.driver.find_elements(By.TAG_NAME, 'img')
                for img in img_elements:
                    src = img.get_attribute('src')
                    if src and ('downloads.fanbox.cc' in src or 'pixiv.pximg.net' in src):
                        if '/cover/' in src:
                            continue

                        original_url = re.sub(r'/w/\d+/', '/', src)
                        if original_url not in images:
                            images.append(original_url)

            # 去重
            images = list(dict.fromkeys(images))

            print(f"  找到 {len(images)} 张图片")

            return title, post_id, images

        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
            return None, None, []

    def download_image(self, img_url, save_path, max_retries=3):
        """下载单张图片，支持重试"""
        for attempt in range(max_retries):
            try:
                # 从浏览器获取cookies
                cookies = self.driver.get_cookies()
                for cookie in cookies:
                    self.download_session.cookies.set(cookie['name'], cookie['value'],
                                                      domain=cookie.get('domain', '.fanbox.cc'))

                response = self.download_session.get(img_url, stream=True, timeout=30)
                response.raise_for_status()

                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f" 重试{attempt + 1}/{max_retries}...", end='', flush=True)
                    time.sleep(2)
                else:
                    print(f" 失败: {e}")
                    return False

        return False

    def scrape_post(self, post_url, base_dir='fanbox_downloads'):
        """爬取单个post的所有图片"""
        title, post_id, images = self.get_post_images(post_url)

        if not title or not images:
            print("  ⚠️ 跳过（无标题或无图片）")
            with open('../../failed_posts.txt', 'a', encoding='utf-8') as f:
                f.write(f"{post_url}\n")
            return

        # 创建文件夹：以标题命名（不带post_id后缀）
        folder_name = title
        post_dir = os.path.join(base_dir, folder_name)
        os.makedirs(post_dir, exist_ok=True)

        # 下载所有图片
        success_count = 0
        for idx, img_url in enumerate(images, 1):
            parsed = urlparse(img_url)
            path = parsed.path
            ext = os.path.splitext(path)[-1] or '.jpg'

            filename = f"{idx:03d}{ext}"
            save_path = os.path.join(post_dir, filename)

            if os.path.exists(save_path):
                print(f"  [{idx}/{len(images)}] 已存在")
                success_count += 1
                continue

            print(f"  [{idx}/{len(images)}] 下载中...", end='', flush=True)
            if self.download_image(img_url, save_path, max_retries=3):
                print(f" ✓")
                success_count += 1
            else:
                print(f" ✗")

            time.sleep(0.3)

        print(f"  ✅ 完成: {success_count}/{len(images)} 张")

    def scrape_all(self, total_pages=5, output_dir=None):
        """爬取所有页面的posts"""
        # 如果没有指定输出路径，使用当前目录
        if output_dir is None:
            output_dir = os.getcwd()
        # 创建 liyoosa 文件夹
        creator_dir = os.path.join(output_dir, self.creator_name)
        os.makedirs(creator_dir, exist_ok=True)

        print("\n" + "=" * 60)
        print(f"开始爬取{self.creator_name}的Fanbox内容")
        print("=" * 60)

        # 收集所有post URLs
        all_post_urls = []
        for page in range(1, total_pages + 1):
            post_urls = self.get_post_urls_from_page(page)
            all_post_urls.extend(post_urls)
            time.sleep(1)

        # 去重
        all_post_urls = list(dict.fromkeys(all_post_urls))
        print(f"\n总共找到 {len(all_post_urls)} 个posts")
        print("=" * 60)

        if not all_post_urls:
            print("未找到任何posts")
            return

        # 下载每个post
        for idx, post_url in enumerate(all_post_urls, 1):
            print(f"\n[{idx}/{len(all_post_urls)}]")
            self.scrape_post(post_url, creator_dir)  # 传入 liyoosa 文件夹路径
            time.sleep(2)

        print("\n" + "=" * 60)
        print("✅ 所有下载完成！")
        print(f"文件保存在: {os.path.abspath(creator_dir)}")
        print("=" * 60)

    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                print("正在关闭浏览器...")
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║      Fanbox 图片下载器 (undetected-chromedriver)        ║
    ╚════════════════════════════════════════════════════════╝

    使用步骤：
    1. 安装依赖: pip install undetected-chromedriver requests
    2. 填写你的 FANBOXSESSID
    3. 运行程序
    """)

    # ===== 配置区域 =====
    SESSION_ID = "66097430_qmRPOoXh2Ot7R64tFOCQGjlBug70izOL"  # 你的session ID
    # ====================

    # 交互式输入
    CREATOR_NAME = input("请输入创作者名称[默认：liyoosa]: ").strip() or "liyoosa"
    TOTAL_PAGES = int(input("要爬取的页数[默认：5]: ").strip() or "5")
    OUTPUT_DIR = input("输出路径[直接回车=当前目录]: ").strip() or None

    print(f"\n将下载{CREATOR_NAME}的{TOTAL_PAGES}页内容")
    print(f"保存到{OUTPUT_DIR if OUTPUT_DIR else '当前目录'}\n")

    scraper = None
    try:
        # 创建爬虫实例
        scraper = FanboxScraper(SESSION_ID)

        # 开始爬取
        scraper.scrape_all(total_pages=TOTAL_PAGES, base_dir='fanbox_downloads')

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if scraper:
            input("\n按 Enter 关闭浏览器...")
            scraper.close()

    print("\n提示：如果某些图片下载失败，可以重新运行程序")
    print("      程序会自动跳过已下载的图片")
