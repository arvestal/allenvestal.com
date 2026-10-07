require('dotenv').config();

const express = require('express');
const path = require('path');
const cookieParser = require('cookie-parser');
const { engine } = require('express-handlebars');

const { buildSeasonNavGroups } = require('./lib/nav');
const helpers = require('./lib/helpers');

const app = express();
const PORT = process.env.PORT || 8080;
const ASSET_VERSION = process.env.RAILWAY_GIT_COMMIT_SHA || 'dev';

// Railway terminates TLS in front of the app; trust its X-Forwarded-* headers so
// req.protocol/req.secure reflect the real client-facing connection.
app.set('trust proxy', 1);

app.engine('hbs', engine({
  extname: '.hbs',
  defaultLayout: 'main',
  layoutsDir: path.join(__dirname, '../views/layouts'),
  partialsDir: path.join(__dirname, '../views/partials'),
  helpers,
}));
app.set('view engine', 'hbs');
app.set('views', path.join(__dirname, '../views'));

app.use(express.static(path.join(__dirname, '../public')));
app.use(cookieParser());
app.use(express.urlencoded({ extended: false }));

// Serves gallery images from the persistent volume (GALLERY_DATA_DIR) instead of public/, so
// admin uploads/deletes take effect without a redeploy.
const { resolveDataDir } = require('./lib/gallery-store');
app.use('/img/gallery', express.static(resolveDataDir()));

// Railway deployment healthcheck target.
app.get('/health', (req, res) => res.status(200).json({ status: 'ok' }));

// www → root redirect, matching playoffrally.com.
app.use((req, res, next) => {
  if (req.hostname === 'www.allenvestal.com') {
    return res.redirect(301, `https://allenvestal.com${req.originalUrl}`);
  }
  next();
});

app.use((req, res, next) => {
  res.locals.seasonNavGroups = buildSeasonNavGroups();
  res.locals.currentYear = new Date().getFullYear();
  res.locals.canonicalUrl = `https://allenvestal.com${req.path}`;
  res.locals.assetVersion = ASSET_VERSION;
  next();
});

app.use('/', require('./routes/index'));
app.use('/softball', require('./routes/softball'));
app.use('/gallery', require('./routes/gallery'));
app.use('/admin', require('./routes/admin'));
app.use('/cf26', require('./routes/cf26'));

app.use((req, res) => {
  res.status(404).render('error', {
    pageTitle: 'Page Not Found',
    message: "The page you're looking for doesn't exist.",
    noIndex: true,
  });
});

/* istanbul ignore if -- exercised by starting the process, not by tests */
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Listening on http://localhost:${PORT}`);
  });
}

module.exports = app;
