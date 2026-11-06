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

## Kurulum komutları

Repo kökünden:

```powershell
python tools/skillctl.py status
python tools/skillctl.py status --details
python tools/skillctl.py install --tag v1.0.0
python tools/skillctl.py rollback
python tools/skillctl.py recover
```

İlk eski kurulum yalnız exact Git baseline eşleşmesiyle benimsenir:
`install --tag v1.0.0 --adopt-baseline <tam-commit>`.
Bu seçenek genel üzerine yazma izni değildir. Kaynak eklenmiş/değişmiş/silinmişse
işlem reddedilir. `__pycache__`, `.pyc`, `.pyo` yeniden üretilebilir önbellektir.

Kurulum uzak release/tag/commit'i, indirilen SHA256SUMS'u ve paket payload'ını
Git commit dosyalarıyla karşılaştırır. `status` yalnız diski okur; GitHub'a gitmez.
`status` exit0 ve clean/modified/unmanaged/invalid/recovery_required döndürür.
Mutasyonda exit2 önkoşul ret, exit3 journal nedeniyle kurtarma gerektiğidir.

Kesinti halinde önce durumu okuyun; `recover` journal ve gerçek hash'leri
karşılaştırır. Hazırlık sırasında kesilirse eski kurulumu korur; hazır işlemde
doğrulanmış yeni kurulumu tamamlar. Aynı recover ikinci kez no-op'tur. Klasör
rename'leri ve receipt yazımı tek fiziksel atomik işlem değildir. Tek yazar OS
kilidi vardır; çalışan logo üretim işleri bitmeden kurulum yapmayın.

Tek previous eski kurulumu tutar; sonraki başarılı kurulumda önceki previous
doğrulanıp kaldırılır. Değişmiş previous korunur ve işlem reddedilir. Junction,
symlink, arşiv kaçışı ve Windows harf/yol çakışmaları kabul edilmez.
