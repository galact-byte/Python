# Pixiv 图片下载工具使用说明

## 功能说明

这个工具可以：
1. 从你提供的特殊格式文本中提取Pixiv作品ID
2. 去除重复的ID
3. 生成作品页面URL列表
4. （可选）尝试下载图片

## 安装依赖

```bash
pip install requests --break-system-packages
```

## 使用方法

### 方法1：交互式运行（推荐）

```bash
python pixiv_downloader.py
```

然后按提示选择操作模式。

### 方法2：直接处理文本文件

```bash
python pixiv_batch_processor.py input.txt
```

## 关于下载图片的重要说明

⚠️ **Pixiv图片下载需要登录认证**

由于Pixiv的反爬虫机制，直接下载原图需要：
1. 有效的登录cookies
2. 正确的请求头
3. 可能需要代理

### 推荐的下载方案：

#### 方案A：使用浏览器插件（最简单）
1. 使用本脚本生成URL列表（会保存在 `pixiv_images/pixiv_urls.txt`）
2. 安装浏览器插件如：
   - Pixiv Downloader
   - Pixiv Toolkit
   - Image Downloader
3. 在Pixiv网站登录后使用插件批量下载

#### 方案B：使用专门的下载工具
使用开源工具如：
- **PixivUtil2** (推荐)
- **gallery-dl**
- **Pixiv Downloader**

PixivUtil2使用示例：
```bash
# 下载单个作品
pixivutil2.py -s 12345678

# 从ID列表文件下载
pixivutil2.py -f pixiv_ids.txt
```

#### 方案C：配置本脚本的cookies（高级用户）

如果你想使用本脚本直接下载，需要：

1. 在浏览器登录Pixiv
2. 获取cookies（使用浏览器开发者工具）
3. 修改脚本添加cookies：

```python
self.session.cookies.update({
    'PHPSESSID': 'your_session_id_here',
    # 其他必要的cookies
})
```

## 输出文件说明

脚本会在 `pixiv_images/` 目录下生成：

- `pixiv_ids.txt` - 提取并去重后的ID列表（每行一个）
- `pixiv_urls.txt` - 作品页面URL列表（可直接在浏览器打开）

## 示例数据格式

你的数据格式：
```
id：100268677|||id：100333887|||id：100364267|||id：101385007
id：101385007|||id：102941645|||id：103298540|||id：103372416
```

提取后的ID列表：
```
100268677
100333887
100364267
101385007
102941645
...
```

## 常见问题

**Q: 为什么下载失败？**
A: Pixiv需要登录才能下载图片。建议使用方案A或B。

**Q: 如何批量在浏览器打开？**
A: 使用生成的 `pixiv_urls.txt` 文件：
- Windows: 可以写一个批处理脚本
- Linux/Mac: 使用 `xargs` 命令
- 或使用浏览器的"打开多个URL"插件

**Q: 重复的ID会被处理吗？**
A: 是的，脚本会自动去重并保持第一次出现的顺序。

## 许可

本工具仅供个人学习研究使用，请遵守Pixiv的使用条款。
