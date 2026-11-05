"""验证生成结果以当前输入为准，不携带模板项目内容。"""
from pathlib import Path
import tempfile
import unittest

from docx import Document
from docx.oxml.ns import qn

from core.doc_writer import generate_beian, generate_report
from models.project_data import ProjectData, ReportInfo

ROOT = Path(__file__).resolve().parents[1]


class DocumentContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = ProjectData(project_name='回归测试系统')
        self.data.unit.unit_name = '回归测试单位'
        self.data.target.name = '回归测试系统'

    def beian(self, template=None):
        output = Path(self.temp.name) / 'beian.docx'
        generate_beian(str(template or ROOT / 'doc_templates/01-新备案表.docx'),
                       str(output), self.data)
        return Document(output)

    def report(self, report=None, template=None):
        output = Path(self.temp.name) / 'report.docx'
        generate_report(str(template or ROOT / 'doc_templates/02-定级报告.docx'),
                        str(output), report or ReportInfo(), '回归测试系统')
        return Document(output)

    def test_blank_fields_override_template_values(self):
        doc = self.beian()
        with self.subTest(field='对象编号'):
            self.assertEqual(''.join(c.text for c in doc.tables[2].rows[0].cells[4:]), '')
        for ti, ri, ci in [(2, 9, 2), (3, 12, 2), (3, 18, 3)]:
            with self.subTest(date=(ti, ri)):
                self.assertNotRegex(doc.tables[ti].cell(ri, ci).text, r'\d')
        with self.subTest(field='对象数量'):
            self.assertEqual(doc.tables[1].cell(17, 1).text, '')
        text = '\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        for residue in ['运城市', '变电站', '山西省', '电力专网', '本单位', '112']:
            with self.subTest(residue=residue):
                self.assertTrue(residue not in text.replace('本单位机房', '').replace('与本单位其他系统连接', ''), residue)
        with self.subTest(field='模板勾选'):
            self.assertFalse(any(s.get(qn('w:char')) == 'F0FE'
                                 for s in doc.tables[2].cell(7, 2)._tc.iter(qn('w:sym'))))

    def test_level_three_keeps_impacts_and_levels_two_and_three(self):
        items = ['对公民、法人和其他组织的合法权益造成严重损害',
                 '对社会秩序和公共利益造成严重损害']
        self.data.grading.biz_level = self.data.grading.service_level = '第三级'
        self.data.grading.final_level = '第三级'
        self.data.grading.biz_level_items = items
        self.data.grading.service_level_items = items
        doc = self.beian()
        for rows in [(2, 3), (7, 8)]:
            for row in rows:
                for col in [1, 4]:
                    with self.subTest(row=row, col=col):
                        syms = doc.tables[3].cell(row, col)._tc.iter(qn('w:sym'))
                        self.assertTrue(any(s.get(qn('w:char')) == 'F0FE' for s in syms))
        from core.doc_reader import read_beian_docx
        parsed = read_beian_docx(str(Path(self.temp.name) / 'beian.docx'))
        self.assertEqual(parsed.grading.biz_level, '第三级')
        self.assertEqual(parsed.grading.biz_level_items, items)
        self.assertEqual(parsed.grading.service_level_items, items)

    def test_empty_grading_round_trip_stays_empty(self):
        from core.doc_reader import read_beian_docx
        grading = self.data.grading
        grading.biz_level = grading.service_level = grading.final_level = ''
        grading.biz_level_items = []
        grading.service_level_items = []
        self.beian()
        parsed = read_beian_docx(str(Path(self.temp.name) / 'beian.docx')).grading
        self.assertEqual((parsed.biz_level, parsed.service_level, parsed.final_level), ('', '', ''))
        self.assertEqual(parsed.biz_level_items, [])
        self.assertEqual(parsed.service_level_items, [])

    def test_report_replaces_conclusions_shading_date_and_template_image(self):
        report = ReportInfo(system_name='回归测试系统', composition='当前对象构成',
                            biz_level='第三级', svc_level='第三级', final_level='第三级',
                            biz_victim='社会秩序、公共利益', biz_degree='严重损害',
                            svc_victim='社会秩序、公共利益', svc_degree='严重损害')
        doc = self.report(report)
        with self.subTest(field='标题'):
            self.assertEqual(doc.paragraphs[0].text, '回归测试系统网络安全等级保护定级报告')
        conclusions = [p.text for p in doc.paragraphs if '等级为' in p.text]
        with self.subTest(field='结论'):
            self.assertEqual(len(conclusions), 3)
            self.assertTrue(all('第三级' in p and '第二级' not in p for p in conclusions))
        with self.subTest(field='示例拓扑图'):
            self.assertEqual(len(doc.inline_shapes), 0)
        for table in doc.tables[:2]:
            shaded = {(ri, ci): c._tc.xpath('./w:tcPr/w:shd/@w:fill')
                      for ri, row in enumerate(table.rows) for ci, c in enumerate(row.cells)
                      if c._tc.xpath('./w:tcPr/w:shd/@w:fill') not in ([], ['auto'], ['FFFFFF'])}
            self.assertEqual(shaded, {(3, 2): ['7E7E7E']})
        signature = next(p for p in doc.paragraphs if '盖章' in p.text)
        with self.subTest(field='签章留白'):
            self.assertGreaterEqual(signature.paragraph_format.space_before.pt, 48)
            self.assertRegex(signature.text, r'单位\s+（盖章）')
        date = next(p for p in doc.paragraphs
                    if '年' in p.text and '月' in p.text and '日' in p.text)
        self.assertNotRegex(date.text, r'\d')

    def test_form_levels_impacts_and_date_reach_both_generated_documents(self):
        import app as app_module
        import dataclasses
        self.data.grading.biz_level = self.data.grading.service_level = '第三级'
        self.data.grading.final_level = '第三级'
        items = ['对公民、法人和其他组织的合法权益造成严重损害', '对社会秩序和公共利益造成严重损害']
        self.data.grading.biz_level_items = self.data.grading.service_level_items = items
        self.data.grading.fill_date = '2031-02-09'
        stale_report = dataclasses.asdict(ReportInfo(system_name='回归系统'))
        result = app_module._generate_documents({
            'beian_template': str(ROOT / 'doc_templates' / '01-新备案表.docx'),
            'report_template': str(ROOT / 'doc_templates' / '02-定级报告.docx'),
            'output_dir': self.temp.name,
        }, dataclasses.asdict(self.data), stale_report)
        report = Document(result['files'][1])
        text = '\n'.join(p.text for p in report.paragraphs)
        self.assertIn('2031年 2 月 9 日', text)
        self.assertNotIn('第二级', '\n'.join(p.text for p in report.paragraphs))
        for table in report.tables[:2]:
            shaded = {(r, c) for r in range(2, 5) for c in range(1, 4)
                      if table.cell(r, c)._tc.xpath('./w:tcPr/w:shd[@w:fill="7E7E7E"]')}
            self.assertEqual(shaded, {(2, 2), (3, 2)})
        self.data.grading.fill_date = ''
        result = app_module._generate_documents({
            'beian_template': str(ROOT / 'doc_templates' / '01-新备案表.docx'),
            'report_template': str(ROOT / 'doc_templates' / '02-定级报告.docx'),
            'output_dir': self.temp.name,
        }, dataclasses.asdict(self.data), stale_report)
        self.assertFalse(any('2031' in p.text for p in Document(result['files'][1]).paragraphs))

    def test_unused_template_fields_and_extra_value_paragraphs_are_cleared(self):
        template = Document(ROOT / 'doc_templates/01-新备案表.docx')
        residue = '旧模板测试残留'
        for ti, ri, ci in [(1, 0, 1), (2, 3, 2), (4, 6, 2), (4, 7, 2),
                           (4, 10, 2), (4, 13, 2), (4, 27, 2), (4, 28, 2)]:
            template.tables[ti].cell(ri, ci).add_paragraph(residue)
        template.tables[2].cell(7, 2).paragraphs[0].runs[6].text = residue
        template.tables[6].cell(9, 1).paragraphs[1].runs[3].text = residue
        template.tables[5].cell(0, 1).add_paragraph(residue)
        template.tables[6].cell(4, 1).add_paragraph(residue)
        for sym in template.element.iter(qn('w:sym')):
            sym.set(qn('w:char'), 'F0FE')
        path = Path(self.temp.name) / 'dirty-template.docx'
        template.save(path)
        doc = self.beian(path)
        text = '\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        self.assertTrue(residue not in text, '未选中的填写区仍保留旧模板内容')
        self.assertFalse(any(s.get(qn('w:char')) == 'F0FE'
                             for s in doc.tables[2].cell(7, 2)._tc.iter(qn('w:sym'))))

    def test_survey_cloud_level_is_read_instead_of_assumed(self):
        from core.doc_reader import read_survey_docx
        template = Document()
        table = template.add_table(rows=2, cols=2)
        table.cell(0, 0).text = '云计算平台名称'
        table.cell(0, 1).text = '合成云平台'
        table.cell(1, 0).text = '平台安全保护等级'
        path = Path(self.temp.name) / 'survey.docx'
        for source, expected in [('', ''), ('第二级', '二级'), ('第四级', '四级')]:
            with self.subTest(source=source):
                table.cell(1, 1).text = source
                template.save(path)
                self.assertEqual(read_survey_docx(str(path))[2]['platform_level'], expected)

    def test_enabled_scenarios_do_not_supply_missing_platform_levels(self):
        cloud = self.data.scenario.cloud
        cloud.enabled, cloud.role = True, '云服务客户'
        bigdata = self.data.scenario.bigdata
        bigdata.enabled, bigdata.composition = True, '大数据应用'
        doc = self.beian()
        for row in [9, 30]:
            self.assertNotIn('三级', doc.tables[4].cell(row, 2).text)

    def test_blank_filling_lines_keep_template_lengths(self):
        self.data.data_enabled = True
        doc = self.beian()
        table = doc.tables[6]
        # 同一模板有文字下划线、带下划线的空格及已填示例三种结构。
        for index, count in [(0, 25), (1, 27), (2, 25)]:
            with self.subTest(field='交互单位', index=index):
                line = table.cell(9, 1).paragraphs[index]
                self.assertEqual(''.join(r.text for r in line.runs if r.font.underline), ' ' * count)
        for row, index, count in [(10, 0, 34), (10, 1, 34), (10, 2, 34),
                                   (10, 3, 34), (11, 2, 22)]:
            with self.subTest(field='存储位置', row=row, index=index):
                self.assertIn('_' * count, table.cell(row, 1).paragraphs[index].text)
        for row in [7, 8]:
            with self.subTest(field='流转单位', row=row):
                runs = table.cell(row, 1).paragraphs[0].runs
                self.assertGreaterEqual(sum(len(r.text) for r in runs if r.font.underline), 10)
        network = doc.tables[2].cell(7, 2).paragraphs[0]
        self.assertEqual([len(r.text) for r in network.runs if r.font.underline], [18, 19, 24])

    def test_filling_lines_support_short_long_and_other_values(self):
        self.data.data_enabled = True
        data = self.data.data
        for value in ['测试单位甲', '用于验证长内容不被截断的合成测试单位名称' * 3]:
            data.inflow_units = data.outflow_units = value
            data.interaction = '2-委托'
            data.interaction_other = value
            data.storage_type = '4-政务云'
            data.storage_cloud_name = value
            data.storage_room = '2-外单位机房'
            data.storage_room_name = value
            data.storage_region = '1-境内'
            data.storage_region_name = value
            data.data_source = '9-其他'
            data.data_source_other = value
            table = self.beian().tables[6]
            for row, index in [(7, 0), (8, 0), (9, 1), (10, 3), (11, 1), (12, 0), (6, 1)]:
                with self.subTest(value=value, row=row):
                    paragraph = table.cell(row, 1).paragraphs[index]
                    self.assertIn(value, paragraph.text)
                    filled = ''.join(r.text for r in paragraph.runs if r.font.underline)
                    self.assertIn(value, filled)
                    if value == '测试单位甲':
                        self.assertGreater(len(filled), len(value) + 3)
                    self.assertEqual(filled.strip(), value)
            self.assertIn('处理', table.cell(9, 1).paragraphs[1].text)

    def test_interaction_values_fill_the_selected_option_without_changing_labels(self):
        self.data.data_enabled = True
        for code, label, suffix in [('1', '对外提供给', ''), ('2', '委托', '处理'),
                                    ('3', '与', '共同处理')]:
            with self.subTest(code=code):
                self.data.data.interaction = f'{code}-选项'
                self.data.data.interaction_other = '交互单位甲'
                doc = self.beian()
                paragraphs = doc.tables[6].cell(9, 1).paragraphs
                self.assertRegex(paragraphs[int(code) - 1].text,
                                 rf'^{code}{label}\s*交互单位甲\s*{suffix}$')
                self.assertTrue(all('交互单位甲' not in p.text
                                    for i, p in enumerate(paragraphs) if i != int(code) - 1))

    def test_supplied_data_quantities_and_storage_locations_are_preserved(self):
        self.data.data_enabled = True
        data = self.data.data
        data.total_size, data.total_size_records = '12', '34'
        data.monthly_growth, data.monthly_growth_unit = '5', 'GB'
        data.inflow_units, data.outflow_units = '来源甲\n来源乙', '去向甲'
        data.storage_type, data.storage_cloud_name = '5-非云计算平台', '数据平台甲'
        data.storage_room, data.storage_room_name = '1-本单位机房', '测试机房甲'
        data.storage_region, data.storage_region_name = '1-本地', '测试地区甲'
        doc = self.beian()
        table = doc.tables[6]
        self.assertIn('12GB', table.cell(4, 1).text)
        self.assertIn('34万条', table.cell(4, 1).text)
        self.assertIn('5GB', table.cell(5, 1).text)
        for row, values in [(7, ['来源甲', '来源乙']), (8, ['去向甲']),
                            (10, ['数据平台甲']), (11, ['测试机房甲']), (12, ['测试地区甲'])]:
            for value in values:
                self.assertEqual(table.cell(row, 1).text.count(value), 1)

    def test_topology_contains_only_the_supplied_image(self):
        from PIL import Image
        image = Path(self.temp.name) / 'topology.png'
        Image.new('RGB', (120, 80), 'white').save(image)
        doc = self.report(ReportInfo(composition='当前对象构成', topology_image=str(image)))
        self.assertEqual(len(doc.inline_shapes), 1)
        images = [rel for rel in doc.part.rels.values() if rel.reltype.endswith('/image')]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].target_part.blob, image.read_bytes())

    def test_short_code_dates_and_internet_fields(self):
        self.data.target.code = '12'
        self.data.target.run_date = '2025-02-03'
        self.data.grading.grading_date = '2025-03-04'
        self.data.grading.fill_date = '2025-04-05'
        self.data.target.network_type = '2-互联网'
        self.data.target.source_ip = '192.0.2.0/24'
        self.data.target.domain = 'example.test'
        self.data.target.protocol_port = 'HTTPS/443'
        doc = self.beian()
        with self.subTest(field='短编号'):
            self.assertEqual([c.text for c in doc.tables[2].rows[0].cells[4:]], ['1', '2', '', '', ''])
        for ti, ri, ci, expected in [(2, 9, 2, '2025年2月3日'),
                                     (3, 12, 2, '2025年3月4日'),
                                     (3, 18, 3, '填表日期：2025年4月5日')]:
            with self.subTest(date=(ti, ri)):
                self.assertEqual(doc.tables[ti].cell(ri, ci).text, expected)
        with self.subTest(field='互联网详情'):
            text = doc.tables[2].cell(7, 2).text
            self.assertRegex(text, r'1业务专网\s+2互联网\s+源站IP地址范围\s*192\.0\.2\.0/24\s*域名\s*example\.test\s*主要协议/端口\s*HTTPS/443')
            self.assertIn('9其他', text)


if __name__ == '__main__':
    unittest.main()
