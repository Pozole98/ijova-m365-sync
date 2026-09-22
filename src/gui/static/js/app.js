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

  async function openRosterModal(teamId, teamName) {
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
      const resp = await fetch(`/api/teams/${teamId}/roster/audit`);
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

  function renderRosterAudit(r) {
    if (rosterModalClassMeta) {
      rosterModalClassMeta.textContent = `${r.grado} • ${r.nivel} | Profesor Titular: ${r.teacher_name}`;
    }

    if (rKpiOfficial) rKpiOfficial.textContent = r.official_count;
    if (rKpiTeam) rKpiTeam.textContent = r.team_count;
    if (rKpiSynced) rKpiSynced.textContent = r.synced_count;
    if (rKpiMissing) rKpiMissing.textContent = r.missing_count;
    if (rKpiUnexpected) rKpiUnexpected.textContent = r.unexpected_count;
    if (rKpiPercent) rKpiPercent.textContent = `${r.sync_percentage}%`;

    // 1. Faltantes
    if (rosterMissingBadge) rosterMissingBadge.textContent = `${r.missing_count} Alumnos Faltantes`;
    if (rosterMissingChips) {
      if (r.missing_students.length === 0) {
        rosterMissingChips.innerHTML = '<span style="color: var(--color-green); font-size: 0.82rem;">Ninguno. Todos los alumnos oficiales están inscritos en el equipo.</span>';
      } else {
        rosterMissingChips.innerHTML = '';
        r.missing_students.forEach(st => {
          const chip = document.createElement('div');
          chip.className = 'student-chip chip-amber';
          chip.innerHTML = `<span class="chip-mat">${escapeHtml(st.matricula)}</span><span>${escapeHtml(st.name)}</span>`;
          rosterMissingChips.appendChild(chip);
        });
      }
    }

    // 2. Inesperados / Bajas
    if (rosterUnexpectedBadge) rosterUnexpectedBadge.textContent = `${r.unexpected_count} Bajas / No pertenecen`;
    if (rosterUnexpectedChips) {
      if (r.unexpected_students.length === 0) {
        rosterUnexpectedChips.innerHTML = '<span style="color: var(--color-green); font-size: 0.82rem;">Ninguno. No hay cuentas de alumnos ajenas al grado actual.</span>';
      } else {
        rosterUnexpectedChips.innerHTML = '';
        r.unexpected_students.forEach(st => {
          const chip = document.createElement('div');
          chip.className = 'student-chip chip-red';
          chip.innerHTML = `<span class="chip-mat">${escapeHtml(st.matricula)}</span><span>${escapeHtml(st.name)}</span>`;
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
          chip.className = 'student-chip';
          chip.innerHTML = `<span class="chip-mat">${escapeHtml(st.matricula)}</span><span>${escapeHtml(st.name)}</span>`;
          rosterSyncedChips.appendChild(chip);
        });
      }
    }

    if (btnExecuteRosterSync) {
      btnExecuteRosterSync.disabled = (r.missing_count === 0 && r.unexpected_count === 0);
      btnExecuteRosterSync.innerHTML = r.missing_count > 0
        ? `<span>Sincronizar ${r.missing_count} Alumno(s) Faltante(s)</span>`
        : '<span>Nómina Sincronizada al 100%</span>';
    }
  }

  // Ejecutar sincronización de roster
  if (btnExecuteRosterSync) {
    btnExecuteRosterSync.addEventListener('click', async () => {
      if (!currentRosterTeamId || !currentRosterAuditData) return;
      btnExecuteRosterSync.disabled = true;
      btnExecuteRosterSync.innerHTML = '<span>Sincronizando miembros en Teams...</span>';

      try {
        const resp = await fetch(`/api/teams/${currentRosterTeamId}/roster/sync`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            add_missing: true,
            remove_unexpected: false,
            nivel: currentRosterAuditData.nivel,
            grado: currentRosterAuditData.grado
          })
        });
        const res = await resp.json();
        if (res.success && res.result) {
          showToast(`Sincronización completada: se agregaron ${res.result.added_count} alumnos al equipo.`, 'success');
          // Re-auditar la clase en vivo para reflejar los cambios
          openRosterModal(currentRosterTeamId, currentRosterAuditData.team_name);
          loadTeamsData(true);
        } else {
          showToast(`Error al sincronizar: ${res.error || 'Error inesperado'}`, 'error');
          btnExecuteRosterSync.disabled = false;
        }
      } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
        btnExecuteRosterSync.disabled = false;
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
});

