async (page) => {
  await page.goto('http://127.0.0.1:5079');
  await page.evaluate(() => { showStep(1); switchTab(document.querySelectorAll('.tab-item')[1], 1); });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const options = [
    ['', false],
    ['1-与其他行业系统连接', false],
    ['2-与本行业其他单位系统连接', false],
    ['3-与本单位其他系统连接', false],
    ['9-其他', true],
  ];
  for (const [value, expected] of options) {
    await page.locator('#interconnect').selectOption(value);
    assert(await page.locator('#interconnect_other').isVisible() === expected, `互联情况“${value}”补充框显隐错误`);
  }
  await page.locator('#interconnect_other').fill('测试补充说明');
  await page.locator('#interconnect').selectOption('3-与本单位其他系统连接');
  assert(await page.locator('#interconnect_other').inputValue() === '', '切回固定互联选项应清空补充说明');
  const target = await page.evaluate(() => collectFormData().target);
  assert(target.interconnect === '3-与本单位其他系统连接' && target.interconnect_other === '', '固定互联选项不应提交补充内容');
  await page.evaluate(() => fillBeianData({target: {interconnect: '3-与本单位其他系统连接', interconnect_other: '旧补充说明'}}));
  assert(!await page.locator('#interconnect_other').isVisible() && await page.locator('#interconnect_other').inputValue() === '', '回填固定选项不能显示或保留旧补充说明');
  await page.evaluate(() => fillBeianData({target: {interconnect: '9-其他', interconnect_other: '实际补充说明'}}));
  assert(await page.locator('#interconnect_other').isVisible() && await page.locator('#interconnect_other').inputValue() === '实际补充说明', '回填其他选项应保留补充说明');
  const shared = await page.evaluate(() => {
    const groups = [
      ['biz_type', 'biz_type_other'], ['svc_scope', 'svc_scope_other'],
      ['svc_target', 'svc_target_other'], ['deploy_scope', 'deploy_scope_other'],
      ['net_type', 'net_type_other'], ['cloud_service', 'cloud_service_other'],
      ['cloud_deploy', 'cloud_deploy_other'],
    ];
    for (const [selectId, inputId] of groups) {
      const select = document.getElementById(selectId);
      const input = document.getElementById(inputId);
      for (const option of select.options) {
        select.value = option.value;
        toggleOtherInput(select, inputId);
        const expected = ['其他', '其它', '9-其他', '99-其他'].includes(option.value);
        if ((input.style.display !== 'none') !== expected) throw new Error(`${selectId}：“${option.value}”显隐错误`);
      }
    }
    return groups.length;
  });
  return {passed: true, interconnectOptions: options.length, sharedDropdowns: shared};
}
