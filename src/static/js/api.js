/**
 * Utilidades para consumo de API REST y manejo de sesión en el cliente.
 */

// Muestra alertas dinámicas en la interfaz
function showAlert(message, type = 'info') {
  const container = document.getElementById('alert-container');
  if (!container) return;

  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type}`;
  alertDiv.innerHTML = `
    <span>${message}</span>
    <button type="button" style="background:none;border:none;cursor:pointer;font-weight:bold;margin-left:1rem;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(alertDiv);
  setTimeout(() => {
    if (alertDiv.parentElement) {
      alertDiv.remove();
    }
  }, 6000);
}

// Wrapper centralizado de Fetch para la API REST
async function fetchAPI(url, options = {}) {
  const token = localStorage.getItem('auth_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers
  });

  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_profile');
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login?msg=sesion_expirada';
    }
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = data.detail || 'Ocurrió un error inesperado al procesar la solicitud.';
    throw new Error(errorMsg);
  }

  return data;
}

// Formateador de fechas para Colombia (America/Bogota)
function formatBogotaDate(isoDateString) {
  if (!isoDateString) return '-';
  const date = new Date(isoDateString);
  return date.toLocaleString('es-CO', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}

