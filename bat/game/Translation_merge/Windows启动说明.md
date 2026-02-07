# Windows 用户启动说明

## ⚠️ 重要：编码问题解决方案

由于Windows批处理文件的编码问题，请使用以下方法之一启动程序：

## 方法1：使用 RUN.bat（推荐）✅

**最简单的方法：**

1. 双击 `RUN.bat`
2. 等待自动检查和安装依赖
3. 程序自动启动

## 方法2：使用 launcher.py

1. 双击 `launcher.py`
2. 如果提示选择程序，选择 Python
3. 或者右键 → 打开方式 → Python

## 方法3：手动命令行

打开命令提示符（CMD）或 PowerShell，进入程序目录：

```cmd
cd E:\Python\Programs\test\Translation_merge
python launcher.py
```

或直接启动主程序：

```cmd
python translation_gui.py
```

## 方法4：直接运行（如果依赖已安装）

如果你已经安装了 PyQt6 和 requests：

```cmd
python translation_gui.py
```

## 🔧 如果遇到 "Python不是内部或外部命令" 错误

说明 Python 没有添加到系统 PATH，有两个解决方案：

### 解决方案A：重装Python并勾选 "Add Python to PATH"

1. 从 https://www.python.org/downloads/ 下载 Python
2. 运行安装程序
3. ⚠️ **勾选底部的 "Add Python to PATH"**
4. 点击 "Install Now"

### 解决方案B：找到Python完整路径

1. 找到 Python 安装位置，例如：
   - `C:\Python311\python.exe`
   - `C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe`

2. 使用完整路径运行：
   ```cmd
   C:\Python311\python.exe launcher.py
   ```

## 📦 手动安装依赖（如果自动安装失败）

打开命令提示符，运行：

```cmd
pip install PyQt6 requests
```

或使用 requirements.txt：

```cmd
pip install -r requirements.txt
```

## ✅ 验证安装

运行以下命令检查：

```cmd
python --version
pip list
```

应该能看到 Python 版本和已安装的包列表。

## 🎯 启动成功后

程序会打开图形界面，包含三个标签页：

1. **合并文件** - 比对新旧版本
2. **API翻译** - 使用AI翻译
3. **回写结果** - 生成最终文件

详细使用方法请查看 `QUICKSTART.md` 或 `README.md`。

---

**如果还有问题，请确保：**
- ✅ Python 3.8+ 已安装
- ✅ Python 已添加到系统 PATH
- ✅ 使用 CMD 或 PowerShell（不是 Git Bash）
- ✅ 所有文件在同一文件夹内
