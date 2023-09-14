import os
import re
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import pandas as pd
import time

# 封装成函数
def scrape_game_info(rj_numbers):
    game_info_list = []

    # 基础URL
    base_url = "https://www.dlsite.com/maniax/work/=/product_id/"

    # 创建一个文件夹来保存图片
    if not os.path.exists("game_images"):
        os.makedirs("game_images")

    for rj in rj_numbers:
        rj = rj.strip()
        url = base_url + rj + ".html"
        print(f"{rj}:{url}")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }
            r = requests.get(url, headers=headers)
            r.encoding = 'utf-8'
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')

            # 抓取数据
            game_name = soup.find('h1', itemprop='name', id='work_name').text.strip()
            img_tag = soup.find('img', itemprop='image')
            text_ = soup.find('div', class_='work_parts_area').text.strip()

            # 提取图像的URL
            image_url = img_tag.get('srcset', '')

            if image_url:
                full_image_url = "https:" + image_url
                response = requests.get(full_image_url)

                if response.status_code == 200:
                    image_name = f"game_images/{rj}_{game_name}.jpg"
                    image = Image.open(BytesIO(response.content))
                    image.save(image_name)
                else:
                    print(f"无法获取图像: {full_image_url}")
            else:
                print(f"未找到图像URL: {url}")

            # 添加游戏信息到列表
            game_info_list.append({
                'RJ号': rj,
                '游戏名字': game_name,
                '内容': text_,
                '图像链接': full_image_url
            })
            time.sleep(2)

        except Exception as e:
            print(f"出现异常: {str(e)}")

    return game_info_list

# 获取用户输入的多个RJ号，不区分中英文逗号和空格
input_text = input("请输入RJ号(多个就使用逗号、中文逗号或空格分隔):")
rj_numbers = re.split(r'[,\s，]+', input_text)

if len(rj_numbers) == 0:
    print("什么都没有哦")
else:
    game_info_list = scrape_game_info(rj_numbers)
    if len(game_info_list) > 0:
        print("存储成功！")
        print('-'*50)
        # 将游戏信息保存为CSV文件
        df = pd.DataFrame(game_info_list)
        df.to_csv("game_info.csv", index=False)
        print("已经将信息存储为csv文件")

        # for game_info in game_info_list:
        #     print('RJ号:', game_info['RJ号'])
        #     print('游戏名字:', game_info['游戏名字'])
        #     print('内容:', game_info['内容'])
        #     print('图像链接:', game_info['图像链接'])
        #     print('-' * 50)  # 添加分隔符
