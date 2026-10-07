const { createAdminToken, verifyAdminToken, safeNextPath } = require('../../src/lib/admin-auth');

describe('createAdminToken / verifyAdminToken', () => {
  it('verifies a token it created itself for the matching email', () => {
    const token = createAdminToken('arvestal@gmail.com', 'test-secret');
    expect(verifyAdminToken(token, 'test-secret', 'arvestal@gmail.com')).toMatchObject({ email: 'arvestal@gmail.com' });
  });

  it('rejects a token whose email does not match the expected admin email', () => {
    const token = createAdminToken('someone-else@gmail.com', 'test-secret');
    expect(verifyAdminToken(token, 'test-secret', 'arvestal@gmail.com')).toBeNull();
  });

  it('rejects a token signed with a different secret', () => {
    const token = createAdminToken('arvestal@gmail.com', 'test-secret');
    expect(verifyAdminToken(token, 'wrong-secret', 'arvestal@gmail.com')).toBeNull();
  });

  it('rejects a malformed token', () => {
    expect(verifyAdminToken('not-a-real-token', 'test-secret', 'arvestal@gmail.com')).toBeNull();
  });

  it('returns null when there is no token at all', () => {
    expect(verifyAdminToken(undefined, 'test-secret', 'arvestal@gmail.com')).toBeNull();
    expect(verifyAdminToken('', 'test-secret', 'arvestal@gmail.com')).toBeNull();
  });

  it('rejects an expired token', () => {
    const jwt = require('jsonwebtoken');
    const expired = jwt.sign({ email: 'arvestal@gmail.com' }, 'test-secret', { expiresIn: -10 });
    expect(verifyAdminToken(expired, 'test-secret', 'arvestal@gmail.com')).toBeNull();
  });
});

describe('safeNextPath', () => {
  it('accepts same-site absolute paths', () => {
    expect(safeNextPath('/cf26/')).toBe('/cf26/');
    expect(safeNextPath('/cf26/opponents/jason-stanford/reports/gameplan.html')).toBe('/cf26/opponents/jason-stanford/reports/gameplan.html');
  });

  it('rejects anything a browser could treat as another host', () => {
    expect(safeNextPath('//evil.com')).toBeNull();
    expect(safeNextPath('/\\evil.com')).toBeNull();
    expect(safeNextPath('https://evil.com')).toBeNull();
    expect(safeNextPath('cf26')).toBeNull();
  });

  it('rejects missing, non-string and overlong values', () => {
    expect(safeNextPath(undefined)).toBeNull();
    expect(safeNextPath(['/cf26/'])).toBeNull();
    expect(safeNextPath(`/${'a'.repeat(600)}`)).toBeNull();
  });
});
