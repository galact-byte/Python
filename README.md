## 🌱 初学的脚印

这个分支（main）保存了我最早的 Python 学习代码。  
那些笨拙的练习，是我成长路上最真实的起点。  
现在它只作为纪念被保留在这里，不会再修改。


## 1. 豆瓣电影Top250影评爬虫

### 概述
脚本可以用来爬取豆瓣电影Top250榜单上电影的影评。

### 使用说明
1. 安装所需的Python库：
   ```bash
   pip install requests beautifulsoup4
2. 运行脚本：
   ```bash
   python movies.py
3. 程序将爬取豆瓣top250电影的名字、评论人、评论时间、评分、评论。
4. 链接保存为txt文件,评论存为csv文件

## 2. RJ号游戏信息爬虫

### 概述
脚本用于爬取指定RJ号的游戏信息，包括游戏名字、图片和介绍内容。

### 使用说明
1. 安装所需的Python库：  
   ```bash
   pip install requests beautifulsoup4 pillow
2. 运行脚本：  
   ```bash
   python game.py
3. 输入要爬取的RJ号，可以一次输入多个，用逗号、空格或中文逗号分隔。  
4. 程序将爬取并显示每个RJ号游戏的信息，包括游戏名字、图片和介绍内容。  
5. 图片将保存在名为 "game_images" 的文件夹中,其余信息存为csv文件。  

## 可以使用pyinstaller打包成exe文件在没有python的环境使用
### 参数说明:
- D: 默认选项,除了主程序demo.exe外,还会在在dist文件夹中生成很多依赖文件。   
- c: 默认选项。使用控制台,只对windows有效。   
- F: 只在dist文件夹中生成一个程序demo.exe文件,适用于没有多依赖.py文件的单个文件。   
- w: 不使用控制台,只对windows有效。      
- p: 设置导入路径。   
- i: 给生成的demo.exe文件设置一个自定义的图标。   
### 使用说明
1. 简单的py文件可以直接运行脚本:
   ```bash 
   pyinstaller –F xxx.py
   ``` 
   执行完毕后，程序目录下生成了build、dist两个文件夹和一个xxx.spec文件。生成的exe文件即存在于dist文件夹中。  

2. 较为复杂的,有许多依赖的其他路径下的.py文件之类的需要通过spec配置文件进行打包发布: 

(1) 生成spec文件,执行下列命令:  

```bash
pyi-makespec main.py
```  

执行后生成main.spec文件(main.py是项目启动的入口文件)
       
(2) 完善spec文件中的内容  

a. Analysis的第一个列表：填入需要打包的.py文件路径，以字符串形式作为列表元素填入。
<details>
注: 填的路径是绝对路径，目录使用双反斜杠避开转义符；

打包操作实质上就是将这些文件直接复制到生成的包中。 
</details>

b. Analysis的datas列表：填入需要打包的非.py类型资源文件，以元组形式作为列表元素填入，路径写至最后一个目录层级。  

c. Analysis的hiddenimports列表：填入需要直接或间接依赖的一系列包名。  

(3) 打包发布,执行命令:   

```bash
pyinstaller –D main.spec
```  
       
dist目录下的main文件夹即发布生成的项目文件。  

## 3.简单的收支计算
