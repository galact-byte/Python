# BidMiner

这是一个把 PDF 里的招标/采购信息提取到 Excel 的小工具。

## 给使用者的最简步骤

如果你不是做技术的，只要按下面做：

1. 安装 `Python 3.11`
2. 安装时一定勾选 `Add Python to PATH`
3. 双击 `install.bat`
4. 打开 `api_key.json`，把你的阿里百炼 `API Key` 填进去
5. 把要处理的 PDF 放进 `pdfs` 文件夹
6. 双击 `run.bat`
7. 等待处理完成，到 `output` 文件夹里拿 Excel

## 第一次使用

### 1. 安装 Python

下载地址：

`https://www.python.org/downloads/`

建议安装：

- `Python 3.11`
- `64-bit`

安装时最重要的一步：

- 勾选 `Add Python to PATH`

如果这一步没勾，后面的 `bat` 可能会运行失败。

### 2. 安装程序依赖

双击：

`install.bat`

它会自动完成这些事情：

- 创建独立运行环境 `.venv`
- 安装程序需要的依赖包

安装成功后，再继续下一步。

## 填写 API Key

打开：

`api_key.json`

把内容改成下面这种格式：

```json
{
  "DASHSCOPE_API_KEY": "sk-你的真实Key"
}
```

阿里百炼控制台：

`https://dashscope.console.aliyun.com/`

## 开始提取

### 1. 放入 PDF

把待处理的 PDF 文件放到：

`pdfs`

### 2. 运行

双击：

`run.bat`

程序会自动：

- 检查运行环境
- 检查 `API Key`
- 检查 `pdfs` 文件夹里有没有 PDF
- 调用模型提取信息
- 生成 Excel

### 3. 查看结果

处理完成后，到这里查看结果：

`output`

每次运行都会生成一个新的 Excel 文件。

## 常见问题

### 1. 双击 `install.bat` 或 `run.bat` 没反应

通常是没有正确安装 Python，或者安装时没有勾选：

`Add Python to PATH`

### 2. 提示 `API Key` 错误

请检查：

- `api_key.json` 是否填写了真实的 Key
- Key 是否可用
- 阿里百炼账户是否正常

### 3. 提示 `pdfs` 文件夹里没有 PDF

说明你还没有把 PDF 放进去。

请把待处理文件放到：

`pdfs`

### 4. Excel 里有些字段是 `/`

这表示该字段当前没有可用值，常见情况有：

- 原文没有写
- 该字段对当前公告类型不适用
- 模型没有稳定识别出来

具体原因会尽量写在 Excel 的“提取备注”列里。

### 5. 运行时报网络或接口错误

常见原因：

- 电脑没有联网
- 网络限制导致无法访问接口
- `API Key` 无效

## 文件说明

- `install.bat`：第一次使用先双击它
- `run.bat`：正式运行时双击它
- `api_key.json`：填写 API Key
- `pdfs`：放 PDF
- `output`：查看结果
- `main.py`：核心提取程序
- `launcher.py`：启动和环境检查程序
