/* ── State ───────────────────────────────────────────────────────────────── */
let currentPage = 1;
let currentQuery = '';
let searchTimer = null;
let authPollInterval = null;
let _maxOpdNumber = 0;   // tracks highest OPD# seen so far
let _sortBy  = 'opd_number';
let _sortDir = 'desc';
const newVisitModal = () => bootstrap.Modal.getOrCreateInstance(document.getElementById('newVisitModal'));
const patientModal  = () => bootstrap.Modal.getOrCreateInstance(document.getElementById('patientModal'));

/* ── Utilities ───────────────────────────────────────────────────────────── */
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

function showToast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.className = `toast align-items-center text-bg-${type} border-0`;
  document.getElementById('toastMsg').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3000 }).show();
}

function showView(name) {
  ['list', 'detail', 'settings'].forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle('d-none', v !== name);
  });
  if (name === 'list') loadList();
  if (name === 'settings') { loadClientId(); loadAuthStatus(); }
}

/* ── List view ───────────────────────────────────────────────────────────── */
function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentPage = 1;
    currentQuery = document.getElementById('searchInput').value.trim();
    loadList();
  }, 300);
}

function clearSearch() {
  document.getElementById('searchInput').value = '';
  currentQuery = '';
  currentPage = 1;
  _sortBy = 'opd_number';
  _sortDir = 'desc';
  loadList();
}

function sortBy(col) {
  if (_sortBy === col) {
    _sortDir = _sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    _sortBy  = col;
    _sortDir = col === 'opd_number' ? 'desc' : 'asc';
  }
  currentPage = 1;
  loadList();
}

async function loadList() {
  const params = new URLSearchParams({
    page: currentPage, limit: 50,
    sort_by: _sortBy, sort_dir: _sortDir,
  });
  if (currentQuery) params.set('q', currentQuery);

  const el = document.getElementById('listContent');
  el.innerHTML = '<div class="text-center py-5 text-muted"><div class="spinner-border"></div></div>';

  try {
    const data = await api('GET', `/api/visits?${params}`);
    renderList(data);
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

function renderList(data) {
  const { total, page, limit, items } = data;
  const el = document.getElementById('listContent');

  if (!items.length) {
    el.innerHTML = '<div class="text-center py-5 text-muted">No records found.</div>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  // Track the highest OPD# (list is sorted descending, page 1 item 0 = max)
  if (page === 1 && !currentQuery && items.length) {
    _maxOpdNumber = Math.max(_maxOpdNumber, items[0].opd_number);
  }

  const rows = items.map(v => `
    <tr class="align-middle" style="cursor:pointer" onclick="openDetail(${v.opd_number})">
      <td class="fw-bold text-primary">${v.opd_number}</td>
      <td>${esc(v.owners) || '<span class="text-muted">—</span>'}</td>
      <td>${esc(v.pets)}</td>
      <td class="hide-sm">${esc(v.pet_types) || ''}</td>
      <td class="hide-sm">${esc(v.phones) || '<span class="text-muted">—</span>'}</td>
      <td class="text-center">
        ${v.has_file
          ? `<span class="badge bg-success badge-file"><i class="bi bi-file-pdf"></i> PDF</span>`
          : `<span class="badge bg-secondary badge-file">No file</span>`}
      </td>
      <td>
        <button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation();deleteVisit(${v.opd_number})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`).join('');

  const si = (col) => {
    if (_sortBy !== col) return '<i class="bi bi-arrow-down-up text-muted ms-1 small"></i>';
    return _sortDir === 'asc'
      ? '<i class="bi bi-arrow-up ms-1 small text-primary"></i>'
      : '<i class="bi bi-arrow-down ms-1 small text-primary"></i>';
  };
  const th = (col, label, cls = '') =>
    `<th class="sortable-header ${cls}" onclick="sortBy('${col}')" style="cursor:pointer;user-select:none">${label}${si(col)}</th>`;

  el.innerHTML = `
    <div class="table-responsive">
      <table class="table table-hover table-visits">
        <thead class="table-light">
          <tr>
            ${th('opd_number','OPD#')}
            ${th('owners','Owner')}
            ${th('pets','Pet')}
            ${th('pet_types','Type','hide-sm')}
            ${th('phones','Phone','hide-sm')}
            ${th('has_file','File','text-center')}
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <small class="text-muted">${total} records total</small>`;

  renderPagination(total, page, limit);
}

function renderPagination(total, page, limit) {
  const pages = Math.ceil(total / limit);
  const ul = document.getElementById('pagination');
  if (pages <= 1) { ul.innerHTML = ''; return; }

  let html = '';
  html += `<li class="page-item ${page === 1 ? 'disabled' : ''}">
    <a class="page-link" href="#" onclick="goPage(${page-1})">«</a></li>`;

  const start = Math.max(1, page - 2);
  const end   = Math.min(pages, page + 2);
  for (let i = start; i <= end; i++) {
    html += `<li class="page-item ${i === page ? 'active' : ''}">
      <a class="page-link" href="#" onclick="goPage(${i})">${i}</a></li>`;
  }

  html += `<li class="page-item ${page === pages ? 'disabled' : ''}">
    <a class="page-link" href="#" onclick="goPage(${page+1})">»</a></li>`;
  ul.innerHTML = html;
}

function goPage(p) {
  currentPage = p;
  loadList();
  return false;
}

/* ── Detail view ─────────────────────────────────────────────────────────── */
async function openDetail(opdNumber) {
  showView('detail');
  const el = document.getElementById('detailContent');
  el.innerHTML = '<div class="text-center py-5"><div class="spinner-border"></div></div>';

  try {
    const visit = await api('GET', `/api/visits/${opdNumber}`);
    renderDetail(visit);
    checkOpdFile(opdNumber);
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

async function checkOpdFile(opdNumber) {
  try {
    const info = await api('GET', `/api/onedrive/file/${opdNumber}`);
    const btn = document.getElementById('fileBtn');
    if (!btn) return;
    if (info.found) {
      btn.outerHTML = `<a href="${esc(info.web_url)}" target="_blank" class="btn btn-success">
        <i class="bi bi-file-pdf me-1"></i> Open PDF
      </a>`;
    } else {
      btn.innerHTML = '<i class="bi bi-file-earmark me-1"></i> No PDF yet';
      btn.disabled = true;
    }
  } catch (_) {}
}

const _patientCache = {};

function renderDetail(visit) {
  const el = document.getElementById('detailContent');

  visit.patients.forEach(p => { _patientCache[p.id] = p; });

  const patientRows = visit.patients.map(p => `
    <tr class="patient-row">
      <td class="fw-semibold">${esc(p.pet_name)}</td>
      <td>${esc(p.pet_type) || '<span class="text-muted">—</span>'}</td>
      <td>
        <button class="btn btn-sm btn-outline-secondary me-1"
          onclick="openEditPatient(${visit.opd_number}, ${p.id})">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger"
          onclick="deletePatient(${visit.opd_number}, ${p.id})">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`).join('');

  const phoneRows = visit.phones.length
    ? visit.phones.map(ph => `
        <div class="d-flex align-items-center gap-2 ms-4">
          <span class="fw-semibold">${esc(ph.phone)}</span>
          <button class="btn btn-sm btn-link text-danger p-0" onclick="deletePhone(${visit.opd_number}, ${ph.id})">
            <i class="bi bi-x-circle"></i>
          </button>
        </div>`).join('')
    : '<span class="text-muted ms-4 small">No phone numbers yet</span>';

  const ownerRows = visit.owners.length
    ? visit.owners.map(o => `
        <div class="d-flex align-items-center gap-2 ms-4">
          <span class="fw-semibold">${esc(o.owner_name)}</span>
          <button class="btn btn-sm btn-link text-danger p-0" onclick="deleteOwner(${visit.opd_number}, ${o.id})">
            <i class="bi bi-x-circle"></i>
          </button>
        </div>`).join('')
    : '<span class="text-muted ms-4 small">No owners yet</span>';

  el.innerHTML = `
    <div class="card mb-3">
      <div class="card-body detail-header">
        <div class="d-flex align-items-center gap-3 flex-wrap">
          <h4 class="mb-0">OPD# <span class="text-primary">${visit.opd_number}</span></h4>
          <button id="fileBtn" class="btn btn-outline-secondary btn-sm ms-auto">
            <i class="bi bi-cloud-download me-1"></i> Checking file…
          </button>
        </div>

        <div class="mt-2">
          <div class="d-flex align-items-center gap-2 mb-1">
            <i class="bi bi-person text-muted"></i>
            <span class="text-muted small fw-semibold">Owners</span>
            <button class="btn btn-sm btn-outline-primary py-0 ms-1" onclick="openAddOwner(${visit.opd_number})">
              <i class="bi bi-plus-lg"></i>
            </button>
          </div>
          ${ownerRows}
        </div>

        <div class="mt-2">
          <div class="d-flex align-items-center gap-2 mb-1">
            <i class="bi bi-telephone text-muted"></i>
            <span class="text-muted small fw-semibold">Phone Numbers</span>
            <button class="btn btn-sm btn-outline-primary py-0 ms-1" onclick="openAddPhone(${visit.opd_number})">
              <i class="bi bi-plus-lg"></i>
            </button>
          </div>
          ${phoneRows}
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header d-flex align-items-center justify-content-between">
        <span class="fw-semibold">Patients (${visit.patients.length})</span>
        <button class="btn btn-primary btn-sm" onclick="openAddPatient(${visit.opd_number})">
          <i class="bi bi-plus-lg"></i> Add Patient
        </button>
      </div>
      <div class="table-responsive">
        <table class="table table-sm mb-0">
          <thead class="table-light">
            <tr><th>Pet</th><th>Type</th><th></th></tr>
          </thead>
          <tbody>${patientRows || '<tr><td colspan="3" class="text-center text-muted py-3">No patients yet</td></tr>'}</tbody>
        </table>
      </div>
    </div>`;
}

/* ── New Visit modal ─────────────────────────────────────────────────────── */
function openNewVisitModal() {
  ['newOwnerName', 'newPetName', 'newPhone']
    .forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  // Pre-fill next OPD number
  document.getElementById('newOpdNumber').value = _maxOpdNumber ? _maxOpdNumber + 1 : '';
  setPetType('new', '');
  document.getElementById('duplicateWarning').className = 'd-none';
  newVisitModal().show();
}

let dupCheckTimer = null;
function checkDuplicatePhone() {
  clearTimeout(dupCheckTimer);
  dupCheckTimer = setTimeout(async () => {
    const phone = document.getElementById('newPhone').value.trim();
    const box = document.getElementById('duplicateWarning');
    if (!phone) { box.className = 'd-none'; return; }
    try {
      const results = await api('GET', `/api/visits/search-phone?phone=${encodeURIComponent(phone)}`);
      if (results.length) {
        const links = results.map(r =>
          `<a href="#" onclick="newVisitModal().hide();openDetail(${r.opd_number});return false">OPD# ${r.opd_number}</a>`
        ).join(', ');
        box.className = 'alert alert-warning mb-3';
        box.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>
          This phone number already exists: ${links}`;
      } else {
        box.className = 'd-none';
      }
    } catch (_) {}
  }, 400);
}

async function submitNewVisit() {
  const opd   = parseInt(document.getElementById('newOpdNumber').value);
  const pet   = document.getElementById('newPetName').value.trim();
  const phone = document.getElementById('newPhone').value.trim();
  const owner = document.getElementById('newOwnerName').value.trim() || null;

  if (!opd || !pet || !phone) {
    showToast('OPD#, Pet Name, and Phone are required', 'danger'); return;
  }

  try {
    await api('POST', '/api/visits', {
      opd_number: opd,
      first_phone: phone,
      first_owner: owner,
      first_patient: {
        pet_name: pet,
        pet_type: getPetType('new'),
      },
    });
    newVisitModal().hide();
    showToast(`OPD# ${opd} created`);
    openDetail(opd);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

/* ── Owner CRUD ───────────────────────────────────────────────────────────── */
function openAddOwner(opdNumber) {
  document.getElementById('addOwnerOpdNumber').value = opdNumber;
  document.getElementById('addOwnerInput').value = '';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('addOwnerModal')).show();
}

async function submitAddOwner() {
  const opdNumber  = parseInt(document.getElementById('addOwnerOpdNumber').value);
  const owner_name = document.getElementById('addOwnerInput').value.trim();
  if (!owner_name) { showToast('Owner name is required', 'danger'); return; }
  try {
    await api('POST', `/api/visits/${opdNumber}/owners`, { owner_name });
    bootstrap.Modal.getOrCreateInstance(document.getElementById('addOwnerModal')).hide();
    showToast('Owner added');
    openDetail(opdNumber);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

async function deleteOwner(opdNumber, ownerId) {
  if (!confirm('Remove this owner?')) return;
  try {
    await api('DELETE', `/api/visits/${opdNumber}/owners/${ownerId}`);
    showToast('Owner removed');
    openDetail(opdNumber);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

/* ── Phone CRUD ───────────────────────────────────────────────────────────── */
function openAddPhone(opdNumber) {
  document.getElementById('addPhoneOpdNumber').value = opdNumber;
  document.getElementById('addPhoneInput').value = '';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('addPhoneModal')).show();
}

async function submitAddPhone() {
  const opdNumber = parseInt(document.getElementById('addPhoneOpdNumber').value);
  const phone = document.getElementById('addPhoneInput').value.trim();
  if (!phone) { showToast('Phone number is required', 'danger'); return; }
  try {
    await api('POST', `/api/visits/${opdNumber}/phones`, { phone });
    bootstrap.Modal.getOrCreateInstance(document.getElementById('addPhoneModal')).hide();
    showToast('Phone added');
    openDetail(opdNumber);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

async function deletePhone(opdNumber, phoneId) {
  if (!confirm('Remove this phone number?')) return;
  try {
    await api('DELETE', `/api/visits/${opdNumber}/phones/${phoneId}`);
    showToast('Phone removed');
    openDetail(opdNumber);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

async function deleteVisit(opdNumber) {
  if (!confirm(`Delete OPD# ${opdNumber} and all its patients?`)) return;
  try {
    await api('DELETE', `/api/visits/${opdNumber}`);
    showToast(`OPD# ${opdNumber} deleted`);
    loadList();
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

/* ── Patient modal ───────────────────────────────────────────────────────── */
function openAddPatient(opdNumber) {
  document.getElementById('patientModalTitle').textContent = 'Add Patient';
  document.getElementById('editPatientId').value = '';
  document.getElementById('editOpdNumber').value = opdNumber;
  document.getElementById('editPetName').value = '';
  setPetType('edit', '');
  patientModal().show();
}

function openEditPatient(opdNumber, patientId) {
  const p = _patientCache[patientId];
  if (!p) return;
  document.getElementById('patientModalTitle').textContent = 'Edit Patient';
  document.getElementById('editPatientId').value = patientId;
  document.getElementById('editOpdNumber').value = opdNumber;
  document.getElementById('editPetName').value = p.pet_name || '';
  setPetType('edit', p.pet_type || '');
  patientModal().show();
}

async function submitPatient() {
  const opd = parseInt(document.getElementById('editOpdNumber').value);
  const pid = document.getElementById('editPatientId').value;
  const pet = document.getElementById('editPetName').value.trim();

  if (!pet) { showToast('Pet Name is required', 'danger'); return; }

  const body = {
    pet_name: pet,
    pet_type: getPetType('edit'),
  };

  try {
    if (pid) {
      await api('PUT', `/api/visits/${opd}/patients/${pid}`, body);
      showToast('Patient updated');
    } else {
      await api('POST', `/api/visits/${opd}/patients`, body);
      showToast('Patient added');
    }
    patientModal().hide();
    openDetail(opd);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

async function deletePatient(opdNumber, patientId) {
  if (!confirm('Delete this patient row?')) return;
  try {
    await api('DELETE', `/api/visits/${opdNumber}/patients/${patientId}`);
    showToast('Patient deleted');
    openDetail(opdNumber);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

/* ── Settings ─────────────────────────────────────────────────────────────── */
async function loadAuthStatus() {
  const statusEl  = document.getElementById('authStatus');
  const actionsEl = document.getElementById('authActions');
  const folderSec = document.getElementById('folderSection');

  try {
    const me = await api('GET', '/api/auth/me');
    if (me.authenticated) {
      statusEl.innerHTML = `<i class="bi bi-check-circle-fill text-success me-1"></i> Signed in as <strong>${esc(me.account)}</strong>`;
      actionsEl.innerHTML = `<button class="btn btn-outline-danger btn-sm" onclick="doLogout()">
        <i class="bi bi-box-arrow-right"></i> Sign out</button>`;
      folderSec.classList.remove('d-none');
      loadCurrentFolder();
    } else {
      statusEl.innerHTML = '<i class="bi bi-cloud-slash text-muted me-1"></i> Not signed in';
      actionsEl.innerHTML = `<button class="btn btn-primary btn-sm" onclick="startAuth()">
        <i class="bi bi-microsoft me-1"></i> Sign in with Microsoft</button>`;
      folderSec.classList.add('d-none');
    }
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
  }
}

async function startAuth() {
  const box = document.getElementById('deviceCodeBox');
  try {
    const flow = await api('POST', '/api/auth/start');
    document.getElementById('deviceCode').textContent = flow.user_code;
    const link = document.getElementById('deviceUri');
    link.href = flow.verification_uri;
    link.textContent = flow.verification_uri;
    box.classList.remove('d-none');
    document.getElementById('authActions').innerHTML = '';

    authPollInterval = setInterval(async () => {
      const status = await api('GET', '/api/auth/status');
      if (status.authenticated) {
        clearInterval(authPollInterval);
        box.classList.add('d-none');
        showToast('Signed in to OneDrive');
        loadAuthStatus();
      }
    }, 4000);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

async function doLogout() {
  await api('DELETE', '/api/auth/logout');
  showToast('Signed out');
  loadAuthStatus();
}

async function loadCurrentFolder() {
  try {
    const cfg = await api('GET', '/api/onedrive/folder');
    const el = document.getElementById('currentFolder');
    el.textContent = cfg.folder_id
      ? `Configured folder ID: ${cfg.folder_id}`
      : 'No folder selected yet.';
  } catch (_) {}
}

async function loadFolders() {
  const el = document.getElementById('folderList');
  el.innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
  try {
    const folders = await api('GET', '/api/onedrive/folders');
    if (!folders.length) {
      el.innerHTML = '<small class="text-muted">No folders found in OneDrive root.</small>';
      return;
    }
    el.innerHTML = folders.map(f => `
      <button class="btn btn-outline-secondary btn-sm me-1 mb-1"
        onclick="selectFolder('${esc(f.item_id)}', '${esc(f.name)}')">
        <i class="bi bi-folder me-1"></i>${esc(f.name)}
      </button>`).join('');
  } catch (e) {
    el.innerHTML = `<span class="text-danger small">${e.message}</span>`;
  }
}

async function selectFolder(itemId, name) {
  await api('POST', `/api/onedrive/folder?item_id=${encodeURIComponent(itemId)}`);
  showToast(`Folder "${name}" saved`);
  loadCurrentFolder();
  document.getElementById('folderList').innerHTML = '';
}

/* ── Import ───────────────────────────────────────────────────────────────── */
async function runImport() {
  const fileInput = document.getElementById('importFile');
  const el = document.getElementById('importResult');

  if (!fileInput.files.length) {
    el.innerHTML = '<div class="alert alert-warning">Please select an Excel file first.</div>';
    return;
  }

  el.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div> Importing… (may take a minute)';

  const form = new FormData();
  form.append('file', fileInput.files[0]);

  try {
    const res = await fetch('/api/admin/import', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    const r = await res.json();
    el.innerHTML = `
      <div class="alert alert-success mb-0">
        <strong>Import complete</strong><br>
        Visits: ${r.visits_created} &nbsp; Patients: ${r.patients_created} &nbsp; Skipped: ${r.skipped_rows}
        ${r.errors.length ? `<br><small class="text-danger">${r.errors.join('<br>')}</small>` : ''}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

/* ── Azure Client ID ──────────────────────────────────────────────────────── */
async function loadClientId() {
  try {
    const r = await api('GET', '/api/auth/client-id');
    document.getElementById('clientIdInput').value = r.client_id || '';
  } catch (_) {}
}

async function saveClientId() {
  const cid = document.getElementById('clientIdInput').value.trim();
  if (!cid) { showToast('Enter a Client ID first', 'warning'); return; }
  try {
    await api('POST', '/api/auth/client-id', { client_id: cid });
    showToast('Client ID saved');
    loadAuthStatus();
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

/* ── Pet type dropdown helpers ───────────────────────────────────────────── */
const KNOWN_TYPES = ['Cat','Dog','Rabbit','Bird','Hamster'];

function toggleOther(prefix) {
  const sel = document.getElementById(`${prefix}PetTypeSelect`);
  const inp = document.getElementById(`${prefix}PetTypeOther`);
  if (sel.value === '__other__') {
    inp.classList.remove('d-none');
    inp.focus();
  } else {
    inp.classList.add('d-none');
    inp.value = '';
  }
}

function getPetType(prefix) {
  const sel = document.getElementById(`${prefix}PetTypeSelect`);
  if (sel.value === '__other__') {
    return document.getElementById(`${prefix}PetTypeOther`).value.trim() || null;
  }
  return sel.value || null;
}

function setPetType(prefix, value) {
  const sel = document.getElementById(`${prefix}PetTypeSelect`);
  const inp = document.getElementById(`${prefix}PetTypeOther`);
  if (!value) {
    sel.value = '';
    inp.classList.add('d-none');
  } else if (KNOWN_TYPES.includes(value)) {
    sel.value = value;
    inp.classList.add('d-none');
  } else {
    sel.value = '__other__';
    inp.classList.remove('d-none');
    inp.value = value;
  }
}

/* ── Escape HTML ─────────────────────────────────────────────────────────── */
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ── Init ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  showView('list');
});
