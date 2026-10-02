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
    'tab-teams': 'Equipos & Clases Teams',
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
    } else if (targetTabId === 'tab-teams') {
      loadTeamsData();
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

  // Soporte para deep-linking vía hash (#tab-teams, #tab-photos, etc.)
  if (window.location.hash) {
    const targetHash = window.location.hash.substring(1);
    if (tabTitles[targetHash]) {
      switchTab(targetHash);
    }
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
      if (forceChangeCheckbox) forceChangeCheckbox.checked = true;
    });

    pwModeCustom.addEventListener('change', () => {
      customPwField.style.display = 'block';
      inputCustomPassword.focus();
      // Al asignar clave específica/personalizada, desactivar por defecto el cambio forzoso
      if (forceChangeCheckbox) forceChangeCheckbox.checked = false;
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
          force_change: forceChangeCheckbox ? forceChangeCheckbox.checked : true
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

        const resData = data.data || data;
        const newPw = resData.password || resData.new_password;
        const dispName = resData.display_name || resData.nombre_oficial;

        successStudentName.textContent = dispName;
        successStudentUpn.textContent = resData.upn;
        successPasswordVal.textContent = newPw;

        ticketName.textContent = dispName;
        ticketMatricula.textContent = resData.matricula;
        ticketLevel.textContent = resData.nivel || currentStudent.nivel || 'Estudiante';
        ticketUpn.textContent = resData.upn;
        ticketPassword.textContent = newPw;

        const ticketFooterStrip = document.querySelector('.ticket-footer-strip span');
        if (ticketFooterStrip) {
          if (forceChangeCheckbox && forceChangeCheckbox.checked) {
            ticketFooterStrip.textContent = 'ℹ️ El sistema te solicitará cambiar esta contraseña en tu primer inicio de sesión por una personal y confidencial.';
          } else {
            ticketFooterStrip.textContent = '✓ Contraseña permanente asignada. No requiere cambio en el primer inicio de sesión.';
          }
        }

        if (resData.pdf_filename) {
          btnPrintVoucher.href = `/api/pdf/${resData.pdf_filename}`;
          btnDownloadVoucher.href = `/api/pdf/${resData.pdf_filename}`;
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

  // =========================================================================
  // PESTAÑA 6: AUDITORÍA Y GESTIÓN DE EQUIPOS Y CLASES DE MICROSOFT TEAMS
  // =========================================================================
  let teamsCacheList = [];
  let teamsDataLoading = false;
  let filterCycle = 'all';
  let filterType = 'all';
  let filterCreator = 'all';
  let filterStatus = 'all';
  let teamsSearchQuery = '';
  let teamsSearchDebounce = null;
  let teachersList = [];
  let currentMembersTeamList = [];

  const teamsTableTbody = document.getElementById('teams-table-tbody');
  const teamsFilteredCount = document.getElementById('teams-filtered-count');
  const teamsSearchInput = document.getElementById('teams-search-input');
  const btnRefreshTeams = document.getElementById('btn-refresh-teams');
  const btnExportTeamsExcel = document.getElementById('btn-export-teams-excel');

  // KPIs elements
  const kpiTeamsTotal = document.getElementById('teams-kpi-total');
  const kpiTeamsActive = document.getElementById('teams-kpi-active2627');
  const kpiTeamsPast = document.getElementById('teams-kpi-pastcycles');
  const kpiTeamsAnomalies = document.getElementById('teams-kpi-anomalies');
  const kpiTeamsStudentOwned = document.getElementById('teams-kpi-studentowned');

  async function loadTeamsData(forceRefresh = false) {
    if (teamsDataLoading) return;
    teamsDataLoading = true;

    if (teamsTableTbody) {
      teamsTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row"><span style="display: inline-flex; align-items: center; gap: 8px;">Auditando equipos en Microsoft Teams en vivo...</span></td></tr>';
    }

    try {
      const url = '/api/teams' + (forceRefresh ? '?refresh=true' : '');
      const resp = await fetch(url);
      const res = await resp.json();

      if (res.success && res.data) {
        const d = res.data;
        teamsCacheList = d.teams || [];

        if (kpiTeamsTotal) kpiTeamsTotal.textContent = d.summary.total_teams || 0;
        if (kpiTeamsActive) kpiTeamsActive.textContent = d.summary.cycle_2026_2027 || 0;
        if (kpiTeamsPast) kpiTeamsPast.textContent = d.summary.past_cycles || 0;
        if (kpiTeamsAnomalies) kpiTeamsAnomalies.textContent = (d.summary.empty_teams || 0) + (d.summary.orphan_teams || 0);
        if (kpiTeamsStudentOwned) kpiTeamsStudentOwned.textContent = d.summary.student_owned_teams || 0;

        applyTeamsFilters();

        if (forceRefresh) {
          showToast('Auditoría de Teams actualizada con éxito.', 'success');
        }
      } else {
        if (teamsTableTbody) {
          teamsTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error al auditar equipos: ${res.error || 'Error desconocido'}</td></tr>`;
        }
        showToast('Error al auditar equipos de Teams: ' + (res.error || ''), 'error');
      }
    } catch (err) {
      if (teamsTableTbody) {
        teamsTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error de conexión: ${err.message}</td></tr>`;
      }
      showToast('Error al conectar con el servidor: ' + err.message, 'error');
    } finally {
      teamsDataLoading = false;
    }
  }

  function applyTeamsFilters() {
    if (!teamsCacheList) return;

    const q = teamsSearchQuery.trim().toLowerCase();

    const filtered = teamsCacheList.filter(t => {
      // 1. Filtro de búsqueda libre
      if (q) {
        const nameMatch = (t.name || '').toLowerCase().includes(q);
        const descMatch = (t.description || '').toLowerCase().includes(q);
        const idMatch = (t.id || '').toLowerCase().includes(q);
        const ownersMatch = (t.owners || []).some(o =>
          (o.name || '').toLowerCase().includes(q) || (o.upn || '').toLowerCase().includes(q)
        );
        if (!nameMatch && !descMatch && !idMatch && !ownersMatch) {
          return false;
        }
      }

      // 2. Filtro de Ciclo
      const cycleVal = t.academic_cycle || t.cycle || '';
      if (filterCycle !== 'all' && cycleVal !== filterCycle) {
        return false;
      }

      // 3. Filtro de Tipo
      if (filterType !== 'all' && t.team_type !== filterType) {
        return false;
      }

      // 4. Filtro de Creador / Origen
      if (filterCreator !== 'all' && t.creator_type !== filterCreator) {
        return false;
      }

      // 5. Filtro de Estado
      const countForStatus = (t.students_count !== undefined) ? t.students_count : ((t.members_count !== undefined) ? t.members_count : (t.member_count || 0));
      if (filterStatus === 'active' && countForStatus === 0) {
        return false;
      }
      if (filterStatus === 'vacio' && countForStatus > 0) {
        return false;
      }

      return true;
    });

    if (teamsFilteredCount) {
      teamsFilteredCount.textContent = `Mostrando ${filtered.length} de ${teamsCacheList.length} equipos`;
    }

    renderTeamsTable(filtered);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderTeamsTable(teams) {
    if (!teamsTableTbody) return;

    if (teams.length === 0) {
      teamsTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row">No se encontraron equipos que coincidan con los filtros seleccionados.</td></tr>';
      return;
    }

    teamsTableTbody.innerHTML = '';

    teams.forEach(t => {
      const tr = document.createElement('tr');

      // Badges de Ciclo
      const cycleVal = t.academic_cycle || t.cycle || '2026-2027';
      let cycleBadge = '<span class="badge badge-gray">Otro</span>';
      if (cycleVal === '2026-2027') {
        cycleBadge = '<span class="badge badge-green">26-27</span>';
      } else if (cycleVal === '2025-2026') {
        cycleBadge = '<span class="badge badge-blue">25-26</span>';
      }

      // Badges de Tipo
      let typeBadge = '<span class="badge badge-gray">General</span>';
      if (t.team_type === 'CLASE') {
        typeBadge = '<span class="badge badge-purple">Clase</span>';
      } else if (t.team_type === 'DOCENTES') {
        typeBadge = '<span class="badge badge-blue">Docentes</span>';
      }

      // Propietarios
      let ownersHtml = '';
      if (!t.owners || t.owners.length === 0) {
        ownersHtml = '<span class="owner-orphan-tag">⚠️ Huérfano (0 Propietarios)</span>';
      } else {
        const ownerNames = t.owners.map(o => escapeHtml(o.name || o.upn)).join(', ');
        ownersHtml = `<div class="owners-tag-list" title="${escapeHtml(ownerNames)}"><strong>${escapeHtml(t.owners[0].name || t.owners[0].upn)}</strong>${t.owners.length > 1 ? `<span style="font-size:0.72rem; color:var(--text-muted);">+${t.owners.length - 1} más</span>` : ''}</div>`;
      }

      // Creador / Origen
      let creatorHtml = '';
      if (t.creator_type === 'MAESTRO_STAFF') {
        creatorHtml = '<span class="badge badge-green">Docente / Staff</span>';
      } else if (t.creator_type === 'ALUMNO') {
        creatorHtml = `<span class="badge badge-purple" title="Propietario estudiantil">Alumno (${t.owners && t.owners[0] ? escapeHtml(t.owners[0].upn.split('@')[0]) : ''})</span>`;
      } else {
        creatorHtml = '<span class="badge badge-amber">Huérfano</span>';
      }

      // Alumnos / Miembros
      const studentCount = (t.students_count !== undefined) ? t.students_count : ((t.members_count !== undefined) ? t.members_count : (t.member_count || 0));
      const memberCount = (t.members_count !== undefined) ? t.members_count : (t.member_count !== undefined ? t.member_count : studentCount);
      const memberBadgeClass = studentCount > 0 ? 'badge-green' : 'badge-amber';
      const membersBadge = `<span class="badge ${memberBadgeClass}" title="${memberCount} miembros totales en Teams">${studentCount}</span>`;

      // Fecha creación
      const rawDate = t.created_date_str || t.created_date || t.created_datetime || '';
      const createdDate = rawDate ? rawDate.substring(0, 10) : 'N/D';

      // Nombre y descripción
      const isArchived = Boolean(t.is_archived);
      const archivedIcon = isArchived ? '<span title="Archivado / Solo lectura" style="font-size: 0.8rem; margin-right: 4px;">🔒</span>' : '';
      const descHtml = t.description ? `<span class="team-desc-muted" title="${escapeHtml(t.description)}">${escapeHtml(t.description)}</span>` : '';

      tr.innerHTML = `
        <td>
          <div class="team-title-cell">
            <span class="team-name-primary">${archivedIcon}${escapeHtml(t.name)}</span>
            ${descHtml}
          </div>
        </td>
        <td>${cycleBadge}</td>
        <td>${typeBadge}</td>
        <td>${ownersHtml}</td>
        <td class="text-center">${membersBadge}</td>
        <td>${creatorHtml}</td>
        <td class="mono" style="font-size: 0.78rem;">${createdDate}</td>
        <td class="text-right">
          <div class="team-actions-cell">
            <button type="button" class="btn-action-sm btn-assignments" data-id="${t.id}" data-name="${escapeHtml(t.name)}" title="Ver tareas y actividades académicas">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
              <span>Tareas</span>
            </button>
            <button type="button" class="btn-action-sm btn-roster" data-id="${t.id}" data-name="${escapeHtml(t.name)}" title="Sincronizar y auditar alumnos de la nómina escolar">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
              <span>Roster</span>
            </button>
            <button type="button" class="btn-action-sm btn-rename" data-id="${t.id}" title="Renombrar equipo">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              <span>Renombrar</span>
            </button>
            <button type="button" class="btn-action-sm btn-members" data-id="${t.id}" title="Ver alumnos y docentes">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
              <span>Integrantes</span>
            </button>
            <button type="button" class="btn-action-sm btn-archive" data-id="${t.id}" data-archived="${isArchived ? 'true' : 'false'}" title="${isArchived ? 'Desarchivar' : 'Archivar (Solo lectura)'}">
              <span>${isArchived ? '🔓 Desarchivar' : '📦 Archivar'}</span>
            </button>
          </div>
        </td>
      `;

      teamsTableTbody.appendChild(tr);
    });

    // Wire action buttons
    teamsTableTbody.querySelectorAll('.btn-assignments').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-id');
        const teamName = btn.getAttribute('data-name');
        openAssignmentsModal(teamId, teamName);
      });
    });

    teamsTableTbody.querySelectorAll('.btn-roster').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-id');
        const teamName = btn.getAttribute('data-name');
        openRosterModal(teamId, teamName);
      });
    });

    teamsTableTbody.querySelectorAll('.btn-rename').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-id');
        openRenameModal(teamId);
      });
    });

    teamsTableTbody.querySelectorAll('.btn-members').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-id');
        openMembersModal(teamId);
      });
    });

    teamsTableTbody.querySelectorAll('.btn-archive').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-id');
        const isArchived = btn.getAttribute('data-archived') === 'true';
        toggleArchiveTeam(teamId, isArchived);
      });
    });
  }

  // Configuración de Filtros tipo Pill
  function setupPillFilters(containerId, activeCallback) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const buttons = container.querySelectorAll('.pill-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCallback(btn);
        applyTeamsFilters();
      });
    });
  }

  setupPillFilters('filter-group-cycle', btn => {
    filterCycle = btn.getAttribute('data-cycle');
  });

  setupPillFilters('filter-group-type', btn => {
    filterType = btn.getAttribute('data-type');
  });

  setupPillFilters('filter-group-creator', btn => {
    filterCreator = btn.getAttribute('data-creator');
  });

  setupPillFilters('filter-group-status', btn => {
    filterStatus = btn.getAttribute('data-status');
  });

  // Búsqueda en tiempo real
  if (teamsSearchInput) {
    teamsSearchInput.addEventListener('input', e => {
      clearTimeout(teamsSearchDebounce);
      teamsSearchDebounce = setTimeout(() => {
        teamsSearchQuery = e.target.value;
        applyTeamsFilters();
      }, 200);
    });
  }

  if (btnRefreshTeams) {
    btnRefreshTeams.addEventListener('click', () => {
      loadTeamsData(true);
    });
  }

  if (btnExportTeamsExcel) {
    btnExportTeamsExcel.addEventListener('click', () => {
      showToast('Generando libro Excel de auditoría consolidada...', 'info');
      window.location.href = '/api/teams/export-excel';
    });
  }

  // ==========================================
  // MODAL 1: CREAR NUEVA CLASE EDUCATIVA
  // ==========================================
  const modalCreateClass = document.getElementById('modal-create-class');
  const btnOpenCreateClass = document.getElementById('btn-open-create-class-modal');
  const btnCloseModalCreate = document.getElementById('btn-close-modal-create');
  const btnCancelCreateClass = document.getElementById('btn-cancel-create-class');
  const btnSubmitCreateClass = document.getElementById('btn-submit-create-class');

  const inputClassSubject = document.getElementById('input-class-subject');
  const selectClassNivel = document.getElementById('select-class-nivel');
  const selectClassGrado = document.getElementById('select-class-grado');
  const selectClassTeacher = document.getElementById('select-class-teacher');
  const inputClassDesc = document.getElementById('input-class-desc');

  const previewContainer = document.getElementById('create-class-preview-container');
  const previewCount = document.getElementById('create-class-preview-count');
  const chipsList = document.getElementById('create-class-chips-list');
  const modalCreateAlert = document.getElementById('modal-create-alert');

  const gradosPorNivel = {
    'Preparatoria': ['1er Semestre', '2do Semestre', '3er Semestre', '4to Semestre', '5to Semestre', '6to Semestre'],
    'Secundaria': ['1° Secundaria', '2° Secundaria', '3° Secundaria'],
    'Primaria': ['1° Primaria', '2° Primaria', '3° Primaria', '4° Primaria', '5° Primaria', '6° Primaria'],
    'Preescolar': ['1° Preescolar', '2° Preescolar', '3° Preescolar']
  };

  async function loadTeachersDropdown() {
    if (teachersList.length > 0) return;
    try {
      const resp = await fetch('/api/teams/teachers');
      const res = await resp.json();
      if (res.success && res.teachers) {
        teachersList = res.teachers;
        if (selectClassTeacher) {
          selectClassTeacher.innerHTML = '<option value="">-- Seleccionar Profesor Titular --</option>';
          teachersList.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            const name = t.displayName || t.display_name || t.name || 'Docente';
            const email = t.userPrincipalName || t.user_principal_name || t.mail || t.upn || '';
            opt.textContent = email ? `${name} (${email})` : name;
            selectClassTeacher.appendChild(opt);
          });
        }
      }
    } catch (err) {
      if (selectClassTeacher) {
        selectClassTeacher.innerHTML = '<option value="">Error al cargar docentes</option>';
      }
    }
  }

  function resetCreateClassModal() {
    if (inputClassSubject) inputClassSubject.value = '';
    if (selectClassNivel) selectClassNivel.value = '';
    if (selectClassGrado) {
      selectClassGrado.innerHTML = '<option value="">-- Primero elija nivel --</option>';
      selectClassGrado.disabled = true;
    }
    if (inputClassDesc) inputClassDesc.value = '';
    if (previewContainer) previewContainer.style.display = 'none';
    if (chipsList) chipsList.innerHTML = '';
    if (modalCreateAlert) {
      modalCreateAlert.style.display = 'none';
      modalCreateAlert.textContent = '';
    }
    if (btnSubmitCreateClass) {
      btnSubmitCreateClass.disabled = true;
      btnSubmitCreateClass.innerHTML = '<span>Crear Clase en Microsoft Teams</span>';
    }
  }

  if (btnOpenCreateClass) {
    btnOpenCreateClass.addEventListener('click', () => {
      resetCreateClassModal();
      loadTeachersDropdown();
      if (modalCreateClass) modalCreateClass.style.display = 'flex';
    });
  }

  function closeCreateClassModal() {
    if (modalCreateClass) modalCreateClass.style.display = 'none';
    resetCreateClassModal();
  }

  if (btnCloseModalCreate) btnCloseModalCreate.addEventListener('click', closeCreateClassModal);
  if (btnCancelCreateClass) btnCancelCreateClass.addEventListener('click', closeCreateClassModal);

  if (selectClassNivel) {
    selectClassNivel.addEventListener('change', () => {
      const nivel = selectClassNivel.value;
      if (!nivel || !gradosPorNivel[nivel]) {
        selectClassGrado.innerHTML = '<option value="">-- Primero elija nivel --</option>';
        selectClassGrado.disabled = true;
        previewContainer.style.display = 'none';
        validateCreateForm();
        return;
      }

      selectClassGrado.innerHTML = '<option value="">-- Seleccionar Grado --</option>';
      gradosPorNivel[nivel].forEach(g => {
        const opt = document.createElement('option');
        opt.value = g;
        opt.textContent = g;
        selectClassGrado.appendChild(opt);
      });
      selectClassGrado.disabled = false;
      previewContainer.style.display = 'none';
      validateCreateForm();
    });
  }

  async function updatePreviewStudents() {
    const nivel = selectClassNivel ? selectClassNivel.value : '';
    const grado = selectClassGrado ? selectClassGrado.value : '';

    if (!nivel || !grado) {
      if (previewContainer) previewContainer.style.display = 'none';
      validateCreateForm();
      return;
    }

    if (previewContainer) previewContainer.style.display = 'block';
    if (chipsList) chipsList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">Cargando lista de alumnos del grado...</span>';

    try {
      const url = `/api/teams/students-by-grade?nivel=${encodeURIComponent(nivel)}&grado=${encodeURIComponent(grado)}`;
      const resp = await fetch(url);
      const res = await resp.json();

      if (res.success && res.students) {
        if (previewCount) previewCount.textContent = `${res.count} Alumnos`;
        if (chipsList) {
          if (res.students.length === 0) {
            chipsList.innerHTML = '<span style="color: var(--color-amber); font-size: 0.8rem;">No se encontraron alumnos registrados para este grado en la base institucional.</span>';
          } else {
            chipsList.innerHTML = '';
            res.students.forEach(st => {
              const chip = document.createElement('div');
              chip.className = 'student-chip';
              chip.innerHTML = `<span class="chip-mat">${escapeHtml(st.matricula)}</span><span>${escapeHtml(st.display_name)}</span>`;
              chipsList.appendChild(chip);
            });
          }
        }
      }
    } catch (err) {
      if (chipsList) chipsList.innerHTML = `<span style="color: var(--color-danger); font-size: 0.8rem;">Error al obtener alumnos: ${err.message}</span>`;
    }
    validateCreateForm();
  }

  if (selectClassGrado) {
    selectClassGrado.addEventListener('change', updatePreviewStudents);
  }

  function validateCreateForm() {
    const subject = inputClassSubject ? inputClassSubject.value.trim() : '';
    const nivel = selectClassNivel ? selectClassNivel.value : '';
    const grado = selectClassGrado ? selectClassGrado.value : '';
    const teacher = selectClassTeacher ? selectClassTeacher.value : '';

    const isValid = Boolean(subject && nivel && grado && teacher);
    if (btnSubmitCreateClass) {
      btnSubmitCreateClass.disabled = !isValid;
    }
  }

  if (inputClassSubject) inputClassSubject.addEventListener('input', validateCreateForm);
  if (selectClassTeacher) selectClassTeacher.addEventListener('change', validateCreateForm);

  if (btnSubmitCreateClass) {
    btnSubmitCreateClass.addEventListener('click', async () => {
      const subject = inputClassSubject.value.trim();
      const nivel = selectClassNivel.value;
      const grado = selectClassGrado.value;
      const teacherId = selectClassTeacher.value;
      const desc = inputClassDesc ? inputClassDesc.value.trim() : '';

      if (!subject || !nivel || !grado || !teacherId) {
        showToast('Por favor completa todos los campos obligatorios.', 'error');
        return;
      }

      btnSubmitCreateClass.disabled = true;
      btnSubmitCreateClass.innerHTML = '<span style="display: inline-flex; align-items: center; gap: 8px;">Creando clase y matriculando alumnos en M365...</span>';
      if (modalCreateAlert) modalCreateAlert.style.display = 'none';

      try {
        const resp = await fetch('/api/teams/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject_name: subject,
            nivel: nivel,
            grado: grado,
            teacher_id: teacherId,
            description: desc
          })
        });
        const res = await resp.json();

        if (res.success && res.result) {
          const r = res.result;
          showToast(`Clase "${r.team_name}" creada con éxito en Teams con ${r.students_enrolled_count} alumnos.`, 'success');
          closeCreateClassModal();
          loadTeamsData(true);
        } else {
          if (modalCreateAlert) {
            modalCreateAlert.style.display = 'block';
            modalCreateAlert.className = 'saas-alert-banner alert-danger';
            modalCreateAlert.textContent = `Error al crear clase: ${res.error || 'Ocurrió un error inesperado'}`;
          }
          btnSubmitCreateClass.disabled = false;
          btnSubmitCreateClass.innerHTML = '<span>Crear Clase en Microsoft Teams</span>';
        }
      } catch (err) {
        if (modalCreateAlert) {
          modalCreateAlert.style.display = 'block';
          modalCreateAlert.className = 'saas-alert-banner alert-danger';
          modalCreateAlert.textContent = `Error de red: ${err.message}`;
        }
        btnSubmitCreateClass.disabled = false;
        btnSubmitCreateClass.innerHTML = '<span>Crear Clase en Microsoft Teams</span>';
      }
    });
  }

  // ==========================================
  // MODAL 2: RENOMBRAR EQUIPO EN TEAMS
  // ==========================================
  const modalRenameTeam = document.getElementById('modal-rename-team');
  const btnCloseModalRename = document.getElementById('btn-close-modal-rename');
  const btnCancelRenameTeam = document.getElementById('btn-cancel-rename-team');
  const btnSubmitRenameTeam = document.getElementById('btn-submit-rename-team');

  const renameTeamId = document.getElementById('rename-team-id');
  const renameCurrentName = document.getElementById('rename-current-name');
  const renameNewName = document.getElementById('rename-new-name');
  const renameNewDesc = document.getElementById('rename-new-desc');
  const modalRenameAlert = document.getElementById('modal-rename-alert');

  function openRenameModal(teamId) {
    const team = teamsCacheList.find(t => t.id === teamId);
    if (!team) return;

    if (renameTeamId) renameTeamId.value = team.id;
    if (renameCurrentName) renameCurrentName.value = team.name;
    if (renameNewName) renameNewName.value = team.name;
    if (renameNewDesc) renameNewDesc.value = team.description || '';
    if (modalRenameAlert) {
      modalRenameAlert.style.display = 'none';
      modalRenameAlert.textContent = '';
    }
    if (btnSubmitRenameTeam) {
      btnSubmitRenameTeam.disabled = false;
      btnSubmitRenameTeam.innerHTML = '<span>Guardar Cambios</span>';
    }

    if (modalRenameTeam) modalRenameTeam.style.display = 'flex';
    if (renameNewName) {
      setTimeout(() => renameNewName.focus(), 150);
    }
  }

  function closeRenameModal() {
    if (modalRenameTeam) modalRenameTeam.style.display = 'none';
  }

  if (btnCloseModalRename) btnCloseModalRename.addEventListener('click', closeRenameModal);
  if (btnCancelRenameTeam) btnCancelRenameTeam.addEventListener('click', closeRenameModal);

  if (btnSubmitRenameTeam) {
    btnSubmitRenameTeam.addEventListener('click', async () => {
      const teamId = renameTeamId ? renameTeamId.value : '';
      const newName = renameNewName ? renameNewName.value.trim() : '';
      const newDesc = renameNewDesc ? renameNewDesc.value.trim() : '';

      if (!teamId || !newName) {
        showToast('El nombre no puede estar vacío.', 'error');
        return;
      }

      btnSubmitRenameTeam.disabled = true;
      btnSubmitRenameTeam.innerHTML = '<span>Guardando cambios en M365...</span>';
      if (modalRenameAlert) modalRenameAlert.style.display = 'none';

      try {
        const resp = await fetch(`/api/teams/${teamId}/rename`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            new_name: newName,
            new_description: newDesc
          })
        });
        const res = await resp.json();

        if (res.success) {
          showToast(`Equipo renombrado a "${newName}" con éxito.`, 'success');
          // Actualizar en memoria local
          const team = teamsCacheList.find(t => t.id === teamId);
          if (team) {
            team.name = newName;
            team.description = newDesc;
          }
          applyTeamsFilters();
          closeRenameModal();
        } else {
          if (modalRenameAlert) {
            modalRenameAlert.style.display = 'block';
            modalRenameAlert.className = 'saas-alert-banner alert-danger';
            modalRenameAlert.textContent = `Error: ${res.error || 'No se pudo renombrar el equipo'}`;
          }
          btnSubmitRenameTeam.disabled = false;
          btnSubmitRenameTeam.innerHTML = '<span>Guardar Cambios</span>';
        }
      } catch (err) {
        if (modalRenameAlert) {
          modalRenameAlert.style.display = 'block';
          modalRenameAlert.className = 'saas-alert-banner alert-danger';
          modalRenameAlert.textContent = `Error de conexión: ${err.message}`;
        }
        btnSubmitRenameTeam.disabled = false;
        btnSubmitRenameTeam.innerHTML = '<span>Guardar Cambios</span>';
      }
    });
  }

  // ==========================================
  // MODAL 3: DETALLE DE INTEGRANTES DE EQUIPO
  // ==========================================
  const modalTeamMembers = document.getElementById('modal-team-members');
  const btnCloseModalMembers = document.getElementById('btn-close-modal-members');
  const btnCloseMembersModal = document.getElementById('btn-close-members-modal');
  const membersModalTeamName = document.getElementById('members-modal-team-name');
  const membersModalTeamMeta = document.getElementById('members-modal-team-meta');
  const membersTeachersRow = document.getElementById('members-teachers-row');
  const membersStudentCount = document.getElementById('members-student-count');
  const filterMembersSubsearch = document.getElementById('filter-members-subsearch');
  const membersStudentsTbody = document.getElementById('members-students-tbody');

  function closeMembersModal() {
    if (modalTeamMembers) modalTeamMembers.style.display = 'none';
  }

  if (btnCloseModalMembers) btnCloseModalMembers.addEventListener('click', closeMembersModal);
  if (btnCloseMembersModal) btnCloseMembersModal.addEventListener('click', closeMembersModal);

  async function openMembersModal(teamId) {
    const team = teamsCacheList.find(t => t.id === teamId);
    if (!team) return;

    if (membersModalTeamName) membersModalTeamName.textContent = team.name;
    if (membersModalTeamMeta) {
      membersModalTeamMeta.textContent = `ID: ${team.id} • Tipo: ${team.team_type} • Ciclo: ${team.academic_cycle}`;
    }
    if (membersTeachersRow) {
      membersTeachersRow.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">Cargando propietarios...</span>';
    }
    if (membersStudentCount) membersStudentCount.textContent = '...';
    if (filterMembersSubsearch) filterMembersSubsearch.value = '';
    if (membersStudentsTbody) {
      membersStudentsTbody.innerHTML = '<tr><td colspan="4" class="table-empty-row">Consultando padrón de integrantes en Microsoft Graph...</td></tr>';
    }

    if (modalTeamMembers) modalTeamMembers.style.display = 'flex';

    try {
      const resp = await fetch(`/api/teams/${teamId}/members`);
      const res = await resp.json();

      if (res.success && res.data) {
        const d = res.data;

        // Render Teachers
        if (membersTeachersRow) {
          if (!d.teachers || d.teachers.length === 0) {
            membersTeachersRow.innerHTML = '<span class="owner-orphan-tag">⚠️ No hay profesores propietarios asignados (Equipo Huérfano)</span>';
          } else {
            membersTeachersRow.innerHTML = '';
            d.teachers.forEach(tc => {
              const pill = document.createElement('div');
              pill.className = 'teacher-pill';
              const tcName = tc.displayName || tc.display_name || tc.name || 'Profesor';
              const tcUpn = tc.userPrincipalName || tc.user_principal_name || tc.upn || tc.mail || '';
              pill.innerHTML = `<span>👤 ${escapeHtml(tcName)}</span>` + (tcUpn ? `<span style="font-size: 0.72rem; opacity: 0.85;">(${escapeHtml(tcUpn)})</span>` : '');
              membersTeachersRow.appendChild(pill);
            });
          }
        }

        // Render Students
        currentMembersTeamList = d.students || [];
        if (membersStudentCount) membersStudentCount.textContent = currentMembersTeamList.length;
        renderMembersSubTable(currentMembersTeamList);
      } else {
        if (membersStudentsTbody) {
          membersStudentsTbody.innerHTML = `<tr><td colspan="4" class="table-empty-row" style="color: var(--color-danger);">Error al cargar integrantes: ${res.error || 'Desconocido'}</td></tr>`;
        }
      }
    } catch (err) {
      if (membersStudentsTbody) {
        membersStudentsTbody.innerHTML = `<tr><td colspan="4" class="table-empty-row" style="color: var(--color-danger);">Error de conexión: ${err.message}</td></tr>`;
      }
    }
  }

  function renderMembersSubTable(students) {
    if (!membersStudentsTbody) return;

    if (students.length === 0) {
      membersStudentsTbody.innerHTML = '<tr><td colspan="4" class="table-empty-row">No hay alumnos inscritos en este equipo.</td></tr>';
      return;
    }

    membersStudentsTbody.innerHTML = '';
    students.forEach(st => {
      const tr = document.createElement('tr');
      const mat = st.matricula || (st.userPrincipalName ? st.userPrincipalName.split('@')[0] : (st.user_principal_name ? st.user_principal_name.split('@')[0] : (st.upn ? st.upn.split('@')[0] : 'N/D')));
      const stName = st.displayName || st.display_name || st.name || 'Sin nombre';
      const stUpn = st.userPrincipalName || st.user_principal_name || st.upn || st.mail || '';
      tr.innerHTML = `
        <td><strong class="highlight mono">${escapeHtml(mat)}</strong></td>
        <td>${escapeHtml(stName)}</td>
        <td class="mono" style="font-size: 0.78rem;">${escapeHtml(stUpn)}</td>
        <td class="text-center"><span class="badge badge-outline">Estudiante</span></td>
      `;
      membersStudentsTbody.appendChild(tr);
    });
  }

  if (filterMembersSubsearch) {
    filterMembersSubsearch.addEventListener('input', e => {
      const q = e.target.value.trim().toLowerCase();
      if (!currentMembersTeamList) return;

      const filtered = currentMembersTeamList.filter(st => {
        const name = (st.displayName || st.display_name || st.name || '').toLowerCase();
        const upn = (st.userPrincipalName || st.user_principal_name || st.upn || st.mail || '').toLowerCase();
        const mat = (st.matricula || '').toLowerCase();
        return name.includes(q) || upn.includes(q) || mat.includes(q);
      });
      renderMembersSubTable(filtered);
    });
  }

  // ==========================================
  // ACCIÓN DE ARCHIVADO / DESARCHIVADO
  // ==========================================
  async function toggleArchiveTeam(teamId, isCurrentlyArchived) {
    const actionName = isCurrentlyArchived ? 'desarchivar' : 'archivar';
    const actionEndpoint = isCurrentlyArchived ? 'unarchive' : 'archive';

    const confirmMsg = isCurrentlyArchived
      ? '¿Deseas desarchivar este equipo y habilitar nuevamente la participación de alumnos y maestros?'
      : '¿Deseas archivar este equipo? Pasará a modo solo lectura y ningún integrante podrá escribir ni enviar tareas.';

    if (!confirm(confirmMsg)) return;

    showToast(`${isCurrentlyArchived ? 'Desarchivando' : 'Archivando'} equipo en Microsoft Teams...`, 'info');

    try {
      const resp = await fetch(`/api/teams/${teamId}/${actionEndpoint}`, { method: 'POST' });
      const res = await resp.json();

      if (res.success) {
        showToast(res.message, 'success');
        const team = teamsCacheList.find(t => t.id === teamId);
        if (team) {
          team.is_archived = !isCurrentlyArchived;
        }
        applyTeamsFilters();
      } else {
        showToast(`Error al ${actionName} equipo: ${res.error || 'Error'}`, 'error');
      }
    } catch (err) {
      showToast(`Error de conexión: ${err.message}`, 'error');
    }
  }

  // ==========================================
  // MODAL 4: EXPLORADOR DE TAREAS ESCOLARES (ASSIGNMENTS)
  // ==========================================
  const modalTeamAssignments = document.getElementById('modal-team-assignments');
  const btnCloseModalAssignments = document.getElementById('btn-close-modal-assignments');
  const btnCloseAssignmentsModalFooter = document.getElementById('btn-close-assignments-modal-footer');
  const assignmentsModalTeamName = document.getElementById('assignments-modal-team-name');
  const assignmentsModalTeamMeta = document.getElementById('assignments-modal-team-meta');
  const assignmentsCountBadge = document.getElementById('assignments-count-badge');
  const assignmentsTurninSummary = document.getElementById('assignments-turnin-summary');
  const assignmentsTbody = document.getElementById('assignments-tbody');
  const btnExportAssignmentsExcel = document.getElementById('btn-export-assignments-excel');

  function closeAssignmentsModal() {
    if (modalTeamAssignments) modalTeamAssignments.style.display = 'none';
  }

  if (btnCloseModalAssignments) btnCloseModalAssignments.addEventListener('click', closeAssignmentsModal);
  if (btnCloseAssignmentsModalFooter) btnCloseAssignmentsModalFooter.addEventListener('click', closeAssignmentsModal);
  if (modalTeamAssignments) {
    modalTeamAssignments.addEventListener('click', (e) => {
      if (e.target === modalTeamAssignments) closeAssignmentsModal();
    });
  }

  async function openAssignmentsModal(teamId, teamName) {
    const team = teamsCacheList.find(t => t.id === teamId);
    const titleName = team ? team.name : (teamName || 'Equipo');

    if (assignmentsModalTeamName) assignmentsModalTeamName.textContent = `Tareas: ${titleName}`;
    if (assignmentsModalTeamMeta) {
      assignmentsModalTeamMeta.textContent = `ID de Clase: ${teamId} • Consultando actividades en Microsoft Graph...`;
    }
    if (assignmentsCountBadge) assignmentsCountBadge.textContent = '...';
    if (assignmentsTurninSummary) assignmentsTurninSummary.textContent = 'Consultando...';
    if (assignmentsTbody) {
      assignmentsTbody.innerHTML = '<tr><td colspan="5" class="table-empty-row">Consultando tareas y entregas en Microsoft Graph...</td></tr>';
    }

    if (modalTeamAssignments) modalTeamAssignments.style.display = 'flex';

    try {
      const resp = await fetch(`/api/teams/${teamId}/assignments`);
      const res = await resp.json();

      if (res.success && res.data) {
        const d = res.data;
        if (assignmentsModalTeamMeta) {
          assignmentsModalTeamMeta.textContent = `ID de Clase: ${teamId} • Total actividades: ${d.total_assignments} • Tasa de entrega: ${d.turn_in_rate}%`;
        }
        if (assignmentsCountBadge) assignmentsCountBadge.textContent = d.total_assignments;
        if (assignmentsTurninSummary) {
          assignmentsTurninSummary.textContent = `${d.total_turned_in} de ${d.total_submissions} entregas registradas (${d.turn_in_rate}%)`;
        }

        renderAssignmentsTable(d.assignments || []);
      } else {
        if (assignmentsTbody) {
          assignmentsTbody.innerHTML = `<tr><td colspan="5" class="table-empty-row" style="color: var(--color-danger);">Error al consultar tareas: ${escapeHtml(res.error || 'No disponible')}</td></tr>`;
        }
      }
    } catch (err) {
      if (assignmentsTbody) {
        assignmentsTbody.innerHTML = `<tr><td colspan="5" class="table-empty-row" style="color: var(--color-danger);">Error de conexión: ${escapeHtml(err.message)}</td></tr>`;
      }
    }
  }

  function renderAssignmentsTable(assignments) {
    if (!assignmentsTbody) return;

    if (!assignments || assignments.length === 0) {
      assignmentsTbody.innerHTML = '<tr><td colspan="5" class="table-empty-row">No se encontraron tareas publicadas en esta clase.</td></tr>';
      return;
    }

    assignmentsTbody.innerHTML = '';
    assignments.forEach(a => {
      const tr = document.createElement('tr');

      // Due date
      let dueDateFormatted = 'Sin fecha límite';
      if (a.due_date) {
        try {
          const dt = new Date(a.due_date);
          dueDateFormatted = dt.toLocaleString('es-MX', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
          });
        } catch (e) {
          dueDateFormatted = a.due_date;
        }
      }

      // Status badge
      let statusBadge = '<span class="badge badge-gray">Borrador</span>';
      if (a.status === 'published' || a.status === 'assigned') {
        statusBadge = '<span class="badge badge-green">Asignada</span>';
      } else if (a.status === 'completed') {
        statusBadge = '<span class="badge badge-blue">Completada</span>';
      }

      // Points
      const pointsText = (a.points !== null && a.points !== undefined) ? `${a.points} pts` : '<span style="color: var(--text-muted); font-size: 0.8rem;">Sin ponderar</span>';

      // Turn in progress
      const subTotal = a.submissions_count || 0;
      const turnedIn = a.turned_in_count || 0;
      const rate = a.turn_in_rate || 0;
      const progressBadgeClass = rate >= 70 ? 'badge-green' : (rate >= 40 ? 'badge-amber' : 'badge-gray');

      let instructionSnippet = '';
      if (a.instructions) {
        const cleanText = a.instructions.replace(/<[^>]*>?/gm, '').trim();
        if (cleanText) {
          const short = cleanText.length > 80 ? cleanText.substring(0, 80) + '...' : cleanText;
          instructionSnippet = `<div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 3px;" title="${escapeHtml(cleanText)}">${escapeHtml(short)}</div>`;
        }
      }

      tr.innerHTML = `
        <td>
          <strong style="color: var(--text-primary); font-size: 0.88rem;">${escapeHtml(a.title || 'Sin título')}</strong>
          ${instructionSnippet}
        </td>
        <td class="mono" style="font-size: 0.8rem;">${dueDateFormatted}</td>
        <td class="text-center">${statusBadge}</td>
        <td class="text-center mono" style="font-size: 0.82rem;">${pointsText}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge ${progressBadgeClass}" style="min-width: 55px; text-align: center;">${turnedIn}/${subTotal}</span>
            <span style="font-size: 0.78rem; color: var(--text-muted);">${rate}%</span>
          </div>
        </td>
      `;
      assignmentsTbody.appendChild(tr);
    });
  }

  // Exportar informe oficial de tareas a PDF
  const btnExportAssignmentsPdf = document.getElementById('btn-export-assignments-pdf');
  const btnModalExportAssignmentsPdf = document.getElementById('btn-modal-export-assignments-pdf');

  function triggerAssignmentsPdfExport() {
    const cycle = (filterCycle && filterCycle !== 'all') ? filterCycle : '2026-2027';
    showToast('Generando informe ejecutivo institucional en PDF para dirección...', 'info');
    window.location.href = `/api/teams/assignments/export-pdf?cycle=${encodeURIComponent(cycle)}`;
  }

  if (btnExportAssignmentsPdf) {
    btnExportAssignmentsPdf.addEventListener('click', triggerAssignmentsPdfExport);
  }

  if (btnModalExportAssignmentsPdf) {
    btnModalExportAssignmentsPdf.addEventListener('click', triggerAssignmentsPdfExport);
  }

  // Exportar reporte de tareas a Excel
  if (btnExportAssignmentsExcel) {
    btnExportAssignmentsExcel.addEventListener('click', () => {
      const cycle = (filterCycle && filterCycle !== 'all') ? filterCycle : '2026-2027';
      showToast('Generando reporte de tareas escolares en Excel...', 'info');
      window.location.href = `/api/teams/assignments/export?cycle=${encodeURIComponent(cycle)}`;
    });
  }

  // ========================================================================
  // FASE 1: MONITOR PREDICTIVO DE LICENCIAS EN HEADER
  // ========================================================================
  const licensePill = document.getElementById('license-status-pill');
  const licenseDot = document.getElementById('license-dot');
  const licenseText = document.getElementById('license-header-text');

  async function loadLicenseStatus() {
    if (!licensePill || !licenseText) return;
    try {
      const resp = await fetch('/api/licenses/status');
      const data = await resp.json();
      if (data.status === 'success') {
        licensePill.className = `license-status-badge ${data.level}`;
        licenseText.textContent = `Licencias A1: ${data.student_available} libres`;
        licensePill.title = `${data.message} • Total libres: ${data.total_available}`;
      }
    } catch (e) {
      licenseText.textContent = 'Licencias A1: N/D';
    }
  }
  loadLicenseStatus();
  setInterval(loadLicenseStatus, 60000);

  // ========================================================================
  // FASE 1: BUSCADOR GLOBAL OMNIBAR (Ctrl + K)
  // ========================================================================
  const modalOmnibar = document.getElementById('modal-omnibar');
  const btnOpenOmnibar = document.getElementById('btn-open-omnibar');
  const btnCloseOmnibar = document.getElementById('btn-close-omnibar');
  const inputOmnibar = document.getElementById('omnibar-search-input');
  const containerOmnibar = document.getElementById('omnibar-results');
  let omnibarDebounceTimer = null;

  function openOmnibar() {
    if (!modalOmnibar) return;
    modalOmnibar.style.display = 'flex';
    if (inputOmnibar) {
      inputOmnibar.value = '';
      inputOmnibar.focus();
    }
    renderOmnibarPlaceholder();
  }

  function closeOmnibar() {
    if (!modalOmnibar) return;
    modalOmnibar.style.display = 'none';
  }

  if (btnOpenOmnibar) btnOpenOmnibar.addEventListener('click', openOmnibar);
  if (btnCloseOmnibar) btnCloseOmnibar.addEventListener('click', closeOmnibar);
  if (modalOmnibar) {
    modalOmnibar.addEventListener('click', (e) => {
      if (e.target === modalOmnibar) closeOmnibar();
    });
  }

  // Atajo de teclado global: Ctrl + K o Cmd + K, y Escape
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (modalOmnibar && modalOmnibar.style.display === 'flex') {
        closeOmnibar();
      } else {
        openOmnibar();
      }
    } else if (e.key === 'Escape' && modalOmnibar && modalOmnibar.style.display === 'flex') {
      closeOmnibar();
    }
  });

  function renderOmnibarPlaceholder(msg = 'Escribe al menos 2 letras o dígitos para buscar en tiempo real...') {
    if (!containerOmnibar) return;
    containerOmnibar.innerHTML = `
      <div class="omnibar-placeholder">
        <p>${escapeHtml(msg)}</p>
        <div class="omnibar-shortcuts-hint">
          <span><kbd>↑</kbd> <kbd>↓</kbd> Navegar</span>
          <span><kbd>ENTER</kbd> Ficha</span>
          <span><kbd>ESC</kbd> Cerrar</span>
        </div>
      </div>
    `;
  }

  if (inputOmnibar) {
    inputOmnibar.addEventListener('input', () => {
      clearTimeout(omnibarDebounceTimer);
      const query = inputOmnibar.value.trim();
      if (query.length < 2) {
        renderOmnibarPlaceholder();
        return;
      }

      containerOmnibar.innerHTML = '<div class="omnibar-placeholder"><p>Buscando en catálogo institucional y Entra ID...</p></div>';

      omnibarDebounceTimer = setTimeout(async () => {
        try {
          const resp = await fetch(`/api/students/search?q=${encodeURIComponent(query)}`);
          const data = await resp.json();
          if (data.success && data.results) {
            renderOmnibarResults(data.results);
          } else {
            renderOmnibarPlaceholder('No se encontraron alumnos con ese criterio.');
          }
        } catch (err) {
          renderOmnibarPlaceholder(`Error de búsqueda: ${err.message}`);
        }
      }, 200);
    });
  }

  function renderOmnibarResults(results) {
    if (!containerOmnibar) return;
    if (results.length === 0) {
      renderOmnibarPlaceholder('No se encontraron alumnos con ese criterio.');
      return;
    }

    containerOmnibar.innerHTML = '';
    results.forEach((st, idx) => {
      const card = document.createElement('div');
      card.className = `omnibar-result-card ${idx === 0 ? 'active' : ''}`;
      
      const initials = (st.name || 'AL').split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
      const avatarHtml = st.photo_url
        ? `<img src="${st.photo_url}" class="omnibar-avatar-img" alt="Foto">`
        : initials;

      const enabledBadge = st.account_enabled === false
        ? '<span class="badge badge-danger">Deshabilitada</span>'
        : (st.in_entra ? '<span class="badge badge-green">Activa</span>' : '<span class="badge badge-amber">Solo Lista</span>');

      card.innerHTML = `
        <div class="omnibar-result-info">
          <div class="omnibar-avatar-circle">${avatarHtml}</div>
          <div class="omnibar-details">
            <div class="omnibar-name-row">
              <span class="omnibar-student-name">${escapeHtml(st.name)}</span>
              <span class="omnibar-mat-pill">${escapeHtml(st.matricula)}</span>
              ${enabledBadge}
            </div>
            <div class="omnibar-meta-row">
              <span>${escapeHtml(st.grado)} • ${escapeHtml(st.nivel)}</span>
              <span> | ${escapeHtml(st.upn)}</span>
            </div>
          </div>
        </div>
        <div class="omnibar-actions">
          <button type="button" class="btn btn-secondary-saas btn-sm btn-omnibar-reset" title="Restablecer contraseña">
            <span>Reset Clave</span>
          </button>
        </div>
      `;

      card.querySelector('.btn-omnibar-reset').addEventListener('click', (e) => {
        e.stopPropagation();
        closeOmnibar();
        // Cambiar a la pestaña de reseteo y precargar matrícula
        const tabResetBtn = document.getElementById('tab-btn-reset');
        if (tabResetBtn) tabResetBtn.click();
        const searchInput = document.getElementById('search-matricula-input');
        if (searchInput) {
          searchInput.value = st.matricula;
          const searchBtn = document.getElementById('btn-verify-matricula');
          if (searchBtn) searchBtn.click();
        }
      });

      card.addEventListener('click', () => {
        closeOmnibar();
        const tabResetBtn = document.getElementById('tab-btn-reset');
        if (tabResetBtn) tabResetBtn.click();
        const searchInput = document.getElementById('search-matricula-input');
        if (searchInput) {
          searchInput.value = st.matricula;
          const searchBtn = document.getElementById('btn-verify-matricula');
          if (searchBtn) searchBtn.click();
        }
      });

      containerOmnibar.appendChild(card);
    });
  }

  // ========================================================================
  // FASE 1: SINCRONIZACIÓN Y AUDITORÍA DE ROSTER EN TEAMS
  // ========================================================================
  const modalRoster = document.getElementById('modal-roster-sync');
  const btnCloseModalRoster = document.getElementById('btn-close-modal-roster');
  const btnCloseRosterModal = document.getElementById('btn-close-roster-modal');
  const btnExecuteRosterSync = document.getElementById('btn-execute-roster-sync');
  const rosterAlertBanner = document.getElementById('roster-alert-banner');

  const rosterModalClassName = document.getElementById('roster-modal-class-name');
  const rosterModalClassMeta = document.getElementById('roster-modal-class-meta');

  const rKpiOfficial = document.getElementById('r-kpi-official');
  const rKpiTeam = document.getElementById('r-kpi-team');
  const rKpiSynced = document.getElementById('r-kpi-synced');
  const rKpiMissing = document.getElementById('r-kpi-missing');
  const rKpiUnexpected = document.getElementById('r-kpi-unexpected');
  const rKpiPercent = document.getElementById('r-kpi-percent');

  const rosterMissingBadge = document.getElementById('roster-missing-badge');
  const rosterMissingChips = document.getElementById('roster-missing-chips');
  const rosterUnexpectedBadge = document.getElementById('roster-unexpected-badge');
  const rosterUnexpectedChips = document.getElementById('roster-unexpected-chips');
  const rosterSyncedBadge = document.getElementById('roster-synced-badge');
  const rosterSyncedChips = document.getElementById('roster-synced-chips');
  const rosterSelectGrade = document.getElementById('roster-select-grade');

  let currentRosterTeamId = null;
  let currentRosterAuditData = null;

  function closeRosterModal() {
    if (!modalRoster) return;
    modalRoster.style.display = 'none';
    currentRosterTeamId = null;
    currentRosterAuditData = null;
  }

  if (btnCloseModalRoster) btnCloseModalRoster.addEventListener('click', closeRosterModal);
  if (btnCloseRosterModal) btnCloseRosterModal.addEventListener('click', closeRosterModal);
  if (modalRoster) {
    modalRoster.addEventListener('click', (e) => {
      if (e.target === modalRoster) closeRosterModal();
    });
  }

  if (rosterSelectGrade) {
    rosterSelectGrade.addEventListener('change', () => {
      if (!currentRosterTeamId) return;
      const val = rosterSelectGrade.value;
      const tName = currentRosterAuditData ? currentRosterAuditData.team_name : 'Clase';
      if (val) {
        const parts = val.split('|');
        openRosterModal(currentRosterTeamId, tName, parts[0], parts[1]);
      } else {
        openRosterModal(currentRosterTeamId, tName);
      }
    });
  }

  const btnRefreshRosterCloud = document.getElementById('btn-refresh-roster-cloud');
  const btnSyncMissingOnly = document.getElementById('btn-sync-missing-only');
  const btnRemoveUnexpectedOnly = document.getElementById('btn-remove-unexpected-only');
  const btnFooterRemoveUnexpected = document.getElementById('btn-footer-remove-unexpected');

  async function openRosterModal(teamId, teamName, overrideNivel = null, overrideGrado = null) {
    if (!modalRoster) return;
    currentRosterTeamId = teamId;
    modalRoster.style.display = 'flex';

    if (rosterModalClassName) rosterModalClassName.textContent = `Roster: ${teamName}`;
    if (rosterModalClassMeta) rosterModalClassMeta.textContent = 'Consultando miembros en Microsoft Teams y nómina escolar...';
    if (rosterAlertBanner) rosterAlertBanner.style.display = 'none';

    // Resetear KPIs
    [rKpiOfficial, rKpiTeam, rKpiSynced, rKpiMissing, rKpiUnexpected, rKpiPercent].forEach(el => {
      if (el) el.textContent = '...';
    });

    if (rosterMissingChips) rosterMissingChips.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">Analizando alumnos...</span>';
    if (rosterUnexpectedChips) rosterUnexpectedChips.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">Analizando alumnos...</span>';
    if (rosterSyncedChips) rosterSyncedChips.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">Analizando alumnos...</span>';

    try {
      let url = `/api/teams/${teamId}/roster/audit`;
      if (overrideNivel && overrideGrado) {
        url += `?nivel=${encodeURIComponent(overrideNivel)}&grado=${encodeURIComponent(overrideGrado)}`;
      }
      const resp = await fetch(url);
      const data = await resp.json();
      if (data.success && data.roster) {
        currentRosterAuditData = data.roster;
        renderRosterAudit(data.roster);
      } else {
        if (rosterAlertBanner) {
          rosterAlertBanner.style.display = 'block';
          rosterAlertBanner.className = 'saas-alert-banner alert-danger';
          rosterAlertBanner.textContent = `Error al auditar roster: ${data.error || 'Error desconocido'}`;
        }
      }
    } catch (err) {
      if (rosterAlertBanner) {
        rosterAlertBanner.style.display = 'block';
        rosterAlertBanner.className = 'saas-alert-banner alert-danger';
        rosterAlertBanner.textContent = `Error de red al consultar roster: ${err.message}`;
      }
    }
  }

  if (btnRefreshRosterCloud) {
    btnRefreshRosterCloud.addEventListener('click', () => {
      if (!currentRosterTeamId || !currentRosterAuditData) return;
      showToast('Actualizando auditoría en vivo desde Microsoft 365...', 'info');
      openRosterModal(
        currentRosterTeamId,
        currentRosterAuditData.team_name,
        currentRosterAuditData.nivel,
        currentRosterAuditData.grado
      );
    });
  }

  function renderRosterAudit(r) {
    if (rosterModalClassMeta) {
      rosterModalClassMeta.textContent = `${r.grado} • ${r.nivel} | Profesor Titular: ${r.teacher_name}`;
    }

    if (rosterSelectGrade) {
      if (r.nivel && r.grado && r.nivel !== 'Desconocido' && r.grado !== 'Desconocido') {
        const optionVal = `${r.nivel}|${r.grado}`;
        let optionExists = false;
        for (let i = 0; i < rosterSelectGrade.options.length; i++) {
          if (rosterSelectGrade.options[i].value === optionVal) {
            optionExists = true;
            break;
          }
        }
        if (optionExists) {
          rosterSelectGrade.value = optionVal;
        }
      } else {
        rosterSelectGrade.value = '';
        if (rosterAlertBanner) {
          rosterAlertBanner.style.display = 'block';
          rosterAlertBanner.className = 'saas-alert-banner alert-warning';
          rosterAlertBanner.textContent = 'Esta clase no tiene un grado explícito en su nombre. Por favor, selecciona el Grado Oficial en el selector superior para auditar la nómina de alumnos.';
        }
      }
    }

    if (rKpiOfficial) rKpiOfficial.textContent = r.official_count;
    if (rKpiTeam) rKpiTeam.textContent = r.team_count;
    if (rKpiSynced) rKpiSynced.textContent = r.synced_count;
    if (rKpiMissing) rKpiMissing.textContent = r.missing_count;
    if (rKpiUnexpected) rKpiUnexpected.textContent = r.unexpected_count;
    if (rKpiPercent) rKpiPercent.textContent = `${r.sync_percentage}%`;

    // 1. Faltantes
    if (rosterMissingBadge) rosterMissingBadge.textContent = `${r.missing_count} Alumnos Faltantes`;
    if (btnSyncMissingOnly) {
      if (r.missing_count > 0) {
        btnSyncMissingOnly.style.display = 'inline-flex';
        btnSyncMissingOnly.textContent = `Inscribir Faltantes (${r.missing_count})`;
      } else {
        btnSyncMissingOnly.style.display = 'none';
      }
    }
    if (rosterMissingChips) {
      if (r.missing_students.length === 0) {
        rosterMissingChips.innerHTML = '<span style="color: var(--color-green); font-size: 0.82rem;">Ninguno. Todos los alumnos oficiales están inscritos en el equipo.</span>';
      } else {
        rosterMissingChips.innerHTML = '';
        r.missing_students.forEach(st => {
          const chip = document.createElement('div');
          chip.className = 'student-chip chip-amber';
          chip.dataset.userId = st.user_id || '';
          chip.dataset.matricula = st.matricula || '';
          chip.dataset.name = st.name || '';
          chip.innerHTML = `
            <span class="chip-mat">${escapeHtml(st.matricula)}</span>
            <span>${escapeHtml(st.name)}</span>
            <button type="button" class="chip-action-btn btn-chip-add" data-user-id="${escapeHtml(st.user_id || '')}" data-matricula="${escapeHtml(st.matricula || '')}" data-name="${escapeHtml(st.name || '')}" title="Inscribir individualmente a ${escapeHtml(st.name)}">+ Inscribir</button>
          `;
          rosterMissingChips.appendChild(chip);
        });
      }
    }

    // 2. Inesperados / Bajas
    if (rosterUnexpectedBadge) rosterUnexpectedBadge.textContent = `${r.unexpected_count} Bajas / No pertenecen`;
    if (btnRemoveUnexpectedOnly) {
      if (r.unexpected_count > 0) {
        btnRemoveUnexpectedOnly.style.display = 'inline-flex';
        btnRemoveUnexpectedOnly.textContent = `Dar de Baja a Todos (${r.unexpected_count})`;
      } else {
        btnRemoveUnexpectedOnly.style.display = 'none';
      }
    }
    if (rosterUnexpectedChips) {
      if (r.unexpected_students.length === 0) {
        rosterUnexpectedChips.innerHTML = '<span style="color: var(--color-green); font-size: 0.82rem;">Ninguno. No hay cuentas de alumnos ajenas al grado actual.</span>';
      } else {
        rosterUnexpectedChips.innerHTML = '';
        r.unexpected_students.forEach(st => {
          const chip = document.createElement('div');
          chip.className = 'student-chip chip-red';
          chip.dataset.userId = st.user_id || '';
          chip.dataset.matricula = st.matricula || '';
          chip.dataset.name = st.name || '';
          chip.innerHTML = `
            <span class="chip-mat">${escapeHtml(st.matricula)}</span>
            <span>${escapeHtml(st.name)}</span>
            <button type="button" class="chip-action-btn btn-chip-remove" data-user-id="${escapeHtml(st.user_id || '')}" data-matricula="${escapeHtml(st.matricula || '')}" data-name="${escapeHtml(st.name || '')}" title="Desvincular a ${escapeHtml(st.name)} de este equipo">× Dar de Baja</button>
          `;
          rosterUnexpectedChips.appendChild(chip);
        });
      }
    }

    // 3. Sincronizados
    if (rosterSyncedBadge) rosterSyncedBadge.textContent = `${r.synced_count} Alumnos Sincronizados`;
    if (rosterSyncedChips) {
      if (r.synced_students.length === 0) {
        rosterSyncedChips.innerHTML = '<span style="color: var(--text-muted); font-size: 0.82rem;">Sin alumnos matriculados todavía.</span>';
      } else {
        rosterSyncedChips.innerHTML = '';
        r.synced_students.forEach(st => {
          const chip = document.createElement('div');
          chip.className = st.just_added ? 'student-chip chip-just-added' : 'student-chip';
          chip.innerHTML = `
            <span class="chip-mat">${escapeHtml(st.matricula)}</span>
            <span>${escapeHtml(st.name)}</span>
            ${st.just_added ? '<span style="font-size: 0.68rem; color: #10B981; font-weight: 700; margin-left: 4px;">Recién Inscrito</span>' : ''}
          `;
          rosterSyncedChips.appendChild(chip);
        });
      }
    }

    // Botones del footer
    if (btnFooterRemoveUnexpected) {
      if (r.unexpected_count > 0 && r.missing_count > 0) {
        btnFooterRemoveUnexpected.style.display = 'inline-flex';
        btnFooterRemoveUnexpected.disabled = false;
        btnFooterRemoveUnexpected.innerHTML = `<span>Dar de Baja No Pertenecientes (${r.unexpected_count})</span>`;
      } else {
        btnFooterRemoveUnexpected.style.display = 'none';
      }
    }

    if (btnExecuteRosterSync) {
      btnExecuteRosterSync.disabled = (r.missing_count === 0 && r.unexpected_count === 0);
      if (r.missing_count > 0 && r.unexpected_count > 0) {
        btnExecuteRosterSync.className = 'btn btn-primary-saas';
        btnExecuteRosterSync.innerHTML = `<span>Regularizar Todo (Inscribir ${r.missing_count} y Dar de Baja ${r.unexpected_count})</span>`;
      } else if (r.missing_count > 0) {
        btnExecuteRosterSync.className = 'btn btn-primary-saas';
        btnExecuteRosterSync.innerHTML = `<span>Inscribir ${r.missing_count} Alumno(s) Faltante(s)</span>`;
      } else if (r.unexpected_count > 0) {
        btnExecuteRosterSync.className = 'btn btn-danger-saas';
        btnExecuteRosterSync.innerHTML = `<span>Dar de Baja a ${r.unexpected_count} Alumno(s)</span>`;
      } else {
        btnExecuteRosterSync.className = 'btn btn-primary-saas';
        btnExecuteRosterSync.innerHTML = '<span>Nómina Sincronizada al 100%</span>';
      }
    }
  }

  // Helper centralizado para ejecución ágil y actualización optimista instantánea
  async function executeRosterSync(options) {
    if (!currentRosterTeamId || !currentRosterAuditData) return;

    const action = options.action || 'custom';
    const missingUserIds = options.missing_user_ids || null;
    const removeUserIds = options.remove_user_ids || null;

    // Deshabilitar controles interactivos durante la operación
    if (btnExecuteRosterSync) btnExecuteRosterSync.disabled = true;
    if (btnFooterRemoveUnexpected) btnFooterRemoveUnexpected.disabled = true;
    if (btnSyncMissingOnly) btnSyncMissingOnly.disabled = true;
    if (btnRemoveUnexpectedOnly) btnRemoveUnexpectedOnly.disabled = true;

    if (options.triggerBtn) {
      options.triggerBtn.dataset.originalText = options.triggerBtn.textContent;
      options.triggerBtn.textContent = 'Procesando...';
    }

    try {
      const resp = await fetch(`/api/teams/${currentRosterTeamId}/roster/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          nivel: currentRosterAuditData.nivel,
          grado: currentRosterAuditData.grado,
          missing_user_ids: missingUserIds,
          remove_user_ids: removeUserIds,
          audit_info: currentRosterAuditData
        })
      });

      const res = await resp.json();
      if (res.success && res.result) {
        const result = res.result;

        // Actualización optimista inmediata en memoria (cero latencia de replicación)
        if (result.added_students && result.added_students.length > 0) {
          const addedIds = new Set(result.added_students.map(s => s.user_id));
          const addedMats = new Set(result.added_students.map(s => s.matricula));

          // Mover de faltantes a sincronizados
          currentRosterAuditData.missing_students = currentRosterAuditData.missing_students.filter(
            s => !addedIds.has(s.user_id) && !addedMats.has(s.matricula)
          );

          result.added_students.forEach(st => {
            currentRosterAuditData.synced_students.push({
              ...st,
              just_added: true,
              status: 'SINCRONIZADO'
            });
          });
        }

        if (result.removed_students && result.removed_students.length > 0) {
          const removedIds = new Set(result.removed_students.map(s => s.user_id));
          const removedMats = new Set(result.removed_students.map(s => s.matricula));

          // Eliminar de inesperados / bajas
          currentRosterAuditData.unexpected_students = currentRosterAuditData.unexpected_students.filter(
            s => !removedIds.has(s.user_id) && !removedMats.has(s.matricula)
          );
        }

        // Recalcular métricas
        currentRosterAuditData.missing_count = currentRosterAuditData.missing_students.length;
        currentRosterAuditData.unexpected_count = currentRosterAuditData.unexpected_students.length;
        currentRosterAuditData.synced_count = currentRosterAuditData.synced_students.length;
        currentRosterAuditData.team_count = currentRosterAuditData.synced_count + currentRosterAuditData.unexpected_count;
        currentRosterAuditData.sync_percentage = currentRosterAuditData.official_count > 0
          ? Math.round((currentRosterAuditData.synced_count / currentRosterAuditData.official_count) * 1000) / 10
          : (currentRosterAuditData.team_count === 0 ? 100.0 : 0.0);
        currentRosterAuditData.is_synced = (currentRosterAuditData.missing_count === 0 && currentRosterAuditData.unexpected_count === 0);

        // Renderizar inmediatamente la vista actualizada
        renderRosterAudit(currentRosterAuditData);

        // Mensaje de éxito claro y profesional
        let feedbackMsg = '';
        if (result.added_count > 0 && result.removed_count > 0) {
          feedbackMsg = `Regularización exitosa: ${result.added_count} alumno(s) inscritos y ${result.removed_count} alumno(s) dados de baja.`;
        } else if (result.added_count > 0) {
          feedbackMsg = `Inscripción confirmada: ${result.added_count} alumno(s) agregados al equipo de Teams.`;
        } else if (result.removed_count > 0) {
          feedbackMsg = `Baja confirmada: ${result.removed_count} alumno(s) desvinculados exitosamente del equipo.`;
        } else {
          feedbackMsg = 'Operación procesada sin cambios requeridos.';
        }

        if (result.errors && result.errors.length > 0) {
          showToast(`${feedbackMsg} (Con advertencias: ${result.errors.join('; ')})`, 'warning');
          if (rosterAlertBanner) {
            rosterAlertBanner.style.display = 'block';
            rosterAlertBanner.className = 'saas-alert-banner alert-warning';
            rosterAlertBanner.textContent = `Advertencias reportadas por Microsoft Graph: ${result.errors.join(' | ')}`;
          }
        } else {
          showToast(feedbackMsg, 'success');
          if (rosterAlertBanner) rosterAlertBanner.style.display = 'none';
        }

        // En segundo plano tras 2.5 segundos (convergencia de replicación de Azure AD), actualizar la tabla de equipos
        setTimeout(() => {
          loadTeamsData(true);
        }, 2500);

      } else {
        showToast(`Error al procesar operación: ${res.error || 'Respuesta no válida'}`, 'error');
        if (rosterAlertBanner) {
          rosterAlertBanner.style.display = 'block';
          rosterAlertBanner.className = 'saas-alert-banner alert-danger';
          rosterAlertBanner.textContent = `Error: ${res.error || 'Error inesperado de Microsoft 365'}`;
        }
        if (btnExecuteRosterSync) btnExecuteRosterSync.disabled = false;
        if (btnFooterRemoveUnexpected) btnFooterRemoveUnexpected.disabled = false;
        if (btnSyncMissingOnly) btnSyncMissingOnly.disabled = false;
        if (btnRemoveUnexpectedOnly) btnRemoveUnexpectedOnly.disabled = false;
      }
    } catch (err) {
      showToast(`Error de conexión con el servidor: ${err.message}`, 'error');
      if (btnExecuteRosterSync) btnExecuteRosterSync.disabled = false;
      if (btnFooterRemoveUnexpected) btnFooterRemoveUnexpected.disabled = false;
      if (btnSyncMissingOnly) btnSyncMissingOnly.disabled = false;
      if (btnRemoveUnexpectedOnly) btnRemoveUnexpectedOnly.disabled = false;
    } finally {
      if (options.triggerBtn && options.triggerBtn.dataset.originalText) {
        options.triggerBtn.textContent = options.triggerBtn.dataset.originalText;
      }
    }
  }

  // Delegación de eventos para botones individuales en chips de alumnos
  if (rosterMissingChips) {
    rosterMissingChips.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-chip-add');
      if (!btn) return;
      const uId = btn.dataset.userId;
      const stName = btn.dataset.name || 'el alumno';
      if (!uId) {
        showToast('No se encontró el identificador de usuario en Entra ID para este alumno.', 'error');
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Inscribiendo...';
      executeRosterSync({
        action: 'add_single',
        missing_user_ids: [uId],
        triggerBtn: btn
      });
    });
  }

  if (rosterUnexpectedChips) {
    rosterUnexpectedChips.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-chip-remove');
      if (!btn) return;
      const uId = btn.dataset.userId;
      const stName = btn.dataset.name || 'este alumno';
      if (!uId) {
        showToast('No se encontró el identificador del usuario en Teams para procesar la baja.', 'error');
        return;
      }
      if (!confirm(`¿Confirmas dar de baja y desvincular a "${stName}" de este equipo de Teams?`)) {
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Desvinculando...';
      executeRosterSync({
        action: 'remove_single',
        remove_user_ids: [uId],
        triggerBtn: btn
      });
    });
  }

  // Botón: Inscribir Todos los Faltantes
  if (btnSyncMissingOnly) {
    btnSyncMissingOnly.addEventListener('click', () => {
      if (!currentRosterAuditData || currentRosterAuditData.missing_count === 0) return;
      executeRosterSync({
        action: 'add',
        triggerBtn: btnSyncMissingOnly
      });
    });
  }

  // Botón: Dar de Baja a Todos los No Pertenecientes (encabezado de sección)
  if (btnRemoveUnexpectedOnly) {
    btnRemoveUnexpectedOnly.addEventListener('click', () => {
      if (!currentRosterAuditData || currentRosterAuditData.unexpected_count === 0) return;
      if (!confirm(`¿Confirmas dar de baja a los ${currentRosterAuditData.unexpected_count} alumnos no pertenecientes de este equipo?`)) {
        return;
      }
      executeRosterSync({
        action: 'remove',
        triggerBtn: btnRemoveUnexpectedOnly
      });
    });
  }

  // Botón: Dar de Baja No Pertenecientes (pie de modal)
  if (btnFooterRemoveUnexpected) {
    btnFooterRemoveUnexpected.addEventListener('click', () => {
      if (!currentRosterAuditData || currentRosterAuditData.unexpected_count === 0) return;
      if (!confirm(`¿Confirmas dar de baja a los ${currentRosterAuditData.unexpected_count} alumnos no pertenecientes de este equipo?`)) {
        return;
      }
      executeRosterSync({
        action: 'remove',
        triggerBtn: btnFooterRemoveUnexpected
      });
    });
  }

  // Botón principal de pie de modal (Regularización Inteligente)
  if (btnExecuteRosterSync) {
    btnExecuteRosterSync.addEventListener('click', async () => {
      if (!currentRosterTeamId || !currentRosterAuditData) return;
      const mCount = currentRosterAuditData.missing_count || 0;
      const uCount = currentRosterAuditData.unexpected_count || 0;

      if (mCount === 0 && uCount === 0) return;

      if (mCount > 0 && uCount > 0) {
        if (!confirm(`Se inscribirán ${mCount} alumno(s) faltantes y se darán de baja ${uCount} alumno(s) no pertenecientes en este equipo. ¿Deseas continuar?`)) {
          return;
        }
        executeRosterSync({ action: 'both', triggerBtn: btnExecuteRosterSync });
      } else if (mCount > 0) {
        executeRosterSync({ action: 'add', triggerBtn: btnExecuteRosterSync });
      } else if (uCount > 0) {
        if (!confirm(`¿Confirmas dar de baja a ${uCount} alumno(s) no pertenecientes de este equipo?`)) {
          return;
        }
        executeRosterSync({ action: 'remove', triggerBtn: btnExecuteRosterSync });
      }
    });
  }

  // Exportar auditoría global de Roster a PDF y Excel
  const btnExportRosterPdf = document.getElementById('btn-export-roster-pdf');
  const btnExportRosterExcel = document.getElementById('btn-export-roster-excel');

  if (btnExportRosterPdf) {
    btnExportRosterPdf.addEventListener('click', () => {
      const cycle = (filterCycle && filterCycle !== 'all') ? filterCycle : '2026-2027';
      showToast('Generando informe oficial en PDF de auditoría de roster...', 'info');
      window.location.href = `/api/teams/roster/export-pdf?cycle=${encodeURIComponent(cycle)}`;
    });
  }

  if (btnExportRosterExcel) {
    btnExportRosterExcel.addEventListener('click', () => {
      const cycle = (filterCycle && filterCycle !== 'all') ? filterCycle : '2026-2027';
      showToast('Generando libro Excel de balance de roster de clases...', 'info');
      window.location.href = `/api/teams/roster/export-excel?cycle=${encodeURIComponent(cycle)}`;
    });
  }

  // =========================================================================
  // SUB-NAVEGACION DE TEAMS & SUBTABS
  // =========================================================================
  const teamsSubnavBtns = document.querySelectorAll('.teams-subnav-btn');
  const teamsSubtabPanes = document.querySelectorAll('.teams-subtab-pane');

  function switchTeamsSubtab(targetSubtabId) {
    teamsSubnavBtns.forEach(btn => {
      if (btn.getAttribute('data-subtab') === targetSubtabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    teamsSubtabPanes.forEach(pane => {
      if (pane.id === targetSubtabId) {
        pane.style.display = 'block';
        pane.classList.add('active');
      } else {
        pane.style.display = 'none';
        pane.classList.remove('active');
      }
    });

    if (targetSubtabId === 'teams-subtab-coverage') {
      loadTeamsCoverageAudit();
    } else if (targetSubtabId === 'teams-subtab-nomenclature') {
      loadTeamsNomenclatureAudit();
    }
  }

  teamsSubnavBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-subtab');
      if (target) switchTeamsSubtab(target);
    });
  });

  // =========================================================================
  // SUB-TAB 2: VERIFICADOR GLOBAL DE MATRICULA Y COBERTURA
  // =========================================================================
  let covAuditCache = null;
  let covLoading = false;
  let covSearchQuery = '';
  let covFilterStatus = 'all';
  let covFilterGrade = 'all';

  const covKpiTotal = document.getElementById('cov-kpi-students-total');
  const covKpiFull = document.getElementById('cov-kpi-full-coverage');
  const covKpiMissing = document.getElementById('cov-kpi-missing-coverage');
  const covKpiClasses = document.getElementById('cov-kpi-classes-count');
  const badgeCoverageUnmet = document.getElementById('badge-coverage-unmet');

  const covSearchInput = document.getElementById('cov-search-input');
  const covFilterGradeSelect = document.getElementById('cov-filter-grade');
  const covFilteredCount = document.getElementById('cov-filtered-count');
  const covTableTbody = document.getElementById('cov-table-tbody');
  const btnSyncGlobalCoverage = document.getElementById('btn-sync-global-coverage');
  const btnExportCoverageExcel = document.getElementById('btn-export-coverage-excel');
  const btnRefreshCoverage = document.getElementById('btn-refresh-coverage');

  async function loadTeamsCoverageAudit(forceRefresh = false) {
    if (covLoading) return;
    covLoading = true;

    if (covTableTbody) {
      covTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row">Consultando padron y membresias de Teams en tiempo real...</td></tr>';
    }

    try {
      const resp = await fetch('/api/teams/coverage/audit?cycle=2026-2027');
      const res = await resp.json();

      if (res.success && res.data) {
        covAuditCache = res.data;
        const s = res.data.summary || {};

        if (covKpiTotal) covKpiTotal.textContent = s.total_students_audited || 0;
        if (covKpiFull) covKpiFull.textContent = s.full_coverage_students || 0;
        if (covKpiMissing) covKpiMissing.textContent = s.unmet_coverage_students || 0;
        if (covKpiClasses) covKpiClasses.textContent = s.active_classes_evaluated || 0;

        if (badgeCoverageUnmet) {
          const unmet = s.unmet_coverage_students || 0;
          if (unmet > 0) {
            badgeCoverageUnmet.style.display = 'inline-flex';
            badgeCoverageUnmet.textContent = unmet;
          } else {
            badgeCoverageUnmet.style.display = 'none';
          }
        }

        applyCovFilters();

        if (forceRefresh) {
          showToast('Verificacion de cobertura actualizada.', 'success');
        }
      } else {
        if (covTableTbody) {
          covTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error: ${res.error || 'No se pudo cargar la verificacion'}</td></tr>`;
        }
        showToast('Error en verificador de cobertura: ' + (res.error || ''), 'error');
      }
    } catch (err) {
      if (covTableTbody) {
        covTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error de conexion: ${err.message}</td></tr>`;
      }
      showToast('Error al conectar con el servidor: ' + err.message, 'error');
    } finally {
      covLoading = false;
    }
  }

  function applyCovFilters() {
    if (!covAuditCache || !covAuditCache.students) return;

    const q = covSearchQuery.trim().toLowerCase();
    const students = covAuditCache.students;

    const filtered = students.filter(st => {
      // 1. Busqueda libre
      if (q) {
        const mat = (st.matricula || '').toLowerCase();
        const nom = (st.nombre || '').toLowerCase();
        const mail = (st.mail || '').toLowerCase();
        if (!mat.includes(q) && !nom.includes(q) && !mail.includes(q)) {
          return false;
        }
      }

      // 2. Filtro de estado
      if (covFilterStatus === 'missing' && st.coverage_status !== 'INCOMPLETO') {
        return false;
      }
      if (covFilterStatus === 'complete' && st.coverage_status !== 'COMPLETO') {
        return false;
      }
      if (covFilterStatus === 'extraneous' && (!st.extraneous_classes || st.extraneous_classes.length === 0)) {
        return false;
      }

      // 3. Filtro de grado
      if (covFilterGrade !== 'all' && st.official_grade !== covFilterGrade) {
        return false;
      }

      return true;
    });

    if (covFilteredCount) {
      covFilteredCount.textContent = `Mostrando ${filtered.length} de ${students.length} alumnos`;
    }

    renderCovTable(filtered);
  }

  function renderCovTable(students) {
    if (!covTableTbody) return;

    if (students.length === 0) {
      covTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row">No se encontraron alumnos con los criterios seleccionados.</td></tr>';
      return;
    }

    covTableTbody.innerHTML = '';

    students.forEach(st => {
      const tr = document.createElement('tr');
      const pct = st.coverage_percentage || 0;
      let fillClass = 'fill-100';
      if (pct < 60) fillClass = 'fill-low';
      else if (pct < 100) fillClass = 'fill-partial';

      // Missing tags
      let missingHtml = '<span style="color: var(--color-green); font-size: 0.78rem; font-weight: 600;">Ninguna (100% inscrito)</span>';
      if (st.missing_classes && st.missing_classes.length > 0) {
        missingHtml = st.missing_classes.map(m => {
          return `<span class="chip-discrepancy chip-discrepancy-missing" title="${escapeHtml(m.team_name)}">${escapeHtml(m.subject)}</span>`;
        }).join('');
      }

      // Extraneous tags
      let extraneousHtml = '<span style="color: var(--text-muted); font-size: 0.78rem;">Ninguna</span>';
      if (st.extraneous_classes && st.extraneous_classes.length > 0) {
        extraneousHtml = st.extraneous_classes.map(e => {
          return `<span class="chip-discrepancy chip-discrepancy-extraneous" title="${escapeHtml(e.team_name)}">${escapeHtml(e.team_name)}</span>`;
        }).join('');
      }

      const hasDiscrepancy = (st.missing_classes && st.missing_classes.length > 0) || (st.extraneous_classes && st.extraneous_classes.length > 0);

      tr.innerHTML = `
        <td style="font-family: monospace; font-weight: 700; color: var(--brand-blue, #60A5FA);">${escapeHtml(st.matricula)}</td>
        <td>
          <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(st.nombre)}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(st.mail)}</div>
        </td>
        <td><span class="chip-filter" style="font-size: 0.76rem;">${escapeHtml(st.official_grade)}</span></td>
        <td class="text-center" style="font-weight: 700;">${st.enrolled_count} / ${st.expected_count}</td>
        <td>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; font-weight: 700;">
            <span>${pct}%</span>
          </div>
          <div class="cov-progress-bar-wrap">
            <div class="cov-progress-bar-fill ${fillClass}" style="width: ${pct}%;"></div>
          </div>
        </td>
        <td style="max-width: 250px;">${missingHtml}</td>
        <td style="max-width: 200px;">${extraneousHtml}</td>
        <td class="text-right">
          ${hasDiscrepancy ? `
            <button type="button" class="btn btn-xs btn-primary-saas btn-sync-single-student" data-matricula="${escapeHtml(st.matricula)}">
              Sincronizar
            </button>
          ` : `
            <span style="color: var(--color-green); font-size: 0.76rem; font-weight: 600;">Correcto</span>
          `}
        </td>
      `;

      covTableTbody.appendChild(tr);
    });

    // Wire single student sync
    covTableTbody.querySelectorAll('.btn-sync-single-student').forEach(btn => {
      btn.addEventListener('click', async () => {
        const mat = btn.getAttribute('data-matricula');
        if (!mat) return;
        btn.disabled = true;
        btn.textContent = 'Sincronizando...';

        try {
          const resp = await fetch('/api/teams/coverage/sync-global', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ matriculas: [mat] })
          });
          const res = await resp.json();

          if (res.success) {
            showToast(`Alumno ${mat} sincronizado correctamente.`, 'success');
            loadTeamsCoverageAudit(false);
          } else {
            showToast(`Error al sincronizar alumno ${mat}: ${res.error || ''}`, 'error');
            btn.disabled = false;
            btn.textContent = 'Reintentar';
          }
        } catch (err) {
          showToast('Error de red: ' + err.message, 'error');
          btn.disabled = false;
          btn.textContent = 'Reintentar';
        }
      });
    });
  }

  // Filter events for coverage
  if (covSearchInput) {
    covSearchInput.addEventListener('input', () => {
      covSearchQuery = covSearchInput.value;
      applyCovFilters();
    });
  }

  const covFilterButtons = document.querySelectorAll('#filter-group-coverage .pill-btn');
  covFilterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      covFilterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      covFilterStatus = btn.getAttribute('data-cov-filter') || 'all';
      applyCovFilters();
    });
  });

  if (covFilterGradeSelect) {
    covFilterGradeSelect.addEventListener('change', () => {
      covFilterGrade = covFilterGradeSelect.value;
      applyCovFilters();
    });
  }

  if (btnRefreshCoverage) {
    btnRefreshCoverage.addEventListener('click', () => {
      loadTeamsCoverageAudit(true);
    });
  }

  if (btnExportCoverageExcel) {
    btnExportCoverageExcel.addEventListener('click', () => {
      showToast('Generando libro de cobertura global en Excel...', 'info');
      window.location.href = '/api/teams/coverage/export-excel?cycle=2026-2027';
    });
  }

  if (btnSyncGlobalCoverage) {
    btnSyncGlobalCoverage.addEventListener('click', async () => {
      const confirmSync = confirm(
        'Deseas sincronizar la matriculacion global de todos los alumnos en Microsoft Teams?\n\n' +
        'El sistema realizara:\n' +
        '1. Inscripcion automatica a todas las materias faltantes de su grado escolar.\n' +
        '2. Baja de equipos que pertenezcan a otros grados no correspondientes.\n\n' +
        'Deseas continuar?'
      );

      if (!confirmSync) return;

      btnSyncGlobalCoverage.disabled = true;
      const originalHtml = btnSyncGlobalCoverage.innerHTML;
      btnSyncGlobalCoverage.innerHTML = '<span>Sincronizando matricula global...</span>';

      try {
        const resp = await fetch('/api/teams/coverage/sync-global', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const res = await resp.json();

        if (res.success && res.data) {
          const d = res.data;
          showToast(`Sincronizacion completada: ${d.total_enrolled} inscritos, ${d.total_removed} desincorporados.`, 'success');
          loadTeamsCoverageAudit(true);
          loadTeamsData(true);
        } else {
          showToast('Error en la sincronizacion global: ' + (res.error || 'Error desconocido'), 'error');
        }
      } catch (err) {
        showToast('Error al conectar con el servidor: ' + err.message, 'error');
      } finally {
        btnSyncGlobalCoverage.disabled = false;
        btnSyncGlobalCoverage.innerHTML = originalHtml;
      }
    });
  }

  // =========================================================================
  // SUB-TAB 3: NORMALIZADOR Y VERIFICADOR DE NOMENCLATURA INSTITUCIONAL
  // =========================================================================
  let nomAuditCache = null;
  let nomLoading = false;
  let nomSearchQuery = '';
  let nomFilterStatus = 'all';
  let nomFilterCycle = '2026-2027';
  const nomSelectedIds = new Set();

  const nomKpiTotal = document.getElementById('nom-kpi-total');
  const nomKpiCompliant = document.getElementById('nom-kpi-compliant');
  const nomKpiNonCompliant = document.getElementById('nom-kpi-non-compliant');
  const nomKpiCycleActive = document.getElementById('nom-kpi-cycle-active');
  const badgeNomenclaturePending = document.getElementById('badge-nomenclature-pending');

  const nomSearchInput = document.getElementById('nom-search-input');
  const nomFilteredCount = document.getElementById('nom-filtered-count');
  const nomTableTbody = document.getElementById('nom-table-tbody');
  const nomSelectAll = document.getElementById('nom-select-all');
  const btnBatchApplyNomenclature = document.getElementById('btn-batch-apply-nomenclature');
  const btnBatchApplyLabel = document.getElementById('btn-batch-apply-label');
  const btnRefreshNomenclature = document.getElementById('btn-refresh-nomenclature');

  async function loadTeamsNomenclatureAudit(forceRefresh = false) {
    if (nomLoading) return;
    nomLoading = true;

    if (nomTableTbody) {
      nomTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row">Analizando nombres de equipos con el estandar institucional...</td></tr>';
    }

    try {
      const resp = await fetch('/api/teams/nomenclature/audit');
      const res = await resp.json();

      if (res.success && res.data) {
        nomAuditCache = res.data;
        const s = res.data.summary || {};

        if (nomKpiTotal) nomKpiTotal.textContent = s.total_evaluated || 0;
        if (nomKpiCompliant) nomKpiCompliant.textContent = s.compliant_count || 0;
        if (nomKpiNonCompliant) nomKpiNonCompliant.textContent = s.non_compliant_count || 0;
        if (nomKpiCycleActive) nomKpiCycleActive.textContent = s.current_cycle_count || 0;

        if (badgeNomenclaturePending) {
          const pending = s.non_compliant_count || 0;
          if (pending > 0) {
            badgeNomenclaturePending.style.display = 'inline-flex';
            badgeNomenclaturePending.textContent = pending;
          } else {
            badgeNomenclaturePending.style.display = 'none';
          }
        }

        nomSelectedIds.clear();
        updateBatchRenameButtonState();
        applyNomFilters();

        if (forceRefresh) {
          showToast('Auditoria de nomenclatura actualizada.', 'success');
        }
      } else {
        if (nomTableTbody) {
          nomTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error: ${res.error || 'No se pudo auditar la nomenclatura'}</td></tr>`;
        }
        showToast('Error en auditoria de nomenclatura: ' + (res.error || ''), 'error');
      }
    } catch (err) {
      if (nomTableTbody) {
        nomTableTbody.innerHTML = `<tr><td colspan="8" class="table-empty-row" style="color: var(--color-danger);">Error de conexion: ${err.message}</td></tr>`;
      }
      showToast('Error al conectar con el servidor: ' + err.message, 'error');
    } finally {
      nomLoading = false;
    }
  }

  function updateBatchRenameButtonState() {
    const count = nomSelectedIds.size;
    if (btnBatchApplyLabel) {
      btnBatchApplyLabel.textContent = `Aplicar Normalizacion (${count} seleccionados)`;
    }
    if (btnBatchApplyNomenclature) {
      btnBatchApplyNomenclature.disabled = count === 0;
    }
  }

  function applyNomFilters() {
    if (!nomAuditCache || !nomAuditCache.classes) return;

    const q = nomSearchQuery.trim().toLowerCase();
    const classes = nomAuditCache.classes;

    const filtered = classes.filter(c => {
      // 1. Busqueda libre
      if (q) {
        const cur = (c.current_name || '').toLowerCase();
        const sug = (c.suggested_name || '').toLowerCase();
        const sub = (c.detected_subject || '').toLowerCase();
        const gr = (c.detected_grade || '').toLowerCase();
        if (!cur.includes(q) && !sug.includes(q) && !sub.includes(q) && !gr.includes(q)) {
          return false;
        }
      }

      // 2. Filtro de estado
      if (nomFilterStatus === 'non_compliant' && c.is_compliant) {
        return false;
      }
      if (nomFilterStatus === 'compliant' && !c.is_compliant) {
        return false;
      }

      // 3. Filtro de ciclo
      const cycleVal = c.detected_cycle || '';
      if (nomFilterCycle === '2026-2027' && !cycleVal.includes('26-27') && !cycleVal.includes('2026-2027')) {
        return false;
      }
      if (nomFilterCycle === '2025-2026' && !cycleVal.includes('25-26') && !cycleVal.includes('2025-2026')) {
        return false;
      }

      return true;
    });

    if (nomFilteredCount) {
      nomFilteredCount.textContent = `Mostrando ${filtered.length} de ${classes.length} equipos`;
    }

    renderNomTable(filtered);
  }

  function renderNomTable(classes) {
    if (!nomTableTbody) return;

    if (classes.length === 0) {
      nomTableTbody.innerHTML = '<tr><td colspan="8" class="table-empty-row">No se encontraron equipos con los filtros seleccionados.</td></tr>';
      return;
    }

    nomTableTbody.innerHTML = '';

    classes.forEach(c => {
      const tr = document.createElement('tr');
      const isCompliant = c.is_compliant;
      const isSelected = nomSelectedIds.has(c.team_id);

      const statusBadge = isCompliant
        ? '<span class="kpi-badge badge-green">Cumple Estandar</span>'
        : '<span class="kpi-badge badge-amber">Requiere Cambio</span>';

      const previewBadgeClass = isCompliant ? 'is-unchanged' : 'is-changed';

      tr.innerHTML = `
        <td style="text-align: center;">
          <input type="checkbox" class="nom-row-checkbox" data-team-id="${escapeHtml(c.team_id)}" ${isSelected ? 'checked' : ''} ${isCompliant ? 'disabled' : ''}>
        </td>
        <td style="font-weight: 600; color: var(--text-primary);">${escapeHtml(c.current_name)}</td>
        <td>
          <input type="text" class="saas-input saas-input-sm nom-suggested-input" data-team-id="${escapeHtml(c.team_id)}" value="${escapeHtml(c.suggested_name)}" style="font-family: monospace; font-size: 0.8rem; width: 100%; min-width: 200px;">
        </td>
        <td><span class="chip-filter" style="font-size: 0.76rem;">${escapeHtml(c.detected_subject || 'General')}</span></td>
        <td><span style="font-size: 0.8rem;">${escapeHtml(c.detected_grade || '-')}${c.detected_group ? ' ' + escapeHtml(c.detected_group) : ''}</span></td>
        <td><span style="font-size: 0.78rem; font-family: monospace;">${escapeHtml(c.detected_cycle || '-')}</span></td>
        <td class="text-center">${statusBadge}</td>
        <td class="text-right" style="white-space: nowrap;">
          <button type="button" class="btn btn-xs btn-primary-saas btn-rename-single-team" data-team-id="${escapeHtml(c.team_id)}" title="Aplicar nombre sugerido de inmediato">
            Renombrar
          </button>
          <button type="button" class="btn btn-xs btn-secondary-saas btn-customize-nom" data-team-id="${escapeHtml(c.team_id)}" title="Abrir asistente de formula">
            Personalizar
          </button>
        </td>
      `;

      nomTableTbody.appendChild(tr);
    });

    // Checkbox individual change
    nomTableTbody.querySelectorAll('.nom-row-checkbox').forEach(cb => {
      cb.addEventListener('change', () => {
        const teamId = cb.getAttribute('data-team-id');
        if (!teamId) return;
        if (cb.checked) {
          nomSelectedIds.add(teamId);
        } else {
          nomSelectedIds.delete(teamId);
        }
        updateBatchRenameButtonState();
      });
    });

    // Single rename direct action
    nomTableTbody.querySelectorAll('.btn-rename-single-team').forEach(btn => {
      btn.addEventListener('click', async () => {
        const teamId = btn.getAttribute('data-team-id');
        if (!teamId) return;

        const input = nomTableTbody.querySelector(`.nom-suggested-input[data-team-id="${teamId}"]`);
        const newName = input ? input.value.trim() : '';

        if (!newName) {
          showToast('El nuevo nombre no puede estar vacio.', 'error');
          return;
        }

        btn.disabled = true;
        btn.textContent = 'Guardando...';

        try {
          const resp = await fetch('/api/teams/nomenclature/rename-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              renames: [{ team_id: teamId, new_name: newName }]
            })
          });
          const res = await resp.json();

          if (res.success) {
            showToast(`Equipo renombrado a "${newName}" con exito.`, 'success');
            loadTeamsNomenclatureAudit(false);
            loadTeamsData(true);
          } else {
            showToast('Error al renombrar: ' + (res.error || ''), 'error');
            btn.disabled = false;
            btn.textContent = 'Renombrar';
          }
        } catch (err) {
          showToast('Error de conexion: ' + err.message, 'error');
          btn.disabled = false;
          btn.textContent = 'Renombrar';
        }
      });
    });

    // Customize in modal
    nomTableTbody.querySelectorAll('.btn-customize-nom').forEach(btn => {
      btn.addEventListener('click', () => {
        const teamId = btn.getAttribute('data-team-id');
        if (!teamId) return;
        openRenameModal(teamId);
        const team = (nomAuditCache.classes || []).find(c => c.team_id === teamId);
        if (team) {
          autofillNomenclatureHelper(team.current_name);
        }
      });
    });
  }

  // Select all checkbox
  if (nomSelectAll) {
    nomSelectAll.addEventListener('change', () => {
      const isChecked = nomSelectAll.checked;
      const checkboxes = nomTableTbody ? nomTableTbody.querySelectorAll('.nom-row-checkbox:not(:disabled)') : [];
      checkboxes.forEach(cb => {
        cb.checked = isChecked;
        const teamId = cb.getAttribute('data-team-id');
        if (teamId) {
          if (isChecked) nomSelectedIds.add(teamId);
          else nomSelectedIds.delete(teamId);
        }
      });
      updateBatchRenameButtonState();
    });
  }

  // Filter events for nomenclature
  if (nomSearchInput) {
    nomSearchInput.addEventListener('input', () => {
      nomSearchQuery = nomSearchInput.value;
      applyNomFilters();
    });
  }

  const nomFilterStatusButtons = document.querySelectorAll('#filter-group-nom-status .pill-btn');
  nomFilterStatusButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      nomFilterStatusButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      nomFilterStatus = btn.getAttribute('data-nom-status') || 'all';
      applyNomFilters();
    });
  });

  const nomFilterCycleButtons = document.querySelectorAll('#filter-group-nom-cycle .pill-btn');
  nomFilterCycleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      nomFilterCycleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      nomFilterCycle = btn.getAttribute('data-nom-cycle') || 'all';
      applyNomFilters();
    });
  });

  if (btnRefreshNomenclature) {
    btnRefreshNomenclature.addEventListener('click', () => {
      loadTeamsNomenclatureAudit(true);
    });
  }

  // Batch apply nomenclature
  if (btnBatchApplyNomenclature) {
    btnBatchApplyNomenclature.addEventListener('click', async () => {
      if (nomSelectedIds.size === 0) return;

      const renames = [];
      nomSelectedIds.forEach(id => {
        const input = nomTableTbody ? nomTableTbody.querySelector(`.nom-suggested-input[data-team-id="${id}"]`) : null;
        if (input && input.value.trim()) {
          renames.push({ team_id: id, new_name: input.value.trim() });
        }
      });

      if (renames.length === 0) {
        showToast('No hay nombres validos para aplicar.', 'error');
        return;
      }

      const confirmBatch = confirm(
        `Deseas aplicar la nomenclatura estandar a los ${renames.length} equipos seleccionados en Microsoft Teams?\n\n` +
        'Esta accion actualizara el nombre visible de los equipos en Microsoft 365.\n\n' +
        'Deseas continuar?'
      );

      if (!confirmBatch) return;

      btnBatchApplyNomenclature.disabled = true;
      const originalText = btnBatchApplyLabel.textContent;
      btnBatchApplyLabel.textContent = `Renombrando ${renames.length} equipos en M365...`;

      try {
        const resp = await fetch('/api/teams/nomenclature/rename-batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ renames })
        });
        const res = await resp.json();

        if (res.success && res.data) {
          const d = res.data;
          showToast(`Normalizacion completada: ${d.total_renamed} equipos renombrados con exito.`, 'success');
          nomSelectedIds.clear();
          if (nomSelectAll) nomSelectAll.checked = false;
          loadTeamsNomenclatureAudit(true);
          loadTeamsData(true);
        } else {
          showToast('Error al renombrar por lote: ' + (res.error || 'Error desconocido'), 'error');
        }
      } catch (err) {
        showToast('Error al conectar con el servidor: ' + err.message, 'error');
      } finally {
        updateBatchRenameButtonState();
      }
    });
  }

  // =========================================================================
  // ASISTENTE DE NOMENCLATURA EN MODAL DE RENOMBRAR
  // =========================================================================
  const helperNomSubject = document.getElementById('helper-nom-subject');
  const helperNomGrade = document.getElementById('helper-nom-grade');
  const helperNomLevel = document.getElementById('helper-nom-level');
  const helperNomCycle = document.getElementById('helper-nom-cycle');
  const helperNomPreview = document.getElementById('helper-nom-preview');
  const btnHelperAutofill = document.getElementById('btn-helper-autofill');
  const btnHelperApplyPreview = document.getElementById('btn-helper-apply-preview');

  function updateHelperNomPreview() {
    const subj = (helperNomSubject?.value || '').trim();
    const grade = helperNomGrade?.value || '1°';
    const level = helperNomLevel?.value || 'Primaria';
    const cycle = helperNomCycle?.value || '26-27';

    if (!helperNomPreview) return;
    if (!subj) {
      helperNomPreview.textContent = '-';
      return;
    }
    helperNomPreview.textContent = `${subj} (${grade} ${level}) - ${cycle}`;
  }

  function autofillNomenclatureHelper(currentName) {
    if (!currentName) return;
    const text = currentName.trim();

    // Ciclo
    let cycle = '26-27';
    if (text.includes('25-26') || text.includes('2025-2026')) {
      cycle = '25-26';
    }
    if (helperNomCycle) helperNomCycle.value = cycle;

    // Limpiar ciclo para detectar grado y nivel
    const clean = text.replace(/202[5-7]-202[6-8]/g, '').replace(/2[5-7]-2[6-8]/g, '').trim();

    // Nivel
    let level = 'Secundaria';
    if (/primaria/i.test(clean)) {
      level = 'Primaria';
    } else if (/secundaria/i.test(clean)) {
      level = 'Secundaria';
    } else {
      level = 'General';
    }
    if (helperNomLevel) helperNomLevel.value = level;

    // Grado
    let grade = '1°';
    if (/\b(1|1ro|1er|1ero|1°|i)\b/i.test(clean)) grade = '1°';
    else if (/\b(2|2do|2°|ii)\b/i.test(clean)) grade = '2°';
    else if (/\b(3|3ro|3er|3ero|3°|iii)\b/i.test(clean)) grade = '3°';
    else if (/\b(4|4to|4°|iv)\b/i.test(clean)) grade = '4°';
    else if (/\b(5|5to|5°|v)\b/i.test(clean)) grade = '5°';
    else if (/\b(6|6to|6°|vi)\b/i.test(clean)) grade = '6°';
    if (helperNomGrade) helperNomGrade.value = grade;

    // Materia
    let subj = clean
      .replace(/\b(primaria|secundaria|general)\b/gi, '')
      .replace(/\b(1ro|2do|3ro|4to|5to|6to|1er|3er|1ero|3ero|1°|2°|3°|4°|5°|6°|iii|ii|iv|vi|v|i)\b/gi, '')
      .replace(/[\(\)\[\]\-_]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    if (subj) {
      subj = subj.toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    }
    if (helperNomSubject) helperNomSubject.value = subj || 'Materia';

    updateHelperNomPreview();
  }

  [helperNomSubject, helperNomGrade, helperNomLevel, helperNomCycle].forEach(el => {
    if (el) {
      el.addEventListener('input', updateHelperNomPreview);
      el.addEventListener('change', updateHelperNomPreview);
    }
  });

  if (btnHelperAutofill) {
    btnHelperAutofill.addEventListener('click', () => {
      const cur = renameCurrentName ? renameCurrentName.value : '';
      autofillNomenclatureHelper(cur);
    });
  }

  if (btnHelperApplyPreview) {
    btnHelperApplyPreview.addEventListener('click', () => {
      const prev = helperNomPreview ? helperNomPreview.textContent : '';
      if (prev && prev !== '-' && renameNewName) {
        renameNewName.value = prev;
        renameNewName.focus();
        showToast('Nombre de la formula aplicado.', 'info');
      }
    });
  }
});

