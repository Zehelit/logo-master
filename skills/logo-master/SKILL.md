---
name: logo-master
description: Açıkça çağrıldığında logo adayları geliştirir; kullanıcı seçiminden sonra gerçek fontlarla temiz vektör, düzenlenebilir Canva kaynakları ve kontrollü varyantlar hazırlar.
---

# Logo Master

Yalnız kullanıcı çağırdığında kullan. Görsel beğeni ve kullanıcı seçimi üretim sürecinin başlangıç koşuludur. Genel kuralları marka profiliyle karıştırma.

## Temel kurallar

- Kullanıcı geliştireceği adayı seçmeden kapsamlı vektörleştirme, Canva aktarımı, sistematik varyant veya uygulama paketi üretimine geçme. Mevcut seçilmiş tasarıma yönelik açık düzenleme isteği seçim yetkisi sayılır.
- İlk adaylarda bile yazıları gerçek fontla diz. Image Gen'e font adı vermek gerçek font kullanıldığına kanıt değildir. Fontu sessizce ikame etme.
- Seçim nihai onay değildir. Beğenilen öğeleri, korunacak özellikleri ve değişmesi istenen öğeleri kaydet. Birden fazla aday seçilebilir.
- Seçilen amblemi renk/boyut varyantı için Image Gen'e yeniden ürettirme. Mevcut geometriden kontrollü dönüşüm yap. Font değişiminde yazı değişebilir; amblem değişmemeli.
- Canlı metinli düzenleme kaynağı ile konturlu teslim SVG'sini birlikte sakla. Konturlu yazıya font ailesi değiştirilebilir deme.
- Yükleme, yerleştirme, düzenleme, kaydetme ve dışa aktarmayı ayrı doğrula. Araç başarılı yanıtı tek başına görsel kalite kanıtı değildir.

## İş akışı

1. Brief ve görsel keşif için [yaratıcı süreç](references/creative.md) belgesini oku. Önce adaylar üret, seçim bekle. Kullanıcının önceki açık seçimini tekrar sorma.
2. Seçilen aday için [vektör ve tipografi](references/vector-type.md) belgesini kullan. Canlı font kaynağını ve seçilmiş amblemi koru.
   Kaynak/seçim/bileşen/çıktı ilişkisini [ortak modelde](references/source-model.md) kaydet; mevcut envanteri önce çalışma kopyasında eşle.
3. Canva düzenlemeleri için [Canva uygulaması](references/canva.md) belgesini oku. Önce mevcut bağlayıcı yeteneklerini keşfet; eksik işlemlerde desteklenen tarayıcı arayüzünü kullan.
4. Varyant, dosyalama ve doğrulama için [üretim ve kalite](references/production.md) belgesini uygula.
5. EMESİS çalışmasında ayrıca [marka profilini](references/emesis.md) oku; diğer markalara uygulama.

## Araçlar ve süreklilik

Image Gen yaratıcı amblem/işaret araştırmasında kullanılabilir. Yazıları gerçek fontu yükleyen Canva veya vektör/dizgi aracıyla oluştur. İlk aday için sınırlı önizleme birleştirmesi, kapsamlı teknik üretime geçme yetkisi değildir.

Rasterless/Potrace izleme ve Inkscape temizleme/dışa aktarma mevcut olduklarında kullanılabilir. Dönüştürme görsel kusursuzluk garantisi değildir. Betikleri dosyalama, denetim ve mevcut çizimde kontrollü dönüşümler için kullan. Dosyaya özgü glyph kimliklerini genel dönüştürücüye sabitleme.

Proje içinde brief, aşama, seçilmiş aday ve seçim kanıtı, korunan özellikler, fontlar, dosyalar, Canva bağlantıları ve açık testleri kaydet. Sonraki oturum kaynakların mevcut durumunu doğrulayıp buradan sürdürsün. Kullanıcıya kanıtlanan sonucu ve kalan sınırlamayı bildir.

Yerel Inkscape ile gerçek fontu kontura çevirme veya bileşen ayırma gerektiğinde [yerel vektör tarifi](references/local-vector.md) belgesini oku. SVG denetleyicisi skill klasörüne göre `python scripts/inspect_svg.py ...` ile çağrılır; başka çalışma klasöründeysen betiğin mutlak yolunu kullan.

Ortak üretim girişi `python scripts/logo.py --help`: doğrulama, render, kontrollü düzenleme, kontur, ayır/birleştir, PNG, varyant kaydı ve yerel pano/paket. Komut sınırlarını üretim rehberinden oku; `needs_render` durumunu başarı diye kapatma. Yeni araç, abonelik, AGWF veya alt ajan bu skill'in gereği değildir.
