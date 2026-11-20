#!/usr/bin/env python3
"""Fills App Store Connect for Paty from appstore/metadata.json, through the App Store Connect API. Safe to run again:
every step looks first and only creates or changes what is missing or different. Each step prints a notice; a step
that fails does not stop the others. Run it from GitHub Actions ("App Store Connect kurulum") or locally:
  ASC_KEY_ID=... ASC_ISSUER_ID=... ASC_KEY_P8="$(cat AuthKey_XXX.p8)" python3 app/tools/asc_setup.py [--only step,step]
Steps: bundle, app, info, version, screenshots, review, iaps, price, testflight, status
What the API cannot do (stays manual, listed at the end of the run):
  - creating the app record itself (App Store Connect > Apps > + > New App)
  - App Privacy answers (App Store Connect > App Privacy) and the Paid Apps agreement
  - submitting for review"""
import hashlib, json, os, pathlib, sys, time, urllib.error, urllib.request
import jwt

ROOT = pathlib.Path(__file__).resolve().parents[2]
M = json.loads((ROOT / 'appstore' / 'metadata.json').read_text(encoding='utf-8'))
KID, ISS, KEY = os.environ['ASC_KEY_ID'], os.environ['ASC_ISSUER_ID'], os.environ['ASC_KEY_P8']
ONLY = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
API = os.environ.get('ASC_API_BASE', 'https://api.appstoreconnect.apple.com')
MANUAL = []
_tok = [None, 0]


def token():
    if time.time() > _tok[1] - 60:
        now = int(time.time())
        _tok[0] = jwt.encode({'iss': ISS, 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'}, KEY, algorithm='ES256', headers={'kid': KID, 'typ': 'JWT'})
        _tok[1] = now + 1100
    return _tok[0]


class ApiError(Exception):
    pass


def call(method, path, body=None, raw=None, headers=None, url=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {'Authorization': 'Bearer ' + token()} if not url else {}
    if body is not None: h['Content-Type'] = 'application/json'
    h.update(headers or {})
    req = urllib.request.Request(url or API + path, data=data, method=method, headers=h)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                txt = r.read()
                return json.loads(txt) if txt and r.headers.get('Content-Type', '').startswith('application/json') else {}
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors='replace')
            if e.code in (429, 500, 502, 503) and attempt < 3: time.sleep(3 * (attempt + 1)); continue
            try: det = '; '.join('%s: %s' % (x.get('title'), x.get('detail')) for x in json.loads(txt)['errors'])
            except Exception: det = txt[:400]
            raise ApiError('%s %s -> HTTP %s %s' % (method, path or url, e.code, det))


def get(path): return call('GET', path)
def post(path, body): return call('POST', path, body)
def patch(path, body): return call('PATCH', path, body)


def note(title, msg): print('::notice title=%s::%s' % (title, str(msg).replace('\n', ' | ')[:3500]), flush=True)
def warn(title, msg): print('::warning title=%s::%s' % (title, str(msg).replace('\n', ' | ')[:3500]), flush=True)


def step(name):
    def deco(fn):
        def run(*a):
            if ONLY and name not in ONLY: return None
            try: return fn(*a)
            except ApiError as e: warn('ASC %s' % name, e)
            except Exception as e: warn('ASC %s' % name, '%s: %s' % (type(e).__name__, e))
        return run
    return deco


def upload_asset(reservation, path):
    """Uploads a file for an asset reservation (screenshot / review screenshot) and commits it."""
    data = path.read_bytes()
    for op in reservation['attributes']['uploadOperations']:
        chunk = data[op['offset']:op['offset'] + op['length']]
        call(op['method'], None, raw=chunk, headers={h['name']: h['value'] for h in op['requestHeaders']}, url=op['url'])
    kind = reservation['type']
    patch('/v1/%s/%s' % (kind, reservation['id']), {'data': {'type': kind, 'id': reservation['id'], 'attributes': {'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()}}})


# ---------------------------------------------------------------- steps
@step('bundle')
def bundle():
    bid = M['bundleId']
    j = get('/v1/bundleIds?filter[identifier]=%s&limit=20' % bid)
    if any(b['attributes']['identifier'] == bid for b in j['data']): note('Bundle ID', '%s kayıtlı' % bid); return
    post('/v1/bundleIds', {'data': {'type': 'bundleIds', 'attributes': {'identifier': bid, 'name': 'Paty', 'platform': 'IOS'}}})
    note('Bundle ID', '%s kaydedildi (In-App Purchase varsayılan olarak açık)' % bid)


def find_app():
    j = get('/v1/apps?filter[bundleId]=%s' % M['bundleId'])
    return j['data'][0] if j['data'] else None


@step('app')
def app_attrs(app):
    want = {'contentRightsDeclaration': M['contentRights']}
    if app['attributes'].get('primaryLocale') != M['primaryLocale']: want['primaryLocale'] = M['primaryLocale']
    patch('/v1/apps/%s' % app['id'], {'data': {'type': 'apps', 'id': app['id'], 'attributes': want}})
    note('Uygulama', 'içerik hakları beyanı ve ana dil ayarlandı')


def editable_app_info(app):
    infos = get('/v1/apps/%s/appInfos' % app['id'])['data']
    for i in infos:
        if i['attributes'].get('appStoreState', i['attributes'].get('state')) not in ('READY_FOR_SALE', 'READY_FOR_DISTRIBUTION', 'REPLACED_WITH_NEW_INFO'):
            return i
    return infos[0]


@step('info')
def app_info(app):
    info = editable_app_info(app)
    iid = info['id']
    c = M['categories']
    rel = {'primaryCategory': {'data': {'type': 'appCategories', 'id': c['primary']}},
           'primarySubcategoryOne': {'data': {'type': 'appCategories', 'id': c['sub1']}},
           'primarySubcategoryTwo': {'data': {'type': 'appCategories', 'id': c['sub2']}}}
    try:
        patch('/v1/appInfos/%s' % iid, {'data': {'type': 'appInfos', 'id': iid, 'relationships': rel}})
        note('Kategori', 'Oyunlar > Simülasyon, Gündelik')
    except ApiError as e: warn('Kategori', e)
    have = {l['attributes']['locale']: l for l in get('/v1/appInfos/%s/appInfoLocalizations' % iid)['data']}
    for loc, v in M['localizations'].items():
        attrs = {'name': v['name'], 'subtitle': v['subtitle'], 'privacyPolicyUrl': M['urls']['privacy']}
        try:
            if loc in have: patch('/v1/appInfoLocalizations/%s' % have[loc]['id'], {'data': {'type': 'appInfoLocalizations', 'id': have[loc]['id'], 'attributes': attrs}})
            else: post('/v1/appInfoLocalizations', {'data': {'type': 'appInfoLocalizations', 'attributes': dict(attrs, locale=loc), 'relationships': {'appInfo': {'data': {'type': 'appInfos', 'id': iid}}}}})
            note('Ad ve alt başlık', '%s: %s / %s' % (loc, v['name'], v['subtitle']))
        except ApiError as e: warn('Ad ve alt başlık %s' % loc, '%s (ad başka bir uygulamada kullanılıyorsa metadata.json içinde değiştir)' % e)
    # Age rating 4+: every content question "none"/"no". Questions Apple adds later are answered the same way, except
    # the ones about ads (the game shows ads) which are answered "yes".
    try:
        ar = get('/v1/appInfos/%s/ageRatingDeclaration' % iid)['data']
        BOOLS = {'gambling', 'unrestrictedWebAccess', 'lootBox', 'advertising', 'messagingAndChat', 'parentalControls', 'ageAssurance',
                 'userGeneratedContent', 'healthOrWellnessTopics', 'seventeenPlus'}
        SKIP = {'kidsAgeBand', 'ageRatingOverride', 'ageRatingOverrideV2', 'koreaAgeRatingOverride', 'developerAgeRatingInfoUrl'}
        attrs = {}
        for k, v in ar['attributes'].items():
            if k in SKIP: continue
            if k in BOOLS or isinstance(v, bool): attrs[k] = (k == 'advertising')   # the game shows ads; everything else: no
            else: attrs[k] = 'NONE'
        patch('/v1/ageRatingDeclarations/%s' % ar['id'], {'data': {'type': 'ageRatingDeclarations', 'id': ar['id'], 'attributes': attrs}})
        note('Yaş derecesi', '4+ (şiddet, korku, kumar vb. hepsi Yok; reklam: Evet)')
    except ApiError as e: warn('Yaş derecesi', '%s (App Store Connect > Uygulama Bilgileri > Yaş Derecesi elle doldurulmalı)' % e); MANUAL.append('Yaş derecesi anketi (hepsi "Yok", reklam "Evet")')


def editable_version(app):
    vs = get('/v1/apps/%s/appStoreVersions?filter[platform]=IOS&limit=20' % app['id'])['data']
    for v in vs:
        if v['attributes']['appStoreState'] in ('PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY'):
            return v
    return None


@step('version')
def version(app):
    v = editable_version(app)
    if not v:
        v = post('/v1/appStoreVersions', {'data': {'type': 'appStoreVersions', 'attributes': {'platform': 'IOS', 'versionString': M['version']},
                                                   'relationships': {'app': {'data': {'type': 'apps', 'id': app['id']}}}}})['data']
        note('Sürüm', '%s oluşturuldu' % M['version'])
    vid = v['id']
    attrs = {'copyright': M['copyright'], 'releaseType': 'AFTER_APPROVAL'}
    if v['attributes']['versionString'] != M['version']: attrs['versionString'] = M['version']
    patch('/v1/appStoreVersions/%s' % vid, {'data': {'type': 'appStoreVersions', 'id': vid, 'attributes': attrs}})
    have = {l['attributes']['locale']: l for l in get('/v1/appStoreVersions/%s/appStoreVersionLocalizations' % vid)['data']}
    first = len(get('/v1/apps/%s/appStoreVersions?filter[platform]=IOS&limit=5' % app['id'])['data']) <= 1
    for loc, d in M['localizations'].items():
        attrs = {'description': d['description'], 'keywords': d['keywords'], 'promotionalText': d['promotionalText'],
                 'supportUrl': M['urls']['support'], 'marketingUrl': M['urls']['marketing']}
        if not first and d.get('whatsNew'): attrs['whatsNew'] = d['whatsNew']
        try:
            if loc in have: patch('/v1/appStoreVersionLocalizations/%s' % have[loc]['id'], {'data': {'type': 'appStoreVersionLocalizations', 'id': have[loc]['id'], 'attributes': attrs}})
            else: post('/v1/appStoreVersionLocalizations', {'data': {'type': 'appStoreVersionLocalizations', 'attributes': dict(attrs, locale=loc), 'relationships': {'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': vid}}}}})
            note('Sürüm metinleri', '%s: açıklama, anahtar kelimeler, tanıtım metni, destek ve pazarlama linki' % loc)
        except ApiError as e: warn('Sürüm metinleri %s' % loc, e)
    return vid


@step('screenshots')
def screenshots(app):
    v = editable_version(app)
    if not v: warn('Ekran görüntüleri', 'düzenlenebilir sürüm yok'); return
    locs = {l['attributes']['locale']: l['id'] for l in get('/v1/appStoreVersions/%s/appStoreVersionLocalizations' % v['id'])['data']}
    shots = ROOT / 'appstore' / 'screenshots'
    for loc in M['localizations']:
        prefix = loc.split('-')[0]
        if loc not in locs: warn('Ekran görüntüleri', '%s sürüm dili yok, önce version adımı çalışmalı' % loc); continue
        files = sorted(shots.glob('%s_*.png' % prefix))
        sets = get('/v1/appStoreVersionLocalizations/%s/appScreenshotSets' % locs[loc])['data']
        s = next((x for x in sets if x['attributes']['screenshotDisplayType'] == 'APP_IPHONE_67'), None)
        if not s:
            s = post('/v1/appScreenshotSets', {'data': {'type': 'appScreenshotSets', 'attributes': {'screenshotDisplayType': 'APP_IPHONE_67'},
                                                        'relationships': {'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': locs[loc]}}}}})['data']
        existing = get('/v1/appScreenshotSets/%s/appScreenshots?limit=20' % s['id'])['data']
        names = {x['attributes']['fileName'] for x in existing if (x['attributes'].get('assetDeliveryState') or {}).get('state') in ('COMPLETE', 'UPLOAD_COMPLETE')}
        for x in existing:  # failed or half-finished uploads from an earlier run
            if x['attributes']['fileName'] not in names: call('DELETE', '/v1/appScreenshots/%s' % x['id'])
        n = 0
        for f in files:
            if f.name in names: continue
            r = post('/v1/appScreenshots', {'data': {'type': 'appScreenshots', 'attributes': {'fileName': f.name, 'fileSize': f.stat().st_size},
                                                     'relationships': {'appScreenshotSet': {'data': {'type': 'appScreenshotSets', 'id': s['id']}}}}})['data']
            upload_asset(r, f); n += 1
        note('Ekran görüntüleri', '%s: %d yüklendi, %d zaten vardı (6,9" iPhone)' % (loc, n, len(names)))


@step('review')
def review(app):
    v = editable_version(app)
    if not v: return
    rd = os.environ.get
    attrs = {'notes': M['localizations']['tr']['reviewNotes'], 'demoAccountRequired': False,
             'contactFirstName': rd('REVIEW_FIRST_NAME') or None, 'contactLastName': rd('REVIEW_LAST_NAME') or None,
             'contactPhone': rd('REVIEW_PHONE') or None, 'contactEmail': rd('REVIEW_EMAIL') or M['testflight']['feedbackEmail']}
    attrs = {k: x for k, x in attrs.items() if x is not None}
    try:
        cur = get('/v1/appStoreVersions/%s/appStoreReviewDetail' % v['id'])['data']
    except ApiError:
        cur = None
    if cur: patch('/v1/appStoreReviewDetails/%s' % cur['id'], {'data': {'type': 'appStoreReviewDetails', 'id': cur['id'], 'attributes': attrs}})
    else: post('/v1/appStoreReviewDetails', {'data': {'type': 'appStoreReviewDetails', 'attributes': attrs, 'relationships': {'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': v['id']}}}}})
    note('İnceleme bilgileri', 'inceleme notu yazıldı' + ('' if rd('REVIEW_PHONE') else ' (iletişim adı ve telefonu yok: REVIEW_FIRST_NAME / REVIEW_LAST_NAME / REVIEW_PHONE secret olarak gir ya da elle doldur)'))
    if not rd('REVIEW_PHONE'): MANUAL.append('İnceleme iletişim bilgileri (ad, soyad, telefon)')


def price_point(pp_path, target):
    """Cheapest price point at or above the target price (customerPrice) in the given territory."""
    best = None
    path = pp_path
    while path:
        j = get(path)
        for p in j['data']:
            cp = float(p['attributes']['customerPrice'])
            if cp + 1e-6 >= target and (best is None or cp < best[0]): best = (cp, p['id'])
        nxt = j.get('links', {}).get('next')
        path = nxt.replace(API, '') if nxt else None
    return best


@step('iaps')
def iaps(app):
    have = {}
    path = '/v1/apps/%s/inAppPurchasesV2?limit=200' % app['id']
    for x in get(path)['data']: have[x['attributes']['productId']] = x
    territories = None
    for p in M['iaps']:
        pid = p['productId']
        try:
            if pid in have: iap = have[pid]
            else:
                iap = post('/v2/inAppPurchases', {'data': {'type': 'inAppPurchases', 'attributes': {'name': p['refName'], 'productId': pid, 'inAppPurchaseType': p['type'],
                                                                                                 'reviewNote': M['iapReviewNote'], 'familySharable': False},
                                                         'relationships': {'app': {'data': {'type': 'apps', 'id': app['id']}}}}})['data']
                note('IAP', '%s oluşturuldu (%s)' % (pid, p['type']))
            iid = iap['id']
            locs = {l['attributes']['locale']: l for l in get('/v2/inAppPurchases/%s/inAppPurchaseLocalizations' % iid)['data']}
            for loc in M['localizations']:
                if loc not in p: continue
                a = {'name': p[loc]['name'], 'description': p[loc]['description']}
                if loc in locs: patch('/v1/inAppPurchaseLocalizations/%s' % locs[loc]['id'], {'data': {'type': 'inAppPurchaseLocalizations', 'id': locs[loc]['id'], 'attributes': a}})
                else: post('/v1/inAppPurchaseLocalizations', {'data': {'type': 'inAppPurchaseLocalizations', 'attributes': dict(a, locale=loc), 'relationships': {'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': iid}}}}})
            # price (base territory Turkey; Apple derives the other countries)
            try:
                sched = get('/v2/inAppPurchases/%s/iapPriceSchedule' % iid).get('data')
            except ApiError: sched = None
            if not sched:
                best = price_point('/v2/inAppPurchases/%s/pricePoints?filter[territory]=TUR&limit=200' % iid, p['priceTRY'])
                if not best: warn('IAP fiyat', '%s: ₺%.2f ya da üstünde fiyat noktası bulunamadı, fiyatı elle seç' % (pid, p['priceTRY']))
                else:
                    post('/v1/inAppPurchasePriceSchedules', {'data': {'type': 'inAppPurchasePriceSchedules', 'relationships': {
                        'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': iid}},
                        'baseTerritory': {'data': {'type': 'territories', 'id': 'TUR'}},
                        'manualPrices': {'data': [{'type': 'inAppPurchasePrices', 'id': '${p1}'}]}}},
                        'included': [{'type': 'inAppPurchasePrices', 'id': '${p1}', 'attributes': {'startDate': None},
                                      'relationships': {'inAppPurchasePricePoint': {'data': {'type': 'inAppPurchasePricePoints', 'id': best[1]}}}}]})
                    note('IAP fiyat', '%s: ₺%.2f' % (pid, best[0]))
            # availability: every territory
            try:
                av = get('/v2/inAppPurchases/%s/inAppPurchaseAvailability' % iid).get('data')
            except ApiError: av = None
            if not av:
                if territories is None:
                    territories, path2 = [], '/v1/territories?limit=200'
                    while path2:
                        j = get(path2); territories += [t['id'] for t in j['data']]
                        nxt = j.get('links', {}).get('next'); path2 = nxt.replace(API, '') if nxt else None
                post('/v1/inAppPurchaseAvailabilities', {'data': {'type': 'inAppPurchaseAvailabilities', 'attributes': {'availableInNewTerritories': True},
                                                                  'relationships': {'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': iid}},
                                                                                    'availableTerritories': {'data': [{'type': 'territories', 'id': t} for t in territories]}}}})
            # review screenshot
            try:
                rs = get('/v2/inAppPurchases/%s/appStoreReviewScreenshot' % iid).get('data')
            except ApiError: rs = None
            if not rs or (rs['attributes'].get('assetDeliveryState') or {}).get('state') not in ('COMPLETE', 'UPLOAD_COMPLETE'):
                f = ROOT / 'appstore' / 'iap_review.png'
                r = post('/v1/inAppPurchaseAppStoreReviewScreenshots', {'data': {'type': 'inAppPurchaseAppStoreReviewScreenshots', 'attributes': {'fileName': f.name, 'fileSize': f.stat().st_size},
                                                                                 'relationships': {'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': iid}}}}})['data']
                upload_asset(r, f)
            st = get('/v2/inAppPurchases/%s' % iid)['data']['attributes'].get('state')
            note('IAP', '%s hazır (durum: %s)' % (pid, st))
        except ApiError as e: warn('IAP %s' % pid, e)


@step('price')
def app_price(app):
    try:
        cur = get('/v1/apps/%s/appPriceSchedule' % app['id']).get('data')
        if cur and get('/v1/appPriceSchedules/%s/manualPrices?limit=1' % cur['id'])['data']:
            note('Fiyat', 'uygulama fiyatı zaten ayarlı'); return
    except ApiError: pass
    best = price_point('/v1/apps/%s/appPricePoints?filter[territory]=USA&limit=200' % app['id'], 0)
    post('/v1/appPriceSchedules', {'data': {'type': 'appPriceSchedules', 'relationships': {
        'app': {'data': {'type': 'apps', 'id': app['id']}},
        'baseTerritory': {'data': {'type': 'territories', 'id': 'USA'}},
        'manualPrices': {'data': [{'type': 'appPrices', 'id': '${p0}'}]}}},
        'included': [{'type': 'appPrices', 'id': '${p0}', 'attributes': {'startDate': None},
                      'relationships': {'appPricePoint': {'data': {'type': 'appPricePoints', 'id': best[1]}}}}]})
    note('Fiyat', 'Ücretsiz')


@step('testflight')
def testflight(app):
    tf = M['testflight']
    locs = {l['attributes']['locale']: l for l in get('/v1/apps/%s/betaAppLocalizations' % app['id'])['data']}
    for loc in ('tr', 'en-US'):
        a = {'feedbackEmail': tf['feedbackEmail'], 'description': tf['description'], 'marketingUrl': M['urls']['marketing'], 'privacyPolicyUrl': M['urls']['privacy']}
        if loc in locs: patch('/v1/betaAppLocalizations/%s' % locs[loc]['id'], {'data': {'type': 'betaAppLocalizations', 'id': locs[loc]['id'], 'attributes': a}})
        else: post('/v1/betaAppLocalizations', {'data': {'type': 'betaAppLocalizations', 'attributes': dict(a, locale=loc), 'relationships': {'app': {'data': {'type': 'apps', 'id': app['id']}}}}})
    groups = get('/v1/apps/%s/betaGroups' % app['id'])['data']
    if not any(g['attributes'].get('isInternalGroup') for g in groups):
        post('/v1/betaGroups', {'data': {'type': 'betaGroups', 'attributes': {'name': 'Flix ekibi', 'isInternalGroup': True, 'hasAccessToAllBuilds': True},
                                         'relationships': {'app': {'data': {'type': 'apps', 'id': app['id']}}}}})
        note('TestFlight', '"Flix ekibi" dahili test grubu açıldı (tüm build\'ler otomatik). Testçileri App Store Connect > TestFlight > Flix ekibi\'nden ekle.')
    note('TestFlight', 'test bilgileri (geri bildirim e-postası, açıklama) yazıldı')


@step('status')
def status(app):
    b = get('/v1/builds?filter[app]=%s&sort=-uploadedDate&limit=5&include=preReleaseVersion' % app['id'])
    pv = {x['id']: x['attributes']['version'] for x in b.get('included', [])}
    rows = ['%s (%s) %s %s' % (pv.get((x['relationships']['preReleaseVersion']['data'] or {}).get('id'), '?'), x['attributes']['version'], x['attributes']['processingState'], x['attributes']['uploadedDate'][:16]) for x in b['data']]
    note('Build durumu', ' ; '.join(rows) or 'henüz build yok')
    ip = get('/v1/apps/%s/inAppPurchasesV2?limit=50' % app['id'])
    note('IAP durumu', ' ; '.join('%s=%s' % (x['attributes']['productId'], x['attributes']['state']) for x in ip['data']) or 'yok')


def main():
    bundle()
    app = find_app()
    if not app:
        warn('Uygulama kaydı yok', 'App Store Connect > Uygulamalar > + > Yeni Uygulama: platform iOS, ad "%s", ana dil Türkçe, paket kimliği %s, SKU %s, Tam Erişim. Sonra bu iş akışını tekrar çalıştır.'
             % (M['localizations']['tr']['name'], M['bundleId'], M['sku']))
        sys.exit(1)
    note('Uygulama', '%s (%s) bulundu' % (app['attributes']['name'], app['id']))
    app_attrs(app); app_info(app); version(app); screenshots(app); review(app); iaps(app); app_price(app); testflight(app); status(app)
    MANUAL[:0] = ['Uygulama Gizliliği anketi (README "Uygulama Gizliliği" bölümündeki cevaplar)', 'Anlaşmalar: Ücretli Uygulamalar anlaşması imzalı olmalı (satın almalar için)',
                  'Yayın ülkeleri (Fiyatlandırma ve Kullanılabilirlik)', 'İlk sürümde IAP\'leri sürüm sayfasındaki "Uygulama İçi Satın Almalar" bölümünden sürüme ekle, sonra İncelemeye Gönder']
    note('Elle yapılacaklar', ' / '.join(MANUAL))


if __name__ == '__main__':
    main()
