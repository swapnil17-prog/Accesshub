// Access + refresh tokens, persisted in localStorage. Every access is wrapped in try/catch
// because storage can be unavailable (private mode, blocked site data).

const ACCESS_KEY = 'accesshub.accessToken';
const REFRESH_KEY = 'accesshub.refreshToken';

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    /* storage unavailable: the session simply won't survive a reload */
  }
}

export const tokenStore = {
  getAccess: () => read(ACCESS_KEY),
  getRefresh: () => read(REFRESH_KEY),
  setAccess: (token) => write(ACCESS_KEY, token),
  set({ access, refresh }) {
    write(ACCESS_KEY, access);
    write(REFRESH_KEY, refresh);
  },
  clear() {
    write(ACCESS_KEY, null);
    write(REFRESH_KEY, null);
  },
};
