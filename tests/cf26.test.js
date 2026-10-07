const request = require('supertest');
const { createAdminToken } = require('../src/lib/admin-auth');
const app = require('../src/app');

const ADMIN_EMAIL = 'arvestal@gmail.com';
const JWT_SECRET = 'test-jwt-secret';

function adminCookies() {
  return [`admin_token=${createAdminToken(ADMIN_EMAIL, JWT_SECRET)}`];
}

beforeEach(() => {
  process.env.ADMIN_EMAIL = ADMIN_EMAIL;
  process.env.ADMIN_JWT_SECRET = JWT_SECRET;
});

describe('/cf26 without a login', () => {
  it('sends you to the login page with ?next= pointing back at the page', async () => {
    const res = await request(app).get('/cf26/opponents/jason-stanford/reports/gameplan.html');
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe(
      `/admin/login?next=${encodeURIComponent('/cf26/opponents/jason-stanford/reports/gameplan.html')}`,
    );
  });

  it('rejects a cookie for a different admin email', async () => {
    const res = await request(app)
      .get('/cf26/')
      .set('Cookie', [`admin_token=${createAdminToken('someone@gmail.com', JWT_SECRET)}`]);
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin/login?next=%2Fcf26%2F');
  });

  it('errors when ADMIN_EMAIL is not configured', async () => {
    delete process.env.ADMIN_EMAIL;
    const res = await request(app).get('/cf26/');
    expect(res.status).toBe(500);
    expect(res.text).toContain('ADMIN_EMAIL is not set');
  });
});

describe('/cf26 with a login', () => {
  it('redirects /cf26 to /cf26/ so the relative links resolve', async () => {
    const res = await request(app).get('/cf26').set('Cookie', adminCookies());
    expect(res.status).toBe(301);
    expect(res.headers.location).toBe('/cf26/');
  });

  it('serves the index page, uncached and noindexed', async () => {
    const res = await request(app).get('/cf26/').set('Cookie', adminCookies());
    expect(res.status).toBe(200);
    expect(res.text).toContain('CF26 scouting');
    expect(res.headers['cache-control']).toBe('private, no-store');
    expect(res.headers['x-robots-tag']).toBe('noindex, nofollow');
  });

  it('serves /cf26/index.html (the pages link back to it)', async () => {
    const res = await request(app).get('/cf26/index.html').set('Cookie', adminCookies());
    expect(res.status).toBe(200);
    expect(res.text).toContain('CF26 scouting');
  });

  it("serves an opponent's game plan and scouting report", async () => {
    const plan = await request(app).get('/cf26/opponents/jason-stanford/reports/gameplan.html').set('Cookie', adminCookies());
    expect(plan.status).toBe(200);
    expect(plan.text).toContain('Jason (Stanford)');

    const report = await request(app).get('/cf26/opponents/mike-iowa/reports/scouting_report.html').set('Cookie', adminCookies());
    expect(report.status).toBe(200);
    expect(report.text).toContain('Mike (Iowa)');
  });

  it('404s for an opponent that has no pages', async () => {
    const res = await request(app).get('/cf26/opponents/nobody/reports/gameplan.html').set('Cookie', adminCookies());
    expect(res.status).toBe(404);
  });

  it('only serves the two report pages, never raw data files', async () => {
    const res = await request(app).get('/cf26/opponents/jason-stanford/reports/gameplan.md').set('Cookie', adminCookies());
    expect(res.status).toBe(404);
    const csv = await request(app).get('/cf26/opponents/jason-stanford/plays.csv').set('Cookie', adminCookies());
    expect(csv.status).toBe(404);
  });

  it('rejects opponent ids that could escape the cf26 folder', async () => {
    const res = await request(app)
      .get('/cf26/opponents/..%2F..%2Fsrc/reports/gameplan.html')
      .set('Cookie', adminCookies());
    expect(res.status).toBe(404);
  });
});
