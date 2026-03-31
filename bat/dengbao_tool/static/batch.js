const batchState = {
  mode: 'single',
  rootDir: '',
  projects: [],
  manifest: null,
  currentProjectDir: '',
  currentSystemId: '',
  initialUiState: {},
  initialFormData: null,
  initialReportData: null,
};

const PERSISTED_FIELD_IDS = [
  'project_dir', 'project_name', 'old_beian', 'old_report', 'survey', 'output_dir',
  'unit_name', 'credit_code', 'province', 'city', 'county', 'address', 'postal_code', 'admin_code',
  'leader_name', 'leader_title', 'leader_phone', 'leader_email',
  'sec_dept', 'sec_name', 'sec_title', 'sec_phone', 'sec_mobile', 'sec_email',
  'data_dept', 'data_name', 'data_title', 'data_phone', 'data_mobile', 'data_email',
  'affiliation', 'unit_type', 'industry', 'cur_total', 'cur_l2', 'cur_l3', 'cur_l4', 'cur_l5',
  'all_total', 'all_l1', 'all_l2', 'all_l3', 'all_l4', 'all_l5',
  'target_name', 'target_code', 'target_type',
  'tech_cloud', 'tech_mobile', 'tech_iot', 'tech_ics', 'tech_bigdata', 'tech_other',
  'biz_type', 'biz_type_other', 'biz_desc', 'svc_scope', 'svc_scope_other', 'svc_target', 'svc_target_other',
  'deploy_scope', 'deploy_scope_other', 'net_type', 'net_type_other', 'source_ip', 'domain', 'protocol_port',
  'interconnect', 'interconnect_other', 'run_date', 'is_sub', 'parent_sys', 'parent_unit',
  'biz_level', 'svc_level', 'grading_date', 'has_report', 'report_name', 'has_review', 'review_name',
  'has_supervisor', 'supervisor_name', 'supervisor_reviewed', 'filler', 'fill_date',
  'cloud_enabled', 'cloud_role', 'cloud_service', 'cloud_service_other', 'cloud_deploy', 'cloud_deploy_other',
  'cloud_provider_kind', 'cloud_provider_preset', 'cloud_provider', 'cloud_provider_scale',
  'cloud_infra_location', 'cloud_ops_location', 'cloud_plat_level', 'cloud_plat_name', 'cloud_plat_code', 'cloud_ops',
  'mobile_enabled', 'mobile_app', 'mobile_wireless', 'mobile_terminal',
  'iot_enabled', 'iot_perception', 'iot_transport',
  'ics_enabled', 'ics_layer', 'ics_comp',
  'bigdata_enabled', 'bigdata_comp', 'bigdata_cross',
  'att_topology', 'att_topology_name', 'att_org', 'att_org_name', 'att_design', 'att_design_name',
  'att_product', 'att_product_name', 'att_service', 'att_service_name', 'att_supervisor', 'att_supervisor_name',
  'data_name_field', 'data_level', 'data_category', 'data_sec_dept', 'data_sec_person',
  'personal_info', 'total_size', 'total_size_tb', 'total_size_records', 'monthly_growth', 'monthly_growth_tb',
  'data_source_collect', 'data_source_generate', 'data_source_manual', 'data_source_trade', 'data_source_share',
  'data_source_other_chk', 'data_source_other', 'inflow_units', 'outflow_units', 'interaction', 'interaction_other',
  'storage_type', 'storage_cloud_name', 'storage_room', 'storage_room_name', 'storage_region', 'storage_region_name',
  'rpt_responsibility', 'rpt_composition', 'rpt_topology', 'rpt_business', 'rpt_security',
  'rpt_biz_info', 'rpt_biz_victim', 'rpt_biz_degree', 'rpt_svc_desc', 'rpt_svc_victim', 'rpt_svc_degree',
];

const originalLoadOldData = window.loadOldData;
const originalCollectReportData = window.collectReportData;

document.addEventListener('DOMContentLoaded', () => {
  batchState.initialUiState = collectUiState();
  batchState.initialFormData = deepClone(window.collectFormData());
  batchState.initialReportData = deepClone(originalCollectReportData());
  initTheme();
});

window.collectReportData = function collectReportDataPatched() {
  const data = originalCollectReportData();
  data.system_name = document.getElementById('target_name').value.trim()
    || document.getElementById('project_name').value.trim();
  return data;
};

window.getPaths = function getPathsPatched() {
  const documentName = document.getElementById('target_name').value.trim()
    || document.getElementById('project_name').value.trim();
  const currentProject = getCurrentProject();
  const currentSystem = getCurrentSystem();
  return {
    project_name: document.getElementById('project_name').value.trim(),
    beian_template: document.getElementById('beian_template').value.trim(),
    report_template: document.getElementById('report_template').value.trim(),
    output_dir: document.getElementById('output_dir').value.trim(),
    document_name: documentName,
    project_dir: currentProject ? currentProject.project_dir : '',
    system_id: currentSystem ? currentSystem.system_id : '',
    source_dir: currentSystem ? currentSystem.source_dir : '',
    old_beian: currentSystem ? (currentSystem.old_beian || '') : document.getElementById('old_beian').value.trim(),
    old_report: currentSystem ? (currentSystem.old_report || '') : document.getElementById('old_report').value.trim(),
    survey: currentSystem ? (currentSystem.survey || '') : document.getElementById('survey').value.trim(),
  };
};

window.loadOldData = async function loadOldDataPatched() {
  if (batchState.mode === 'batch' && getCurrentSystem()) {
    await ensureCurrentSystemLoaded(false);
    showStep(1);
    return;
  }
  await originalLoadOldData();
};

window.previewDoc = async function previewDocPatched(type) {
  try {
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        doc_type: type,
        paths: window.getPaths(),
        form_data: window.collectFormData(),
        report_data: window.collectReportData(),
      }),
    });
    const data = await res.json();
    if (data.success) {
      showAlert('gen-result', '预览已用 Word 打开: ' + data.path.split(/[/\\]/).pop(), 'success');
    } else {
      showAlert('gen-result', '预览失败: ' + data.message, 'error');
    }
  } catch (e) {
    showAlert('gen-result', '预览失败: ' + e, 'error');
  }
};

window.generateDocs = async function generateDocsPatched() {
  const outDir = document.getElementById('output_dir').value.trim();
  if (!outDir) {
    showModal('请先设置输出目录');
    return;
  }

  const currentSystem = getCurrentSystem();
  const currentProject = getCurrentProject();
  const payload = {
    paths: window.getPaths(),
    form_data: window.collectFormData(),
    report_data: window.collectReportData(),
    ui_state: collectUiState(),
  };
  if (currentSystem) {
    payload.system_meta = systemMetaForSave(currentProject, currentSystem);
  }

  try {
    if (batchState.mode === 'batch' && currentSystem) {
      await saveCurrentSystem(true);
    }
    showAlert('gen-result', '正在生成...', 'info');
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
      showAlert(
        'gen-result',
        data.message.replace(/\n/g, '<br>') + '<br><br><button onclick="openDir()">打开输出目录</button>',
        'success',
      );
      if (currentSystem) {
        currentSystem.needs_update = false;
        currentSystem.status = 'updated';
        currentSystem.generated_at = new Date().toLocaleString('zh-CN', {hour12:false});
        renderBatchProjectList();
        renderCurrentProjectSummary('当前系统已生成并写入状态文件。');
        renderSystemStatus(currentSystem);
      }
    } else {
      showAlert('gen-result', data.message, 'error');
    }
  } catch (e) {
    showAlert('gen-result', '生成失败: ' + e, 'error');
  }
};

window.scanBatchRoot = async function scanBatchRoot(preserveSelection = false) {
  const rootDir = document.getElementById('batch_root_dir').value.trim();
  if (!rootDir) {
    showModal('请先选择总目录');
    return;
  }

  const previousProjectDir = preserveSelection ? batchState.currentProjectDir : '';
  const previousSystemId = preserveSelection ? batchState.currentSystemId : '';
  try {
    const res = await fetch('/api/scan_batch_root', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({root_dir: rootDir}),
    });
    const data = await res.json();
    if (!data.success) {
      showAlert('scan-result', data.message || '批量扫描失败', 'error');
      return;
    }

    batchState.mode = 'batch';
    batchState.rootDir = data.root_dir;
    batchState.projects = data.projects || [];
    mergeManifestProjects();
    renderBatchProjectList();

    const nextProject = findProject(previousProjectDir) || batchState.projects[0];
    const nextSystemId = previousProjectDir && previousProjectDir === (nextProject && nextProject.project_dir)
      ? previousSystemId
      : '';

    if (nextProject) {
      await selectBatchProject(nextProject.project_dir, nextSystemId, true);
      showAlert(
        'scan-result',
        `批量扫描完成，共识别 ${batchState.projects.length} 个项目。`,
        'success',
      );
    } else {
      renderCurrentProjectSummary('未在该总目录下识别到可用项目。');
      showAlert('scan-result', '未识别到包含备案表/定级报告的项目目录。', 'info');
    }
  } catch (e) {
    showAlert('scan-result', '批量扫描失败: ' + e, 'error');
  }
};

window.importBatchManifest = async function importBatchManifest() {
  const manifestPath = document.getElementById('manifest_file').value.trim();
  if (!manifestPath) {
    showModal('请先选择 Excel 清单文件');
    return;
  }

  try {
    const res = await fetch('/api/import_manifest', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({manifest_path: manifestPath}),
    });
    const data = await res.json();
    if (!data.success) {
      showAlert('scan-result', data.message || '导入清单失败', 'error');
      return;
    }

    batchState.manifest = data;
    mergeManifestProjects();
    renderBatchProjectList();
    renderCurrentProjectSummary(
      `已导入清单《${data.sheet_name}》，共 ${data.projects.length} 个项目分组。`,
    );
    showAlert('scan-result', `清单导入成功：${data.projects.length} 个项目分组`, 'success');
  } catch (e) {
    showAlert('scan-result', '导入清单失败: ' + e, 'error');
  }
};

window.switchCurrentSystem = async function switchCurrentSystem(systemId) {
  if (!systemId) {
    return;
  }
  const currentProject = getCurrentProject();
  if (!currentProject) {
    return;
  }
  await selectBatchProject(currentProject.project_dir, systemId);
};

window.saveCurrentSystem = async function saveCurrentSystem(silent = false) {
  if (batchState.mode !== 'batch') {
    if (!silent) {
      showAlert('system-status', '当前仍是单系统模式，无需保存状态文件。', 'info');
    }
    return true;
  }

  const currentProject = getCurrentProject();
  const currentSystem = getCurrentSystem();
  if (!currentProject || !currentSystem) {
    return true;
  }

  persistCurrentSystemLocally();
  try {
    const res = await fetch('/api/save_system', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        project_dir: currentProject.project_dir,
        system_id: currentSystem.system_id,
        project_name: document.getElementById('project_name').value.trim(),
        output_dir: document.getElementById('output_dir').value.trim(),
        form_data: currentSystem.form_data,
        report_data: currentSystem.report_data,
        ui_state: currentSystem.ui_state,
        system_meta: systemMetaForSave(currentProject, currentSystem),
      }),
    });
    const data = await res.json();
    if (!data.success) {
      if (!silent) {
        showAlert('system-status', data.message || '保存失败', 'error');
      }
      return false;
    }

    currentSystem.has_saved_data = true;
    currentSystem.needs_update = true;
    currentSystem.status = 'pending';
    currentSystem.updated_at = data.updated_at;
    if (!silent) {
      showAlert('system-status', `当前系统已保存到状态文件：${data.updated_at}`, 'success');
    }
    renderBatchProjectList();
    renderCurrentProjectSummary();
    renderSystemStatus(currentSystem);
    return true;
  } catch (e) {
    if (!silent) {
      showAlert('system-status', '保存失败: ' + e, 'error');
    }
    return false;
  }
};

window.reloadCurrentSystem = async function reloadCurrentSystem() {
  if (batchState.mode !== 'batch' || !getCurrentSystem()) {
    showModal('当前没有可重载的批量系统。');
    return;
  }
  await ensureCurrentSystemLoaded(true);
};

window.addManualSystem = async function addManualSystem() {
  if (batchState.mode !== 'batch') {
    showModal('请先扫描总目录，再在当前项目下新增系统。');
    return;
  }
  const currentProject = getCurrentProject();
  if (!currentProject) {
    showModal('请先选择一个项目。');
    return;
  }

  const name = window.prompt('请输入新系统名称：', '');
  if (!name || !name.trim()) {
    return;
  }

  await saveCurrentSystem(true);

  const {formData, reportData} = buildNewSystemPayload(
    currentProject.project_name,
    name.trim(),
    getCurrentSystem(),
  );
  const system = {
    system_id: `manual_${Date.now()}`,
    system_name: name.trim(),
    source_dir: currentProject.project_dir,
    old_beian: '',
    old_report: '',
    survey: '',
    output_dir: document.getElementById('output_dir').value.trim() || currentProject.output_dir || currentProject.project_dir,
    generated_at: '',
    generated_files: [],
    generated_files_exist: false,
    status: 'pending',
    needs_update: true,
    has_saved_data: true,
    source_changed: false,
    manual: true,
    loaded: true,
    form_data: formData,
    report_data: reportData,
  };
  currentProject.systems.push(system);
  currentProject.system_count = currentProject.systems.length;
  currentProject.pending_count = (currentProject.pending_count || 0) + 1;
  renderBatchProjectList();
  await selectBatchProject(currentProject.project_dir, system.system_id, true);
  showAlert('system-status', `已新增系统：${system.system_name}`, 'success');
};

window.generateBatchDocs = async function generateBatchDocs() {
  if (batchState.mode !== 'batch' || !batchState.rootDir) {
    showModal('请先扫描总目录，再执行批量生成。');
    return;
  }

  const saved = await saveCurrentSystem(true);
  if (!saved) {
    showModal('当前系统保存失败，已停止批量生成。');
    return;
  }

  try {
    showAlert('batch-result', '正在批量生成待更新项...', 'info');
    const res = await fetch('/api/generate_batch', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        root_dir: batchState.rootDir,
        paths: {
          beian_template: document.getElementById('beian_template').value.trim(),
          report_template: document.getElementById('report_template').value.trim(),
        },
        skip_updated: true,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      showAlert('batch-result', data.message || '批量生成失败', 'error');
      return;
    }

    const summary = [
      `批量生成完成`,
      `生成 ${data.generated_count} 项`,
      `跳过 ${data.skipped_count} 项`,
      `失败 ${data.failed_count} 项`,
    ].join('，');
    showAlert('batch-result', summary, data.failed_count ? 'error' : 'success');
    await scanBatchRoot(true);
  } catch (e) {
    showAlert('batch-result', '批量生成失败: ' + e, 'error');
  }
};

window.toggleTheme = function toggleTheme() {
  const current = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  const next = current === 'light' ? 'dark' : 'light';
  applyTheme(next);
};

async function selectBatchProject(projectDir, preferredSystemId = '', skipSave = false) {
  if (!skipSave) {
    await saveCurrentSystem(true);
  }
  batchState.currentProjectDir = projectDir;
  const project = getCurrentProject();
  if (!project) {
    return;
  }
  renderBatchProjectList();
  renderSystemSelector();
  const targetSystem = project.systems.find(item => item.system_id === preferredSystemId) || project.systems[0];
  if (!targetSystem) {
    renderCurrentProjectSummary('当前项目尚未识别到系统。');
    return;
  }
  batchState.currentSystemId = targetSystem.system_id;
  renderSystemSelector();
  await ensureCurrentSystemLoaded(false);
}

async function ensureCurrentSystemLoaded(forceReload) {
  const project = getCurrentProject();
  const system = getCurrentSystem();
  if (!project || !system) {
    return;
  }

  if (!forceReload && system.loaded && system.ui_state) {
    applySystemSnapshot(project, system);
    return;
  }

  if (!forceReload && !system.old_beian && !system.old_report && system.form_data && system.report_data) {
    system.loaded = true;
    applySystemSnapshot(project, system);
    return;
  }

  if (!forceReload && !system.old_beian && !system.old_report && !system.form_data) {
    const payload = buildNewSystemPayload(project.project_name, system.system_name, null);
    system.form_data = payload.formData;
    system.report_data = payload.reportData;
    system.loaded = true;
    applySystemSnapshot(project, system);
    return;
  }

  const res = await fetch('/api/load_system', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      project_dir: project.project_dir,
      system_id: system.system_id,
      force_reload: forceReload,
    }),
  });
  const data = await res.json();
  if (!data.success) {
    showAlert('system-status', data.message || '加载系统失败', 'error');
    return;
  }

  project.project_name = data.project.project_name;
  project.output_dir = data.project.output_dir;
  mergeSystemMeta(system, data.system);
  system.form_data = data.form_data;
  system.report_data = data.report_data;
  system.ui_state = data.ui_state || {};
  system.loaded = true;
  system.has_saved_data = true;
  applySystemSnapshot(project, system);

  if (data.errors && data.errors.length) {
    showAlert('system-status', data.errors.join('<br>'), 'error');
  } else if (forceReload) {
    showAlert('system-status', '已按旧文档重新加载当前系统。', 'success');
  } else {
    renderSystemStatus(system);
  }
}

function applySystemSnapshot(project, system) {
  applyUiState(batchState.initialUiState);
  clearFieldMarks();
  applyProjectFields(project, system);

  if (system.ui_state && Object.keys(system.ui_state).length) {
    applyUiState(system.ui_state);
  } else {
    if (system.form_data) {
      fillBeianData(system.form_data);
      applyHighlightedFields(system.form_data.highlighted_fields || []);
    }
    if (system.report_data) {
      fillReportData(system.report_data);
    }
  }

  document.getElementById('project_name').value = project.project_name || document.getElementById('project_name').value;
  document.getElementById('target_name').value = document.getElementById('target_name').value || system.system_name || '';
  document.getElementById('output_dir').value = system.output_dir || project.output_dir || project.project_dir || '';

  onTargetTypeChange();
  onNetworkTypeChange();
  onSupervisorChange();
  onStorageTypeChange();
  toggleInteractionFields();
  refreshCloudPresetOptions();
  ['cloud', 'mobile', 'iot', 'ics', 'bigdata'].forEach(toggleSection);
  updateFinalLevel();
  clearLog();
  updatePreview();
  updateCurrentLabels(project, system);
  renderCurrentProjectSummary();
  renderSystemStatus(system);
  system.ui_state = collectUiState();
}

function persistCurrentSystemLocally() {
  const project = getCurrentProject();
  const system = getCurrentSystem();
  if (!project || !system) {
    return;
  }
  system.form_data = window.collectFormData();
  system.report_data = window.collectReportData();
  system.ui_state = collectUiState();
  system.system_name = system.form_data.target.name || system.system_name;
  system.output_dir = document.getElementById('output_dir').value.trim();
  system.old_beian = document.getElementById('old_beian').value.trim();
  system.old_report = document.getElementById('old_report').value.trim();
  system.survey = document.getElementById('survey').value.trim();
  project.project_name = document.getElementById('project_name').value.trim() || project.project_name;
}

function applyProjectFields(project, system) {
  document.getElementById('project_dir').value = project.project_dir || '';
  document.getElementById('project_name').value = project.project_name || '';
  document.getElementById('old_beian').value = system.old_beian || '';
  document.getElementById('old_report').value = system.old_report || '';
  document.getElementById('survey').value = system.survey || '';
  document.getElementById('output_dir').value = system.output_dir || project.output_dir || project.project_dir || '';
}

function renderBatchProjectList() {
  const container = document.getElementById('batch-project-list');
  if (!container) {
    return;
  }
  if (!batchState.projects.length) {
    container.innerHTML = '<p class="hint">尚未扫描总目录</p>';
    renderCurrentProjectSummary();
    renderSystemSelector();
    return;
  }

  const html = batchState.projects.map(project => {
    const active = project.project_dir === batchState.currentProjectDir ? ' active' : '';
    const pending = project.systems.filter(item => item.needs_update).length;
    return `
      <button type="button" class="batch-project-item${active}" data-project-dir="${escapeHtml(project.project_dir)}">
        <span class="batch-project-name">${escapeHtml(project.project_name || project.project_dir.split(/[/\\\\]/).pop())}</span>
        <span class="batch-project-meta">${project.systems.length} 个系统 / ${pending} 个待更新</span>
      </button>
    `;
  }).join('');
  container.innerHTML = html;
  container.querySelectorAll('.batch-project-item').forEach(el => {
    el.addEventListener('click', async () => {
      const projectDir = el.dataset.projectDir;
      await selectBatchProject(projectDir);
    });
  });
  renderCurrentProjectSummary();
  renderSystemSelector();
}

function renderCurrentProjectSummary(extraMessage = '') {
  const container = document.getElementById('batch-project-summary');
  if (!container) {
    return;
  }

  const project = getCurrentProject();
  if (!project) {
    container.textContent = extraMessage || '扫描后会在这里显示项目、系统数量和待更新状态。';
    return;
  }

  const systems = project.systems.map(item => {
    const statusClass = item.needs_update ? 'pending' : 'updated';
    const statusText = item.status === 'missing_source'
      ? '缺少旧文档'
      : (item.needs_update ? '待更新' : '已更新');
    return `
      <div class="batch-system-row ${item.system_id === batchState.currentSystemId ? 'active' : ''}">
        <div>
          <div class="batch-system-name">${escapeHtml(item.system_name || item.system_id)}</div>
          <div class="batch-system-path">${escapeHtml(item.source_dir || project.project_dir)}</div>
        </div>
        <span class="batch-system-badge ${statusClass}">${statusText}</span>
      </div>
    `;
  }).join('');

  const manifestText = batchState.manifest
    ? `<div class="hint">已导入清单：${escapeHtml(batchState.manifest.sheet_name || 'Excel 清单')}</div>`
    : '';

  container.innerHTML = `
    <div class="batch-summary-head">
      <div>
        <div class="batch-summary-title">${escapeHtml(project.project_name || project.project_dir)}</div>
        <div class="batch-summary-path">${escapeHtml(project.project_dir)}</div>
      </div>
      <div class="batch-summary-count">${project.systems.length} 个系统</div>
    </div>
    ${manifestText}
    ${extraMessage ? `<div class="alert alert-info">${extraMessage}</div>` : ''}
    <div class="batch-system-list">${systems}</div>
  `;
}

function renderSystemSelector() {
  const selector = document.getElementById('system_selector');
  const project = getCurrentProject();
  if (!selector) {
    return;
  }
  if (!project) {
    selector.innerHTML = '<option value="">当前仅单系统模式</option>';
    updateCurrentLabels(null, null);
    return;
  }

  selector.innerHTML = project.systems.map(system => {
    const status = system.status === 'missing_source'
      ? '缺少旧文档'
      : (system.needs_update ? '待更新' : '已更新');
    return `<option value="${escapeHtml(system.system_id)}">${escapeHtml(system.system_name)} · ${status}</option>`;
  }).join('');
  selector.value = batchState.currentSystemId || (project.systems[0] && project.systems[0].system_id) || '';
  updateCurrentLabels(project, getCurrentSystem());
}

function renderSystemStatus(system) {
  if (!system) {
    showAlert('system-status', '当前未选择系统。', 'info');
    return;
  }

  let message = `系统：${escapeHtml(system.system_name)}`;
  let type = 'info';
  if (system.status === 'missing_source') {
    message += '，缺少旧备案表/定级报告，需要手动完善后再生成。';
    type = 'error';
  } else if (system.needs_update) {
    message += '，存在未生成的改动或源文档变化。';
    type = 'info';
  } else {
    message += '，状态正常，可批量跳过。';
    type = 'success';
  }
  showAlert('system-status', message, type);
}

function mergeManifestProjects() {
  if (!batchState.manifest || !batchState.projects.length) {
    return;
  }

  batchState.manifest.projects.forEach(manifestProject => {
    const match = batchState.projects.find(project => matchName(project.project_name, manifestProject.project_name));
    if (!match) {
      return;
    }
    manifestProject.systems.forEach(row => {
      const exists = match.systems.find(system => matchName(system.system_name, row.system_name));
      if (exists) {
        exists.manifest = row;
        return;
      }
      match.systems.push({
        system_id: `manifest_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
        system_name: row.system_name || row.system_code || '清单系统',
        source_dir: match.project_dir,
        old_beian: '',
        old_report: '',
        survey: '',
        output_dir: match.output_dir || match.project_dir,
        generated_at: '',
        generated_files: [],
        generated_files_exist: false,
        status: 'missing_source',
        needs_update: false,
        has_saved_data: false,
        source_changed: false,
        manifest_only: true,
        manifest: row,
      });
    });
    match.system_count = match.systems.length;
  });
}

function collectUiState() {
  const state = {};
  PERSISTED_FIELD_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    state[id] = el.type === 'checkbox' ? !!el.checked : el.value;
  });
  state.final_level = document.getElementById('final_level').textContent;
  state.highlighted_fields = Array.from(highlightedFields);
  return state;
}

function applyUiState(state) {
  PERSISTED_FIELD_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    if (!(id in state)) {
      return;
    }
    if (el.type === 'checkbox') {
      el.checked = !!state[id];
    } else {
      el.value = state[id] ?? '';
    }
  });
  if (state.final_level) {
    document.getElementById('final_level').textContent = state.final_level;
  }
  applyHighlightedFields(state.highlighted_fields || []);
  onTargetTypeChange();
  onNetworkTypeChange();
  if ('cloud_provider_kind' in state) {
    document.getElementById('cloud_provider_kind').value = state.cloud_provider_kind || 'cloud_vendor';
  }
  refreshCloudPresetOptions();
  if ('cloud_provider_preset' in state) {
    document.getElementById('cloud_provider_preset').value = state.cloud_provider_preset || '';
  }
  onSupervisorChange();
  onStorageTypeChange();
  toggleInteractionFields();
  ['cloud', 'mobile', 'iot', 'ics', 'bigdata'].forEach(toggleSection);
  updateFinalLevel();
}

function applyHighlightedFields(fieldIds) {
  highlightedFields.clear();
  document.querySelectorAll('.highlight-yellow').forEach(el => el.classList.remove('highlight-yellow'));
  fieldIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el) {
      return;
    }
    highlightedFields.add(id);
    el.classList.add('highlight-yellow');
  });
  document.querySelectorAll('.highlight-btn').forEach(btn => {
    const ids = (btn.dataset.targets || '').split(',').filter(Boolean);
    btn.classList.toggle('active', ids.length > 0 && ids.every(id => highlightedFields.has(id)));
  });
}

function clearFieldMarks() {
  document.querySelectorAll('.auto-filled, .modified').forEach(el => {
    el.classList.remove('auto-filled', 'modified');
  });
}

function clearLog() {
  if (typeof changeLog !== 'undefined') {
    changeLog.length = 0;
    renderLog();
  }
}

function updateCurrentLabels(project, system) {
  document.getElementById('current_project_label').textContent = project ? (project.project_name || '未命名项目') : '未选择';
  document.getElementById('current_system_label').textContent = system ? (system.system_name || '未命名系统') : '未选择';
}

function buildNewSystemPayload(projectName, systemName, baseSystem) {
  const baseForm = deepClone(baseSystem && baseSystem.form_data ? baseSystem.form_data : batchState.initialFormData);
  const baseReport = deepClone(baseSystem && baseSystem.report_data ? baseSystem.report_data : batchState.initialReportData);

  baseForm.project_name = projectName || '';
  baseForm.target = baseForm.target || {};
  baseForm.target.name = systemName;
  baseForm.target.code = '';
  baseForm.target.tech_type = '';
  baseForm.target.biz_desc = '';
  baseForm.target.interconnect = '';
  baseForm.target.run_date = '';
  baseForm.target.parent_system = '';
  baseForm.target.parent_unit = '';
  baseForm.target.service_scope = '';
  baseForm.target.service_target = '';
  baseForm.target.deploy_scope = '';
  baseForm.target.network_type = '';
  baseForm.scenario = deepClone(batchState.initialFormData.scenario);
  baseForm.attachment = deepClone(batchState.initialFormData.attachment);
  baseForm.data = deepClone(batchState.initialFormData.data);
  baseForm.highlighted_fields = [];

  baseReport.system_name = systemName;
  baseReport.responsibility = '';
  baseReport.composition = '';
  baseReport.topology_image = '';
  baseReport.business_desc = '';
  baseReport.security_resp = '';
  baseReport.biz_info_desc = '';
  baseReport.biz_victim = '';
  baseReport.biz_degree = '';
  baseReport.svc_desc = '';
  baseReport.svc_victim = '';
  baseReport.svc_degree = '';
  baseReport.subsystems = [];

  return {formData: baseForm, reportData: baseReport};
}

function systemMetaForSave(project, system) {
  return {
    system_id: system.system_id,
    system_name: document.getElementById('target_name').value.trim() || system.system_name,
    source_dir: system.source_dir || project.project_dir,
    old_beian: document.getElementById('old_beian').value.trim(),
    old_report: document.getElementById('old_report').value.trim(),
    survey: document.getElementById('survey').value.trim(),
    output_dir: document.getElementById('output_dir').value.trim() || system.output_dir || project.output_dir || project.project_dir,
  };
}

function mergeSystemMeta(target, incoming) {
  Object.assign(target, incoming || {});
}

function getCurrentProject() {
  return batchState.projects.find(project => project.project_dir === batchState.currentProjectDir) || null;
}

function getCurrentSystem() {
  const project = getCurrentProject();
  if (!project) {
    return null;
  }
  return project.systems.find(system => system.system_id === batchState.currentSystemId) || null;
}

function findProject(projectDir) {
  return batchState.projects.find(project => project.project_dir === projectDir) || null;
}

function initTheme() {
  const savedTheme = localStorage.getItem('dengbao_theme');
  const preferredLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  applyTheme(savedTheme || (preferredLight ? 'light' : 'dark'));
}

function applyTheme(theme) {
  const normalized = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = normalized;
  localStorage.setItem('dengbao_theme', normalized);
  const btn = document.getElementById('theme_toggle');
  if (btn) {
    btn.textContent = normalized === 'light' ? '切换深色' : '切换浅色';
  }
}

function matchName(left, right) {
  const a = normalizeName(left);
  const b = normalizeName(right);
  return !!a && !!b && (a === b || a.includes(b) || b.includes(a));
}

function normalizeName(value) {
  return (value || '')
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/[()（）_\-—.]/g, '');
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
