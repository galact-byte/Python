# MEGAcmd 批量下载教程

> 用途：从 MEGA 网盘**整个文件夹一次性拖下来**，零弹窗、零点击、断点续传。
> 适合几百上千个文件的批量下载，替代浏览器逐个「另存为」点保存。

---

## 零、要会员吗？

**不要。** MEGAcmd 工具本身完全免费，免费账号甚至不登录都能用。

唯一的限制是 MEGA 的**每日下载流量配额**（按 IP / 账号算）——但这个限制用浏览器还是用 MEGAcmd 都一样，换工具绕不过去。撞到配额时 MEGA 会让你等几小时，而 MEGAcmd 的好处是会**自动等待 + 续传**，不用守着。

---

## 一、安装

下载 Windows 安装包，双击安装：

- 官方地址：https://mega.io/cmd
- 备用：https://mega.nz/cmd

装完会得到两样东西：

1. **MEGAcmd 终端**：开始菜单搜 "MEGAcmd"，是个独立命令行窗口。
   在里面敲命令**不用加 `mega-` 前缀**（直接 `get`、`ls`、`login`）。
2. **`mega-*` 命令脚本**：位于 `%LOCALAPPDATA%\MEGAcmd\`，
   可以在普通 **CMD / PowerShell** 里调用（**要加 `mega-` 前缀**）。

下面的例子都用普通 CMD 写法（带 `mega-` 前缀）。

---

## 二、核心用法：下载公开文件夹链接（最常用）

公开链接**无需登录**，直接拖整个文件夹：

```cmd
mega-get "https://mega.nz/folder/xxxxx#yyyyy" "E:\Downloads\目标文件夹"
```

- 第一个参数：MEGA 文件夹分享链接
- 第二个参数：本地保存目录（整个文件夹连同里面所有文件会**递归**下载进去）
- ⚠️ **链接务必加引号**，否则里面的 `#` 会被命令行当成注释截断

---

## 三、救命选项

| 选项 | 作用 |
| :--- | :--- |
| `-q` | 后台队列下载，不阻塞窗口，可以继续敲别的命令 |
| `-m` | 目标文件夹已存在时**合并**：保留已下好的，只补缺失的（适合补下到一半的任务） |
| `--password=xxx` | 链接带密码时使用 |
| `--help` | 查看某命令全部参数，如 `mega-get --help` |

**断点续传**：中途关闭 / 断网后，重新跑**同一条** `mega-get` 命令，会接着没下完的继续，不会从头开始。

---

## 四、登录账号下载自己网盘的文件（可选）

```cmd
mega-login 你的邮箱 你的密码
mega-ls                              REM 列出网盘内容
mega-get "/某个文件夹" "E:\Downloads"
mega-logout
```

---

## 五、下次标准流程（三步）

1. 复制 MEGA 文件夹分享链接
2. 普通 CMD 里执行：`mega-get "链接" "E:\目标目录"`
3. 该干嘛干嘛，回来文件全在了——全程一次保存都不用点

---

## 六、命令速查表（复制即用）

```cmd
REM ── 下载公开文件夹链接（无需登录，最常用）──
mega-get "https://mega.nz/folder/xxxxx#yyyyy" "E:\Downloads\目标文件夹"

REM ── 后台下载，不阻塞窗口 ──
mega-get -q "https://mega.nz/folder/xxxxx#yyyyy" "E:\Downloads\目标文件夹"

REM ── 续传 / 补下到一半的任务（合并，已下好的不重下）──
mega-get -m "https://mega.nz/folder/xxxxx#yyyyy" "E:\Downloads\目标文件夹"

REM ── 带密码的链接 ──
mega-get --password=你的密码 "https://mega.nz/folder/xxxxx#yyyyy" "E:\Downloads\目标文件夹"

REM ── 登录后下载自己网盘 ──
mega-login 你的邮箱 你的密码
mega-ls
mega-get "/某个文件夹" "E:\Downloads"
mega-logout

REM ── 查看任意命令的全部参数 ──
mega-get --help

REM ── 查看正在进行的传输 ──
mega-transfers
```

> 说明：上面是**普通 CMD / PowerShell** 的写法（带 `mega-` 前缀）。
> 如果你开的是 MEGAcmd 自带的终端窗口，去掉 `mega-` 前缀即可，例如 `get "链接" "目录"`。

---

## 参考来源

- [MEGAcmd get 命令官方文档](https://github.com/meganz/MEGAcmd/blob/master/contrib/docs/commands/get.md)
- [MEGAcmd 用户指南](https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md)
- [多链接下载讨论 Issue #829](https://github.com/meganz/MEGAcmd/issues/829)
