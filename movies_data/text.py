import requests
from bs4 import BeautifulSoup

# IMDb Top 250 页面的 URL
url = 'https://www.imdb.com/chart/top'
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'}
# 发送 GET 请求获取页面内容
response = requests.get(url,headers=headers)

# 使用 BeautifulSoup 解析 HTML 页面
soup = BeautifulSoup(response.text, 'html.parser')

# 定位电影列表的容器元素
movie_list = soup.find('tbody', {'class': 'lister-list'})

# 创建并打开结果文件
file = open('imdb_reviews.txt', 'w', encoding='utf-8')

# 遍历每个电影条目并获取评论
for movie in movie_list.find_all('tr'):
    # 获取电影标题和评分
    title_element = movie.find('td', {'class': 'titleColumn'})
    rating_element = movie.find('td', {'class': 'ratingColumn'})

    if title_element and rating_element:
        title = title_element.find('a').text.strip()
        rating = rating_element.find('strong').text.strip()

        # 获取电影详情页面的链接
        movie_link = title_element.find('a')['href']
        movie_url = 'https://www.imdb.com' + movie_link

        # 发送 GET 请求获取电影详情页面内容
        movie_response = requests.get(movie_url)
        movie_soup = BeautifulSoup(movie_response.text, 'html.parser')

        # 定位用户评论的容器元素
        review_container = movie_soup.find('div', {'class': 'lister-list'})

        # 遍历每个用户评论并获取评论内容
        if review_container:
            for review in review_container.find_all('div', {'class': 'lister-item-content'}):
                review_text = review.find('div', {'class': 'text'}).text.strip()

                # 将结果写入文件
                file.write('Title: ' + title + '\n')
                file.write('Rating: ' + rating + '\n')
                file.write('Review: ' + review_text + '\n')
                file.write('-----------------------\n')

# 关闭文件
file.close()
