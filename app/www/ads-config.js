/* Paty: the one place for AdMob ids and switches (app only; the web build never loads AdMob).
   Real ids come from AdMob (apps.admob.com > Apps > Add app > iOS "Paty" > Ad units: one Rewarded, one Interstitial).
   An id left empty (or not in the ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX form) falls back to Google's TEST ad unit,
   so a build never shows real ads by mistake and never crashes on a malformed id.
   Instead of editing this file you can set the GitHub secrets PATY_ADMOB_APP_ID, PATY_ADMOB_REWARDED_ID and
   PATY_ADMOB_INTERSTITIAL_ID (the TestFlight workflow passes them on; tools/ios_setup.py writes them into the app).
   tools/ads_audit.py prints on every TestFlight run which ads are REAL and which are TEST.
   Ad pacing is a game rule and lives in the game (maybeInterstitial / rewardedAd in src/game.js):
   - Rewarded: only when the player taps it (+30 coins in the shop, 5 a day; +1 try in the search game). Reward only after AdMob's reward callback.
   - Interstitial: only after a mini-game or a search, never in the tutorial, at most once every 3 minutes, never within
     a minute of a rewarded ad, never with "No Ads" (paty_noads). No banner. */
window.FLIX_ADS_CONFIG = {
  forceTestAds: false,
  ids: {
    IOS_APP_ID: 'ca-app-pub-9939733946730095~2924028181',          // ca-app-pub-XXXXXXXXXXXXXXXX~XXXXXXXXXX (with ~)
    IOS_REWARDED: 'ca-app-pub-9939733946730095/1391454661',        // ca-app-pub-XXXXXXXXXXXXXXXX/XXXXXXXXXX (with /)
    IOS_INTERSTITIAL: 'ca-app-pub-9939733946730095/6237633416',
    IOS_BANNER: '',
    ANDROID_REWARDED: '',
    ANDROID_INTERSTITIAL: '',
    ANDROID_BANNER: ''
  },
  bannerEnabled: false,
  // Apple's "Allow tracking?" question, asked once, after Google's consent message and before AdMob starts (ads.js).
  // If you set false, also change App Store Connect > App Privacy so "Device ID" is no longer "used for tracking".
  requestTracking: true,
  testDevices: []
};
