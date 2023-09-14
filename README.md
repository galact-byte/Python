# 1. 豆瓣电影Top250影评爬虫

## 概述
脚本可以用来爬取豆瓣电影Top250榜单上电影的影评。

## 使用说明
1. 安装所需的Python库：
   ```bash
   pip install requests beautifulsoup4
2. 运行脚本：
   python movies.py
3. 程序将爬取豆瓣top250电影的名字、评论人、评论时间、评分、评论。
4. 链接保存为txt文件,评论存为csv文件

# 2. RJ号游戏信息爬虫

## 概述
脚本用于爬取指定RJ号的游戏信息，包括游戏名字、图片和介绍内容。

## 使用说明
1. 安装所需的Python库：
   ```bash
   pip install requests beautifulsoup4 pillow
2. 运行脚本：
   python game.py
3.输入要爬取的RJ号，可以一次输入多个，用逗号、空格或中文逗号分隔。
4.程序将爬取并显示每个RJ号游戏的信息，包括游戏名字、图片和介绍内容。
5.图片将保存在名为 "game_images" 的文件夹中,其余信息存为csv文件。

