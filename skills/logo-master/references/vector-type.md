# Gerçek fontlar ve vektör kaynakları

Font ailesi, ağırlığı/stili, kaynağı, varsa sürümü, kullanım lisansı kaynağı ve kullanıldığı araç kaydedilir. Erişim/ücret durumunu doğrula; satın alma varsayma. İ/ı, Ş/ş, Ğ/ğ, Ç/ç, Ö/ö, Ü/ü karakterlerini gerçek metinle kontrol et. Görsel benzerliğe dayalı tahmini kesin font adı diye yazma.

Canva'da bulunan fontun yerelde aynı sürümle kurulu olduğunu varsayma. İkame oluşursa doğru fontu sağla veya kullanıcıya yeni seçenek göster. Özel harf müdahalesi seçilmişse temel fontu ve değişen harfleri kaydet; standart fontla birebir aynı olduğunu iddia etme.

## Geometri temizliği

Rasterdaki doku, ışık ve ton farklılıklarını şekilden ayır. Tek renk siluette uygun izleme eşiği iç boşlukları ve ince bağlantıları korusun. Çok renkli işarette bölgeleri ayrı ele al. Sırf düğüm azaltmak için biçimi bozma.

İzleme sonrasında iç/dış konturlar, köşeler, kıvrımlar, amaçlanan simetri, boşluklar ve kalınlıkları incele. Otomatik izleme kusursuz yeniden çizim değildir. Seçilen siluetten sapmayı düzelt veya kullanıcıya karşılaştırma göster.

## Kaynak türleri

1. Düzenlenebilir kaynak: ayrı amblem, marka yazısı ve alt satırlar; canlı font bilgileri, yerleşim ve renk rolleri.
2. Teslim SVG'si: gerçek vektör yolları, gereken font konturları, doğru viewBox ve amaçlanan şeffaflık. Harfleri gerçek fonttan kontura dönüştür; raster harf izlemeyi varsayılan yapma.

Canva PDF'deki glyph konturlarını Inkscape/Poppler ile almak bir seçenektir. Her PDF'nin metni vektör tuttuğunu kontrol et. Dosyaya özgü glyph/source kimliklerini ve grup sayılarını yeni dosyaya sabitleme; bitmap amblemi nihai SVG'ye kopyalama.

SVG içindeki image, filter, maske, clip, dış referans, use/clone ve transform öğelerini incele. Varlıkları otomatik hata değildir; görünüm ve taşınabilirliğe etkilerini belirle. Düz logo tesliminde beklenmeyen raster/doku olmamalı. Gerçek renderer ile önizle; sayfa sınırında kontur kırpılmasını kontrol et.
