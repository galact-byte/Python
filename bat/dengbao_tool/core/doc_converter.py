"""DOC 格式转换 — .doc → .docx"""

import os


def find_docx_alternative(doc_path: str) -> str | None:
    """
    查找同目录下是否有可用的 .docx 替代文件。
    例如选了 备案表_XX.doc，但目录下有 01-新备案表.docx，也可以用。
    """
    if not doc_path.lower().endswith('.doc'):
        return None

    dir_path = os.path.dirname(doc_path)

    # 先检查同名 .docx
    docx_same = doc_path + "x"
    if os.path.exists(docx_same):
        return docx_same

    # 搜索同目录下其他 .docx 文件（含相关关键字）
    base = os.path.basename(doc_path).lower()
    keywords = []
    if "备案表" in base:
        keywords = ["备案表", "新备案表"]
    elif "定级报告" in base:
        keywords = ["定级报告"]

    if keywords:
        for f in os.listdir(dir_path):
            if f.lower().endswith('.docx') and any(k in f for k in keywords):
                return os.path.join(dir_path, f)

    return None


def convert_doc_to_docx(doc_path: str) -> str | None:
    """
    将 .doc 转换为 .docx。
    优先查找已有的 .docx 替代文件，找不到再尝试 win32com 转换。
    """
    if not doc_path.lower().endswith('.doc'):
        return doc_path

    # 先找现成的 .docx
    alt = find_docx_alternative(doc_path)
    if alt:
        return alt

    # 尝试 win32com 转换
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        return None

    docx_path = doc_path + "x"
    word = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False

        abs_path = os.path.abspath(doc_path)
        doc = word.Documents.Open(abs_path)
        doc.SaveAs2(os.path.abspath(docx_path), FileFormat=16)
        doc.Close()
        return docx_path
    except Exception as e:
        print(f"转换失败: {e}")
        return None
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
