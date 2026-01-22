import os
import re


## 当你有一堆用顿号或逗号分隔的IP/URL，需要转换成每行一个的格式时使用

def detect_content_type(content):
    """检测内容类型：IP地址还是URL"""
    # 简单的IP地址正则
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    # 简单的URL正则
    url_pattern = r'https?://[^\s、,，]+'

    ip_matches = re.findall(ip_pattern, content)
    url_matches = re.findall(url_pattern, content)

    if url_matches:
        return "URL", len(url_matches)
    elif ip_matches:
        return "IP", len(ip_matches)
    else:
        return "未知", 0


def convert_addresses():
    print("=== IP/URL地址格式转换工具 ===")
    print("支持格式:")
    print("- IP地址: 22.168.107.1、22.168.107.2、22.168.107.3")
    print("- URL: http://example.com、https://test.com")
    print("输出格式: 每行一个地址")
    print("提示: 支持多行输入，输入完成后输入一个空行结束")
    print()

    # 获取用户输入（支持多行）
    print("请输入地址 (IP或URL，用顿号、逗号或空格分隔，可以多行输入):")
    input_lines = []
    while True:
        line = input().strip()
        if line == "":  # 空行表示输入结束
            if input_lines:  # 如果已经有输入内容
                break
            else:  # 如果还没有输入任何内容
                print("输入不能为空，请重新输入!")
                continue
        input_lines.append(line)

        if not (line.endswith('、') or line.endswith(',') or line.endswith('，')):
            break

    # 将所有行合并
    full_input = " ".join(input_lines)

    # 检测内容类型
    content_type, detected_count = detect_content_type(full_input)
    print(f"\n检测到内容类型: {content_type}")

    # 处理地址 - 支持多种分隔符
    # 替换各种分隔符为统一的逗号
    processed_input = full_input.replace('、', ',').replace('，', ',').replace(' ', ',').replace('\n', ',')
    # 按逗号分割
    address_list = processed_input.split(',')
    # 去除每个地址前后的空白字符，过滤空字符串
    address_list = [addr.strip() for addr in address_list if addr.strip()]

    if not address_list:
        print("❌ 没有找到有效的地址!")
        return

    print(f"\n解析到 {len(address_list)} 个地址:")
    # 只显示前10个，如果太多的话
    display_count = min(10, len(address_list))
    for i in range(display_count):
        print(f"{i + 1}. {address_list[i]}")

    if len(address_list) > 10:
        print(f"... 还有 {len(address_list) - 10} 个地址")

    # 获取保存路径
    print("\n请选择保存路径:")
    print("1. 当前文件夹 (默认)")
    print("2. 自定义路径")

    choice = input("请选择 (1/2，直接回车选择1): ").strip()

    if choice == '2':
        save_path = input("请输入保存路径: ").strip()
        if not save_path or not os.path.exists(save_path):
            if save_path:
                print(f"路径不存在: {save_path}")
            save_path = os.getcwd()
            print(f"使用当前路径: {save_path}")
    else:
        save_path = os.getcwd()
        print(f"使用当前路径: {save_path}")

    # 获取文件名
    default_name = "ips.txt" if content_type == "IP" else "urls.txt"
    filename = input(f"请输入文件名 (直接回车使用默认名'{default_name}'): ").strip()
    if not filename:
        filename = default_name
    elif not filename.endswith('.txt'):
        filename += '.txt'

    # 完整文件路径
    full_path = os.path.join(save_path, filename)

    # 写入文件
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            for addr in address_list:
                f.write(addr + '\n')

        print(f"\n✅ 转换完成!")
        print(f"📁 文件保存至: {full_path}")
        print(f"📊 共保存 {len(address_list)} 个{content_type}地址")

        # 简单验证
        if content_type == "IP":
            valid_ips = [addr for addr in address_list if re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', addr.strip())]
            if len(valid_ips) != len(address_list):
                print(f"⚠️  警告: 检测到 {len(address_list) - len(valid_ips)} 个可能无效的IP地址格式")
        elif content_type == "URL":
            valid_urls = [addr for addr in address_list if re.match(r'^https?://', addr.strip())]
            if len(valid_urls) != len(address_list):
                print(f"⚠️  警告: 检测到 {len(address_list) - len(valid_urls)} 个可能无效的URL格式")

    except Exception as e:
        print(f"❌ 保存文件时出错: {e}")


def main():
    try:
        convert_addresses()
    except KeyboardInterrupt:
        print("\n\n程序已取消")
    except Exception as e:
        print(f"\n程序出错: {e}")


if __name__ == "__main__":
    main()
