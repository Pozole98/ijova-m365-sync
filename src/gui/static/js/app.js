/**
 * IJOVA • Cloud Identity Hub • Microsoft 365
 * Enterprise SaaS Client Controller:
 * - Reseteo Seguro con Verificación Previa y Confirmación Obligatoria
 * - Bajas Controladas con Candado de Matrícula
 * - Papelera de Reciclaje y Restauración en 1 Clic
 * - Auditoría y Galería Filtrable de Fotos de Perfil
 * - Bitácora Histórica de Reseteos y Comprobantes
 * - Terminal & Guía CLI con Botones de Copiado Rápido
 * - Sistema de Notificaciones Toast Flotantes
 */

document.addEventListener('DOMContentLoaded', () => {
  // Estado local
  let currentStudent = null;
  let currentDeleteStudent = null;
  let searchDebounceTimeout = null;
  let activePhotoFilter = 'all';
  let activeLevelFilter = 'all';

  // ==========================================
  // SISTEMA DE NOTIFICACIONES TOAST
  // ==========================================
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--color-green); flex-shrink: 0;"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--color-danger); flex-shrink: 0;"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color: var(--brand-blue); flex-shrink: 0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, 3600);
  }

  // ==========================================
  // NAVEGACIÓN POR PESTAÑAS & BREADCRUMBS
  // ==========================================
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const breadcrumbCurrent = document.getElementById('active-breadcrumb-title');

  const tabTitles = {
    'tab-reset': 'Restablecer Contraseña',
    'tab-delete': 'Bajas de Alumnos',
    'tab-recycle': 'Papelera & Restauración',
    'tab-photos': 'Auditoría de Fotos de Perfil',
    'tab-history': 'Historial de Fichas',
    'tab-tenant': 'Salud del Tenant',
    'tab-cli': 'Terminal & Guía CLI'
  };

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

    if (breadcrumbCurrent && tabTitles[targetTabId]) {
      breadcrumbCurrent.textContent = tabTitles[targetTabId];
    }

    // Carga de datos bajo demanda
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
    if (themeIcon) themeIcon.textContent = '☀️';
  }

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener('click', () => {
      document.body.classList.toggle('light-mode');
      const isLight = document.body.classList.contains('light-mode');
      if (themeIcon) themeIcon.textContent = isLight ? '☀️' : '🌙';
      localStorage.setItem('ijova_theme', isLight ? 'light' : 'dark');
      showToast(isLight ? 'Modo claro activado' : 'Modo oscuro activado', 'info');
    });
  }

  // ==========================================
  // PESTAÑA 1: RESTABLECER CONTRASEÑA
  // ==========================================
  const searchInput = document.getElementById('search-matricula-input');
  const btnSearch = document.getElementById('btn-search-student');
  const btnClearSearch = document.getElementById('btn-clear-search');
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

  // Control de botón limpiar
  if (searchInput && btnClearSearch) {
    searchInput.addEventListener('input', () => {
      btnClearSearch.style.display = searchInput.value.length > 0 ? 'block' : 'none';
    });
    btnClearSearch.addEventListener('click', () => {
      searchInput.value = '';
      btnClearSearch.style.display = 'none';
      autocompleteList.style.display = 'none';
      searchInput.focus();
    });
  }

  // Autocomplete predictivo
  if (searchInput) {
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

          if (!data.success || !data.results || data.results.length === 0) {
            autocompleteList.style.display = 'none';
            return;
          }

          autocompleteList.innerHTML = '';
          data.results.forEach(item => {
            const row = document.createElement('div');
            row.className = 'autocomplete-item';

            const nameParts = (item.nombre || item.upn).split(' ');
            const initials = ((nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L')).toUpperCase();

            row.innerHTML = `
              <div class="auto-student-info">
                <div class="auto-avatar-mini">${initials}</div>
                <div>
                  <div class="auto-name-val">${item.nombre}</div>
                  <div class="auto-level-val">${item.nivel || 'Estudiante'} • ${item.upn}</div>
                </div>
              </div>
              <span class="auto-mat-val">${item.matricula}</span>
            `;
            row.addEventListener('click', () => {
              searchInput.value = item.matricula;
              autocompleteList.style.display = 'none';
              verifyStudent(item.matricula);
            });
            autocompleteList.appendChild(row);
          });
          autocompleteList.style.display = 'block';

        } catch (err) {
          console.error('Error en búsqueda predictiva:', err);
        }
      }, 220);
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !autocompleteList.contains(e.target)) {
        autocompleteList.style.display = 'none';
      }
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        autocompleteList.style.display = 'none';
        const query = searchInput.value.trim();
        if (query) verifyStudent(query);
      }
    });
  }

  if (btnSearch) {
    btnSearch.addEventListener('click', () => {
      const query = searchInput.value.trim();
      if (query) verifyStudent(query);
    });
  }

  // Verificación en vivo contra Entra ID
  async function verifyStudent(identifier) {
    autocompleteList.style.display = 'none';
    verificationCard.style.display = 'none';
    notFoundAlert.style.display = 'none';
    successCard.style.display = 'none';

    loadingIndicator.style.display = 'flex';
    if (btnSearch) {
      btnSearch.querySelector('.btn-text').style.display = 'none';
      btnSearch.querySelector('.btn-spinner').style.display = 'inline-block';
      btnSearch.disabled = true;
    }

    try {
      const resp = await fetch(`/api/student/${encodeURIComponent(identifier)}`);
      const result = await resp.json();

      loadingIndicator.style.display = 'none';
      if (btnSearch) {
        btnSearch.querySelector('.btn-text').style.display = 'inline';
        btnSearch.querySelector('.btn-spinner').style.display = 'none';
        btnSearch.disabled = false;
      }

      if (!result.success || !result.data || !result.data.registered) {
        alertErrorTitle.textContent = 'Alumno No Registrado';
        alertErrorDesc.textContent = result.data?.error || result.error || `La matrícula ${identifier} no existe en Microsoft Entra ID.`;
        notFoundAlert.style.display = 'flex';
        showToast(`El alumno ${identifier} no está registrado en Microsoft 365.`, 'error');
        return;
      }

      currentStudent = result.data;

      studentDisplayName.textContent = currentStudent.nombre_oficial || currentStudent.display_name;
      studentMatriculaVal.textContent = currentStudent.matricula;
      studentUpnVal.textContent = currentStudent.upn;
      studentLevelVal.textContent = `${currentStudent.nivel} (${currentStudent.grado_semestre})`;
      studentIdVal.textContent = currentStudent.id || 'Nube Entra ID';

      const nameParts = (currentStudent.nombre_oficial || currentStudent.display_name).split(' ');
      studentInitials.textContent = ((nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L')).toUpperCase();

      if (currentStudent.has_photo) {
        studentPhotoImg.src = `/api/student/${encodeURIComponent(currentStudent.matricula)}/photo?t=${Date.now()}`;
        studentPhotoImg.style.display = 'block';
        studentAvatarPlaceholder.style.display = 'none';
        studentPhotoStatus.textContent = '✓ Foto Oficial Configurada';
        studentPhotoStatus.style.color = 'var(--color-green)';
      } else {
        studentPhotoImg.style.display = 'none';
        studentAvatarPlaceholder.style.display = 'flex';
        studentPhotoStatus.textContent = 'Sin foto registrada';
        studentPhotoStatus.style.color = 'var(--text-muted)';
      }

      confirmCheckbox.checked = false;
      btnExecuteReset.disabled = true;

      verificationCard.style.display = 'block';
      verificationCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
      showToast(`Alumno ${currentStudent.matricula} verificado con éxito en Entra ID.`, 'success');

    } catch (err) {
      loadingIndicator.style.display = 'none';
      if (btnSearch) {
        btnSearch.querySelector('.btn-text').style.display = 'inline';
        btnSearch.querySelector('.btn-spinner').style.display = 'none';
        btnSearch.disabled = false;
      }
      alertErrorTitle.textContent = 'Error de Conexión';
      alertErrorDesc.textContent = `No se pudo conectar con el servidor: ${err.message}`;
      notFoundAlert.style.display = 'flex';
      showToast(`Error de conexión con el servidor: ${err.message}`, 'error');
    }
  }

  // Checkbox de confirmación obligatoria
  if (confirmCheckbox) {
    confirmCheckbox.addEventListener('change', (e) => {
      btnExecuteReset.disabled = !e.target.checked;
    });
  }

  // Alternador de modos de contraseña
  if (pwModeAuto && pwModeCustom) {
    pwModeAuto.addEventListener('change', () => {
      customPwField.style.display = 'none';
    });

    pwModeCustom.addEventListener('change', () => {
      customPwField.style.display = 'block';
      inputCustomPassword.focus();
    });
  }

  if (btnToggleCustomPw && inputCustomPassword) {
    btnToggleCustomPw.addEventListener('click', () => {
      const isPw = inputCustomPassword.type === 'password';
      inputCustomPassword.type = isPw ? 'text' : 'password';
      btnToggleCustomPw.textContent = isPw ? '🔒 Ocultar' : '👁️ Ver';
    });
  }

  // Cancelar reseteo
  if (btnCancelReset) {
    btnCancelReset.addEventListener('click', () => {
      verificationCard.style.display = 'none';
      currentStudent = null;
      if (searchInput) {
        searchInput.value = '';
        searchInput.focus();
      }
      showToast('Operación cancelada por el usuario.', 'info');
    });
  }

  // Ejecución de reseteo
  if (btnExecuteReset) {
    btnExecuteReset.addEventListener('click', async () => {
      if (!currentStudent || !confirmCheckbox.checked) {
        showToast('Debes marcar la casilla de verificación antes de continuar.', 'error');
        return;
      }

      let passwordMode = 'auto';
      let customPassword = null;

      if (pwModeCustom.checked) {
        passwordMode = 'custom';
        customPassword = inputCustomPassword.value.trim();
        if (!customPassword || customPassword.length < 8) {
          showToast('La contraseña personalizada debe tener al menos 8 caracteres.', 'error');
          inputCustomPassword.focus();
          return;
        }
      }

      btnExecuteReset.disabled = true;
      btnExecuteReset.querySelector('.btn-text').style.display = 'none';
      btnExecuteReset.querySelector('.btn-spinner').style.display = 'inline-flex';

      try {
        const payload = {
          matricula: currentStudent.matricula,
          confirmed: true,
          password_mode: passwordMode,
          custom_password: customPassword,
          force_change: forceChangeCheckbox.checked
        };

        const resp = await fetch('/api/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await resp.json();

        btnExecuteReset.querySelector('.btn-text').style.display = 'inline';
        btnExecuteReset.querySelector('.btn-spinner').style.display = 'none';

        if (!data.success) {
          btnExecuteReset.disabled = false;
          showToast(`Error: ${data.error}`, 'error');
          return;
        }

        verificationCard.style.display = 'none';

        successStudentName.textContent = data.data.display_name;
        successStudentUpn.textContent = data.data.upn;
        successPasswordVal.textContent = data.data.new_password;

        ticketName.textContent = data.data.display_name;
        ticketMatricula.textContent = data.data.matricula;
        ticketLevel.textContent = data.data.nivel || currentStudent.nivel || 'Estudiante';
        ticketUpn.textContent = data.data.upn;
        ticketPassword.textContent = data.data.new_password;

        if (data.data.pdf_filename) {
          btnPrintVoucher.href = `/api/pdf/${data.data.pdf_filename}`;
          btnDownloadVoucher.href = `/api/pdf/${data.data.pdf_filename}`;
          btnPrintVoucher.style.display = 'inline-flex';
          btnDownloadVoucher.style.display = 'inline-flex';
        } else {
          btnPrintVoucher.style.display = 'none';
          btnDownloadVoucher.style.display = 'none';
        }

        successCard.style.display = 'block';
        successCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        showToast('¡Contraseña restablecida exitosamente en Microsoft 365!', 'success');

      } catch (err) {
        btnExecuteReset.disabled = false;
        btnExecuteReset.querySelector('.btn-text').style.display = 'inline';
        btnExecuteReset.querySelector('.btn-spinner').style.display = 'none';
        showToast(`Error al procesar el reseteo: ${err.message}`, 'error');
      }
    });
  }

  // Copiar contraseña
  if (btnCopyPw) {
    btnCopyPw.addEventListener('click', async () => {
      const pw = successPasswordVal.textContent;
      try {
        await navigator.clipboard.writeText(pw);
        showToast('Contraseña temporal copiada al portapapeles.', 'success');
      } catch (e) {
        prompt('Copia manualmente la contraseña:', pw);
      }
    });
  }

  // Atender a otro alumno
  if (btnResetAnother) {
    btnResetAnother.addEventListener('click', () => {
      successCard.style.display = 'none';
      currentStudent = null;
      if (searchInput) {
        searchInput.value = '';
        searchInput.focus();
      }
    });
  }

  // ==========================================
  // PESTAÑA 2: BAJAS DE ALUMNOS (ZONA CONTROLADA)
  // ==========================================
  const deleteSearchInput = document.getElementById('delete-matricula-input');
  const btnSearchDelete = document.getElementById('btn-search-delete-student');
  const deleteStudentCard = document.getElementById('delete-student-card');
  const deleteResultAlert = document.getElementById('delete-result-alert');
  const deleteResultTitle = document.getElementById('delete-result-title');
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
  const deleteLockBadge = document.getElementById('delete-lock-status-badge');
  const btnExecuteDelete = document.getElementById('btn-execute-delete');
  const btnCancelDelete = document.getElementById('btn-cancel-delete');

  async function searchStudentForDelete() {
    const matricula = deleteSearchInput.value.trim();
    if (!matricula) return;

    deleteStudentCard.style.display = 'none';
    deleteResultAlert.style.display = 'none';
    inputDeleteConfirmCode.value = '';
    btnExecuteDelete.disabled = true;

    if (deleteLockBadge) {
      deleteLockBadge.className = 'lock-status-pill locked';
      deleteLockBadge.textContent = '🔒 Bloqueado';
    }

    try {
      const resp = await fetch(`/api/student/${encodeURIComponent(matricula)}`);
      const result = await resp.json();

      if (!result.success || !result.data || !result.data.registered) {
        showToast(result.data?.error || result.error || `El alumno ${matricula} no existe en Microsoft 365.`, 'error');
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
      showToast(`Alumno ${currentDeleteStudent.matricula} localizado. Escribe su matrícula para confirmar la baja.`, 'info');

    } catch (err) {
      showToast(`Error al buscar alumno: ${err.message}`, 'error');
    }
  }

  if (btnSearchDelete) btnSearchDelete.addEventListener('click', searchStudentForDelete);
  if (deleteSearchInput) {
    deleteSearchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        searchStudentForDelete();
      }
    });
  }

  // Candado de seguridad estricto: la matrícula debe coincidir exactamente
  if (inputDeleteConfirmCode) {
    inputDeleteConfirmCode.addEventListener('input', (e) => {
      const val = e.target.value.trim();
      const isMatch = currentDeleteStudent && val === currentDeleteStudent.matricula;
      btnExecuteDelete.disabled = !isMatch;

      if (deleteLockBadge) {
        if (isMatch) {
          deleteLockBadge.className = 'lock-status-pill unlocked';
          deleteLockBadge.textContent = '🔓 Desbloqueado';
        } else {
          deleteLockBadge.className = 'lock-status-pill locked';
          deleteLockBadge.textContent = '🔒 Bloqueado';
        }
      }
    });
  }

  if (btnCancelDelete) {
    btnCancelDelete.addEventListener('click', () => {
      deleteStudentCard.style.display = 'none';
      currentDeleteStudent = null;
      if (deleteSearchInput) {
        deleteSearchInput.value = '';
        deleteSearchInput.focus();
      }
      showToast('Baja cancelada.', 'info');
    });
  }

  if (btnExecuteDelete) {
    btnExecuteDelete.addEventListener('click', async () => {
      if (!currentDeleteStudent) return;
      const code = inputDeleteConfirmCode.value.trim();
      if (code !== currentDeleteStudent.matricula) {
        showToast('Debes ingresar exactamente la matrícula del alumno para confirmar.', 'error');
        return;
      }

      btnExecuteDelete.disabled = true;
      btnExecuteDelete.textContent = '⏳ Procesando baja en Microsoft 365...';

      try {
        const resp = await fetch('/api/student/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            matricula: currentDeleteStudent.matricula,
            confirmation: code
          })
        });

        const data = await resp.json();

        if (data.success) {
          deleteStudentCard.style.display = 'none';
          deleteResultTitle.textContent = 'Baja Aplicada Exitosamente';
          deleteResultDesc.textContent = `La cuenta ${currentDeleteStudent.matricula} (@${currentDeleteStudent.upn}) fue enviada a la Papelera de Reciclaje (30 días de retención).`;
          deleteResultAlert.style.display = 'flex';
          deleteResultAlert.scrollIntoView({ behavior: 'smooth', block: 'start' });
          showToast(`Alumno ${currentDeleteStudent.matricula} enviado a la papelera.`, 'success');
          currentDeleteStudent = null;
          if (deleteSearchInput) deleteSearchInput.value = '';
        } else {
          btnExecuteDelete.disabled = false;
          btnExecuteDelete.textContent = 'Confirmar Baja a Papelera de Reciclaje';
          showToast(`Error al procesar la baja: ${data.error}`, 'error');
        }
      } catch (err) {
        btnExecuteDelete.disabled = false;
        btnExecuteDelete.textContent = 'Confirmar Baja a Papelera de Reciclaje';
        showToast(`Error de conexión: ${err.message}`, 'error');
      }
    });
  }

  // ==========================================
  // PESTAÑA 3: PAPELERA DE RECICLAJE & RESTAURACIÓN
  // ==========================================
  const recycleTbody = document.getElementById('recycle-tbody');
  const btnRefreshRecycle = document.getElementById('btn-refresh-recycle');

  async function loadRecycleBin() {
    recycleTbody.innerHTML = '<tr><td colspan="6" class="table-empty-row">Consultando Papelera de Microsoft Entra ID...</td></tr>';
    try {
      const resp = await fetch('/api/recycle-bin');
      const data = await resp.json();
      const users = data.users || [];

      if (users.length === 0) {
        recycleTbody.innerHTML = '<tr><td colspan="6" class="table-empty-row">✨ La Papelera de Reciclaje está vacía. No hay cuentas de alumnos en retención.</td></tr>';
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
          <td class="text-right">
            <button type="button" class="btn btn-sm btn-primary-saas btn-restore-user" data-mat="${u.matricula}">
              Restaurar Alumno
            </button>
          </td>
        `;
        recycleTbody.appendChild(tr);
      });

      // Eventos de restauración
      document.querySelectorAll('.btn-restore-user').forEach(b => {
        b.addEventListener('click', async () => {
          const mat = b.getAttribute('data-mat');
          b.disabled = true;
          b.textContent = 'Restaurando...';

          try {
            const rResp = await fetch('/api/recycle-bin/restore', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ matricula: mat })
            });
            const rData = await rResp.json();

            if (rData.success) {
              showToast(`Cuenta ${mat} restaurada con éxito en Microsoft 365.`, 'success');
              loadRecycleBin();
            } else {
              showToast(`Error al restaurar: ${rData.error}`, 'error');
              b.disabled = false;
              b.textContent = 'Restaurar Alumno';
            }
          } catch (err) {
            showToast(`Error de conexión: ${err.message}`, 'error');
            b.disabled = false;
            b.textContent = 'Restaurar Alumno';
          }
        });
      });

    } catch (err) {
      recycleTbody.innerHTML = `<tr><td colspan="6" class="table-empty-row" style="color: var(--color-danger);">Error al consultar papelera: ${err.message}</td></tr>`;
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
    photosGalleryGrid.innerHTML = '<p class="table-empty-row" style="grid-column: 1 / -1;">Cargando catálogo fotográfico...</p>';
    try {
      const resp = await fetch(`/api/photos/gallery?filter=${encodeURIComponent(filterType)}&level=${encodeURIComponent(levelFilter)}`);
      const data = await resp.json();
      const students = data.students || [];

      if (students.length === 0) {
        photosGalleryGrid.innerHTML = '<p class="table-empty-row" style="grid-column: 1 / -1;">No se encontraron alumnos con los filtros seleccionados.</p>';
        return;
      }

      photosGalleryGrid.innerHTML = '';
      students.forEach(s => {
        const card = document.createElement('div');
        card.className = 'photo-card-saas';

        const nameParts = s.nombre.split(' ');
        const initials = ((nameParts[0]?.[0] || 'A') + (nameParts[1]?.[0] || 'L')).toUpperCase();

        const avatarHtml = s.has_photo
          ? `<img src="${s.photo_url}" alt="Foto de ${s.nombre}" loading="lazy">`
          : `<span>${initials}</span>`;

        const pillHtml = s.has_photo
          ? `<span class="photo-card-pill has-photo">✓ Foto Oficial</span>`
          : `<span class="photo-card-pill no-photo">○ Sin Foto</span>`;

        card.innerHTML = `
          <div class="photo-card-avatar">
            ${avatarHtml}
          </div>
          <div class="photo-card-name" title="${s.nombre}">${s.nombre}</div>
          <div class="photo-card-mat">${s.matricula}</div>
          <div style="font-size: 0.76rem; color: var(--text-muted); margin-bottom: 0.65rem;">${s.nivel} (${s.grado})</div>
          <div>${pillHtml}</div>
        `;
        photosGalleryGrid.appendChild(card);
      });

    } catch (err) {
      photosGalleryGrid.innerHTML = `<p class="table-empty-row" style="grid-column: 1 / -1; color: var(--color-danger);">Error al cargar galería: ${err.message}</p>`;
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
      btnTriggerPhotoScan.disabled = true;
      btnTriggerPhotoScan.innerHTML = '⚡ Escaneando en segundo plano...';

      try {
        const resp = await fetch('/api/photos/scan', { method: 'POST' });
        const data = await resp.json();

        if (data.success) {
          showToast('Escaneo concurrente de fotos iniciado en segundo plano.', 'info');
          const pollInterval = setInterval(async () => {
            try {
              const sResp = await fetch('/api/photos/scan/status');
              const sData = await sResp.json();
              if (!sData.running) {
                clearInterval(pollInterval);
                btnTriggerPhotoScan.disabled = false;
                btnTriggerPhotoScan.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Sincronizar Fotos desde Nube</span>';
                showToast(`Escaneo finalizado: ${sData.downloaded} fotos descargadas.`, 'success');
                loadPhotosStats();
                loadPhotosGallery(activePhotoFilter, activeLevelFilter);
              }
            } catch (e) {
              clearInterval(pollInterval);
              btnTriggerPhotoScan.disabled = false;
              btnTriggerPhotoScan.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Sincronizar Fotos desde Nube</span>';
            }
          }, 3000);
        } else {
          showToast(`No se pudo iniciar el escaneo: ${data.message}`, 'error');
          btnTriggerPhotoScan.disabled = false;
          btnTriggerPhotoScan.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Sincronizar Fotos desde Nube</span>';
        }
      } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
        btnTriggerPhotoScan.disabled = false;
        btnTriggerPhotoScan.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg><span>Sincronizar Fotos desde Nube</span>';
      }
    });
  }

  // ==========================================
  // PESTAÑA 5: HISTORIAL DE FICHAS
  // ==========================================
  const historyTbody = document.getElementById('history-tbody');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');

  async function loadHistory() {
    historyTbody.innerHTML = '<tr><td colspan="6" class="table-empty-row">Cargando bitácora de reseteos...</td></tr>';
    try {
      const resp = await fetch('/api/history');
      const data = await resp.json();
      const rows = data.history || [];

      if (rows.length === 0) {
        historyTbody.innerHTML = '<tr><td colspan="6" class="table-empty-row">No hay registros de reseteos aún en la bitácora.</td></tr>';
        return;
      }

      historyTbody.innerHTML = '';
      rows.forEach(r => {
        const tr = document.createElement('tr');
        const pdfLink = r.pdf_url
          ? `<a href="${r.pdf_url}" target="_blank" class="btn btn-sm btn-secondary-saas">📄 Ver Comprobante</a>`
          : `<span style="color: var(--text-muted);">No generada</span>`;

        tr.innerHTML = `
          <td class="mono">${r.timestamp_utc}</td>
          <td><strong class="highlight">${r.matricula}</strong></td>
          <td>${r.display_name}</td>
          <td class="mono">${r.upn}</td>
          <td><span class="badge badge-success">${r.reset_by}</span></td>
          <td class="text-right">${pdfLink}</td>
        `;
        historyTbody.appendChild(tr);
      });
    } catch (err) {
      historyTbody.innerHTML = `<tr><td colspan="6" class="table-empty-row" style="color: var(--color-danger);">Error al cargar historial: ${err.message}</td></tr>`;
    }
  }

  if (btnRefreshHistory) {
    btnRefreshHistory.addEventListener('click', loadHistory);
  }

  // ==========================================
  // PESTAÑA 6: SALUD DEL TENANT
  // ==========================================
  const tenantAdminUpn = document.getElementById('tenant-admin-upn');
  const tenantAuthType = document.getElementById('tenant-auth-type');
  const tenantDomainVerified = document.getElementById('tenant-domain-verified');
  const btnRefreshStatus = document.getElementById('btn-refresh-status');

  async function loadTenantStatus() {
    try {
      const resp = await fetch('/api/status');
      const data = await resp.json();
      if (data.success) {
        tenantAdminUpn.textContent = data.admin_upn || 'Conectado';
        tenantAuthType.textContent = data.auth_type || 'Managed';
        tenantDomainVerified.textContent = data.is_verified ? 'Verificado' : 'No verificado';
        tenantDomainVerified.className = data.is_verified ? 'chip-status-ok' : 'chip-status-danger';
        showToast('Diagnóstico de tenant actualizado.', 'info');
      } else {
        tenantAdminUpn.textContent = 'Error de conexión';
      }
    } catch (err) {
      tenantAdminUpn.textContent = 'Desconectado';
    }
  }

  if (btnRefreshStatus) {
    btnRefreshStatus.addEventListener('click', loadTenantStatus);
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
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<span style="color: var(--color-green); font-weight: 700;">✓ Copiado</span>';
        showToast(`Comando copiado: "${cmd}"`, 'success');

        setTimeout(() => {
          btn.innerHTML = originalHtml;
        }, 2000);
      } catch (err) {
        prompt('Copia el comando manualmente:', cmd);
      }
    });
  });
});
