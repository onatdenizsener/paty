// Browser twin of asc_setup.py: run inside a signed-in App Store Connect tab (appstoreconnect.apple.com).
// Uses the same JSON:API resources through the web app's /iris endpoints with the signed-in session,
// so no API key is needed. Expects window.PATY_META = {M: metadata.json, A: {path: {name,size,md5}}}.
// Assets are fetched from the public GitHub repo. Every step logs to window.PATY_LOG and never throws.
(() => {
  const META = window.PATY_META, M = META.M, A = META.A;
  const RAW = 'https://raw.githubusercontent.com/onatdenizsener/paty/main/';
  const LOG = window.PATY_LOG = window.PATY_LOG || [];
  const log = (t, m) => { LOG.push(t + ': ' + m); };
  const H = { 'Content-Type': 'application/json', 'X-Csrf-Itc': '[asc-ui]', 'X-Requested-With': 'XMLHttpRequest' };
  async function call(method, path, body) {
    for (let i = 0; i < 4; i++) {
      const r = await fetch('/iris' + path, { method, credentials: 'include', headers: H, body: body ? JSON.stringify(body) : undefined });
      const txt = await r.text();
      if ([429, 500, 502, 503].includes(r.status) && i < 3) { await new Promise(s => setTimeout(s, 3000 * (i + 1))); continue; }
      let j = {}; try { j = txt ? JSON.parse(txt) : {}; } catch (e) {}
      if (!r.ok) throw new Error(method + ' ' + path + ' -> ' + r.status + ' ' + ((j.errors || []).map(e => e.title + ': ' + e.detail).join('; ') || txt.slice(0, 300)));
      return j;
    }
  }
  const get = p => call('GET', p), post = (p, b) => call('POST', p, b), patch = (p, b) => call('PATCH', p, b);
  const rel = (type, id) => ({ data: { type, id } });
  async function all(path) { let out = [], p = path; while (p) { const j = await get(p); out = out.concat(j.data); const n = j.links && j.links.next; p = n ? n.replace(/^https?:\/\/[^/]+(\/iris)?/, '') : null; } return out; }

  async function upload(res, assetPath) {
    const buf = new Uint8Array(await (await fetch(RAW + assetPath)).arrayBuffer());
    for (const op of res.attributes.uploadOperations) {
      const h = {}; op.requestHeaders.forEach(x => h[x.name] = x.value);
      const r = await fetch(op.url, { method: op.method, headers: h, body: buf.slice(op.offset, op.offset + op.length) });
      if (!r.ok) throw new Error('upload ' + r.status);
    }
    await patch('/v1/' + res.type + '/' + res.id, { data: { type: res.type, id: res.id, attributes: { uploaded: true, sourceFileChecksum: A[assetPath].md5 } } });
  }

  const S = window.PATY = {};
  S.app = async () => { const j = await get('/v1/apps?filter[bundleId]=' + M.bundleId); return j.data[0]; };

  S.appAttrs = async app => {
    await patch('/v1/apps/' + app.id, { data: { type: 'apps', id: app.id, attributes: { contentRightsDeclaration: M.contentRights } } });
    log('Uygulama', 'içerik hakları: ' + M.contentRights);
  };

  S.info = async app => {
    const infos = (await get('/v1/apps/' + app.id + '/appInfos')).data;
    const info = infos.find(i => !['READY_FOR_SALE', 'READY_FOR_DISTRIBUTION', 'REPLACED_WITH_NEW_INFO'].includes(i.attributes.appStoreState || i.attributes.state)) || infos[0];
    const c = M.categories;
    try {
      await patch('/v1/appInfos/' + info.id, { data: { type: 'appInfos', id: info.id, relationships: {
        primaryCategory: rel('appCategories', c.primary), primarySubcategoryOne: rel('appCategories', c.sub1), primarySubcategoryTwo: rel('appCategories', c.sub2) } } });
      log('Kategori', 'tamam');
    } catch (e) { log('Kategori HATA', e.message); }
    const have = {}; (await get('/v1/appInfos/' + info.id + '/appInfoLocalizations')).data.forEach(l => have[l.attributes.locale] = l);
    for (const [loc, v] of Object.entries(M.localizations)) {
      const attrs = { name: v.name, subtitle: v.subtitle, privacyPolicyUrl: M.urls.privacy };
      try {
        if (have[loc]) await patch('/v1/appInfoLocalizations/' + have[loc].id, { data: { type: 'appInfoLocalizations', id: have[loc].id, attributes: attrs } });
        else await post('/v1/appInfoLocalizations', { data: { type: 'appInfoLocalizations', attributes: Object.assign({ locale: loc }, attrs), relationships: { appInfo: rel('appInfos', info.id) } } });
        log('Ad/alt başlık', loc);
      } catch (e) { log('Ad/alt başlık HATA ' + loc, e.message); }
    }
    try {
      const ar = (await get('/v1/appInfos/' + info.id + '/ageRatingDeclaration')).data;
      const SKIP = new Set(['kidsAgeBand', 'ageRatingOverride', 'ageRatingOverrideV2', 'koreaAgeRatingOverride', 'developerAgeRatingInfoUrl']);
      const BOOLS = new Set(['gambling', 'unrestrictedWebAccess', 'lootBox', 'advertising', 'messagingAndChat', 'parentalControls', 'ageAssurance', 'userGeneratedContent', 'healthOrWellnessTopics', 'seventeenPlus']);
      const attrs = {};
      for (const [k, v] of Object.entries(ar.attributes)) { if (SKIP.has(k)) continue; attrs[k] = (BOOLS.has(k) || typeof v === 'boolean') ? (k === 'advertising') : 'NONE'; }
      await patch('/v1/ageRatingDeclarations/' + ar.id, { data: { type: 'ageRatingDeclarations', id: ar.id, attributes: attrs } });
      log('Yaş', '4+ (reklam: evet)');
    } catch (e) { log('Yaş HATA', e.message); }
  };

  S.editableVersion = async app => (await get('/v1/apps/' + app.id + '/appStoreVersions?filter[platform]=IOS&limit=20')).data
    .find(v => ['PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY'].includes(v.attributes.appStoreState));

  S.version = async app => {
    const v = await S.editableVersion(app);
    const attrs = { copyright: M.copyright, releaseType: 'AFTER_APPROVAL' };
    if (v.attributes.versionString !== M.version) attrs.versionString = M.version;
    await patch('/v1/appStoreVersions/' + v.id, { data: { type: 'appStoreVersions', id: v.id, attributes: attrs } });
    const have = {}; (await get('/v1/appStoreVersions/' + v.id + '/appStoreVersionLocalizations')).data.forEach(l => have[l.attributes.locale] = l);
    for (const [loc, d] of Object.entries(M.localizations)) {
      const a = { description: d.description, keywords: d.keywords, promotionalText: d.promotionalText, supportUrl: M.urls.support, marketingUrl: M.urls.marketing };
      try {
        if (have[loc]) await patch('/v1/appStoreVersionLocalizations/' + have[loc].id, { data: { type: 'appStoreVersionLocalizations', id: have[loc].id, attributes: a } });
        else await post('/v1/appStoreVersionLocalizations', { data: { type: 'appStoreVersionLocalizations', attributes: Object.assign({ locale: loc }, a), relationships: { appStoreVersion: rel('appStoreVersions', v.id) } } });
        log('Sürüm metni', loc);
      } catch (e) { log('Sürüm metni HATA ' + loc, e.message); }
    }
  };

  S.screenshots = async (app, onlyLoc) => {
    const v = await S.editableVersion(app);
    const locs = {}; (await get('/v1/appStoreVersions/' + v.id + '/appStoreVersionLocalizations')).data.forEach(l => locs[l.attributes.locale] = l.id);
    for (const loc of Object.keys(M.localizations)) {
      if (onlyLoc && loc !== onlyLoc) continue;
      try {
        const prefix = loc.split('-')[0];
        const files = Object.keys(A).filter(p => p.startsWith('appstore/screenshots/' + prefix + '_')).sort();
        const sets = (await get('/v1/appStoreVersionLocalizations/' + locs[loc] + '/appScreenshotSets')).data;
        let s = sets.find(x => x.attributes.screenshotDisplayType === 'APP_IPHONE_67');
        if (!s) s = (await post('/v1/appScreenshotSets', { data: { type: 'appScreenshotSets', attributes: { screenshotDisplayType: 'APP_IPHONE_67' }, relationships: { appStoreVersionLocalization: rel('appStoreVersionLocalizations', locs[loc]) } } })).data;
        const existing = (await get('/v1/appScreenshotSets/' + s.id + '/appScreenshots?limit=20')).data;
        const ok = new Set(existing.filter(x => ['COMPLETE', 'UPLOAD_COMPLETE'].includes((x.attributes.assetDeliveryState || {}).state)).map(x => x.attributes.fileName));
        for (const x of existing) if (!ok.has(x.attributes.fileName)) await call('DELETE', '/v1/appScreenshots/' + x.id);
        let n = 0;
        for (const p of files) {
          if (ok.has(A[p].name)) continue;
          const r = (await post('/v1/appScreenshots', { data: { type: 'appScreenshots', attributes: { fileName: A[p].name, fileSize: A[p].size }, relationships: { appScreenshotSet: rel('appScreenshotSets', s.id) } } })).data;
          await upload(r, p); n++;
        }
        log('Ekran görüntüsü', loc + ': ' + n + ' yüklendi, ' + ok.size + ' vardı');
      } catch (e) { log('Ekran görüntüsü HATA ' + loc, e.message); }
    }
  };

  S.review = async (app, contact) => {
    const v = await S.editableVersion(app);
    const attrs = Object.assign({ notes: M.localizations.tr.reviewNotes, demoAccountRequired: false, contactEmail: M.testflight.feedbackEmail }, contact || {});
    let cur = null; try { cur = (await get('/v1/appStoreVersions/' + v.id + '/appStoreReviewDetail')).data; } catch (e) {}
    if (cur) await patch('/v1/appStoreReviewDetails/' + cur.id, { data: { type: 'appStoreReviewDetails', id: cur.id, attributes: attrs } });
    else await post('/v1/appStoreReviewDetails', { data: { type: 'appStoreReviewDetails', attributes: attrs, relationships: { appStoreVersion: rel('appStoreVersions', v.id) } } });
    log('İnceleme', 'not yazıldı');
  };

  async function pricePoint(path, target) {
    let best = null;
    for (const p of await all(path)) { const cp = parseFloat(p.attributes.customerPrice); if (cp + 1e-6 >= target && (!best || cp < best[0])) best = [cp, p.id]; }
    return best;
  }

  S.iaps = async app => {
    const have = {}; (await get('/v1/apps/' + app.id + '/inAppPurchasesV2?limit=200')).data.forEach(x => have[x.attributes.productId] = x);
    let territories = null;
    for (const p of M.iaps) {
      const pid = p.productId;
      try {
        let iap = have[pid];
        if (!iap) {
          iap = (await post('/v2/inAppPurchases', { data: { type: 'inAppPurchases', attributes: { name: p.refName, productId: pid, inAppPurchaseType: p.type, reviewNote: M.iapReviewNote, familySharable: false }, relationships: { app: rel('apps', app.id) } } })).data;
          log('IAP', pid + ' oluşturuldu');
        }
        const iid = iap.id;
        const locs = {}; (await get('/v2/inAppPurchases/' + iid + '/inAppPurchaseLocalizations')).data.forEach(l => locs[l.attributes.locale] = l);
        for (const loc of Object.keys(M.localizations)) {
          if (!p[loc]) continue;
          const a = { name: p[loc].name, description: p[loc].description };
          try {
            if (locs[loc]) await patch('/v1/inAppPurchaseLocalizations/' + locs[loc].id, { data: { type: 'inAppPurchaseLocalizations', id: locs[loc].id, attributes: a } });
            else await post('/v1/inAppPurchaseLocalizations', { data: { type: 'inAppPurchaseLocalizations', attributes: Object.assign({ locale: loc }, a), relationships: { inAppPurchaseV2: rel('inAppPurchases', iid) } } });
          } catch (e) { log('IAP dil HATA ' + pid + ' ' + loc, e.message); }
        }
        let sched = null; try { sched = (await get('/v2/inAppPurchases/' + iid + '/iapPriceSchedule?include=manualPrices')).data; } catch (e) {}
        const hasPrice = sched && sched.relationships && sched.relationships.manualPrices && (sched.relationships.manualPrices.data || []).length;
        if (!hasPrice) {
          const best = await pricePoint('/v2/inAppPurchases/' + iid + '/pricePoints?filter[territory]=TUR&limit=200', p.priceTRY);
          if (!best) log('IAP fiyat HATA', pid);
          else {
            await post('/v1/inAppPurchasePriceSchedules', { data: { type: 'inAppPurchasePriceSchedules', relationships: {
              inAppPurchase: rel('inAppPurchases', iid), baseTerritory: rel('territories', 'TUR'), manualPrices: { data: [{ type: 'inAppPurchasePrices', id: '${p1}' }] } } },
              included: [{ type: 'inAppPurchasePrices', id: '${p1}', attributes: { startDate: null }, relationships: { inAppPurchasePricePoint: rel('inAppPurchasePricePoints', best[1]) } }] });
            log('IAP fiyat', pid + ' ₺' + best[0]);
          }
        }
        let av = null; try { av = (await get('/v2/inAppPurchases/' + iid + '/inAppPurchaseAvailability')).data; } catch (e) {}
        if (!av) {
          if (!territories) territories = (await all('/v1/territories?limit=200')).map(t => t.id);
          await post('/v1/inAppPurchaseAvailabilities', { data: { type: 'inAppPurchaseAvailabilities', attributes: { availableInNewTerritories: true },
            relationships: { inAppPurchase: rel('inAppPurchases', iid), availableTerritories: { data: territories.map(t => ({ type: 'territories', id: t })) } } } });
          log('IAP ülkeler', pid + ' ' + territories.length);
        }
        let rs = null; try { rs = (await get('/v2/inAppPurchases/' + iid + '/appStoreReviewScreenshot')).data; } catch (e) {}
        if (!rs || !['COMPLETE', 'UPLOAD_COMPLETE'].includes((rs.attributes.assetDeliveryState || {}).state)) {
          const f = 'appstore/iap_review.png';
          const r = (await post('/v1/inAppPurchaseAppStoreReviewScreenshots', { data: { type: 'inAppPurchaseAppStoreReviewScreenshots', attributes: { fileName: A[f].name, fileSize: A[f].size }, relationships: { inAppPurchaseV2: rel('inAppPurchases', iid) } } })).data;
          await upload(r, f);
          log('IAP görsel', pid);
        }
        log('IAP durum', pid + ' ' + (await get('/v2/inAppPurchases/' + iid)).data.attributes.state);
      } catch (e) { log('IAP HATA ' + pid, e.message); }
    }
  };

  S.price = async app => {
    try {
      const cur = (await get('/v1/apps/' + app.id + '/appPriceSchedule')).data;
      if (cur && (await get('/v1/appPriceSchedules/' + cur.id + '/manualPrices?limit=1')).data.length) { log('Fiyat', 'zaten ayarlı'); return; }
    } catch (e) {}
    const best = await pricePoint('/v1/apps/' + app.id + '/appPricePoints?filter[territory]=USA&limit=200', 0);
    await post('/v1/appPriceSchedules', { data: { type: 'appPriceSchedules', relationships: {
      app: rel('apps', app.id), baseTerritory: rel('territories', 'USA'), manualPrices: { data: [{ type: 'appPrices', id: '${p0}' }] } } },
      included: [{ type: 'appPrices', id: '${p0}', attributes: { startDate: null }, relationships: { appPricePoint: rel('appPricePoints', best[1]) } }] });
    log('Fiyat', 'Ücretsiz');
  };

  S.testflight = async app => {
    const tf = M.testflight;
    const locs = {}; (await get('/v1/apps/' + app.id + '/betaAppLocalizations')).data.forEach(l => locs[l.attributes.locale] = l);
    for (const loc of ['tr', 'en-US']) {
      const a = { feedbackEmail: tf.feedbackEmail, description: tf.description, marketingUrl: M.urls.marketing, privacyPolicyUrl: M.urls.privacy };
      if (locs[loc]) await patch('/v1/betaAppLocalizations/' + locs[loc].id, { data: { type: 'betaAppLocalizations', id: locs[loc].id, attributes: a } });
      else await post('/v1/betaAppLocalizations', { data: { type: 'betaAppLocalizations', attributes: Object.assign({ locale: loc }, a), relationships: { app: rel('apps', app.id) } } });
    }
    const groups = (await get('/v1/apps/' + app.id + '/betaGroups')).data;
    if (!groups.some(g => g.attributes.isInternalGroup)) {
      await post('/v1/betaGroups', { data: { type: 'betaGroups', attributes: { name: 'Flix ekibi', isInternalGroup: true, hasAccessToAllBuilds: true }, relationships: { app: rel('apps', app.id) } } });
      log('TestFlight', 'Flix ekibi grubu açıldı');
    }
    log('TestFlight', 'test bilgileri yazıldı');
  };

  S.run = async (steps) => {
    const app = await S.app();
    for (const s of steps) { try { await S[s](app); } catch (e) { log(s + ' HATA', e.message); } }
    return LOG.slice();
  };
})();
