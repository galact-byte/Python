async (page) => {
  await page.goto('http://127.0.0.1:5079');
  await page.evaluate(() => {
    showStep(1);
    switchTab(document.querySelectorAll('.tab-item')[1], 1);
    document.getElementById('net_type').value = '2-互联网';
    onNetworkTypeChange();
  });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const scenarios = [];
  for (const width of [1440, 1280, 1200, 1101, 1100, 900, 760, 720, 390]) {
    await page.setViewportSize({width, height: 1000});
    for (const zoom of [0.8, 1, 1.25]) {
      await page.evaluate(zoom => { document.body.style.zoom = zoom; }, zoom);
      const metrics = await page.locator('#net_type').evaluate(select => {
        const reference = document.getElementById('svc_scope').getBoundingClientRect();
        const controls = [select, ...['source_ip', 'domain', 'protocol_port'].map(id => document.getElementById(id))];
        const rects = controls.map(control => control.getBoundingClientRect());
        return {
          contained: rects.every(rect => rect.left >= reference.left - 1 && rect.right <= reference.right + 1),
          aligned: rects.every((rect, index) => index && Math.abs(rect.top - rects[index - 1].top) < 1 || Math.abs(rect.left - reference.left) < 1),
        };
      });
      assert(metrics.contained, `${width}px / ${zoom}：网络输入框超出其他输入框的边界`);
      assert(metrics.aligned, `${width}px / ${zoom}：换行后的输入框未与上方对齐`);
      scenarios.push({width, zoom});
    }
  }
  await page.evaluate(() => { document.body.style.zoom = ''; });
  await page.setViewportSize({width: 1440, height: 1000});
  for (const theme of ['light', 'dark']) {
    await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
    assert(await page.locator('#protocol_port').isVisible(), `${theme}主题下协议输入框应可见`);
  }
  await page.locator('#source_ip').fill('192.0.2.1');
  await page.locator('#domain').fill('example.com');
  await page.locator('#protocol_port').fill('HTTPS/443');
  const target = await page.evaluate(() => collectFormData().target);
  assert(target.source_ip === '192.0.2.1' && target.domain === 'example.com' && target.protocol_port === 'HTTPS/443', '网络字段提交值不一致');
  await page.locator('#net_type').selectOption({label: '9-其他'});
  assert(await page.locator('#net_type_other').isVisible() && !await page.locator('#protocol_port').isVisible(), '其他网络类型显隐异常');
  await page.locator('#net_type').selectOption({label: '1-业务专网'});
  assert(!await page.locator('#net_type_other').isVisible() && !await page.locator('#source_ip').isVisible(), '专网字段显隐异常');
  return {passed: true, scenarios};
}
