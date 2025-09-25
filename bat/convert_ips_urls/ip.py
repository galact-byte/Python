import os


def convert_ips():
    print("=== IP地址格式转换工具 ===")
    print("输入格式示例: 22.168.107.1、22.168.107.2、22.168.107.3")
    print("输出格式: 每行一个IP地址")
    print("提示: 支持多行输入，输入完成后输入一个空行结束")
    print()

    # 获取用户输入的IP地址（支持多行）
    print("请输入IP地址 (用顿号或逗号分隔，可以多行输入):")
    ip_lines = []
    while True:
        line = input().strip()
        if line == "":  # 空行表示输入结束
            if ip_lines:  # 如果已经有输入内容
                break
            else:  # 如果还没有输入任何内容
                print("输入不能为空，请重新输入!")
                continue
        ip_lines.append(line)

    # 将所有行合并
    ip_input = " ".join(ip_lines)

    # 处理IP地址 - 支持顿号和逗号分隔，以及换行
    # 替换中文顿号为英文逗号，处理换行符
    ip_input = ip_input.replace('、', ',').replace('\n', ',')
    ip_list = ip_input.split(',')
    # 去除每个IP前后的空白字符，过滤空字符串
    ip_list = [ip.strip() for ip in ip_list if ip.strip()]

    print(f"\n解析到 {len(ip_list)} 个IP地址:")
    for i, ip in enumerate(ip_list, 1):
        print(f"{i}. {ip}")

    # 获取保存路径
    print("\n请选择保存路径:")
    print("1. 当前文件夹 (默认)")
    print("2. 自定义路径")

    choice = input("请选择 (1/2，直接回车选择1): ").strip()

    if choice == '2':
        save_path = input("请输入保存路径: ").strip()
        if not os.path.exists(save_path):
            print(f"路径不存在: {save_path}")
            save_path = os.getcwd()
            print(f"使用当前路径: {save_path}")
    else:
        save_path = os.getcwd()
        print(f"使用当前路径: {save_path}")

    # 获取文件名
    filename = input("请输入文件名 (直接回车使用默认名'ips.txt'): ").strip()
    if not filename:
        filename = "ips.txt"
    elif not filename.endswith('.txt'):
        filename += '.txt'

    # 完整文件路径
    full_path = os.path.join(save_path, filename)

    # 写入文件
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            for ip in ip_list:
                f.write(ip + '\n')

        print(f"\n✅ 转换完成!")
        print(f"📁 文件保存至: {full_path}")
        print(f"📊 共保存 {len(ip_list)} 个IP地址")

    except Exception as e:
        print(f"❌ 保存文件时出错: {e}")


if __name__ == "__main__":
    try:
        convert_ips()
        input("\n按回车键退出...")
    except KeyboardInterrupt:
        print("\n\n程序已取消")
    except Exception as e:
        print(f"\n程序出错: {e}")
        input("按回车键退出...")