# Sürüm ve kurulum sözleşmesi

GitHub `Zehelit/logo-master` private reposu kaynak geçmişinin merkezidir.
Geliştirme tek checkout'ta, Codex kullanımı ayrı skill kurulumunda yapılır.
Her sürüm için ayrı çalışma klasörü veya sürekli çalışan güncelleyici yoktur.

Sürümün kaynağı `skills/logo-master/VERSION` dosyasıdır. Patch düzeltme,
minor uyumlu ekleme, major uyumsuz sözleşme değişimidir. `schema_version`
veri biçimini ayrıca tanımlar. Adlandırılmış sürümler `vX.Y.Z` Git tag'iyle
işaretlenebilir; yayımlanmış tag taşınmaz. GitHub Release zorunlu değildir.
Eski `v1.0.0` Release ve arşivleri tarihsel kayıt olarak korunur; yeni
kurulum ve dağıtım bunları kullanmaz.

## Doğrudan kaynak sözleşmesi

[INSTALL.md](../INSTALL.md) insan ve AI ajanı kurulumunun ortak yönergesidir.
`install` yerel `HEAD`, `--ref` ise yereldeki seçili tag/commit'i çözer.
Commit içindeki `skills/logo-master/` dosyaları Git blob'larından okunur;
commit edilmemiş dosyalar kurulmaz. VERSION, tam commit ve her dosyanın
SHA-256 özeti makbuza kaydedilir. Kaynağın origin'i beklenen repo olmalıdır.
Kurulum sırasında ağ erişimi veya GitHub CLI kullanılmaz. Kaynağı almak ve
yenilemek ayrı, açık `clone`, `pull` veya `fetch` işlemleridir.

Varsayılan hedef `.codex/skills/logo-master`; `CODEX_HOME` ayarlanmışsa onun
skill dizinidir. Makbuz/tek previous kurtarma kopyası Codex kökünün
`skill-installations/logo-master` klasöründe, skill keşif ağacının dışında
tutulur. Aynı commit yeniden kurulursa no-op'tur. Bilinmeyen yerel değişikliklerin
üstüne yazılmaz. Durum sorgusu ağa bağlanmaz; varsayılan özet 2048 byte'ı geçmez.

`status` exit0 ile clean/modified/unmanaged/invalid/recovery_required döndürür;
exit0 tek başına kabul değildir. Mutasyonda exit2 önkoşul ret, exit3 journal
nedeniyle kurtarma gerektiğidir. `--tag` eski komutlarla uyumludur; yalnız
Git tag'i ve VERSION eşleşmesini gerektirir. İlk VERSION'sız kurulumun açık
benimsenmesi, tüm dosyaların exact Git baseline ile eşleşmesine bağlıdır.
`__pycache__`, `.pyc`, `.pyo` yeniden üretilebilir önbellektir.

Kesinti halinde `recover` journal ile gerçek hash'leri karşılaştırır.
Hazırlık sırasında kesilirse eski kurulumu korur; hazır işlemde doğrulanmış
yeni kurulumu tamamlar. İkinci recover no-op'tur. Klasör rename'leri ve receipt
yazımı tek fiziksel atomik işlem değildir. Tek yazar OS kilidi vardır.
Kurulum sırasında aynı kaynakları kullanan logo işlerini çalıştırmayın.

Tek previous eski kurulumu tutar; sonraki başarılı kurulumda önceki previous
doğrulanıp kaldırılır. Değişmiş previous korunur ve işlem reddedilir. Junction,
symlink, yol kaçışı ve Windows harf/yol çakışmaları kabul edilmez.
Tamamen elle kopyalama seçeneği yönetim makbuzu ve otomatik rollback sağlamaz.

## Test ve sürüm işaretleme

`tools/check.py` kaynak/test ve kurulu skill'i karıştırmaz; iki test kökünü
ayrı alt süreçlerde çalıştırır, skill import'larını checkout içinde doğrular.
GitHub Windows/Python3.12 portable işi sadece contents okuma izniyle çalışır;
yayın/kurulum yapmaz. Atlanan beş font/renderer testi isimleriyle raporlanır.
Full profil gerçek Inkscape/Pango'yu başlatır ve sıfır atlama ister.

Sürüm işaretlemeden önce temiz exact commit'in CI sonucu ve yerel full
raporu doğrulanır. CHANGELOG ile VERSION aynı kaynakta güncellenir. Uygun
commit'e Git tag'i eklenir; paket derleme/yükleme veya Release açma gerekmez.
Sonradan düzeltme yeni commit ve gerektiğinde yeni sürümdür.

Günlük bağlam kısa durum, ilgili diff ve gereken kaynaklarla sınırlıdır.
Bütün Git geçmişi ve eski raporlar otomatik okunmaz. Gerçek logo/font/Canva
varlıkları bu genel skill reposuna taşınmaz. Kurulu dosya sürümü, oturumun
bellekte tuttuğu talimatlardan ayrıdır; hot-reload vaat edilmez.

İlk kabul Windows ve mevcut renderer ortamı içindir. Bu yönetim sistemi
logo estetiği, baskı/nakış veya Canva senkronizasyonunu doğrulamaz.
