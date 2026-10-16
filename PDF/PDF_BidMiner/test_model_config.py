import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import main
import requests


NOTICE_INDEX = """<html><h2>下线模型列表</h2>
<a href="https://www.aliyun.com/notice/118177">历史模型下线通知</a></html>"""


def official_response(url, **kwargs):
    response = requests.Response()
    response.status_code = 200
    response.encoding = "utf-8"
    if "help.aliyun.com" in url:
        content = NOTICE_INDEX
    else:
        content = json.dumps({
            "success": True,
            "data": {"success": True, "info": {
                "title": "部分历史模型下线通知",
                "detailList": [{"language": "zh", "contentHtml": """
                    <table><tr><td>模型名称</td><td>输入成本</td><td>推荐替换模型</td></tr>
                    <tr><td>qwen-flash</td><td>0.15</td><td>qwen-plus</td></tr>
                    <tr><td>qwen3-vl-plus-2025-09-23</td><td>1</td><td>qwen3.7-plus</td></tr>
                    </table>"""}],
            }},
        })
    response._content = content.encode("utf-8")
    return response


class ModelConfigurationTests(unittest.TestCase):
    def test_recent_check_skips_network_until_day_fifteen(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "model_config.json"
            cache = root / ".model_check.json"
            config.write_text(json.dumps({"check_interval_days": 15}), encoding="utf-8")
            cache.write_text(json.dumps({
                "version": 1, "checked_at": 1000000, "notices": {},
            }), encoding="utf-8")
            with patch("model_config.time.time", return_value=1000000 + 14 * 86400), patch("requests.get") as network:
                settings = model_config.configure_models(config, cache)
            network.assert_not_called()
            self.assertEqual(settings["text_model"], "qwen-flash")
            self.assertEqual(settings["vision_model"], "qwen3-vl-plus")

    def test_day_fifteen_checks_official_notices_and_persists_allowed_replacement(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, cache = root / "model_config.json", root / ".model_check.json"
            config.write_text(json.dumps({"check_interval_days": 15}), encoding="utf-8")
            cache.write_text(json.dumps({"version": 1, "checked_at": 1000000, "notices": {}}), encoding="utf-8")
            with patch("model_config.time.time", return_value=1000000 + 15 * 86400), patch("requests.get", side_effect=official_response):
                settings = model_config.configure_models(config, cache)
            self.assertEqual(settings["text_model"], "qwen-plus")
            self.assertEqual(settings["vision_model"], "qwen3-vl-plus")
            self.assertEqual(json.loads(config.read_text(encoding="utf-8"))["text_model"], "qwen-plus")
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8"))["checked_at"], 2296000)
            with patch("model_config.time.time", return_value=2296001), patch("requests.get") as network:
                self.assertEqual(model_config.configure_models(config, cache)["text_model"], "qwen-plus")
            network.assert_not_called()

    def test_latest_batch_is_checked_without_requesting_old_image_notices(self):
        import model_config

        def dated_index(url, **kwargs):
            response = official_response(url, **kwargs)
            if "help.aliyun.com" in url:
                today = model_config.datetime.date.today()
                previous = today - model_config.datetime.timedelta(days=100)
                response._content = (
                    '<h2>下线模型列表</h2>'
                    f'<h3>{today.year}年{today.month}月{today.day}日已下线</h3>'
                    '<a href="https://www.aliyun.com/notice/118177">最新下线公告</a>'
                    f'<h3>{previous.year}年{previous.month}月{previous.day}日已下线</h3>'
                    '<a href="https://www.aliyun.com/notice/117351">历史图片名单</a>'
                ).encode("utf-8")
            elif kwargs["params"]["id"] == "117351":
                raise AssertionError("不应请求较早批次的历史图片公告")
            return response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("requests.get", side_effect=dated_index):
                settings = model_config.configure_models(root / "model_config.json", root / ".model_check.json")
            self.assertEqual(settings["text_model"], "qwen-plus")

    def test_offline_check_preserves_models_and_does_not_postpone_retry(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, cache = root / "model_config.json", root / ".model_check.json"
            original = {"version": 1, "checked_at": 1, "notices": {}}
            cache.write_text(json.dumps(original), encoding="utf-8")
            output = io.StringIO()
            with patch("requests.get", side_effect=requests.Timeout), contextlib.redirect_stdout(output):
                settings = model_config.configure_models(config, cache)
            self.assertEqual(settings["text_model"], "qwen-flash")
            self.assertFalse(config.exists())
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), original)
            self.assertIn("下次启动重试", output.getvalue())

    def test_unapproved_replacement_explains_manual_update_for_beginner(self):
        import model_config

        for field, current, recommendation in (
            ("text_model", "qwen-flash", "qwen-plus"),
            ("vision_model", "qwen3-vl-plus-2025-09-23", "qwen3.7-plus"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config, cache = root / "model_config.json", root / ".model_check.json"
                original = {field: current, "text_fallbacks": [], "vision_fallbacks": []}
                config.write_text(json.dumps(original), encoding="utf-8")
                output = io.StringIO()
                with patch("requests.get", side_effect=official_response), contextlib.redirect_stdout(output):
                    settings = model_config.configure_models(config, cache)
                self.assertEqual(settings[field], current)
                self.assertEqual(json.loads(config.read_text(encoding="utf-8")), original)
                message = output.getvalue()
                self.assertIn(f"官方替代建议：{recommendation}", message)
                self.assertIn(str(config.resolve()), message)
                self.assertIn("记事本", message)
                self.assertIn(f'"{field}"', message)
                self.assertIn("Ctrl+S", message)
                self.assertIn("run.bat", message)
                self.assertNotIn("发给提供软件的人", message)
                # 用户自行保存型号后，下次启动直接采用，不需要等待联网检查。
                original[field] = recommendation
                config.write_text(json.dumps(original), encoding="utf-8")
                with patch("requests.get") as network, contextlib.redirect_stdout(io.StringIO()):
                    settings = model_config.configure_models(config, cache)
                self.assertEqual(settings[field], recommendation)
                network.assert_not_called()

    def test_cached_retirement_still_applies_when_config_changes(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / ".model_check.json"
            cache.write_text(json.dumps({
                "version": 1, "checked_at": 1000000,
                "notices": {"qwen-flash": {"replacement": "qwen-plus", "source": "https://www.aliyun.com/notice/118177"}},
            }), encoding="utf-8")
            with patch("model_config.time.time", return_value=1000001), patch("requests.get") as network:
                settings = model_config.configure_models(root / "model_config.json", cache)
            self.assertEqual(settings["text_model"], "qwen-plus")
            network.assert_not_called()

    def test_retirement_records_survive_newer_announcement_batches(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, cache = root / "model_config.json", root / ".model_check.json"
            cache.write_text(json.dumps({
                "version": 1, "checked_at": 1,
                "notices": {"qwen-plus": {"replacement": "", "source": "https://www.aliyun.com/notice/118344"}},
            }), encoding="utf-8")
            with patch("requests.get", side_effect=official_response):
                settings = model_config.configure_models(config, cache)
            self.assertEqual(settings["text_model"], "qwen-flash")
            self.assertIn("qwen-plus", json.loads(cache.read_text(encoding="utf-8"))["notices"])

    def test_retirement_warning_can_be_used_if_cache_directory_is_read_only(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked_path = root / "directory"
            blocked_path.mkdir()
            with patch("requests.get", side_effect=official_response):
                settings = model_config.configure_models(blocked_path / "model_config.json", blocked_path)
            self.assertEqual(settings["text_model"], "qwen-plus")

    def test_retirement_keeps_runtime_replacement_when_config_cannot_be_saved(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "model_config.json"
            config.write_text("{}", encoding="utf-8")
            real_replace = model_config.os.replace

            def replace(source, destination):
                if destination == config:
                    raise PermissionError("read only")
                return real_replace(source, destination)

            with patch("requests.get", side_effect=official_response), patch("model_config.os.replace", side_effect=replace):
                settings = model_config.configure_models(config, root / ".model_check.json")
            self.assertEqual(settings["text_model"], "qwen-plus")
            self.assertEqual(config.read_text(encoding="utf-8"), "{}")
            self.assertEqual({path.name for path in root.iterdir()}, {"model_config.json", ".model_check.json"})

    def test_all_retired_candidates_do_not_get_selected(self):
        import model_config

        def response_with_retired_fallback(url, **kwargs):
            response = official_response(url, **kwargs)
            if "help.aliyun.com" not in url:
                data = response.json()
                data["data"]["info"]["detailList"][0]["contentHtml"] += "<ul><li>qwen-plus</li></ul>"
                response._content = json.dumps(data).encode("utf-8")
            return response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("requests.get", side_effect=response_with_retired_fallback):
                settings = model_config.configure_models(root / "model_config.json", root / ".model_check.json")
            self.assertEqual(settings["text_model"], "qwen-flash")

    def test_legacy_model_in_plain_list_can_use_explicit_fallback(self):
        import model_config

        def plain_list(url, **kwargs):
            response = official_response(url, **kwargs)
            if "help.aliyun.com" not in url:
                data = response.json()
                data["data"]["info"]["detailList"][0]["contentHtml"] = "<p>qwen-turbo<br>qwen-vl-plus</p>"
                response._content = json.dumps(data).encode("utf-8")
            return response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "model_config.json"
            config.write_text(json.dumps({"text_model": "qwen-turbo", "text_fallbacks": ["qwen-flash"]}), encoding="utf-8")
            with patch("requests.get", side_effect=plain_list):
                settings = model_config.configure_models(config, root / ".model_check.json")
            self.assertEqual(settings["text_model"], "qwen-flash")

    def test_changed_official_page_is_not_cached_as_success(self):
        import model_config

        def changed_page(url, **kwargs):
            response = official_response(url, **kwargs)
            response._content = b"<html>Please sign in</html>"
            return response

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / ".model_check.json"
            with patch("requests.get", side_effect=changed_page):
                settings = model_config.configure_models(root / "model_config.json", cache)
            self.assertEqual(settings["text_model"], "qwen-flash")
            self.assertFalse(cache.exists())

    def test_invalid_config_is_rejected_before_network(self):
        import model_config

        for content in ('[]', '{"check_interval_days":true}', '{"text_fallbacks":"qwen-plus"}', '{"text_model":""}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / "model_config.json"
                config.write_text(content, encoding="utf-8")
                with patch("requests.get") as network, self.assertRaises(ValueError):
                    model_config.configure_models(config, root / ".model_check.json")
                network.assert_not_called()

    def test_corrupt_or_future_cache_forces_fresh_check(self):
        import model_config

        for content in ('invalid', '[]', '{"version":1,"checked_at":999999999999,"notices":{}}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cache = root / ".model_check.json"
                cache.write_text(content, encoding="utf-8")
                with patch("requests.get", side_effect=official_response):
                    settings = model_config.configure_models(root / "model_config.json", cache)
                self.assertEqual(settings["text_model"], "qwen-plus")

    def test_known_retirement_is_still_honored_when_overdue_check_is_offline(self):
        import model_config

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / ".model_check.json"
            data = {
                "version": 1, "checked_at": 1,
                "notices": {"qwen-flash": {"replacement": "qwen-plus", "source": "https://www.aliyun.com/notice/118177"}},
            }
            cache.write_text(json.dumps(data), encoding="utf-8")
            with patch("requests.get", side_effect=requests.Timeout):
                settings = model_config.configure_models(root / "model_config.json", cache)
            self.assertEqual(settings["text_model"], "qwen-plus")
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), data)

    def test_launcher_failure_keeps_self_service_guidance_visible(self):
        import launcher
        import subprocess

        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "api_key.json").write_text('{"DASHSCOPE_API_KEY":"test-key-not-a-secret"}', encoding="utf-8")
            (root / "test.pdf").write_bytes(b"synthetic placeholder")
            with patch("sys.argv", ["launcher.py", "run"]), patch.object(launcher, "API_KEY_FILE", root / "api_key.json"), patch.object(launcher, "PDF_DIR", root), patch("subprocess.run", side_effect=[
                SimpleNamespace(returncode=0, stdout=json.dumps({
                    "version": list(sys.version_info[:2]),
                    "base": sys._base_executable,
                    "prefix": str(launcher.VENV_DIR.resolve()),
                })),
                SimpleNamespace(returncode=0),
                subprocess.CalledProcessError(1, ["python", "main.py"]),
            ]), patch.object(Path, "exists", return_value=True), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as caught:
                    launcher.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("上方", output.getvalue())
        self.assertNotIn("请把本窗口截图发给技术支持", output.getvalue())

    def test_startup_invalid_config_explains_how_to_fix_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text(Path(main.__file__).read_text(encoding="utf-8"), encoding="utf-8")
            (root / "api_key.json").write_text('{"DASHSCOPE_API_KEY":"test-key-not-a-secret"}', encoding="utf-8")
            (root / "prompt.txt").write_text("提取项目名称", encoding="utf-8")
            config = root / "model_config.json"
            config.write_text('{"text_model": "qwen-plus"', encoding="utf-8")
            with patch("sys.argv", [str(root / "main.py")]), patch("requests.get") as network, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    runpy.run_path(str(root / "main.py"), run_name="__main__")
            message = str(caught.exception)
            self.assertIn(str(config), message)
            self.assertIn("记事本", message)
            self.assertIn("英文双引号", message)
            self.assertIn("README.md", message)
            self.assertNotIn("发给提供软件的人", message)
            self.assertFalse(list((root / "output").glob("*.xlsx")))
            network.assert_not_called()

    def test_startup_uses_replacement_and_writes_expected_excel(self):
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"项目名称":"测试项目","预算（万元）":16,"预算原文":"160000元"}'),
            )]),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text(Path(main.__file__).read_text(encoding="utf-8"), encoding="utf-8")
            (root / "api_key.json").write_text('{"DASHSCOPE_API_KEY":"test-key-not-a-secret"}', encoding="utf-8")
            (root / "prompt.txt").write_text("提取项目名称", encoding="utf-8")
            (root / "pdfs").mkdir()
            with main.fitz.open() as doc:
                doc.new_page().insert_text((40, 50), "Synthetic procurement test document. " * 3)
                doc.save(root / "pdfs" / "test.pdf")
            with patch("sys.argv", [str(root / "main.py")]), patch("requests.get", side_effect=official_response), patch.object(main.Generation, "call", return_value=response) as request, patch("time.sleep"), patch.object(main.dashscope, "api_key", None), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(root / "main.py"), run_name="__main__")
            self.assertEqual(request.call_args.kwargs["model"], "qwen-plus")
            self.assertIs(request.call_args.kwargs["enable_thinking"], False)
            workbook = main.openpyxl.load_workbook(next((root / "output").glob("*.xlsx")), read_only=True)
            rows = list(workbook.active.values)
            workbook.close()
            self.assertEqual(rows[1][2], "测试项目")
            self.assertEqual(rows[1][7], "16")

    def test_account_error_is_not_retried_and_key_is_redacted(self):
        response = SimpleNamespace(status_code=400, code="Arrearage", message="account test-secret")
        with patch.object(main.dashscope, "api_key", "test-secret"), patch.object(main.Generation, "call", return_value=response) as request, patch("main.time.sleep") as wait:
            with self.assertRaises(main.ModelCallError) as caught:
                main.call_text_model("提取", "测试")
        self.assertIn("Arrearage", str(caught.exception))
        self.assertNotIn("test-secret", str(caught.exception))
        self.assertEqual(request.call_count, 1)
        wait.assert_not_called()

    def test_rate_limit_stops_after_three_attempts_with_reason(self):
        response = SimpleNamespace(status_code=429, code="Throttling.RateQuota", message="Requests rate limit exceeded")
        with patch.object(main.Generation, "call", return_value=response) as request, patch("main.time.sleep") as wait, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(main.ModelCallError, "Throttling.RateQuota"):
                main.call_text_model("提取", "测试")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(wait.call_count, 2)

    def test_timeout_can_recover_and_truncated_output_is_rejected(self):
        response = SimpleNamespace(status_code=200, output=SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content='{"项目名称":"测试项目"}'),
        )]))
        with patch.object(main.Generation, "call", side_effect=[requests.Timeout("timeout"), response]), patch("main.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main.call_text_model("提取", "测试"), {"项目名称": "测试项目"})
        response.output.choices[0].finish_reason = "length"
        with patch.object(main.Generation, "call", return_value=response):
            with self.assertRaisesRegex(main.ModelCallError, "长度上限"):
                main.call_text_model("提取", "测试")

    def test_failed_model_call_is_recorded_in_excel(self):
        response = SimpleNamespace(status_code=400, code="Arrearage", message="account unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with main.fitz.open() as doc:
                doc.new_page().insert_text((40, 50), "Synthetic procurement announcement. " * 4)
                doc.save(root / "test.pdf")
            output = root / "result.xlsx"
            with patch.object(main.Generation, "call", return_value=response), patch.object(main.dashscope, "api_key", None), patch("main.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main.process_pdfs(str(root), str(output), "fake-key", "提取"), (0, 1))
            workbook = main.openpyxl.load_workbook(output, read_only=True)
            rows = list(workbook.active.values)
            workbook.close()
            self.assertEqual(rows[1][2], "提取失败")
            self.assertIn("Arrearage", rows[1][12])

    def test_excel_preserves_two_category_information_types(self):
        cases = (
            ("招标公告", "招标信息"),
            ("询比/竞价公告", "招标信息"),
            ("供应商征集公告", "招标信息"),
            ("中标/成交候选人公示", "投标结果公告"),
            ("中标/成交结果公告", "投标结果公告"),
        )
        workbook = main.openpyxl.Workbook()
        try:
            for original, expected in cases:
                with self.subTest(original=original):
                    data = {"项目名称": "测试项目", "信息类型": original}
                    if expected == "投标结果公告":
                        data["开标时间"] = "不适用"
                    main.append_row(workbook.active, "test.pdf", data)
                    row = list(workbook.active.values)[-1]
                    self.assertEqual(row[1], expected)
                    if expected == "投标结果公告":
                        self.assertIn("因该文件为投标结果公告", row[12])
        finally:
            workbook.close()

    def test_text_request_uses_flash_without_thinking(self):
        response = SimpleNamespace(
            status_code=200,
            output=SimpleNamespace(choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"项目名称":"测试项目"}'),
            )]),
        )
        with patch.object(main.Generation, "call", return_value=response) as request:
            self.assertEqual(main.call_text_model("提取项目名称", "测试项目"), {"项目名称": "测试项目"})
        self.assertEqual(request.call_args.kwargs["model"], "qwen-flash")
        self.assertIs(request.call_args.kwargs.get("enable_thinking"), False)


if __name__ == "__main__":
    unittest.main()
