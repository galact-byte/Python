import pandas as pd
import requests
from bs4 import BeautifulSoup

# 1.1 获取豆瓣电影top250链接
urls = []
n = [i for i in range(0, 226, 25)]
for i in n:
    url = "https://movie.douban.com/top250?start=" + str(i) + "&filter="
    urls.append(url)
# print(urls)

# 1.2 爬取所需要的数据
data = []
for url in urls:
    # 把爬虫请求伪装成谷歌浏览器请求
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    # 发出请求
    r = requests.get(url, headers=headers)
    r.encoding = 'utf-8'
    html = r.text
    # 利用BeautifulSoup库对网页进行解析
    soup = BeautifulSoup(html, 'html.parser')
    # 抓取数据
    names = soup.find_all('div', class_='hd')  # 名字

    # 显示信息
    for ne in names:
        # 对字符串进行简单清洗
        a_tag = ne.find('a')
        href = a_tag.get('href')
        # print('{}'.format(names))
        data.append(href)
        # print(href)

# print(data)

# 1.3 将获取到的链接保存到文件
filename = 'TOP250URL.txt'
with open(filename, 'w', encoding='utf-8') as file:
    for item in data:
        file.write(item + '\n')

print("数据已保存到文件:", filename)

# 2.1爬取影评
data1 = []
for url in data:
    # 把爬虫请求伪装成谷歌浏览器请求
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    # 发出请求
    r = requests.get(url, headers=headers)
    r.encoding = 'utf-8'
    html = r.text
    # 利用BeautifulSoup库对网页进行解析
    soup = BeautifulSoup(html, 'html.parser')
    # 抓取数据
    movie_name = soup.find('h1').find('span', property='v:itemreviewed').text.strip()
    comments = soup.find_all('p', class_='comment-content')  # 评论
    names = soup.find_all('span', class_='comment-info')  # 评论人、评分和评分时间

    # 显示信息
    for co, na in zip(comments, names):
        # 提取电影名字
        print('电影名字:{}'.format(movie_name))

        # 提取用户名
        username = na.find('a').text.strip()

        # 提取评分
        rating_span = na.find('span', class_=lambda value: value and value.startswith('allstar'))
        rating_title = rating_span.get('title') if rating_span else None
        if rating_title == '力荐':
            rating = '5星'
        elif rating_title == '推荐':
            rating = '4星'
        elif rating_title == '还行':
            rating = '3星'
        elif rating_title == '较差':
            rating = '2星'
        else:
            rating = '1星'

        # 提取评论
        if co.find('span', class_='expand'):
            co.find('span', class_='expand').decompose()
        full_comment = co.find('span', class_='full')
        if full_comment:
            reviews = full_comment.text.strip()
        else:
            reviews = co.get_text().strip()

        # 提取评论时间
        comment_time = na.find('span', class_='comment-time').text.strip()

        print('用户名:{} '.format(username))
        print('评分:{}'.format(rating))
        print('评论:{}'.format(reviews))
        print('评论时间:{}'.format(comment_time))
        print('-' * 30)
        review_dict = {
            '评论': reviews,
            '评论时间': comment_time,
            '评论人': username,
            '电影名': movie_name,
            '评分': rating
        }
        data1.append(review_dict)

# 2.2 将数据保存为csv文件
data1 = pd.DataFrame(data1, columns=['评论', '评论时间', '评论人', '电影名', '评分'])
data1.to_csv('movie_reviews.csv', index=False)

# 2.3 将数据保存到文件
filename = 'data.txt'
with open(filename, 'w', encoding='utf-8') as file:
    for item in data:
        file.write(item + '\n')

print("数据已保存到文件:", filename)
