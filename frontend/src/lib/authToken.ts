const ACCESS_TOKEN_KEY = "access_token"
const LEGACY_ACCESS_TOKEN_KEYS = ["accessToken", "token"]

export function getAccessToken() {
  return (
    sessionStorage.getItem(ACCESS_TOKEN_KEY) ||
    localStorage.getItem(ACCESS_TOKEN_KEY) ||
    LEGACY_ACCESS_TOKEN_KEYS.map((key) => localStorage.getItem(key)).find(Boolean) ||
    ""
  )
}

export function setAccessToken(token: string) {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token)
  localStorage.removeItem(ACCESS_TOKEN_KEY)
}

export function clearAccessToken() {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  LEGACY_ACCESS_TOKEN_KEYS.forEach((key) => {
    localStorage.removeItem(key)
  })
}

export function hasAccessToken() {
  return Boolean(getAccessToken())
}