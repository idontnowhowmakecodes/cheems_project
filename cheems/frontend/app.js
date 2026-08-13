/**
 * CHEEMS Frontend Controller — Interfaz y Bridge PyWebView
 */

// Estado Global de la Sesión en el Cliente
const state = {
  currentTab: 'tab-patient',
  selectedProtocol: 'stat',
  isSessionActive: false,
  isSessionFinished: false,
  currentVerdict: null,
  timerSeconds: 0,
  timerInterval: null,
  videoStreamInterval: null,
  lastEvaluationResult: null,
  isCameraOnline: false,
  currentItemIndex: 0,
  totalItemsCount: 12,
  cameraSources: [],
  lastAiPassed: null,
};

// ================= NAVEGACIÓN PROTEGIDA ENTRE PESTAÑAS =================
function initTabs() {
  const tabs = document.querySelectorAll('.nav-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-tab');
      trySwitchTab(target);
    });
  });
}

function trySwitchTab(tabId) {
  if (tabId === 'tab-live' && !state.isSessionActive) {
    alert('Debe iniciar una sesión de evaluación en el Paso 1 antes de ingresar a la evaluación.');
    return;
  }
  if (tabId === 'tab-results' && !state.isSessionFinished && !state.lastEvaluationResult) {
    alert('No hay resultados disponibles todavía. Debe completar la evaluación en el Paso 2.');
    return;
  }

  switchTab(tabId);
}

function switchTab(tabId) {
  state.currentTab = tabId;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const activeBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
  const activeContent = document.getElementById(tabId);
  if (activeBtn) activeBtn.classList.add('active');
  if (activeContent) activeContent.classList.add('active');

  if (tabId === 'tab-settings') {
    loadSettingsIntoForm();
    scanAllCamerasUI();
  }
}

function updateNavigationLocks() {
  const btnLive = document.getElementById('btnTabLive');
  const btnResults = document.getElementById('btnTabResults');

  if (btnLive) {
    if (state.isSessionActive) {
      btnLive.classList.remove('disabled');
    } else {
      btnLive.classList.add('disabled');
    }
  }

  if (btnResults) {
    if (state.isSessionFinished || state.lastEvaluationResult) {
      btnResults.classList.remove('disabled');
    } else {
      btnResults.classList.add('disabled');
    }
  }
}

// ================= SELECCIÓN DE PROTOCOLO =================
function selectProtocol(protocol) {
  state.selectedProtocol = protocol;
  document.getElementById('optStat').classList.toggle('selected', protocol === 'stat');
  document.getElementById('optAdos2').classList.toggle('selected', protocol === 'ados2');
  
  const adosOptions = document.getElementById('ados2Options');
  if (adosOptions) {
    adosOptions.style.display = protocol === 'ados2' ? 'block' : 'none';
  }
}

function updateSubAlgorithms() {
  const moduleSelect = document.getElementById('adosModule');
  const subAlgoSelect = document.getElementById('adosSubAlgo');
  if (!moduleSelect || !subAlgoSelect) return;

  const mod = moduleSelect.value;
  subAlgoSelect.innerHTML = '';

  if (mod === 'Toddler') {
    subAlgoSelect.innerHTML = `
      <option value="toddler_12_20_few">12-20 meses (Pocas/Ninguna palabra)</option>
      <option value="toddler_21_30_few">21-30 meses (Pocas/Ninguna palabra)</option>
      <option value="toddler_21_30_some">21-30 meses (Algunas palabras)</option>
    `;
  } else if (mod === 'Módulo 1') {
    subAlgoSelect.innerHTML = `
      <option value="m1_few_no_words">Pocas o Ninguna Palabra</option>
      <option value="m1_some_words" selected>Algunas Palabras</option>
    `;
  } else if (mod === 'Módulo 2') {
    subAlgoSelect.innerHTML = `
      <option value="m2_younger_5">Menores de 5 años</option>
      <option value="m2_older_5">5 años o más</option>
    `;
  } else {
    subAlgoSelect.innerHTML = `<option value="standard">Algoritmo Estándar</option>`;
  }
}

// ================= GESTIÓN INTELIGENTE DE CÁMARAS =================
async function refreshAvailableCameras() {
  const select = document.getElementById('cameraSelect');
  const badge = document.getElementById('cameraAutoBadge');
  badge.innerText = 'Escaneando cámaras disponibles...';
  badge.className = 'help-text text-cyan';

  if (window.pywebview && window.pywebview.api) {
    try {
      const scanRes = await window.pywebview.api.scan_camera_sources();
      state.cameraSources = scanRes.sources || [];
      select.innerHTML = '';

      let hasOnline = false;
      let onlineCamName = '';

      state.cameraSources.forEach(cam => {
        const opt = document.createElement('option');
        opt.value = cam.url;
        const icon = cam.connected ? '● (Conectada)' : '○ (No responde)';
        opt.innerText = `${cam.name} — ${icon} [${cam.url}]`;
        select.appendChild(opt);

        if (cam.connected && !hasOnline) {
          hasOnline = true;
          onlineCamName = cam.name;
          select.value = cam.url;
        }
      });

      if (hasOnline) {
        badge.innerText = `Cámara conectada automáticamente: ${onlineCamName}`;
        badge.className = 'help-text text-cyan';
      } else {
        badge.innerText = 'No se detectó señal en red. Verifique en Configuración.';
        badge.className = 'help-text text-magenta';
      }
    } catch (e) {
      console.error('Error al escanear cámaras:', e);
      badge.innerText = 'Error al escanear cámaras.';
    }
  } else {
    // Simulación offline
    select.innerHTML = `
      <option value="http://192.168.1.122:4747/video">● DroidCam Móvil (Conectada) [http://192.168.1.122:4747/video]</option>
      <option value="0">● Cámara Integrada (Conectada) [0]</option>
    `;
    badge.innerText = 'Cámara conectada automáticamente: DroidCam Móvil';
  }
}

async function scanAllCamerasUI() {
  const tbody = document.getElementById('camerasListBody');
  tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">Escaneando dispositivos y streams en red...</td></tr>`;

  if (window.pywebview && window.pywebview.api) {
    try {
      const scanRes = await window.pywebview.api.scan_camera_sources();
      renderCamerasTable(scanRes.sources || []);
      refreshAvailableCameras();
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="4" style="color:var(--color-magenta); text-align:center;">Error al escanear: ${e}</td></tr>`;
    }
  } else {
    renderCamerasTable([
      { name: 'DroidCam Móvil', url: 'http://192.168.1.122:4747/video', connected: true, resolution: '1280x720', status_text: 'Conectada' },
      { name: 'Raspberry Pi Zero 2W', url: 'rtsp://192.168.1.50:8554/stream', connected: false, resolution: '', status_text: 'No responde' },
    ]);
  }
}

function renderCamerasTable(sources) {
  const tbody = document.getElementById('camerasListBody');
  tbody.innerHTML = '';
  if (!sources || sources.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">No hay cámaras guardadas.</td></tr>`;
    return;
  }

  sources.forEach(cam => {
    const statusClass = cam.connected ? 'text-cyan' : 'text-magenta';
    const statusText = cam.connected ? `Conectada (${cam.resolution || 'HD'})` : 'No responde';
    tbody.innerHTML += `
      <tr>
        <td><strong>${cam.name}</strong></td>
        <td><code>${cam.url}</code></td>
        <td><span class="${statusClass}"><strong>${statusText}</strong></span></td>
        <td>
          <button class="btn-link text-magenta" onclick="removeCameraUI('${cam.url}')">Eliminar</button>
        </td>
      </tr>
    `;
  });
}

async function addNewCameraUI() {
  const name = document.getElementById('newCamName').value.trim();
  const url = document.getElementById('newCamUrl').value.trim();

  if (!url) {
    alert('Ingrese una URL o índice de cámara.');
    return;
  }

  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.add_camera_source(name, url);
      alert(res.message || 'Cámara guardada.');
      document.getElementById('newCamName').value = '';
      document.getElementById('newCamUrl').value = '';
      scanAllCamerasUI();
    } catch (e) {
      alert('Error agregando cámara: ' + e);
    }
  } else {
    alert('Cámara guardada (modo prueba).');
    scanAllCamerasUI();
  }
}

async function removeCameraUI(url) {
  if (!confirm(`¿Eliminar la cámara con URL ${url}?`)) return;

  if (window.pywebview && window.pywebview.api) {
    try {
      await window.pywebview.api.remove_camera_source(url);
      scanAllCamerasUI();
    } catch (e) {
      alert('Error eliminando cámara: ' + e);
    }
  } else {
    scanAllCamerasUI();
  }
}

// ================= CONFIGURACIONES Y EXPLORADOR DE CARPETAS =================
async function loadSettingsIntoForm() {
  if (window.pywebview && window.pywebview.api) {
    try {
      const cfg = await window.pywebview.api.get_settings();
      if (cfg) {
        if (document.getElementById('cfgRecordingsDir')) document.getElementById('cfgRecordingsDir').value = cfg.recordings_dir || 'data/recordings';
        if (document.getElementById('cfgProvisionalDir')) document.getElementById('cfgProvisionalDir').value = cfg.provisional_reports_dir || 'data/reports/provisional';
        if (document.getElementById('cfgFinalDir')) document.getElementById('cfgFinalDir').value = cfg.final_reports_dir || 'data/reports/final';
      }
    } catch (e) {
      console.error('Error cargando configuración:', e);
    }
  }
}

async function saveSystemSettings() {
  const recordingsDir = document.getElementById('cfgRecordingsDir').value.trim();
  const provisionalDir = document.getElementById('cfgProvisionalDir').value.trim();
  const finalDir = document.getElementById('cfgFinalDir').value.trim();

  const payload = {
    recordings_dir: recordingsDir,
    provisional_reports_dir: provisionalDir,
    final_reports_dir: finalDir,
  };

  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.save_settings(payload);
      alert(res.message || 'Configuración de rutas guardada.');
    } catch (e) {
      alert('Error al guardar: ' + e);
    }
  } else {
    alert('Configuración de rutas guardada.');
  }
}

async function browseFolder(targetInputId) {
  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.select_folder('Seleccionar Carpeta de Destino');
      if (res && res.success && res.path) {
        document.getElementById(targetInputId).value = res.path;
      }
    } catch (e) {
      console.error('Error abriendo selector de carpetas:', e);
    }
  } else {
    const manual = prompt('Ingrese la ruta del directorio:', document.getElementById(targetInputId).value);
    if (manual) document.getElementById(targetInputId).value = manual;
  }
}

// ================= CONTROL DE SESIÓN =================
const STAT_ITEMS_CATALOG = [
  { code: 'P-1', name: 'Juego con Objetos', domain: 'Juego', instruction: 'Observar interacción espontánea y respuesta al modelo lúdico.' },
  { code: 'P-2', name: 'Juego Simbólico / Representacional', domain: 'Juego', instruction: 'Invitar al paciente a alimentar a la muñeca o rodar el carrito.' },
  { code: 'R-1', name: 'Petición con Juguete de Cuerda', domain: 'Petición', instruction: 'Activar juguete mecánico y entregarlo apagado para observar petición.' },
  { code: 'R-2', name: 'Petición con Burbujas', domain: 'Petición', instruction: 'Cerrar frasco de burbujas y esperar iniciativa del paciente.' },
  { code: 'DA-1', name: 'Atención a Estímulo Cercano', domain: 'Atención Conjunta', instruction: 'Mostrar objeto visual llamativo en el campo visual.' },
  { code: 'DA-2', name: 'Señalar Objeto Lejano', domain: 'Atención Conjunta', instruction: 'Señalar estímulo a distancia e invitar a compartir la mirada.' },
  { code: 'DA-3', name: 'Mostrar Objeto', domain: 'Atención Conjunta', instruction: 'Observar si el paciente extiende o muestra el objeto sin soltarlo.' },
  { code: 'DA-4', name: 'Seguimiento de Mirada', domain: 'Atención Conjunta', instruction: 'Girar cabeza y mirada hacia un póster u objeto lateral.' },
  { code: 'MI-1', name: 'Imitación: Golpear Mesa con Manos', domain: 'Imitación Motora', instruction: 'Modelar acción motora gruesa de percusión con palmas.' },
  { code: 'MI-2', name: 'Imitación: Manos a la Cabeza', domain: 'Imitación Motora', instruction: 'Llevar ambas manos sobre la cabeza diciendo "¡Mira!".' },
  { code: 'MI-3', name: 'Imitación: Rodar Cochecito', domain: 'Imitación Motora', instruction: 'Rodar autito haciendo sonido representacional.' },
  { code: 'MI-4', name: 'Imitación: Tocar Taza con Cuchara', domain: 'Imitación Motora', instruction: 'Revolver o percutir con cuchara en taza plástica.' },
];

async function startNewSession() {
  const patientId = document.getElementById('patientId').value.trim();
  const patientName = document.getElementById('patientName').value.trim();
  const patientAge = parseInt(document.getElementById('patientAge').value, 10);
  const evaluator = document.getElementById('evaluatorName').value.trim();
  const cameraSource = document.getElementById('cameraSelect').value.trim() || '0';

  if (!patientId || !patientName || isNaN(patientAge)) {
    alert('Por favor, complete los datos del paciente.');
    return;
  }

  state.currentItemIndex = 0;
  state.totalItemsCount = state.selectedProtocol === 'stat' ? 12 : 3;

  const sessionConfig = {
    patient_id: patientId,
    patient_name: patientName,
    patient_age: patientAge,
    evaluator: evaluator,
    camera_source: cameraSource,
    test_type: state.selectedProtocol,
    module: document.getElementById('adosModule')?.value,
    sub_algorithm: document.getElementById('adosSubAlgo')?.value,
  };

  try {
    if (window.pywebview && window.pywebview.api) {
      const response = await window.pywebview.api.start_session(sessionConfig);
      if (!response.success) {
        alert('Error al iniciar sesión: ' + response.error);
        return;
      }
      updateActiveItemDisplay(response.current_item);
    } else {
      updateActiveItemDisplay(STAT_ITEMS_CATALOG[0]);
    }

    state.isSessionActive = true;
    state.isSessionFinished = false;
    state.currentVerdict = null;
    state.lastAiPassed = null;
    updateNavigationLocks();

    startTimer();
    startVideoRendering();
    
    // Iniciar Grabación si la cámara está activa
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.start_recording();
    }
    
    switchTab('tab-live');
    document.getElementById('statusBadge').innerText = 'Sesión Activa';
  } catch (err) {
    console.error('Fallo al iniciar sesión:', err);
  }
}

function updateActiveItemDisplay(item) {
  if (!item) return;
  state.currentItemIndex++;
  const num = state.currentItemIndex;
  const total = state.totalItemsCount;

  document.getElementById('activeItemBadge').innerText = `[${item.code}] ${item.name}`;
  document.getElementById('itemDomain').innerText = item.domain || 'Dominio';
  document.getElementById('itemName').innerText = `${item.code}: ${item.name}`;
  document.getElementById('itemDesc').innerText = item.instruction || 'Realice la actividad según el protocolo.';
  
  const btnNextTitle = document.getElementById('btnNextTitle');
  if (btnNextTitle) {
    btnNextTitle.innerText = num >= total ? 'Finalizar Evaluación' : `Finalizar Actividad (${num}/${total})`;
  }

  document.getElementById('itemNotes').value = '';
  state.currentVerdict = null;
  state.lastAiPassed = null;
  
  const aiVerdictTag = document.getElementById('aiVerdictTag');
  if (aiVerdictTag) aiVerdictTag.innerText = 'Capturando datos...';
  
  const aiReasoningText = document.getElementById('aiReasoningText');
  if (aiReasoningText) aiReasoningText.innerText = 'Esperando al menos 30 frames...';
  
  const aiConfidenceText = document.getElementById('aiConfidenceText');
  if (aiConfidenceText) aiConfidenceText.innerText = '';
}


function markVerdict(passed) {
  state.currentVerdict = passed;
  document.getElementById('btnPass').style.opacity = passed ? '1' : '0.4';
  document.getElementById('btnFail').style.opacity = !passed ? '1' : '0.4';
}

// ================= CONTROLES DE GRABACIÓN =================
async function pauseRecording() {
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.pause_recording();
  }
  document.getElementById('recStatusLabel').innerText = '◌ En Pausa';
  document.getElementById('btnPauseRec').style.display = 'none';
  document.getElementById('btnResumeRec').style.display = 'inline-flex';
}

async function resumeRecording() {
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.resume_recording();
  }
  document.getElementById('recStatusLabel').innerText = '⏺ Grabando';
  document.getElementById('btnResumeRec').style.display = 'none';
  document.getElementById('btnPauseRec').style.display = 'inline-flex';
}

async function cutRecording() {
  if (confirm('¿Cortar el segmento de grabación actual y comenzar uno nuevo?')) {
    if (window.pywebview && window.pywebview.api) {
      const r = await window.pywebview.api.cut_recording();
      document.getElementById('recStatusLabel').innerText = '⏺ Grabando (nuevo segmento)';
    }
  }
}

// ================= MODAL DE REVISIÓN DEL ÍTEM =================
let _reviewPendingVerdict = null;

async function requestItemReview() {
  // Solicitar veredicto final de la IA al backend
  let aiVerdict = null;
  if (window.pywebview && window.pywebview.api) {
    aiVerdict = await window.pywebview.api.get_final_ai_verdict();
  }

  // Poblar el modal con los datos
  const itemName = document.getElementById('itemName').innerText;
  document.getElementById('reviewModalTitle').innerText = `Revisión: ${itemName}`;

  const tag = document.getElementById('reviewVerdictTag');
  const reasonEl = document.getElementById('reviewReasoning');
  const confEl = document.getElementById('reviewConfidence');
  const metricsEl = document.getElementById('reviewMetrics');

  if (aiVerdict && aiVerdict.suggested_verdict !== null && aiVerdict.suggested_verdict !== undefined) {
    const isPass = aiVerdict.suggested_verdict;
    tag.innerText = isPass ? 'Sugerencia IA: PASS' : 'Sugerencia IA: FAIL';
    tag.className = 'pill-badge ' + (isPass ? 'text-cyan' : 'text-magenta');
    tag.style.opacity = '1';
    state.lastAiPassed = isPass;

    const conf = Math.round((aiVerdict.confidence || 0) * 100);
    confEl.innerText = `Certeza: ${conf}% | ${aiVerdict.frame_count || 0} frames analizados`;
    reasonEl.innerText = aiVerdict.reasoning || '';

    // Tabla de métricas en lenguaje natural
    let metricsHtml = '';
    for (const [label, value] of Object.entries(aiVerdict.metrics_summary || {})) {
      metricsHtml += `<div><strong>${label}:</strong></div><div>${value}</div>`;
    }
    metricsEl.innerHTML = metricsHtml;
  } else {
    tag.innerText = 'Sin datos suficientes';
    tag.className = 'pill-badge';
    confEl.innerText = '';
    reasonEl.innerText = 'No se acumularon suficientes frames. Decida manualmente.';
    metricsEl.innerHTML = '';
  }

  // Resetear estado de selección del modal
  _reviewPendingVerdict = null;
  document.getElementById('reviewBtnConfirm').disabled = true;
  document.getElementById('reviewNotes').value = document.getElementById('itemNotes').value;
  document.getElementById('reviewBtnPass').style.opacity = '1';
  document.getElementById('reviewBtnFail').style.opacity = '1';

  document.getElementById('modalItemReview').style.display = 'flex';
}

function confirmReview(passed) {
  _reviewPendingVerdict = passed;
  document.getElementById('reviewBtnPass').style.opacity = passed ? '1' : '0.4';
  document.getElementById('reviewBtnFail').style.opacity = !passed ? '1' : '0.4';
  document.getElementById('reviewBtnConfirm').disabled = false;
}

function cancelReview() {
  document.getElementById('modalItemReview').style.display = 'none';
  // If the user cancelled the review, they return to the recording view
  // Nothing changes on the backend, recording is still active
}


async function submitReview() {
  if (_reviewPendingVerdict === null) return;

  const notes = document.getElementById('reviewNotes').value.trim();
  document.getElementById('modalItemReview').style.display = 'none';

  try {
    let result;
    if (window.pywebview && window.pywebview.api) {
      result = await window.pywebview.api.advance_item({
        passed: _reviewPendingVerdict,
        ai_passed: state.lastAiPassed,
        notes: notes,
      });
    } else {
      if (state.currentItemIndex < state.totalItemsCount) {
        result = { completed: false, next_item: STAT_ITEMS_CATALOG[state.currentItemIndex] };
      } else {
        result = { completed: true, evaluation: getMockResults() };
      }
    }

    if (result.completed) {
      finishSession(result.evaluation);
    } else {
      updateActiveItemDisplay(result.next_item);
    }
  } catch (err) {
    console.error('Error al guardar revisión:', err);
  }
}

function cancelSession() {
  if (confirm('¿Desea interrumpir y cancelar la sesión actual?')) {
    stopTimer();
    stopVideoRendering();
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.stop_recording();
    }
    state.isSessionActive = false;
    state.isSessionFinished = false;
    updateNavigationLocks();
    switchTab('tab-patient');
    document.getElementById('statusBadge').innerText = 'Sesión Cancelada';
  }
}

function finishSession(evaluationResult) {
  stopTimer();
  stopVideoRendering();
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.stop_recording();
  }
  state.isSessionActive = false;
  state.isSessionFinished = true;
  state.lastEvaluationResult = evaluationResult;

  updateNavigationLocks();
  renderResults(evaluationResult);
  switchTab('tab-results');
  document.getElementById('statusBadge').innerText = 'Sesión Finalizada';

  // Mostrar reproductor pre-informe si hay grabación disponible
  const recPath = evaluationResult && evaluationResult.recording_path;
  if (recPath) {
    setTimeout(() => showReplayModal(recPath), 600);
  }
}

function showReplayModal(videoPath) {
  const src = document.getElementById('replaySource');
  const video = document.getElementById('sessionReplayVideo');
  // En PyWebView, podemos cargar archivos locales directamente
  src.src = videoPath.startsWith('file://') ? videoPath : `file:///${videoPath.replace(/\\/g, '/')}`;
  video.load();
  document.getElementById('modalReplay').style.display = 'flex';
}

async function generateReport(format) {
  const anonymize = document.getElementById('chkAnonymize') ? document.getElementById('chkAnonymize').checked : false;
  if (window.pywebview && window.pywebview.api) {
    const result = await window.pywebview.api.export_report({
      format: format,
      anonymize: anonymize,
      is_final: true,
    });
    document.getElementById('modalReplay').style.display = 'none';
    alert(result.message || 'Reporte generado con éxito.');
  } else {
    alert(`Exportando reporte en formato ${format.toUpperCase()}`);
  }
}

// ================= RENDERIZADO DE RESULTADOS =================
function renderResults(res) {
  if (!res) return;

  const isStat = res.test_type === 'stat' || res.overall_risk !== undefined;
  
  if (isStat) {
    const risk = res.overall_risk || 'N/A';
    document.getElementById('riskBadge').innerText = risk.toUpperCase();
    document.getElementById('riskTitle').innerText = `Resultado: ${risk}`;
    document.getElementById('riskExplanation').innerText = res.explanation || '';
    document.getElementById('cssScoreBox').style.display = 'none';

    let domainHtml = '';
    for (const [key, dom] of Object.entries(res.domain_results || {})) {
      domainHtml += `
        <div class="obs-item">
          <span>${dom.domain_name}:</span>
          <span class="obs-val font-bold ${dom.domain_failed ? 'text-magenta' : 'text-cyan'}">
            ${dom.domain_failed ? 'FALLADO' : 'APROBADO'} (${dom.items_failed}/${dom.items_total})
          </span>
        </div>
      `;
    }
    document.getElementById('domainsBreakdown').innerHTML = domainHtml;
  } else {
    // ADOS-2
    const classification = res.classification || 'No clasificado';
    document.getElementById('riskBadge').innerText = classification.toUpperCase();
    document.getElementById('riskTitle').innerText = `Clasificación ADOS-2: ${classification}`;
    document.getElementById('riskExplanation').innerText = `Total SA: ${res.totals?.sa || 0} | Total RRB: ${res.totals?.rrb || 0} | Total Bruto: ${res.totals?.overall || 0}`;

    if (res.css_score && res.css_score > 0) {
      document.getElementById('cssScoreBox').style.display = 'block';
      document.getElementById('cssNumber').innerText = res.css_score;
    } else {
      document.getElementById('cssScoreBox').style.display = 'none';
    }

    document.getElementById('domainsBreakdown').innerHTML = `
      <div class="obs-item"><span>Afecto Social (SA):</span><span class="obs-val">${res.totals?.sa || 0} pts</span></div>
      <div class="obs-item"><span>Comportamiento Restringido (RRB):</span><span class="obs-val">${res.totals?.rrb || 0} pts</span></div>
      <div class="obs-item"><span>Puntuación Total Algorítmica:</span><span class="obs-val font-bold">${res.totals?.overall || 0} pts</span></div>
    `;
  }

  const tbody = document.getElementById('itemsTableBody');
  tbody.innerHTML = '';
  for (const [code, item] of Object.entries(res.item_scores || {})) {
    let therapistVerdict = item.therapist_passed !== undefined ? (item.therapist_passed ? '<span class="text-cyan">PASS</span>' : '<span class="text-magenta">FAIL</span>') : `Código: ${item.raw_code}`;
    let aiVerdict = 'N/A';
    let notes = item.notes || '';
    
    // Extraer sugerencia IA de las notas
    const aiMatch = notes.match(/\[IA Sugirió: (PASS|FAIL)\](.*)/);
    if (aiMatch) {
      aiVerdict = aiMatch[1] === 'PASS' ? '<span class="text-cyan">PASS</span>' : '<span class="text-magenta">FAIL</span>';
      notes = aiMatch[2].trim();
    }
    
    tbody.innerHTML += `
      <tr>
        <td><strong>${code}</strong></td>
        <td>${code}</td>
        <td>${item.domain || 'Dominio'}</td>
        <td><strong>${therapistVerdict}</strong></td>
        <td>${aiVerdict}</td>
        <td style="font-size:12px; max-width:250px; color:var(--color-text-dim);">${notes}</td>
      </tr>
    `;
  }
}

// ================= EXPORTACIÓN =================
async function exportReport(format) {
  const anonymize = document.getElementById('chkAnonymize').checked;
  if (window.pywebview && window.pywebview.api) {
    const result = await window.pywebview.api.export_report({
      format: format,
      anonymize: anonymize,
      is_final: true,
    });
    alert(result.message || 'Reporte generado con éxito.');
  } else {
    alert(`Exportando reporte en formato ${format.toUpperCase()} (Anonimizado: ${anonymize})`);
  }
}

// ================= VIDEO STREAMING Y ESTADO =================
function startVideoRendering() {
  const canvas = document.getElementById('videoCanvas');
  const ctx = canvas.getContext('2d');
  const overlayMsg = document.getElementById('videoOverlay');
  const statusDot = document.getElementById('statusDot');
  const liveStateText = document.getElementById('liveStateText');
  const camPill = document.getElementById('cameraStatus');

  state.videoStreamInterval = setInterval(async () => {
    if (window.pywebview && window.pywebview.api) {
      const frameData = await window.pywebview.api.get_camera_frame();
      if (frameData && frameData.connected && frameData.image_b64) {
        state.isCameraOnline = true;
        statusDot.className = 'status-indicator online';
        liveStateText.innerText = 'Cámara Conectada (Transmitiendo)';
        camPill.innerText = 'Cámara: Conectada';
        camPill.className = 'pill-badge pill-cam connected';
        overlayMsg.style.display = 'none';

        const img = new Image();
        img.onload = () => ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        img.src = 'data:image/jpeg;base64,' + frameData.image_b64;

        if (frameData.metrics) {
          updateLiveMetrics(frameData.metrics);
        }
        if (frameData.ai_suggestion) {
          updateAISuggestion(frameData.ai_suggestion);
        }
      } else {
        state.isCameraOnline = false;
        statusDot.className = 'status-indicator offline';
        liveStateText.innerText = 'Sin señal de cámara / Desconectada';
        camPill.innerText = 'Cámara: Desconectada';
        camPill.className = 'pill-badge pill-cam';
        
        ctx.fillStyle = '#090d16';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        overlayMsg.style.display = 'block';
        document.getElementById('overlayMainText').innerText = frameData?.message || 'Sin señal de video';
      }
    } else {
      statusDot.className = 'status-indicator online';
      liveStateText.innerText = 'Modo Simulación Activo';
      overlayMsg.style.display = 'none';
      drawSimulatedFrame(ctx, canvas);
    }
  }, 66);
}

function stopVideoRendering() {
  if (state.videoStreamInterval) {
    clearInterval(state.videoStreamInterval);
    state.videoStreamInterval = null;
  }
}

function drawSimulatedFrame(ctx, canvas) {
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#33C4DA';
  ctx.lineWidth = 2;
  ctx.strokeRect(canvas.width / 4, canvas.height / 4, canvas.width / 2, canvas.height / 2);
  ctx.fillStyle = '#33C4DA';
  ctx.font = '14px Inter, sans-serif';
  ctx.fillText('Simulación de Video Stream', canvas.width / 4 + 20, canvas.height / 2);
}

function updateLiveMetrics(metrics) {
  if (metrics.gaze_alignment_score !== undefined) {
    const val = Math.round(metrics.gaze_alignment_score * 100);
    document.getElementById('mGaze').innerText = `${val}%`;
    document.getElementById('mGazeBar').style.width = `${val}%`;
  }
  if (metrics.pointing_detected !== undefined) {
    const p = Math.round(metrics.pointing_detected * 100);
    document.getElementById('mPointing').innerText = p > 50 ? 'Detectado' : 'No';
  }
  if (metrics.flapping_detected !== undefined) {
    const a = Math.round(metrics.flapping_detected * 100);
    document.getElementById('mAtypical').innerText = a > 50 ? 'Estereotipia (Aleteo)' : 'Ninguno';
  }
}

function updateAISuggestion(suggestion) {
  if (suggestion.suggested_verdict === null) return;
  
  state.lastAiPassed = suggestion.suggested_verdict;
  const tag = document.getElementById('aiVerdictTag');
  tag.innerText = suggestion.suggested_verdict ? 'Sugerencia: PASS' : 'Sugerencia: FAIL';
  tag.className = 'pill-badge ' + (suggestion.suggested_verdict ? 'text-cyan' : 'text-magenta');
  
  const conf = Math.round(suggestion.confidence * 100);
  document.getElementById('aiConfidenceText').innerText = `Certeza IA: ${conf}%`;
  document.getElementById('aiReasoningText').innerText = suggestion.reasoning || '';
  
  // Pre-seleccion visual brillante removida (botones eliminados de la UI principal)
}

// ================= TIMER =================
function startTimer() {
  state.timerSeconds = 0;
  clearInterval(state.timerInterval);
  state.timerInterval = setInterval(() => {
    state.timerSeconds++;
    const mins = String(Math.floor(state.timerSeconds / 60)).padStart(2, '0');
    const secs = String(state.timerSeconds % 60).padStart(2, '0');
    document.getElementById('sessionTimer').innerText = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  clearInterval(state.timerInterval);
}

// ================= HOTKEYS =================
window.addEventListener('keydown', (e) => {
  // Solo procesar si hay sesión activa y el modal NO está visible
  if (!state.isSessionActive) return;
  const modal = document.getElementById('modalItemReview');
  if (modal.style.display === 'flex') {
    // Si el modal está visible, no procesar estas teclas (salvo quizás enter para confirmar)
    return;
  }

  if (e.key === 'F9' || e.key === 'Enter') {
    e.preventDefault();
    requestItemReview();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    cancelSession();
  }
});

function getMockResults() {
  return {
    test_type: 'stat',
    overall_risk: 'Riesgo Bajo de TEA',
    explanation: 'El paciente superó los puntos de corte en los 4 dominios del STAT.',
    domain_results: {
      play: { domain_name: 'Juego', items_total: 2, items_failed: 0, domain_failed: false },
      requesting: { domain_name: 'Petición', items_total: 2, items_failed: 0, domain_failed: false },
      joint_attention: { domain_name: 'Atención Conjunta', items_total: 4, items_failed: 0, domain_failed: false },
      motor_imitation: { domain_name: 'Imitación Motora', items_total: 4, items_failed: 0, domain_failed: false },
    },
    item_scores: {
      'P-1': { domain: 'Juego', therapist_passed: true, score: 0 },
      'P-2': { domain: 'Juego', therapist_passed: true, score: 0 },
    }
  };
}

// Inicializar al cargar
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  updateSubAlgorithms();
  loadSettingsIntoForm();
  updateNavigationLocks();
  setTimeout(refreshAvailableCameras, 400);
});
