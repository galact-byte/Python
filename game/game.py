import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image
import requests
from io import BytesIO

# 1.存储网站链接
# 获取用户输入的多个RJ号，不区分中英文逗号和空格
input_text = input("请输入RJ号(多个就使用逗号、中文逗号或空格分隔):")
# 使用正则表达式来匹配逗号、中文逗号和空格，进行分割
rj_numbers = re.split(r'[,\s，]+', input_text)

# 基础URL
base_url = "https://www.dlsite.com/maniax/work/=/product_id/"
rj_url = []
# 生成并输出相应的网址
for rj in rj_numbers:
    rj = rj.strip()  # 去除输入中的空格
    url = base_url + rj + ".html"  # 将RJ号和网址连接起来
    print(f"{rj}:{url}", '\n')
    rj_url.append(url)

if len(rj_url) == 0:
    print("什么都没有哦")
else:
    print("存储成功！")
# print(data)

# 2.爬取游戏名字图片和内容简介
img_ur1 = []
for url in rj_url:
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

    # 如果URL不为空，输出URL
    if image_url:
        full_image_url = "https:" + image_url
        # print("图像URL:", full_image_url)
        img_ur1.append(full_image_url)
        # 使用requests库获取图像内容
        response = requests.get(full_image_url)

        # 检查请求是否成功
        if response.status_code == 200:
            # 使用Pillow库加载图像
            image = Image.open(BytesIO(response.content))

            # 显示图像
            #image.show()

            # 保存图像到磁盘
            image.save("image.jpg")
        else:
            print("无法获取图像")
    else:
        print("未找到图像URL")

    # 提取游戏名字
    print('游戏名字:{}'.format(game_name))

    # 提取介绍内容
    print('内容:{}'.format(text_))
