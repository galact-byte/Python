import pandas as pd
import requests
from bs4 import BeautifulSoup
import time


# 获取豆瓣电影top250链接(只是获取了5页排名的链接)
def get_top250_urls():
    urls = []
    n = [i for i in range(0, 226, 25)]
    for i in n:
        url = "https://movie.douban.com/top250?start=" + str(i) + "&filter="
        urls.append(url)
    return urls


# 获取电影链接(每部电影详细内容的链接)
def get_movie_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        names = soup.find_all('div', class_='hd')
        data = []
        for ne in names:
            a_tag = ne.find('a')
            href = a_tag.get('href')
            data.append(href)
        return data
    else:
        print('无法访问网页')
        return []


# 获取影评
def get_movie_reviews(movie_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    response = requests.get(movie_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        movie_name = soup.find('h1').find('span', property='v:itemreviewed').text.strip()
        comments = soup.find_all('p', class_='comment-content')
        names = soup.find_all('span', class_='comment-info')
        data = []
        for co, na in zip(comments, names):
            username = na.find('a').text.strip()
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
            if co.find('span', class_='expand'):
                co.find('span', class_='expand').decompose()
            full_comment = co.find('span', class_='full')
            if full_comment:
                reviews = full_comment.text.strip()
            else:
                reviews = co.get_text().strip()
            comment_time = na.find('span', class_='comment-time').text.strip()
            review_dict = {
                '评论': reviews,
                '评论时间': comment_time,
                '评论人': username,
                '电影名': movie_name,
                '评分': rating
            }
            data.append(review_dict)
        return data
    else:
        print('无法访问网页')
        return []


# 保存数据到文件
def save_data_to_file(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        for item in data:
            file.write(item + '\n')
    print(f"数据已保存到文件: {filename}")


# 主函数
def main():
    urls = get_top250_urls()  # 获取排名链接
    movie_urls = []
    reviews_data = []

    for url in urls:
        movie_urls.extend(get_movie_url(url))

    for movie_url in movie_urls:
        reviews_data.extend(get_movie_reviews(movie_url))
        time.sleep(5)  # 添加时间间隔，避免频繁访问网站

    reviews_df = pd.DataFrame(reviews_data, columns=['评论', '评论时间', '评论人', '电影名', '评分'])
    reviews_df.to_csv('movie_reviews.csv', index=False)
    save_data_to_file(movie_urls, 'TOP250URL.txt')


if __name__ == "__main__":
    main()
