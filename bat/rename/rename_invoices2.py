import os
import re
import sys
from pathlib import Path

# 检查依赖库
try:
    import pdfplumber
except ImportError:
    print("❌ 错误：请先安装 pdfplumber 库")
    print("安装命令：pip install pdfplumber")
    sys.exit(1)


def get_folder_path():
    """获取并验证文件夹路径"""
    while True:
        folder = input("请输入存放发票 PDF 的文件夹路径：").strip()
        folder_path = Path(folder)

        if not folder_path.exists():
            print("❌ 文件夹不存在，请重新输入")
            continue

        if not folder_path.is_dir():
            print("❌ 输入的不是文件夹，请重新输入")
            continue

        return folder_path


def extract_invoice_number(pdf_path):
    """从PDF中提取发票号码"""
    # 匹配20位数字（发票号码）
    pattern = re.compile(r"\b\d{20}\b")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                return None

            page = pdf.pages[0]

            # 定义多个搜索区域（右上角、左上角、上半部分）
            search_areas = [
                (395, 0, 595, 200),  # A4 纸右上角（酒店发票）
                (0, 0, 200, 200),  # A4 纸左上角（高铁发票）
                (0, 0, 595, 300),  # 整个上半部分
            ]

            # 依次在不同区域搜索
            for bbox in search_areas:
                try:
                    crop = page.within_bbox(bbox)
                    area_text = crop.extract_text()
                    if area_text:
                        match = pattern.search(area_text)
                        if match:
                            return match.group(0)
                except Exception:
                    continue  # 如果某个区域提取失败，继续尝试下一个

            # 如果指定区域都没找到，最后尝试全页搜索
            try:
                full_text = page.extract_text()
                if full_text:
                    match = pattern.search(full_text)
                    if match:
                        return match.group(0)
            except Exception:
                pass

    except Exception as e:
        print(f"❌ 读取PDF失败 {pdf_path.name}: {e}")

    return None


def get_unique_filename(folder_path, base_name):
    """生成唯一的文件名，避免重名覆盖"""
    new_filepath = folder_path / f"{base_name}.pdf"

    if not new_filepath.exists():
        return new_filepath

    count = 1
    while True:
        new_filepath = folder_path / f"{base_name}_{count}.pdf"
        if not new_filepath.exists():
            return new_filepath
        count += 1


# def rename_invoice_pdfs():
#     """主函数：批量重命名发票PDF"""
#     folder_path = get_folder_path()
#
#     # ---------- 修复点：只收集一次所有扩展名为 .pdf 的文件（不重复） ----------
#     # 推荐做法：用 iterdir + suffix.lower() 来避免重复匹配（兼容大小写）
#     all_pdf_files = [p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() == '.pdf']
#
#     # 过滤掉已经是发票号码格式的文件（避免重复处理）
#     invoice_pattern = re.compile(r"^\d{20}(_\d+)?\.pdf$", re.IGNORECASE)
#     pdf_files = [f for f in all_pdf_files if not invoice_pattern.match(f.name)]
#
#     if not pdf_files:
#         already_renamed = len(all_pdf_files) - len(pdf_files)
#         if already_renamed > 0:
#             print(f"✅ 所有PDF文件已经是发票号码格式，无需重命名")
#         else:
#             print("❌ 文件夹中没有找到PDF文件")
#         return
#
#     print(f"找到 {len(pdf_files)} 个待处理的PDF文件")
#     if len(all_pdf_files) > len(pdf_files):
#         print(f"跳过 {len(all_pdf_files) - len(pdf_files)} 个已经是发票号码格式的文件")
#     print("-" * 50)
#
#     success_count = 0
#     failed_count = 0
#     duplicate_count = 0
#
#     # 记录已发现的发票号码，用于检测重复
#     found_invoices = {}
#
#     for pdf_file in pdf_files:
#         print(f"正在处理: {pdf_file.name}")
#
#         # 提取发票号码
#         invoice_number = extract_invoice_number(pdf_file)
#
#         if not invoice_number:
#             print(f"⚠️ 未找到20位发票号码: {pdf_file.name}")
#             failed_count += 1
#             continue
#
#         print(f"📄 提取到发票号码: {invoice_number}")
#
#         # 检查是否有重复的发票号码
#         if invoice_number in found_invoices:
#             print(f"⚠️ 发现重复发票号码 {invoice_number}:")
#             print(f"   已存在: {found_invoices[invoice_number]}")
#             print(f"   当前文件: {pdf_file.name}")
#             duplicate_count += 1
#
#             # 对重复的文件添加后缀
#             new_filepath = get_unique_filename(folder_path, invoice_number)
#         else:
#             # 首次出现的发票号码，直接使用
#             new_filepath = folder_path / f"{invoice_number}.pdf"
#             found_invoices[invoice_number] = pdf_file.name
#
#         # 如果目标文件名与原文件名相同，跳过重命名
#         if pdf_file.name == new_filepath.name:
#             print(f"⏭️ 文件名已正确: {pdf_file.name}")
#             success_count += 1
#             continue
#
#         # 重命名文件
#         try:
#             pdf_file.rename(new_filepath)
#             print(f"✅ 重命名成功: {pdf_file.name} -> {new_filepath.name}")
#             success_count += 1
#
#         except PermissionError:
#             print(f"❌ 权限不足，无法重命名: {pdf_file.name}")
#             failed_count += 1
#         except Exception as e:
#             print(f"❌ 重命名失败 {pdf_file.name}: {e}")
#             failed_count += 1
#
#         print()  # 添加空行，让输出更清晰
#
#     # 统计结果
#     print("-" * 50)
#     print(f"处理完成！成功: {success_count} 个，失败: {failed_count} 个")
#     if duplicate_count > 0:
#         print(f"发现重复发票号码: {duplicate_count} 个（已添加后缀区分）")
def rename_invoice_pdfs():
    """主函数：批量重命名发票PDF"""
    folder_path = get_folder_path()

    # ---------- 改动：递归遍历目录树 ----------
    all_pdf_files = [p for p in folder_path.rglob("*") if p.is_file() and p.suffix.lower() == '.pdf']

    # 过滤掉已经是发票号码格式的文件（避免重复处理）
    invoice_pattern = re.compile(r"^\d{20}(_\d+)?\.pdf$", re.IGNORECASE)
    pdf_files = [f for f in all_pdf_files if not invoice_pattern.match(f.name)]

    if not pdf_files:
        already_renamed = len(all_pdf_files) - len(pdf_files)
        if already_renamed > 0:
            print(f"✅ 所有PDF文件已经是发票号码格式，无需重命名")
        else:
            print("❌ 文件夹中没有找到PDF文件")
        return

    print(f"找到 {len(pdf_files)} 个待处理的PDF文件")
    if len(all_pdf_files) > len(pdf_files):
        print(f"跳过 {len(all_pdf_files) - len(pdf_files)} 个已经是发票号码格式的文件")
    print("-" * 50)

    success_count = 0
    failed_count = 0
    duplicate_count = 0
    no_invoice_count = 0  # 新增：不是发票 / 没有20位发票号码的文件数量

    # 记录已发现的发票号码，用于检测重复（全局唯一）
    found_invoices = {}

    for pdf_file in pdf_files:
        print(f"正在处理: {pdf_file}")

        # 提取发票号码
        invoice_number = extract_invoice_number(pdf_file)

        if not invoice_number:
            print(f"⏭️ 跳过（非发票或无发票号码）: {pdf_file}")
            no_invoice_count += 1
            continue

        print(f"📄 提取到发票号码: {invoice_number}")

        # 检查是否有重复的发票号码
        if invoice_number in found_invoices:
            print(f"⚠️ 发现重复发票号码 {invoice_number}:")
            print(f"   已存在: {found_invoices[invoice_number]}")
            print(f"   当前文件: {pdf_file.name}")
            duplicate_count += 1

            # 对重复的文件添加后缀（在当前文件夹下）
            new_filepath = get_unique_filename(pdf_file.parent, invoice_number)
        else:
            # 首次出现的发票号码，直接使用
            new_filepath = pdf_file.parent / f"{invoice_number}.pdf"
            found_invoices[invoice_number] = str(pdf_file)

        # 如果目标文件名与原文件名相同，跳过重命名
        if pdf_file.name == new_filepath.name:
            print(f"⏭️ 文件名已正确: {pdf_file}")
            success_count += 1
            continue

        # 重命名文件
        try:
            pdf_file.rename(new_filepath)
            print(f"✅ 重命名成功: {pdf_file.name} -> {new_filepath.name}")
            success_count += 1

        except PermissionError:
            print(f"❌ 权限不足，无法重命名: {pdf_file}")
            failed_count += 1
        except Exception as e:
            print(f"❌ 重命名失败 {pdf_file}: {e}")
            failed_count += 1

        print()  # 添加空行，让输出更清晰

    # 统计结果
    print("-" * 50)
    print(f"处理完成！成功: {success_count} 个，失败: {failed_count} 个")
    if no_invoice_count > 0:
        print(f"跳过（非发票/无发票号码）: {no_invoice_count} 个")
    if duplicate_count > 0:
        print(f"发现重复发票号码: {duplicate_count} 个（已添加后缀区分）")


if __name__ == "__main__":
    try:
        rename_invoice_pdfs()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")