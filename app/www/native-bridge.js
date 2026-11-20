/* Paty native bridge (Capacitor 8). The game calls window.FlixNative.{buy, restore, price, flush, haptic, notify}.
   On the web this file does nothing and the gem store runs as a clearly marked demo.
   In the iOS / Android app it connects to:
     - cordova-plugin-purchase (CdvPurchase v13): App Store / Google Play in-app purchases
     - @capacitor/haptics, @capacitor/status-bar, @capacitor/local-notifications
   Ads (AdMob) are in ads.js, their ids in ads-config.js.
   Purchase rules learned from the earlier FLIX games (do not undo them):
     1. Goods are handed to the game (window.__flixGrant, saved at once) BEFORE the transaction is finished, so a crash
        in between never loses a purchase; unfinished transactions come back on the next launch.
     2. Only real, approved/finished transactions count as owned (realOwned). The plugin's temporary "virtual.<id>"
        transaction that exists while the payment sheet is open must never unlock anything (Kick Up / Jump 1.3.5 bug).
     3. Ask to Buy: buy() answers 'pending', the goods come later through approved().
     4. Closing the payment sheet is not an error ('cancelled', the game shows nothing); a store that cannot be reached
        is 'unavailable' (the game says so). Prices always come from the store, never hard-coded in the app.
     5. "Restore Purchases" is in Settings and in the gem store (Apple guideline 3.1.1). */
(function () {
  const Cap = window.Capacitor;
  if (!Cap || !Cap.isNativePlatform || !Cap.isNativePlatform()) return;
  const ios = Cap.getPlatform() === 'ios';
  const P = Cap.Plugins || {};

  // Product ids must match App Store Connect exactly (appstore/metadata.json).
  const CONSUMABLE = ['paty_gems_50', 'paty_gems_120', 'paty_gems_300'];
  const NON_CONSUMABLE = ['paty_noads'];

  let store = null; const pending = {}; const waiting = []; const deferred = new Set();
  function isCancel(e) { const C = window.CdvPurchase && window.CdvPurchase.ErrorCode; return !!e && e.code === ((C && C.PAYMENT_CANCELLED) || 6777006); }
  function settle(id, ok) { if (pending[id]) { pending[id](ok); delete pending[id]; } }
  function deliver(t) {
    const grant = window.__flixGrant; if (!grant) return false;
    for (const p of t.products) { deferred.delete(p.id); grant(p.id, t.transactionId || null); settle(p.id, true); }
    return true;
  }
  let priceTimer = 0;
  const synced = new Set();
  function realOwned(id) {
    if (!store) return false;
    for (const r of store.localReceipts || []) for (const t of r.transactions || []) {
      if (String(t.transactionId || '').startsWith('virtual.')) continue;
      if (t.state !== 'approved' && t.state !== 'finished') continue;
      if (t.isConsumed || t.isPending) continue;
      if (t.expirationDate && +t.expirationDate <= Date.now()) continue;
      if ((t.products || []).some(p => p.id === id)) return true;
    }
    return false;
  }
  function syncOwned() {
    if (!store || !window.__flixGrant) return;
    for (const id of NON_CONSUMABLE) if (!synced.has(id) && realOwned(id)) { synced.add(id); window.__flixGrant(id, null); }
  }
  function initStore() {
    if (!window.CdvPurchase) { console.warn('CdvPurchase missing'); return; }
    const {store: S, ProductType, Platform} = window.CdvPurchase;
    const platform = ios ? Platform.APPLE_APPSTORE : Platform.GOOGLE_PLAY;
    S.register([
      ...CONSUMABLE.map(id => ({id, type: ProductType.CONSUMABLE, platform})),
      ...NON_CONSUMABLE.map(id => ({id, type: ProductType.NON_CONSUMABLE, platform}))
    ]);
    S.when()
      .approved(t => { if (deliver(t)) t.verify(); else waiting.push(t); })
      .pending(t => { for (const p of t.products) { deferred.add(p.id); settle(p.id, 'pending'); } })
      .verified(r => r.finish())
      .productUpdated(() => { clearTimeout(priceTimer); priceTimer = setTimeout(() => window.dispatchEvent(new Event('flixprices')), 300); syncOwned(); })
      .receiptUpdated(syncOwned);
    S.error(e => { console.warn('store error', e); for (const id in pending) settle(id, isCancel(e) ? 'cancelled' : false); });
    S.initialize([platform]);
    store = S;
  }

  let lastHap = 0;
  function haptic(ms) {
    const H = P.Haptics; if (!H) return;
    const now = Date.now(); if (now - lastHap < 40) return; lastHap = now;
    H.impact({style: ms >= 80 ? 'HEAVY' : ms >= 25 ? 'MEDIUM' : 'LIGHT'}).catch(() => {});
  }

  // Local notifications: the game schedules a few reminders when it goes to the background and cancels them when it comes back.
  const LN = P.LocalNotifications;
  const notify = LN ? {
    async permission() {
      try { let p = await LN.checkPermissions(); if (p.display === 'prompt' || p.display === 'prompt-with-rationale') p = await LN.requestPermissions(); return p.display === 'granted'; }
      catch (e) { return false; }
    },
    async schedule(items) {
      try {
        const p = await LN.checkPermissions(); if (p.display !== 'granted') return;
        await this.cancel();
        const list = (items || []).filter(i => i.at > Date.now() + 60000).slice(0, 6)
          .map((i, k) => ({id: 100 + k, title: i.title, body: i.body, schedule: {at: new Date(i.at), allowWhileIdle: true}}));
        if (list.length) await LN.schedule({notifications: list});
      } catch (e) { console.warn('notify', e); }
    },
    async cancel() {
      try { const r = await LN.getPending(); if (r.notifications && r.notifications.length) await LN.cancel({notifications: r.notifications.map(n => ({id: n.id}))}); } catch (e) {}
    }
  } : null;

  window.FlixNative = {
    // true (bought), 'pending' (Ask to Buy), 'cancelled' (sheet closed), 'unavailable' (store not loaded / offline), 'busy', false (failed)
    buy(id) {
      return new Promise(res => {
        if (deferred.has(id)) return res('pending');
        if (!store) return res('unavailable');
        const prod = store.get(id), offer = prod && prod.getOffer();
        if (!offer) return res('unavailable');
        if (pending[id]) return res('busy');
        pending[id] = res;
        offer.order().then(err => { if (err) settle(id, isCancel(err) ? 'cancelled' : false); }, () => settle(id, false));
      });
    },
    async restore() {
      if (!store) throw new Error('store unavailable');
      const err = await store.restorePurchases();
      if (err) throw err;
      return NON_CONSUMABLE.filter(id => realOwned(id));
    },
    price(id) { const p = store && store.get(id); return p && p.pricing ? p.pricing.price : null; },
    flush() { for (const t of waiting.splice(0)) if (deliver(t)) t.verify(); syncOwned(); },
    haptic,
    notify
  };

  document.addEventListener('deviceready', () => { try { initStore(); } catch (e) { console.warn('store init', e); store = null; } }, false);
  if (P.StatusBar) P.StatusBar.hide().catch(() => {});
})();
