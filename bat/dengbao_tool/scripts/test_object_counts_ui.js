async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  await page.goto('http://127.0.0.1:5079');
  await page.evaluate(() => { showStep(1); switchTab(document.querySelectorAll('.tab-item')[0], 0); });
  const values = prefix => page.locator(`input[id^="${prefix}_"]`).evaluateAll(inputs => inputs.map(input => input.value));
  assert((await values('cur')).every(value => value === ''), '初始本次备案数量应全部留空');
  assert((await values('all')).every(value => value === ''), '初始总数应全部留空');
  await page.locator('#cur_l3').fill('1');
  assert(JSON.stringify(await values('cur')) === JSON.stringify(['1', '0', '1', '0', '0']), '只有一个三级时应自动汇总为1，其余等级补0');
  assert((await values('all')).every(value => value === ''), '本次备案不能改写单位累计数量');
  await page.locator('#all_l3').fill('1');
  assert(JSON.stringify(await values('all')) === JSON.stringify(['1', '0', '0', '1', '0', '0']), '累计数量也应按等级汇总并补0');
  await page.locator('#cur_l2').fill('2');
  assert(await page.locator('#cur_total').inputValue() === '3', '二级与三级数量应相加');
  await page.locator('#cur_l2').fill('');
  await page.locator('#cur_l3').fill('');
  assert((await values('cur')).every(value => value === ''), '清空所有手填等级数量时应连同自动0和总数一起清空');
  await page.locator('#cur_l4').fill('0');
  assert((await values('cur')).every(value => value === '0'), '明确填写0应保留零数量');
  await page.locator('#cur_l4').fill('');
  assert((await values('cur')).every(value => value === ''), '清空明确的0后应恢复空行');
  await page.locator('#cur_total').fill('8');
  assert((await values('cur')).slice(1).every(value => value === ''), '只填总数不能推测等级分布');
  await page.locator('#cur_total').fill('');
  await page.locator('#cur_l3').fill('2');
  await page.evaluate(() => {
    fillBeianData({unit: {current_total: '7', current_level2: '2', current_level3: '5',
      current_level4: '0', current_level5: '0', all_total: '20', all_level1: '1',
      all_level2: '4', all_level3: '10', all_level4: '3', all_level5: '2'}});
  });
  assert(await page.locator('#all_total').inputValue() === '20', '导入应保留实际累计数量');
  await page.locator('#cur_l3').fill('6');
  assert(await page.locator('#cur_total').inputValue() === '8', '导入后修改等级数量应更新汇总');
  assert(await page.locator('#cur_l2').inputValue() === '2', '导入的其他等级数量不能丢失');
  await page.evaluate(() => {
    fillBeianData({unit: {current_total: '7个', current_level2: '2个', current_level3: '5个',
      current_level4: 0, current_level5: '0个'}});
  });
  await page.locator('#cur_l3').fill('6');
  assert(await page.locator('#cur_total').inputValue() === '8', '旧文档带“个”的数量也应正确汇总');
  assert(await page.locator('#cur_l4').inputValue() === '0', '数字0导入后不能丢失');
  await page.evaluate(() => fillBeianData({unit: {}}));
  assert((await values('cur')).every(value => value === ''), '导入空数量不能留下上一份数据');
  await page.evaluate(() => {
    fillBeianData({unit: {current_total: '7', current_level2: '2', current_level3: '5',
      current_level4: '0', current_level5: '0', all_total: '20', all_level1: '1',
      all_level2: '4', all_level3: '10', all_level4: '3', all_level5: '2'}});
  });
  await page.evaluate(() => {
    const state = collectUiState();
    state.cur_total = '6'; state.cur_l2 = '1'; state.cur_l3 = '2'; state.cur_l4 = '3'; state.cur_l5 = '0';
    applyUiState(state);
  });
  await page.locator('#cur_l3').fill('4');
  assert(await page.locator('#cur_total').inputValue() === '8', '批量回填后仍应正确计算');
  const unit = await page.evaluate(() => collectFormData().unit);
  assert(unit.current_total === '8' && unit.current_level2 === '1' && unit.current_level3 === '4' && unit.current_level4 === '3' && unit.current_level5 === '0', '提交应包含更新的所有等级数量');
  assert(unit.all_total === '20' && unit.all_level1 === '1' && unit.all_level5 === '2', '累计数量应完整提交');
  const layouts = [];
  for (const width of [1440, 900, 390]) {
    await page.setViewportSize({width, height: 1000});
    const fits = await page.locator('#cur_total').evaluate(input => {
      const group = input.closest('.form-group');
      return Array.from(group.querySelectorAll('input')).every(el => {
        const rect = el.getBoundingClientRect(); const bounds = group.getBoundingClientRect();
        return rect.left >= bounds.left && rect.right <= bounds.right;
      });
    });
    assert(fits, `数量输入框在${width}px应完整显示`);
    layouts.push(width);
  }
  await page.setViewportSize({width: 1440, height: 1100});
  return {passed: true, layouts, unit};
}
