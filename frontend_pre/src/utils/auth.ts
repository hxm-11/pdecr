// src/utils/auth.ts
// 登录状态判断
export const isLoggedIn = (): boolean => {
  const token = localStorage.getItem('access_token')
  return !!token && token.trim().length > 0
}

// 保存登录token
export const setAuthToken = (token: string): void => {
  localStorage.setItem('access_token', token)
}

// 清除登录token（退出登录）
export const clearAuthToken = (): void => {
  localStorage.removeItem('access_token')
  // 可选：清除用户信息
  localStorage.removeItem('user_info')
}

// 获取当前token
export const getAuthToken = (): string | null => {
  return localStorage.getItem('access_token')
}