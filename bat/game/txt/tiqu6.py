from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re


def scrape_webpage(url, output_file):
    # 设置 Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 可选，后台运行
    options.add_argument('--proxy-server=127.0.0.1:7890')  # 直接在 Chrome 选项中设置代理
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)

        # 等待页面加载
        time.sleep(3)

        # 点击页面任意位置以处理可能的提示或弹窗
        driver.find_element(By.TAG_NAME, "body").click()

        # 等待内容加载
        time.sleep(3)

        try:
            # 直接定位content-container下content里的content-block
            xpath = "//div[contains(@class,'content-container')]/div[contains(@class,'content')]/div[contains(@class,'content-block') and not(ancestor::div[contains(@class,'left-side-container')])]"

            content_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )

            # 获取所有文本内容，包括正确的排版
            formatted_text = ""

            # 处理多个元素类型：p、h1、h2、ol、ul等
            elements = content_element.find_elements(By.XPATH, ".//p | .//h1 | .//h2 | .//ol | .//ul")

            for element in elements:
                if element.tag_name == 'p':
                    p_text = element.text.strip()
                    if p_text:
                        formatted_text += p_text + "\n\n"
                elif element.tag_name == 'h1':
                    h1_text = element.text.strip()
                    if h1_text:
                        formatted_text += f"\n\n{'=' * len(h1_text)}\n{h1_text}\n{'=' * len(h1_text)}\n\n"
                elif element.tag_name == 'h2':
                    h2_text = element.text.strip()
                    if h2_text:
                        formatted_text += f"\n{'-' * len(h2_text)}\n{h2_text}\n{'-' * len(h2_text)}\n"
                elif element.tag_name == 'ol' or element.tag_name == 'ul':
                    list_items = element.find_elements(By.TAG_NAME, "li")
                    for li in list_items:
                        li_text = li.text.strip()
                        if li_text:
                            formatted_text += f"• {li_text}\n"

            # 清理最终文本，删除多余的空行
            formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
            formatted_text = formatted_text.strip()

            with open(output_file, 'w', encoding='utf-8') as file:
                file.write(formatted_text)

            print(f"Content successfully saved to {output_file}")
            print(f"First 200 characters of content: {formatted_text[:200]}...")

        except Exception as e:
            print(f"Error finding content: {e}")
            print("Attempting to debug by getting page source...")

            # 保存完整页面源码以便调试
            with open("page_source.html", 'w', encoding='utf-8') as file:
                file.write(driver.page_source)
            print("Saved page source to page_source.html for debugging")

    except Exception as e:
        print(f"Error loading page: {e}")
    finally:
        driver.quit()


# 目标 URL 和输出文件
# url = "https://wt.tepis.me/#/chapter/%E9%81%93%E5%85%B7%E9%9B%86/%E6%B0%B8%E4%B9%85%E6%80%A7%E6%B7%AB%E7%BA%B9.html"
# output_file = "permanent.txt"
url = "https://wt.tepis.me/#/chapter/%E9%AD%94%E6%B3%95%E5%B0%91%E5%A5%B3%E7%BB%93%E6%9C%88/%E7%AC%AC-1-%E7%AB%A0.html"
output_file = "magicgirl.txt"

scrape_webpage(url, output_file)
