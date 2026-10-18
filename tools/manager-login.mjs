// BrowserContext.request shares Set-Cookie responses with every page in this context.
export async function loginManager(context, managerURL) {
  const password = process.env.MANAGER_PASSWORD;
  if (!password) throw new Error('Set MANAGER_PASSWORD to the vim4-manager login password (MANAGER_USERNAME defaults to admin)');
  const origin = new URL(managerURL).origin;
  const response = await context.request.post(`${origin}/__vim4/api/auth/login`, {
    headers: { 'Content-Type': 'application/json', Origin: origin },
    data: { username: process.env.MANAGER_USERNAME || 'admin', password },
    maxRedirects: 0,
  });
  if (!response.ok()) throw new Error(`Manager login failed: HTTP ${response.status()}`);
  const cookies = await context.cookies(origin);
  if (!cookies.some(cookie => cookie.name === 'vim4_session')) {
    throw new Error('Manager login did not set a vim4_session cookie');
  }
}
