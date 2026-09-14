/**
 * IJOVA • Panel de Gestión Microsoft 365
 * Lógica interactiva completa:
 * - Reseteo Seguro con Verificación
 * - Bajas con Confirmación Estricta
 * - Papelera de Reciclaje y Restauración
 * - Auditoría y Galería de Fotografías
 * - Bitácora Histórica
 * - Catálogo de Comandos CLI con Copiado Rápido
 */

document.addEventListener('DOMContentLoaded', () => {
  // Estado local
  let currentStudent = null;
  let currentDeleteStudent = null;
  let searchDebounceTimeout = null;
  let activePhotoFilter = 'all';
  let activeLevelFilter = 'all';

  // ==========================================
  // NAVEGACIÓN POR PESTAÑAS
  // ==========================================
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  function switchTab(targetTabId) {
    tabButtons.forEach(b => {
      if (b.getAttribute('data-tab') === targetTabId) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    tabContents.forEach(c => {
      if (c.id === targetTabId) {
        c.style.display = 'block';
        c.classList.add('active');
      } else {
        c.style.display = 'none';
        c.classList.remove('active');
      }
    });

    // Carga de datos bajo demanda según pestaña
    if (targetTabId === 'tab-recycle') {
      loadRecycleBin();
    } else if (targetTabId === 'tab-photos') {
      loadPhotosStats();
      loadPhotosGallery(activePhotoFilter, activeLevelFilter);
    } else if (targetTabId === 'tab-history') {
      loadHistory();
    } else if (targetTabId === 'tab-tenant') {
      loadTenantStatus();
    }
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTabId = btn.getAttribute('data-tab');
      switchTab(targetTabId);
    });
  });

  // Botón para saltar a la papelera desde el resultado de baja
  const btnGotoRecycleBin = document.getElementById('btn-goto-recycle-bin');
  if (btnGotoRecycleBin) {
    btnGotoRecycleBin.addEventListener('click', () => {
      switchTab('tab-recycle');
    });
  }

  // ==========================================
  // TEMA VISUAL (CLARO / OSCURO)
  // ==========================================
  const btnThemeToggle = document.getElementById('btn-theme-toggle');
  const themeIcon = document.getElementById('theme-icon');

  const savedTheme = localStorage.getItem('ijova_theme');
  if (savedTheme === 'light') {
    document.body.classList.add('light-mode');
    themeIcon.textContent = '☀️';
  }

  btnThemeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    themeIcon.textContent = isLight ? '☀️' : '🌙';
    localStorage.setItem('ijova_theme', isLight ? 'light' : 'dark');
  });

  // ==========================================
  // PESTAÑA 1: RESTABLECER CONTRASEÑA
  // ==========================================
  const searchInput = document.getElementById('search-matricula-input');
  const btnSearch = document.getElementById('btn-search-student');
  const autocompleteList = document.getElementById('search-autocomplete-list');
  const loadingIndicator = document.getElementById('student-loading-indicator');
  const notFoundAlert = document.getElementById('student-not-found-alert');
  const alertErrorTitle = document.getElementById('alert-error-title');
  const alertErrorDesc = document.getElementById('alert-error-desc');
  const verificationCard = document.getElementById('student-verification-card');
  const successCard = document.getElementById('reset-success-card');

  const studentDisplayName = document.getElementById('student-display-name');
  const studentMatriculaVal = document.getElementById('student-matricula-val');
  const studentUpnVal = document.getElementById('student-upn-val');
  const studentLevelVal = document.getElementById('student-level-val');
  const studentIdVal = document.getElementById('student-id-val');
  const studentPhotoImg = document.getElementById('student-photo-img');
  const studentAvatarPlaceholder = document.getElementById('student-avatar-placeholder');
  const studentInitials = document.getElementById('student-initials');
  const studentPhotoStatus = document.getElementById('student-photo-status');
  const accountStatusBadge = document.getElementById('account-status-badge');

  const confirmCheckbox = document.getElementById('confirm-student-checkbox');
  const btnExecuteReset = document.getElementById('btn-execute-reset');
  const btnCancelReset = document.getElementById('btn-cancel-reset');
  const pwModeAuto = document.getElementById('pw_mode_auto');
  const pwModeCustom = document.getElementById('pw_mode_custom');
  const customPwField = document.getElementById('custom-password-field');
  const inputCustomPassword = document.getElementById('input-custom-password');
  const btnToggleCustomPw = document.getElementById('btn-toggle-custom-pw');
  const forceChangeCheckbox = document.getElementById('force-change-checkbox');

  const successStudentName = document.getElementById('success-student-name');
  const successStudentUpn = document.getElementById('success-student-upn');
  const successPasswordVal = document.getElementById('success-password-val');
  const btnCopyPw = document.getElementById('btn-copy-pw');
  const btnPrintVoucher = document.getElementById('btn-print-voucher');
  const btnDownloadVoucher = document.getElementById('btn-download-voucher');
  const btnResetAnother = document.getElementById('btn-reset-another');

  const ticketName = document.getElementById('ticket-name');
  const ticketMatricula = document.getElementById('ticket-matricula');
  const ticketLevel = document.getElementById('ticket-level');
  const ticketUpn = document.getElementById('ticket-upn');
  const ticketPassword = document.getElementById('ticket-password');

  // Autocomplete predictivo
  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    clearTimeout(searchDebounceTimeout);

    if (query.length < 2) {
      autocompleteList.style.display = 'none';
      return;
    }

    searchDebounceTimeout = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await resp.json();
        renderAutocomplete(data.results || []);
      } catch (err) {
        console.error('Error en búsqueda predictiva:', err);
      }
    }, 250);
  });

  function renderAutocomplete(results) {
    autocompleteList.innerHTML = '';
    if (results.length === 0) {
      autocompleteList.style.display = 'none';
      return;
    }

    results.forEach(item => {
      const row = document.createElement('div');
      row.className = 'autocomplete-item';
      row.innerHTML = `
        <div>
          <span class="student-title">${item.nombre}</span>
          <div class="student-meta">🎓 ${item.matricula} • ${item.nivel} (${item.grado})</div>
        </div>
        <span class="badge badge-success">Seleccionar</span>
      `;
      row.addEventListener('click', () => {
        searchInput.value = item.matricula;
        autocompleteList.style.display = 'none';
        verifyStudent(item.matricula);
      });
      autocompleteList.appendChild(row);
    });

    autocompleteList.style.display = 'block';
  }

  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !autocompleteList.contains(e.target)) {
      autocompleteList.style.display = 'none';
    }
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      autocompleteList.style.display = 'none';
      const val = searchInput.value.trim();
      if (val) verifyStudent(val);
    }
  });

  btnSearch.addEventListener('click', () => {
    autocompleteList.style.display = 'none';
    const val = searchInput.value.trim();
    if (val) verifyStudent(val);
  });

  async function verifyStudent(matricula) {
    matricula = matricula.trim();
    if (!matricula) return;

    verificationCard.style.display = 'none';
    notFoundAlert.style.display = 'none';
    successCard.style.display = 'none';
    loadingIndicator.style.display = 'block';
    currentStudent = null;
    confirmCheckbox.checked = false;
    btnExecuteReset.disabled = true;

    try {
      const resp = await fetch(`/api/student/${encodeURIComponent(matricula)}`);
      const result = await resp.json();
      loadingIndicator.style.display = 'none';

      if (!result.success || !result.data || !result.data.registered) {
        alertErrorTitle.textContent = 'Alumno No Registrado en Microsoft 365';
        alertErrorDesc.textContent = result.data?.error || result.error || `La matrícula ${matricula} no existe en Entra ID.`;
        notFoundAlert.style.display = 'flex';
        return;
      }

      const st = result.data;
      currentStudent = st;

      studentDisplayName.textContent = st.nombre_oficial || st.display_name;
      studentMatriculaVal.textContent = st.matricula;
      studentUpnVal.textContent = st.upn;
      studentLevelVal.textContent = `${st.nivel} — ${st.grado_semestre}`;
      studentIdVal.textContent = st.user_id || 'Microsoft Entra ID';

      const nameParts = (st.nombre_oficial || st.display_name).split(' ');
      const initials = (nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L');
      studentInitials.textContent = initials.toUpperCase();

      if (st.has_photo) {
        studentPhotoImg.src = `/api/student/${encodeURIComponent(st.matricula)}/photo?t=${Date.now()}`;
        studentPhotoImg.style.display = 'block';
        studentAvatarPlaceholder.style.display = 'none';
        studentPhotoStatus.textContent = '📸 Fotografía institucional';
      } else {
        studentPhotoImg.style.display = 'none';
        studentAvatarPlaceholder.style.display = 'flex';
        studentPhotoStatus.textContent = '⚪ Sin foto de perfil';
      }

      if (st.account_enabled) {
        accountStatusBadge.textContent = 'Cuenta Activa';
        accountStatusBadge.className = 'account-status-badge';
      } else {
        accountStatusBadge.textContent = 'Cuenta Deshabilitada';
        accountStatusBadge.className = 'account-status-badge disabled';
      }

      verificationCard.style.display = 'block';
      verificationCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      loadingIndicator.style.display = 'none';
      alertErrorTitle.textContent = 'Error de Comunicación';
      alertErrorDesc.textContent = `No fue posible conectar con el servicio: ${err.message}`;
      notFoundAlert.style.display = 'flex';
    }
  }

  confirmCheckbox.addEventListener('change', () => {
    btnExecuteReset.disabled = !confirmCheckbox.checked;
  });

  btnCancelReset.addEventListener('click', () => {
    verificationCard.style.display = 'none';
    currentStudent = null;
    searchInput.value = '';
    searchInput.focus();
  });

  pwModeAuto.addEventListener('change', () => {
    customPwField.style.display = 'none';
  });

  pwModeCustom.addEventListener('change', () => {
    customPwField.style.display = 'block';
    inputCustomPassword.focus();
  });

  btnToggleCustomPw.addEventListener('click', () => {
    const isPassword = inputCustomPassword.type === 'password';
    inputCustomPassword.type = isPassword ? 'text' : 'password';
    btnToggleCustomPw.textContent = isPassword ? '🔒 Ocultar' : '👁️ Ver';
  });

  btnExecuteReset.addEventListener('click', async () => {
    if (!currentStudent || !confirmCheckbox.checked) {
      alert('Debes confirmar expresamente la identidad del alumno antes de continuar.');
      return;
    }

    let customPw = null;
    if (pwModeCustom.checked) {
      customPw = inputCustomPassword.value.trim();
      if (!customPw) {
        alert('Por favor ingresa la contraseña personalizada o selecciona la opción aleatoria.');
        inputCustomPassword.focus();
        return;
      }
    }

    const forceChange = forceChangeCheckbox.checked;

    btnExecuteReset.disabled = true;
    const btnText = btnExecuteReset.querySelector('.btn-text');
    const btnSpinner = btnExecuteReset.querySelector('.btn-spinner');
    if (btnText) btnText.style.display = 'none';
    if (btnSpinner) btnSpinner.style.display = 'inline';

    try {
      const payload = {
        matricula: currentStudent.matricula,
        confirmed: true,
        custom_password: customPw || undefined,
        force_change: forceChange
      };

      const resp = await fetch('/api/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await resp.json();

      if (!result.success) {
        alert(`❌ Error al restablecer: ${result.error}`);
        btnExecuteReset.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnSpinner) btnSpinner.style.display = 'none';
        return;
      }

      verificationCard.style.display = 'none';
      successCard.style.display = 'block';

      successStudentName.textContent = result.nombre_oficial || result.display_name;
      successStudentUpn.textContent = result.upn;
      successPasswordVal.textContent = result.password;

      ticketName.textContent = result.nombre_oficial || result.display_name;
      ticketMatricula.textContent = result.matricula;
      ticketLevel.textContent = `${result.nivel} (${result.grado_semestre})`;
      ticketUpn.textContent = result.upn;
      ticketPassword.textContent = result.password;

      if (result.pdf_url) {
        btnPrintVoucher.href = result.pdf_url;
        btnPrintVoucher.onclick = (e) => {
          e.preventDefault();
          const win = window.open(result.pdf_url, '_blank');
          if (win) win.focus();
        };

        btnDownloadVoucher.href = `${result.pdf_url}?download=1`;
        btnDownloadVoucher.style.display = 'inline-flex';
      } else {
        btnPrintVoucher.onclick = (e) => {
          e.preventDefault();
          window.print();
        };
        btnDownloadVoucher.style.display = 'none';
      }

      successCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      alert(`Error inesperado al comunicarse con el servidor: ${err.message}`);
    } finally {
      btnExecuteReset.disabled = false;
      if (btnText) btnText.style.display = 'inline';
      if (btnSpinner) btnSpinner.style.display = 'none';
    }
  });

  btnCopyPw.addEventListener('click', async () => {
    const pw = successPasswordVal.textContent.trim();
    try {
      await navigator.clipboard.writeText(pw);
      btnCopyPw.textContent = '✓ ¡Copiada!';
      setTimeout(() => { btnCopyPw.textContent = '📋 Copiar'; }, 2000);
    } catch (err) {
      alert(`Contraseña: ${pw}`);
    }
  });

  btnResetAnother.addEventListener('click', () => {
    successCard.style.display = 'none';
    searchInput.value = '';
    searchInput.focus();
    currentStudent = null;
  });

  // ==========================================
  // PESTAÑA 2: BAJAS DE ALUMNOS (ZONA CONTROLADA)
  // ==========================================
  const deleteSearchInput = document.getElementById('delete-matricula-input');
  const btnSearchDelete = document.getElementById('btn-search-delete-student');
  const deleteStudentCard = document.getElementById('delete-student-card');
  const deleteResultAlert = document.getElementById('delete-result-alert');
  const deleteResultDesc = document.getElementById('delete-result-desc');

  const deleteStudentDisplayName = document.getElementById('delete-student-display-name');
  const deleteStudentMatriculaVal = document.getElementById('delete-student-matricula-val');
  const deleteStudentUpnVal = document.getElementById('delete-student-upn-val');
  const deleteStudentLevelVal = document.getElementById('delete-student-level-val');
  const deleteStudentPhotoImg = document.getElementById('delete-student-photo-img');
  const deleteStudentAvatarPh = document.getElementById('delete-student-avatar-placeholder');
  const deleteStudentInitials = document.getElementById('delete-student-initials');

  const deleteTargetHint = document.getElementById('delete-target-hint');
  const inputDeleteConfirmCode = document.getElementById('input-delete-confirm-code');
  const btnExecuteDelete = document.getElementById('btn-execute-delete');
  const btnCancelDelete = document.getElementById('btn-cancel-delete');

  async function searchStudentForDelete() {
    const matricula = deleteSearchInput.value.trim();
    if (!matricula) return;

    deleteStudentCard.style.display = 'none';
    deleteResultAlert.style.display = 'none';
    inputDeleteConfirmCode.value = '';
    btnExecuteDelete.disabled = true;

    try {
      const resp = await fetch(`/api/student/${encodeURIComponent(matricula)}`);
      const result = await resp.json();

      if (!result.success || !result.data || !result.data.registered) {
        alert(result.data?.error || result.error || `El alumno ${matricula} no existe en Microsoft 365.`);
        return;
      }

      currentDeleteStudent = result.data;

      deleteStudentDisplayName.textContent = currentDeleteStudent.nombre_oficial || currentDeleteStudent.display_name;
      deleteStudentMatriculaVal.textContent = currentDeleteStudent.matricula;
      deleteStudentUpnVal.textContent = currentDeleteStudent.upn;
      deleteStudentLevelVal.textContent = `${currentDeleteStudent.nivel} (${currentDeleteStudent.grado_semestre})`;
      deleteTargetHint.textContent = currentDeleteStudent.matricula;

      const nameParts = (currentDeleteStudent.nombre_oficial || currentDeleteStudent.display_name).split(' ');
      deleteStudentInitials.textContent = ((nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L')).toUpperCase();

      if (currentDeleteStudent.has_photo) {
        deleteStudentPhotoImg.src = `/api/student/${encodeURIComponent(currentDeleteStudent.matricula)}/photo?t=${Date.now()}`;
        deleteStudentPhotoImg.style.display = 'block';
        deleteStudentAvatarPh.style.display = 'none';
      } else {
        deleteStudentPhotoImg.style.display = 'none';
        deleteStudentAvatarPh.style.display = 'flex';
      }

      deleteStudentCard.style.display = 'block';
      deleteStudentCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      inputDeleteConfirmCode.focus();

    } catch (err) {
      alert(`Error al buscar alumno: ${err.message}`);
    }
  }

  btnSearchDelete.addEventListener('click', searchStudentForDelete);
  deleteSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      searchStudentForDelete();
    }
  });

  // Candado de seguridad: solo se activa si la matrícula escrita coincide exactamente
  inputDeleteConfirmCode.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (currentDeleteStudent && val === currentDeleteStudent.matricula) {
      btnExecuteDelete.disabled = false;
    } else {
      btnExecuteDelete.disabled = true;
    }
  });

  btnCancelDelete.addEventListener('click', () => {
    deleteStudentCard.style.display = 'none';
    currentDeleteStudent = null;
    deleteSearchInput.value = '';
    deleteSearchInput.focus();
  });

  btnExecuteDelete.addEventListener('click', async () => {
    if (!currentDeleteStudent) return;
    const confirmVal = inputDeleteConfirmCode.value.trim();

    if (confirmVal !== currentDeleteStudent.matricula) {
      alert(`Debes escribir exactamente la matrícula '${currentDeleteStudent.matricula}' para confirmar.`);
      inputDeleteConfirmCode.focus();
      return;
    }

    btnExecuteDelete.disabled = true;
    btnExecuteDelete.textContent = '⏳ Enviando a Papelera...';

    try {
      const resp = await fetch('/api/student/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          matricula: currentDeleteStudent.matricula,
          confirmation: confirmVal
        })
      });

      const res = await resp.json();

      if (!res.success) {
        alert(`❌ Error al dar de baja: ${res.error}`);
        btnExecuteDelete.disabled = false;
        btnExecuteDelete.textContent = '🗑️ Confirmar Baja a Papelera de Reciclaje';
        return;
      }

      deleteStudentCard.style.display = 'none';
      deleteResultDesc.textContent = res.message;
      deleteResultAlert.style.display = 'flex';
      deleteResultAlert.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      alert(`Error inesperado: ${err.message}`);
      btnExecuteDelete.disabled = false;
      btnExecuteDelete.textContent = '🗑️ Confirmar Baja a Papelera de Reciclaje';
    }
  });

  // ==========================================
  // PESTAÑA 3: PAPELERA DE RECICLAJE & RESTAURACIÓN
  // ==========================================
  const recycleTbody = document.getElementById('recycle-tbody');
  const btnRefreshRecycle = document.getElementById('btn-refresh-recycle');

  async function loadRecycleBin() {
    recycleTbody.innerHTML = '<tr><td colspan="6" class="text-center">Consultando Papelera de Microsoft Entra ID...</td></tr>';
    try {
      const resp = await fetch('/api/recycle-bin');
      const data = await resp.json();
      const users = data.users || [];

      if (users.length === 0) {
        recycleTbody.innerHTML = '<tr><td colspan="6" class="text-center">✨ La Papelera de Reciclaje está vacía. No hay cuentas de alumnos eliminadas recientemente.</td></tr>';
        return;
      }

      recycleTbody.innerHTML = '';
      users.forEach(u => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong class="highlight">${u.matricula}</strong></td>
          <td>${u.display_name}</td>
          <td class="mono">${u.upn}</td>
          <td class="mono">${u.deleted_datetime}</td>
          <td><span class="badge badge-success">Recuperable (< 30 días)</span></td>
          <td>
            <button type="button" class="btn btn-sm btn-primary btn-restore-user" data-mat="${u.matricula}">
              🔄 Restaurar Cuenta
            </button>
          </td>
        `;
        recycleTbody.appendChild(tr);
      });

      // Eventos de restauración
      document.querySelectorAll('.btn-restore-user').forEach(b => {
        b.addEventListener('click', async () => {
          const mat = b.getAttribute('data-mat');
          if (!confirm(`¿Deseas restaurar la cuenta del alumno ${mat} preservando su buzón y OneDrive?`)) return;

          b.disabled = true;
          b.textContent = '⏳ Restaurando...';

          try {
            const rResp = await fetch('/api/recycle-bin/restore', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ matricula: mat })
            });
            const rData = await rResp.json();

            if (rData.success) {
              alert(`✅ ${rData.message}`);
              loadRecycleBin();
            } else {
              alert(`❌ Error al restaurar: ${rData.error}`);
              b.disabled = false;
              b.textContent = '🔄 Restaurar Cuenta';
            }
          } catch (err) {
            alert(`Error de conexión: ${err.message}`);
            b.disabled = false;
            b.textContent = '🔄 Restaurar Cuenta';
          }
        });
      });

    } catch (err) {
      recycleTbody.innerHTML = `<tr><td colspan="6" class="text-center" style="color: var(--color-danger);">Error al consultar papelera: ${err.message}</td></tr>`;
    }
  }

  if (btnRefreshRecycle) {
    btnRefreshRecycle.addEventListener('click', loadRecycleBin);
  }

  // ==========================================
  // PESTAÑA 4: AUDITORÍA Y GALERÍA DE FOTOS
  // ==========================================
  const photoStatWith = document.getElementById('photo-stat-with');
  const photoStatWithout = document.getElementById('photo-stat-without');
  const photoStatTotal = document.getElementById('photo-stat-total');
  const photoStatPct = document.getElementById('photo-stat-pct');
  const photosGalleryGrid = document.getElementById('photos-gallery-grid');
  const btnTriggerPhotoScan = document.getElementById('btn-trigger-photo-scan');

  async function loadPhotosStats() {
    try {
      const resp = await fetch('/api/photos/stats');
      const data = await resp.json();
      if (data.success) {
        photoStatWith.textContent = data.with_photo;
        photoStatWithout.textContent = data.without_photo;
        photoStatTotal.textContent = data.total_students;
        photoStatPct.textContent = `${data.compliance_pct}% con fotografía`;
      }
    } catch (err) {
      console.error('Error al cargar estadísticas de fotos:', err);
    }
  }

  async function loadPhotosGallery(filterType = 'all', levelFilter = 'all') {
    photosGalleryGrid.innerHTML = '<p class="text-center" style="grid-column: 1 / -1; padding: 2rem; color: var(--text-muted);">Cargando catálogo fotográfico...</p>';
    try {
      const resp = await fetch(`/api/photos/gallery?filter=${encodeURIComponent(filterType)}&level=${encodeURIComponent(levelFilter)}`);
      const data = await resp.json();
      const students = data.students || [];

      if (students.length === 0) {
        photosGalleryGrid.innerHTML = '<p class="text-center" style="grid-column: 1 / -1; padding: 2rem; color: var(--text-muted);">No se encontraron alumnos con los filtros seleccionados.</p>';
        return;
      }

      photosGalleryGrid.innerHTML = '';
      students.forEach(s => {
        const card = document.createElement('div');
        card.className = 'photo-student-card';

        const nameParts = s.nombre.split(' ');
        const initials = ((nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L')).toUpperCase();

        const avatarHtml = s.has_photo
          ? `<img src="${s.photo_url}" alt="Foto de ${s.nombre}" loading="lazy">`
          : `<div class="avatar-ph">${initials}</div>`;

        const badgeHtml = s.has_photo
          ? `<span class="badge badge-success">📸 Con foto</span>`
          : `<span class="badge badge-danger">⚪ Sin foto</span>`;

        card.innerHTML = `
          <div class="photo-card-avatar">
            ${avatarHtml}
          </div>
          <div class="photo-card-name" title="${s.nombre}">${s.nombre}</div>
          <div class="photo-card-matricula">🎓 ${s.matricula}</div>
          <div class="photo-card-level">${s.nivel} (${s.grado})</div>
          <div style="margin-top: 0.5rem;">${badgeHtml}</div>
        `;
        photosGalleryGrid.appendChild(card);
      });

    } catch (err) {
      photosGalleryGrid.innerHTML = `<p class="text-center" style="grid-column: 1 / -1; padding: 2rem; color: var(--color-danger);">Error al cargar galería: ${err.message}</p>`;
    }
  }

  // Filtros de estado de foto
  document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activePhotoFilter = btn.getAttribute('data-filter');
      loadPhotosGallery(activePhotoFilter, activeLevelFilter);
    });
  });

  // Filtros de nivel escolar
  document.querySelectorAll('.btn-filter-level').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-filter-level').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeLevelFilter = btn.getAttribute('data-level');
      loadPhotosGallery(activePhotoFilter, activeLevelFilter);
    });
  });

  // Botón para iniciar escaneo masivo
  if (btnTriggerPhotoScan) {
    btnTriggerPhotoScan.addEventListener('click', async () => {
      if (!confirm('¿Deseas iniciar la auditoría y descarga masiva de fotos desde Microsoft 365? Se ejecutará en segundo plano.')) return;

      btnTriggerPhotoScan.disabled = true;
      btnTriggerPhotoScan.textContent = '⏳ Escaneando fotos...';

      try {
        const resp = await fetch('/api/photos/scan', { method: 'POST' });
        const data = await resp.json();
        alert(data.message || 'Auditoría en curso.');

        // Polling del estado
        const interval = setInterval(async () => {
          const sResp = await fetch('/api/photos/scan/status');
          const sData = await sResp.json();
          if (!sData.running) {
            clearInterval(interval);
            btnTriggerPhotoScan.disabled = false;
            btnTriggerPhotoScan.textContent = '⚡ Iniciar / Actualizar Descarga de Fotos';
            loadPhotosStats();
            loadPhotosGallery(activePhotoFilter, activeLevelFilter);
          }
        }, 3000);

      } catch (err) {
        alert(`Error al iniciar auditoría: ${err.message}`);
        btnTriggerPhotoScan.disabled = false;
        btnTriggerPhotoScan.textContent = '⚡ Iniciar / Actualizar Descarga de Fotos';
      }
    });
  }

  // ==========================================
  // PESTAÑA 5: HISTORIAL DE FICHAS
  // ==========================================
  const historyTbody = document.getElementById('history-tbody');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');

  async function loadHistory() {
    historyTbody.innerHTML = '<tr><td colspan="6" class="text-center">Cargando bitácora de reseteos...</td></tr>';
    try {
      const resp = await fetch('/api/history');
      const data = await resp.json();
      const rows = data.history || [];

      if (rows.length === 0) {
        historyTbody.innerHTML = '<tr><td colspan="6" class="text-center">No hay registros de reseteos aún en la bitácora.</td></tr>';
        return;
      }

      historyTbody.innerHTML = '';
      rows.forEach(r => {
        const tr = document.createElement('tr');
        const pdfLink = r.pdf_url
          ? `<a href="${r.pdf_url}" target="_blank" class="btn btn-sm btn-secondary">📄 Abrir Ficha</a>`
          : `<span style="color: var(--text-muted);">No generada</span>`;

        tr.innerHTML = `
          <td class="mono">${r.timestamp_utc}</td>
          <td><strong>${r.matricula}</strong></td>
          <td>${r.display_name}</td>
          <td class="mono">${r.upn}</td>
          <td><span class="badge badge-success">${r.reset_by}</span></td>
          <td>${pdfLink}</td>
        `;
        historyTbody.appendChild(tr);
      });
    } catch (err) {
      historyTbody.innerHTML = `<tr><td colspan="6" class="text-center" style="color: var(--color-danger);">Error al cargar historial: ${err.message}</td></tr>`;
    }
  }

  if (btnRefreshHistory) {
    btnRefreshHistory.addEventListener('click', loadHistory);
  }

  // ==========================================
  // PESTAÑA 6: ESTADO DEL TENANT
  // ==========================================
  const tenantAdminUpn = document.getElementById('tenant-admin-upn');
  const tenantAuthType = document.getElementById('tenant-auth-type');
  const tenantDomainVerified = document.getElementById('tenant-domain-verified');

  async function loadTenantStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (data.success) {
        tenantAdminUpn.textContent = data.admin_upn || 'Conectado';
        tenantAuthType.textContent = data.auth_type || 'Managed';
        tenantDomainVerified.textContent = data.is_verified ? 'Verificado' : 'No verificado';
        tenantDomainVerified.className = data.is_verified ? 'tile-tag tag-success' : 'tile-tag tag-danger';
      } else {
        tenantAdminUpn.textContent = 'Error de conexión';
      }
    } catch (err) {
      tenantAdminUpn.textContent = 'Desconectado';
    }
  }

  // ==========================================
  // PESTAÑA 7: GUÍA DE COMANDOS CLI (COPIADO)
  // ==========================================
  document.querySelectorAll('.btn-copy-cli').forEach(btn => {
    btn.addEventListener('click', async () => {
      const cmd = btn.getAttribute('data-cmd');
      if (!cmd) return;

      try {
        await navigator.clipboard.writeText(cmd);
        const originalText = btn.textContent;
        btn.textContent = '✓ ¡Copiado!';
        btn.style.background = 'var(--color-success)';
        btn.style.color = '#ffffff';

        setTimeout(() => {
          btn.textContent = originalText;
          btn.style.background = '';
          btn.style.color = '';
        }, 1800);
      } catch (err) {
        prompt('Copia el comando manualmente:', cmd);
      }
    });
  });
});
