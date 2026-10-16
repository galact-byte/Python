"""使用虚构公告验证真实接口和 Excel 输出；会产生少量模型调用费用。"""

import tempfile
from pathlib import Path

import main
from model_config import configure_models


ANNOUNCEMENT = """太原市测试学校设备采购项目招标公告
本公告仅用于软件测试，所有单位和项目均为虚构。
项目名称：太原市测试学校设备采购项目
采购人：太原市测试学校
采购人地址：太原市
行业：教育
服务内容：采购教学电脑
预算金额：160000元
开标时间：2026年11月20日09时00分
代理机构：测试采购代理有限公司
本项目尚未开标，无中标单位和中标金额。
"""


def run():
    root = Path(__file__).parent
    main.dashscope.api_key = main.load_api_key(str(root / "api_key.json"))
    prompt = main.load_prompt(str(root / "prompt.txt"))
    settings = configure_models(root / "model_config.json", root / ".model_check.json")
    main.TEXT_MODEL, main.VISION_MODEL = settings["text_model"], settings["vision_model"]

    fallback = main.call_model(
        main.Generation, "qwen-plus",
        [{"role": "user", "content": '仅返回JSON：{"项目名称":"虚构测试项目"}'}],
        "候选模型测试", enable_thinking=False,
    )
    assert fallback["项目名称"] == "虚构测试项目", fallback
    print("PASS: qwen-plus 候选模型真实调用和 JSON 解析")

    with tempfile.TemporaryDirectory(prefix="bidminer-smoke-") as directory:
        work = Path(directory)
        pdf_dir = work / "pdfs"
        pdf_dir.mkdir()
        text_pdf, image_pdf = pdf_dir / "测试文字公告.pdf", pdf_dir / "测试图片公告.pdf"
        with main.fitz.open() as doc:
            page = doc.new_page()
            font_path = Path("C:/Windows/Fonts/simsun.ttc")
            font_options = {"fontname": "test-font", "fontfile": str(font_path)} if font_path.exists() else {"fontname": "china-s"}
            page.insert_text((40, 50), ANNOUNCEMENT, fontsize=14, **font_options)
            doc.save(text_pdf)
            image = page.get_pixmap(matrix=main.fitz.Matrix(300 / 72, 300 / 72)).tobytes("png")
        with main.fitz.open() as doc:
            page = doc.new_page()
            page.insert_image(page.rect, stream=image)
            doc.save(image_pdf)
        assert not main.is_image_based_pdf(str(text_pdf))
        assert main.is_image_based_pdf(str(image_pdf))
        output = work / "result.xlsx"
        success, failed = main.process_pdfs(str(pdf_dir), str(output), main.dashscope.api_key, prompt)
        wb = main.openpyxl.load_workbook(output, read_only=True)
        rows = list(wb.active.values)
        wb.close()
        print("RESULTS", rows[1:])
        assert (success, failed) == (2, 0), (success, failed)
        assert len(rows) == 3
        for row in rows[1:]:
            assert row[1] == "招标信息", row
            assert row[2] == "太原市测试学校设备采购项目", row
            assert row[4] == "太原市", row
            assert float(row[7]) == 16, row
            assert row[8] == "太原市测试学校", row
        print("PASS: 文字和图片 PDF → 真实模型 → Excel；项目名称、城市、预算、采购人均正确")


if __name__ == "__main__":
    run()
