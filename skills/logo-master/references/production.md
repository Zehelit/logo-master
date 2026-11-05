# Kontrollü üretim ve teslim

Önce [ortak kaynak modelini](source-model.md) kullan. Kaynak, bileşen, font, seçim ve çıktı ilişkileri burada tutulur. Mevcut başka envanteri yerinde dönüştürmeden önce salt okunur eşleme yap. Sayı, marka adı ve araç yolu genel kodda sabit değildir.

## Tek giriş noktası

Skill köküne göre `python scripts/logo.py --help`; başka klasörde mutlak yol kullan. Gereksinimler: Python; PNG işlemleri için Pillow/NumPy; SVG render/kontur için Inkscape; font kanıtı için gi/Pango/PangoCairo destekli Python ve Fontconfig. Mevcut kurulumu keşfet; PATH'te olmamasını kurulu değil diye sunma. Yeni kurulum/ücretli hizmet varsayılan değildir.

`--environment ortam.json` yalnız komut sürecine LOGO_INKSCAPE, LOGO_FONT_PYTHON, FONTCONFIG_FILE, PANGOCAIRO_BACKEND ve gerekirse INKSCAPE_PROFILE_DIR verir. Sistem ayarını değiştirme. `--receipt yeni.json` sonucu kaydeder. Mevcut dosyaya yazılmaz.

```text
logo.py validate project.json
logo.py audit source.svg
logo.py audit source.svg --compare changed.svg --contract operation-contract.json
logo.py audit before.png --compare after.png
logo.py render source.svg preview.png --width 1200 --height 1200
logo.py edit project.json operation.json new-edit-dir
logo.py outline source.svg outlined.svg
logo.py split source.svg parts-dir --ids emblem brand descriptor legal
logo.py assemble parts-dir/split.json assembled.svg
logo.py export source.svg logo.png --width 2000 --height 2000 --dpi 300
logo.py stage project.json new-edit-dir/edit-receipt.json staging-dir
logo.py commit project.json staging-dir/<transaction-key>/staged.json
logo.py artifact project.json variant-id artifact-record.json
logo.py outputs project.json new-panel-dir --kinds inventory panel
logo.py package project.json new-package-dir
```

Bunlar argüman örnekleridir; dosya ve kimlikleri modelden al. İki SVG için işlem sözleşmesi, iki PNG için RGBA karşılaştırması kullanılır. `inspect_svg.py source.svg --compare changed.svg` eski çağrıyla uyumlu salt okunur imza raporudur.

## Düzenleme sözleşmesi

`edit` girdisi kind, variant_id, target_component, parameters ve sabit operation_id taşır. target_component modeldeki bileşen kimliğidir.

- recolor: parameters.replacements açık eski→yeni düz renk sözlüğü. Beyaz boşluk/çerçeve korunur; tüm dolguları tek renge çevirme varsayılanı yok. Kalıtımlı/CSS rengi tahmin edilmez.
- scale: pozitif factor; isteğe bağlı yerel center:[x,y]. Tek oranlı transform, mevcut eğriler korunur.
- layout: translate:[x,y]. Konum değişikliği ayrı varyanttır.
- canvas: width, height ve isteğe bağlı kesirli margin (0≤m<0.5). Görünür sınıra göre tek oranla ortalar. Birim dönüşümü, CSS veya desteklenmeyen preserveAspectRatio açık hata verir; sessiz varsayım yok.

Yüzdeye bağlı geometri/stil tuval yeniden boyutlamasında reddedilir; önce eski viewport bağlamında mutlak koordinata çözülmelidir. Referansı defs dışında kalan bir parçanın bağımsız kopyası bozulacaksa split başarı vermez; kaynağı bağımsız defs ile düzenle. Bu yardımcı otomatik bütün SVG özelliklerini çözmez.

Makbuz kaynak hash'i, ebeveyn, işlem ve korunan yapı sonucunu taşır. `needs_render` tamamlanmış kalite kontrolü değildir. Gerçek renderı incele; gerekçeli ek inceleme kaydını bağla. `stage` yalnız passed kabul eder. Seçilmiş amblem Image Gen ile yeniden üretilmez.

Font ailesi değiştirme otomatik CLI eylemi değildir. Gerçek dizgi aracı/Canva ile bilinçli varyant oluştur, font/yerleşimi tekrar doğrula. Konturlu yazı canlı metne dönüşmez.

`split` ortak viewBox, ata bağlamı ve defs ile parçalar ve iskelet manifest'i verir. `assemble` özgün çizim sırasına yerleştirir. Ortak defs, tuval veya ata transform değişirse sessizce düşürmez; yeniden eşleme ister. İç içe hedefler ve bozuk/çakışan id'ler reddedilir. Tight crop ve Canva yerleştirmesi ayrıca koordinat hesabı/uygulama testi gerektirir.

## Kayıt ve çıktılar

Tasarım değişikliği yeni varyanttır; format/ölçü/DPI aynı varyantın çıktısıdır. `stage` sabit işlem kimliğiyle kopya/hash hazırlar. `commit` OS kilidi, günlük, ayrılmış numara ve atomik JSON değişimi kullanır. Kesinti sonrası aynı staging kaydıyla tekrar çalıştır; ikinci varyant yaratmaz. Günlük/lock dosyalarını elle temizleme. Dosya sistemi ve JSON tek fiziksel atomik işlem değildir; günlük bu aralığın kurtarılmasını sağlar.

`artifact` mevcut dosya/hash kaydını ekler, eski kaydın üzerine yazmaz. `outputs/package` modelden envanter, aktif liste, göreceli varlıklar, manifest ve yan yana HTML çıkarır. Pasif/elenmişler panoya dönmez. Oylama/kayıt/gönderme eklenmez. Font×renk×yerleşim çarpımı kendiliğinden üretilmez. Karşılaştırma çiftlerinde ortak crop/ölçek tercihini koru; pano otomatik optik normalizasyon iddiası taşımaz.

Canlı SVG alıcının fontuna bağlı olabilir. Paylaşım için doğrulanmış PNG artifact veya konturlu teslim kullan. Paket ZIP CRC ve dosya hash'lerini doğrular; yayın, hesap, hosting veya Sites bağlantısı kurmaz. Bilinmeyen model alanlarını silme; paketleme otomatik canlı göç değildir.

SVG içindeki harici dosya/URL bağımlılığı otomatik yeniden yazılmaz: paketleyici bunu reddeder, önce kaynağı gömülü/bağımsız hale getir. ZIP ayrı geçici dizine açılarak model ve dosya hash'leri tekrar doğrulanır. Font bytes eklemek için lisans dosyası ve kanıta dayalı açık redistribution kaydı gerekir; yalnız fontun makinede bulunması dağıtım izni değildir. İzin bilinmiyorsa konturlu/raster teslim seç veya uygun kaynağı sağla. Bu kontrol lisansı yorumlayan hukuk hizmeti değildir; kullanıcı/projece doğrulanmış dağıtım kararını uygular.

## İşleme uygun denetim

Renk: hedef dışı yapı ve yol/stroke/transform korunumu. Ölçek: beklenen tek transform. Kontur: gerçek font çözümlemesi, canlı metin kalmaması, amblem ve render karşılaştırması. Birleştirme: ata/defs/sıra ve render. Export: gerçek ölçü, alfa dağılımı ve DPI.

Dosya hash'i, geometri imzası ve görünüm imzası ayrıdır. Stroke, href/use, gömülü görüntü ve sıralı ata transform zincirleri raporlanır. CSS, iç SVG viewBox bileşimi ve efektler gerçek renderer gerektirir. Yapısal passed estetik veya baskı uygunluğu belgesi değildir.

PNG DPI baskı ölçeği bilgisidir: aynı piksel ölçüsünde 96→300 yeni ayrıntı üretmez. Yalnız DPI değişiminde RGBA aynı kalmalı. SVG'den büyük render ile raster upscale ayrı raporlanır; raster ölçü değişimi açık --allow-raster-resize ister. Tüm alfa dağılımını, görünür sınırı ve aynı RGBA'nın açık/koyu/küçük görünümünü incele. Dört köşe yeterli değildir; kullanıcı istemedikçe ayrı zemin logoları türetme.

Kanıt girdiyi, işlemi, beklenen farkı, korunan özellikleri, gözlemi ve dosya/hash'i bağlar. Araç yanıtı, yapısal test, render ve Canva testi ayrı sonuçlardır. Bir örnek bütün logoları doğrulamaz. Thumbnail bulanıklığını gerçek kaynak kaybı saymadan indirilen dosyayı kontrol et. Baskı/nakış uygunluğu üretici şartları olmadan garanti edilmez.

Pano değişikliğinde gerçek tarayıcıda masaüstü ve dar ekran renderını incele. Kare, yatay ve dikey varlıkların çizilen img dikdörtgeni `.art` kutusunun hem yatay hem dikey sınırları içinde kalmalı; başlık veya sonraki karta taşmamalı. Yalnız sayfa scrollWidth kontrolü bu hatayı yakalamaz. Lazy görseller için sayfayı dolaşıp gerçek yüklemeyi doğrula. Yeni CSS'nin statik paket testinden geçmesi görsel regresyon kabulü değildir; tarayıcı erişimi yoksa render kabulünü açık bırak.
