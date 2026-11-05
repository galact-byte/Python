"""启动及文档生成回归：python -m unittest discover -s scripts -p 'test_*.py'。"""

import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]


class StartupRegressionTests(unittest.TestCase):
    def test_python_sources_compile(self):
        for source in ROOT.rglob('*.py'):
            with self.subTest(source=source.relative_to(ROOT)):
                compile(source.read_bytes(), str(source), 'exec')

    def setUp(self):
        self.backend = importlib.import_module('app')
        self.client = self.backend.app.test_client()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.payload = {
            'paths': {
                'beian_template': str(ROOT / 'doc_templates' / '01-新备案表.docx'),
                'report_template': str(ROOT / 'doc_templates' / '02-定级报告.docx'),
                'output_dir': self.temp.name,
            },
            'form_data': {
                'unit': {'unit_name': '测试单位'},
                'target': {'name': '测试系统', 'service_scope': '99-其它',
                           'service_scope_other': '本单位'},
            },
            'report_data': {
                'system_name': '测试系统',
                'responsibility': '责任主体测试正文',
                'composition': '对象构成第一段\n对象构成第二段',
                'business_desc': '承载业务测试正文',
                'carried_data': '承载数据测试正文',
                'security_resp': '安全责任测试正文，选中片段，后续内容',
                'biz_info_desc': '业务信息测试正文',
                'biz_victim': '公民、法人和其他组织的合法权益',
                'biz_degree': '严重损害',
                'biz_level': '第二级',
                'svc_desc': '系统服务测试正文',
                'svc_victim': '公民、法人和其他组织的合法权益',
                'svc_degree': '严重损害',
                'svc_level': '第二级',
                'final_level': '第二级',
                'highlighted_fragments': {'rpt_security': ['选中片段']},
            },
        }

    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_generate_documents_with_names_sections_and_highlights(self):
        response = self.client.post('/api/generate', json=self.payload)
        result = response.get_json()
        self.assertEqual(response.status_code, 200, result)
        self.assertTrue(result['success'], result)
        self.assertEqual(
            [Path(p).name for p in result['files']],
            ['测试单位-测试系统-备案表.docx', '测试单位-测试系统-定级报告.docx'],
        )
        beian = Document(result['files'][0])
        self.assertEqual(beian.tables[1].cell(0, 1).text.strip(), '测试单位')
        self.assertEqual(beian.tables[2].cell(4, 2).text.count('本单位'), 1)
        report = Document(result['files'][1])
        paragraphs = [p.text for p in report.paragraphs]
        for field in ('responsibility', 'business_desc', 'carried_data', 'security_resp',
                      'biz_info_desc', 'svc_desc'):
            self.assertIn(self.payload['report_data'][field], paragraphs)
        self.assertIn('对象构成第一段', paragraphs)
        self.assertIn('对象构成第二段', paragraphs)
        security = next(p for p in report.paragraphs if '安全责任测试正文' in p.text)
        highlighted = [r.text for r in security.runs
                       if r._element.find(qn('w:rPr') + '/' + qn('w:highlight')) is not None]
        self.assertEqual(highlighted, ['选中片段'])
        self.assertTrue(all(r.font.size.pt == 14 for r in security.runs if r.text))

    def test_preview_generates_both_document_types(self):
        with patch('app.tempfile.gettempdir', return_value=self.temp.name), \
                patch('app.os.startfile') as open_file:
            for doc_type, suffix in [('beian', '备案表'), ('report', '定级报告')]:
                with self.subTest(doc_type=doc_type):
                    response = self.client.post('/api/preview', json={
                        **self.payload, 'doc_type': doc_type,
                    })
                    result = response.get_json()
                    self.assertEqual(response.status_code, 200, result)
                    self.assertTrue(Path(result['path']).is_file())
                    self.assertTrue(Path(result['path']).name.startswith(
                        f'预览_测试单位-测试系统-{suffix}_'))
                    Document(result['path'])
                    open_file.assert_called_with(result['path'])

    def test_report_accepts_empty_optional_values_and_project_name_fallback(self):
        from core.doc_writer import generate_report
        from models.project_data import ReportInfo
        output = Path(self.temp.name) / 'empty.docx'
        generate_report(self.payload['paths']['report_template'], str(output),
                        ReportInfo(), '备用系统')
        report = Document(output)
        text = '\n'.join(p.text for p in report.paragraphs)
        summary = next(table for table in report.tables
                       if table.cell(0, 0).text.strip() == '定级对象名称')
        self.assertEqual(summary.cell(1, 0).text.strip(), '备用系统')
        self.assertNotIn('责任主体测试正文', text)

    def test_missing_template_returns_failure(self):
        self.payload['paths']['report_template'] = str(Path(self.temp.name) / 'missing.docx')
        response = self.client.post('/api/generate', json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()['success'])


if __name__ == '__main__':
    unittest.main()
