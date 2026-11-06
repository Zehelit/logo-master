# Sürüm ve kurulum sözleşmesi

GitHub `Zehelit/logo-master` private reposu kaynak geçmişini ve release'leri tutar.
Geliştirme tek checkout'ta, Codex kullanımı yönetilen skill kurulumunda yapılır.
Her sürüm için ayrı çalışma klasörü veya sürekli çalışan güncelleyici yoktur.

Sürümün tek kaynağı `skills/logo-master/VERSION` olacak; ilk adlandırılmış sürüm
1.0.0. Patch düzeltme, minor uyumlu ekleme, major uyumsuz sözleşme değişimidir.
Veri modelinin `schema_version` değeri ayrıca yönetilir. Release tag'i taşınmaz.

Kurulum ve geri dönüş araçları tamamlanmadan mevcut kurulum elle değiştirilmez.
Makbuz/tek previous kurtarma kopyası `.codex/skill-installations/logo-master`
altında, skill keşif ağacının dışında tutulur. Bilinmeyen yerel değişikliklerin
üstüne yazılmaz. Durum sorgusu ağa bağlanmaz; varsayılan özet 2048 byte'ı geçmez.

Günlük bağlam yalnız kısa durum, ilgili diff ve gereken kaynakları içerir.
Bütün Git geçmişi, eski raporlar veya tüm skill referansları otomatik okunmaz.
Gerçek logo/font/Canva varlıkları bu genel skill reposuna taşınmaz.

Taşınabilir CI sonucu gerçek font/renderer veya Canva kabulünün yerine geçmez.
Kurulu dosya sürümü, Codex oturumunun bellekte tuttuğu talimatlardan ayrıdır;
hot-reload doğrulanmadıkça vaat edilmez.
