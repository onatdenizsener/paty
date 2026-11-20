# Paty

Retro piksel evcil hayvan oyunu (Flix Toys). Oyuncu barınaktan ilk kedisini ya da köpeğini sahiplenir. Rehber Flix odaya yürüyerek gelir ve dostları besler, yıkar, onlarla oynar. Zaman gerçek saatle akar. İhmal edilen dost kaçar ve 24 saat içinde bulunmazsa kalıcı olarak gider. Barınakta nadir cinsler var, Egzotik dükkandaki dostlar elmasla alınıyor.

- Web demo: `index.html` (GitHub Pages'te açılır, satın alma ve reklamlar demo olarak işaretli)
- iOS: `app/` (Capacitor 8, `com.flixtoys.paty`, yalnızca iPhone, dikey)

## Dosyalar
| Yol | İçerik |
|---|---|
| `src/game.js` | Oyunun tamamı (çizim, simülasyon, Flix, barınak, mağaza, mini oyunlar) |
| `src/index.src.html` | Sayfa iskeleti ve stiller |
| `src/fonts/` | Pixelify Sans (SIL OFL). Oyuna gömülür, internetten hiçbir şey yüklenmez |
| `src/build.py` | `src/` → `index.html` (tek dosya) |
| `app/www/ads-config.js` | AdMob kimlikleri ve ayarları (boşsa Google test reklamı) |
| `app/www/ads.js` | AdMob servisi (Flix oyunlarındaki son, düzeltilmiş sürüm) |
| `app/www/native-bridge.js` | App Store satın almaları, geri yükleme, titreşim, yerel bildirimler |
| `app/www/flix-privacy.js` | Ayarlar'daki "Gizlilik Seçenekleri" düğmesi (AB/İngiltere/İsviçre) |
| `app/tools/ios_setup.py` | iOS projesini hazırlar: dikey, yalnızca iPhone, ikon, AdMob kimliği, ATT metni, SKAdNetwork |
| `app/tools/ads_audit.py` | Her TestFlight çalıştırmasında hangi reklamların GERÇEK, hangilerinin TEST olduğunu yazar |
| `app/tools/asc_setup.py` | App Store Connect'i `appstore/metadata.json`'dan doldurur |
| `appstore/` | Mağaza metinleri (6 dil), 6,9" ekran görüntüleri (6 dil), IAP inceleme görseli |
| `gizlilik.html`, `destek.html` | Gizlilik politikası ve destek sayfası (GitHub Pages) |

Derleme: `python3 src/build.py` → `index.html`. Uygulama için `cd app && npm ci && npm run build`.

## Önceki Flix oyunlarından alınan dersler (bu repoda baştan uygulandı)
**Satın almalar**
- **realOwned:** Ödeme ekranı açıkken eklentinin oluşturduğu geçici `virtual.*` işlem hiçbir şeyin kilidini açmaz. Sayılan tek şey gerçek, onaylanmış ya da bitmiş işlemdir. (Kick Up ve Jump'taki "ödemeyi kapatsan da ürün veriliyor" hatası.)
- **Teslim sırası:** Ürün önce oyuna teslim edilir ve hemen kaydedilir, işlem ancak ondan sonra kapatılır. Aynı işlem ikinci kez verilmez (`S.txs`).
- **Ask to Buy:** Ebeveyn onayı bekleyen alımda "onay bekliyor" mesajı çıkar, ürün onay gelince verilir.
- **Mesajlar:** Oyuncu ödeme ekranını kendisi kapatırsa mesaj çıkmaz. Mağazaya ulaşılamazsa ve satın alma başarısız olursa ayrı mesajlar çıkar.
- **Fiyatlar:** Uygulamada sabit TL fiyat yok, fiyatlar mağazadan gelir (yüklenene kadar "…" görünür).
- **Geri yükleme:** "Satın alımları geri yükle" hem Ayarlar'da hem elmas mağazasında var.

**Reklamlar**
- **İzin sırası:** Önce Google onay mesajı (yalnızca AB/İngiltere/İsviçre), sonra Apple'ın izleme izni (ATT), en son AdMob başlar. (Apple 5.1.1(iv) reddi.)
- **ATT zamanlaması:** İzleme izni uygulama tam açıldıktan sonra sorulur. (Kick Up 1.5, Guideline 2.1 reddi.)
- **addListener:** `Promise.resolve(addListener(...))` kullanılıyor. Eskiden yüklenen reklam gösterilemiyordu.
- **AdMob sürümü:** Eklenti `8.3.0`'a sabit. 8.4.0, CocoaPods'ta olmayan bir bağımlılık istiyor ve TestFlight derlemesini kırıyor.
- **Kimlikler:** Boş ya da biçimi yanlış AdMob kimliği uygulamayı çökertmez, test kimliğine düşer. `ads_audit.py` her çalıştırmada uyarır.
- **Ödüllü reklam:** Ödül yalnızca AdMob'un ödül sinyalinden sonra verilir.
- **Ara reklam:** Mini oyundan ya da aramadan sonra çıkar. Eğitimde hiç çıkmaz, 3 dakikada en fazla 1 kez gösterilir, ödüllü reklamdan sonraki 1 dakika içinde gösterilmez, "Reklamsız" alındıysa hiç çıkmaz. Banner yok.

**iOS ve TestFlight**
- Yalnızca iPhone (`TARGETED_DEVICE_FAMILY = 1` doğrulanıyor). Kick Up, iPad yüzünden Guideline 4 reddi almıştı.
- Arşiv imzasız alınıyor, imza dışa aktarırken atılıyor (sertifika sınırı sorunu).
- Build numarası düz: 1, 2, 3…
- `ITSAppUsesNonExemptEncryption = NO` olduğu için her yüklemede şifreleme sorusu gelmiyor.

**İnceleme**
- Egzotik dükkan elmasla çalışıyor. Barınağı yenilemek altınla yapılıyor (altın satın alınamaz), böylece gerçek parayla rastgele ödül ("loot box") yok. Olasılıklar yine de barınakta yazıyor.
- Test paneli uygulamada gizli: Ayarlar'da sürüm yazısına 7 kez dokununca açılıyor. Uygulamada altın, elmas ya da seviye vermiyor.
- Bildirim izni eğitimden sonra, açıklama yapılarak soruluyor.

## Yayın adımları

### 1. GitHub secret'ları (Flix Jump / Kick Up'takilerle aynı değerler)
```bash
R=onatdenizsener/paty
gh secret set APP_STORE_CONNECT_KEY_ID      -R $R -b "KEY_ID"
gh secret set APP_STORE_CONNECT_ISSUER_ID   -R $R -b "ISSUER_ID"
gh secret set APPLE_TEAM_ID                 -R $R -b "TEAM_ID"
gh secret set APP_STORE_CONNECT_PRIVATE_KEY -R $R < ~/Downloads/AuthKey_KEY_ID.p8
# İnceleme iletişim bilgisi (isteğe bağlı, App Store Connect'te elle de girilebilir)
gh secret set REVIEW_FIRST_NAME -R $R -b "Ad"
gh secret set REVIEW_LAST_NAME  -R $R -b "Soyad"
gh secret set REVIEW_PHONE      -R $R -b "+905xxxxxxxxx"
```
API anahtarının rolü **Yönetici (Admin)** olmalı.

### 2. App Store Connect'te uygulama kaydı (bir kez, elle; API ile açılamıyor)
Uygulamalar > **+** > Yeni Uygulama:
- Platform: iOS
- Ad: **Paty: Retro Evcil Hayvan**
- Ana dil: Türkçe
- Paket kimliği: `com.flixtoys.paty`
- SKU: `paty1`
- Erişim: Tam Erişim

Paket kimliği listede yoksa önce 3. adımdaki iş akışını `only=bundle` ile çalıştır, kimliği o kaydeder.

### 3. App Store Connect'i doldur
```bash
gh workflow run asc-setup.yml -R onatdenizsener/paty
```
Bu iş akışı şunları doldurur:
- 6 dilde (TR, EN, AR, FR, DE, ES) ad ve alt başlık
- Kategori: Oyunlar > Simülasyon / Gündelik
- Yaş derecesi 4+
- Sürüm 1.0 metinleri: açıklama, anahtar kelimeler, tanıtım metni, destek ve pazarlama linki, telif
- 6,9" ekran görüntüleri (6 dilde, her dilde 6 adet)
- İnceleme notu
- 4 uygulama içi ürün: TR/EN adları, fiyatları, tüm ülkeler, inceleme görseli
- Uygulama fiyatı: ücretsiz
- TestFlight test bilgileri ve "Flix ekibi" dahili test grubu

Tekrar çalıştırmak güvenli. Run sayfasındaki notice'lar her adımın sonucunu yazar.

| Ürün kimliği | Tür | Fiyat (TR) | İçerik |
|---|---|---|---|
| `paty_gems_50` | Tüketilebilir | ₺49,99 | 50 elmas |
| `paty_gems_120` | Tüketilebilir | ₺99,99 | 120 elmas |
| `paty_gems_300` | Tüketilebilir | ₺199,99 | 300 elmas |
| `paty_noads` | Tüketilemez | ₺79,99 | Reklamsız (ara reklamlar kalkar) |

### 4. TestFlight'a yükle
```bash
gh workflow run ios-testflight.yml -R onatdenizsener/paty -f version=1.0
gh run watch -R onatdenizsener/paty
```
Yükleme 15-25 dakika sürer. Build, 10-30 dakika sonra TestFlight'ta görünür. Satın almayı denemek için iPhone'da Ayarlar > App Store > Sandbox Hesabı.

### 5. Elle yapılması gerekenler (API desteklemiyor)
- **Uygulama Gizliliği** (App Store Connect > Uygulama Gizliliği): "Evet, veri toplanıyor". Seçilecekler:
  - **Cihaz Kimliği:** Üçüncü taraf reklam + Analiz; izleme için kullanılıyor: **Evet**; kimliğe bağlı: Hayır
  - **Ürün Etkileşimi:** Üçüncü taraf reklam + Analiz; izleme: Hayır
  - **Reklam Verileri:** Üçüncü taraf reklam; izleme: Hayır
  - **Kaba Konum:** Üçüncü taraf reklam; izleme: Hayır
  - **Çökme Verileri ve Performans Verileri:** Uygulama işlevselliği; izleme: Hayır
  - **Satın Alımlar:** toplanmıyor. Ödemeyi Apple işliyor, oyun yalnızca cihazda tutuyor.
  - Gizlilik politikası: https://onatdenizsener.github.io/paty/gizlilik.html
- **Anlaşmalar:** "Ücretli Uygulamalar" anlaşması imzalı olmalı. İmzalı değilse satın almalar TestFlight'ta bile çalışmaz.
- **Sürüme IAP ekleme:** İlk sürümde, sürüm sayfasındaki "Uygulama İçi Satın Almalar ve Abonelikler" bölümünden 4 ürünü ekle, sonra İncelemeye Gönder.
- **AdMob:**
  - apps.admob.com'da iOS uygulaması "Paty" aç, bir Ödüllü ve bir Geçiş reklam birimi oluştur.
  - Kimlikleri `app/www/ads-config.js`'e yaz ya da `PATY_ADMOB_APP_ID`, `PATY_ADMOB_REWARDED_ID`, `PATY_ADMOB_INTERSTITIAL_ID` secret'ı olarak gir. Girilene kadar Google test reklamları çıkar.
  - Gizlilik ve mesajlaşma bölümünde GDPR mesajı oluştur.
  - app-ads.txt dosyası flixgamestudios.com / flixtoysofficial.com kökünde olmalı.
- **GitHub Pages:** Settings > Pages > Branch: `main` / root. Gizlilik ve destek linkleri buna bağlı.

## Diller
Oyun Türkçe (varsayılan), İngilizce, Arapça (sağdan sola), Fransızca, Almanca ve İspanyolca. Dil açılış ekranından ya da Ayarlar > Dil / Language'den seçilir.
- Çeviriler: `src/i18n_src.txt` (satır başına `Türkçe || English || العربية || Français || Deutsch || Español`; `[patterns]` altında isim ve sayı içeren cümleler). `src/build.py` bunu `src/i18n.js`'e çevirip oyuna gömer.
- Oyun metni Türkçe yazılır. Çeviri, Flix'in konuşmalarına, bildirimlere, tuval yazılarına ve ekrandaki her yazıya uygulanır. Yeni bir yazı eklersen `i18n_src.txt`'e de ekle. Web'de `window.__paty.MISS` çevrilmemiş yazıları listeler.
- Mağaza: 6 dilde ad, alt başlık, açıklama, anahtar kelime, IAP adları ve 6'şar dilli ekran görüntüsü (`appstore/screenshots/<dil>_N.png`).

## Sonraki adımlar
- Çatı katı odası.
