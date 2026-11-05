async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  await page.goto('http://127.0.0.1:5079');
  await page.evaluate(() => { showStep(1); switchTab(document.querySelectorAll('.tab-item')[2], 2); });
  assert(await page.locator('#biz_level').getAttribute('readonly') !== null, '业务信息等级应为只读结果');
  assert(await page.locator('input[data-level-kind="biz"]').count() === 9, '应始终显示全部九种损害项');
  assert(await page.locator('input[data-level-kind="biz"]:checked').count() === 0, '初始不能自动选择损害项');
  const expectedLevels = ['第一级', '第二级', '第二级', '第二级', '第三级', '第四级', '第四级', '第五级', '第五级'];
  for (const [index, expected] of expectedLevels.entries()) {
    const option = page.locator('input[data-level-kind="biz"]').nth(index);
    await option.check();
    assert(await page.locator('#biz_level').inputValue() === expected, `第${index + 1}项应对应${expected}`);
    await option.uncheck();
  }
  const legal = page.locator('input[data-level-kind="biz"]').filter({ visible: true }).nth(1);
  const publicImpact = page.locator('input[data-level-kind="biz"]').nth(4);
  await legal.check();
  await publicImpact.check();
  assert(await page.locator('#biz_level').inputValue() === '第三级', '二级与三级多选应取三级');
  assert(await legal.isChecked(), '选择三级项应保留二级项');
  await publicImpact.uncheck();
  assert(await page.locator('#biz_level').inputValue() === '第二级', '取消三级项应降至二级');
  await legal.focus();
  await page.keyboard.press('Space');
  assert(await page.locator('#biz_level').inputValue() === '', '全部取消应保持空等级');
  assert(await page.locator('#final_level').textContent() === '', '空选不能默认补二级');
  await page.evaluate(() => {
    fillBeianData({grading: {
      biz_level: '第二级', service_level: '第二级', final_level: '第二级',
      biz_level_items: ['对公民、法人和其他组织的合法权益造成严重损害', '对社会秩序和公共利益造成严重损害'],
      service_level_items: ['对国家安全或地区安全、国计民生造成严重损害'],
    }});
    fillReportData({biz_level: '第二级', svc_level: '第二级'}, {preserveGrading: true});
  });
  let state = await page.evaluate(() => ({form: collectFormData(), report: collectReportData()}));
  assert(state.form.grading.biz_level === '第三级', '回填应从损害项重算等级');
  assert(state.form.grading.service_level === '第五级' && state.form.grading.final_level === '第五级', '最终等级应取两类最高值');
  assert(state.form.grading.biz_level_items.length === 2, '报告回填不能抹去备案表多选');
  assert(state.report.biz_level === '第三级' && state.report.svc_level === '第五级', '报告提交等级应一致');
  await page.evaluate(() => {
    const saved = collectUiState();
    saved.biz_level = '第一级'; saved.svc_level = '第一级'; saved.final_level = '第一级';
    applyUiState(saved);
  });
  assert(await page.locator('#biz_level').inputValue() === '第三级', '批量状态恢复必须按勾选重算');
  await page.evaluate(() => {
    fillBeianData({grading: {biz_level: '第五级', service_level: '第五级', biz_level_items: [], service_level_items: []}});
    fillReportData({biz_level: '第五级', svc_level: '第五级'}, {preserveGrading: true});
  });
  state = await page.evaluate(() => collectFormData().grading);
  assert(state.biz_level === '' && state.service_level === '' && state.final_level === '', '明确空选不能被旧等级覆盖');
  await page.evaluate(() => fillReportData({biz_level_items: ['对社会秩序和公共利益造成一般损害'], svc_level_items: []}));
  assert(await page.locator('#biz_level').inputValue() === '第二级', '单独导入报告应恢复明确的损害项');
  const layouts = [];
  for (const width of [1440, 900, 390]) {
    await page.setViewportSize({width, height: 1000});
    const layout = await page.locator('#biz_level_checks').evaluate(el => ({
      width: el.getBoundingClientRect().width, scrollWidth: el.scrollWidth,
      targetHeight: Math.min(...Array.from(el.querySelectorAll('label')).map(item => item.getBoundingClientRect().height)),
    }));
    assert(layout.scrollWidth <= layout.width + 1, `等级矩阵在 ${width}px 不能横向溢出`);
    assert(layout.targetHeight >= 44, '勾选区域应至少44像素高');
    layouts.push({viewportWidth: width, ...layout});
  }
  await page.setViewportSize({width: 1440, height: 1100});
  return {passed: true, layouts};
}
