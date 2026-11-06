# Değişiklik günlüğü

## 1.1.0

Kurulum ve dağıtım doğrudan Git reposuna taşındı. Kullanıcı için elle klasör
kopyalama ve yönetilen kurulum; AI ajanı için aynı komutu kullanan ayrı
yönerge INSTALL.md içinde. `install` yerel HEAD'i, `--ref` seçili tag/commit'i
kurar; Release, ZIP, GitHub CLI ve kurulum sırasında ağ erişimi gerektirmez.
Eski `--tag` seçeneği korunur; artık Git tag'i yeterlidir.

Makbuz biçimi, yerel değişiklik koruması, kesinti kurtarma ve tek önceki kopya
ile geri dönüş korunur. `CODEX_HOME` desteği eklendi. ZIP paketleme/indirme
araçları kaldırıldı; tarihsel v1.0.0 Release ve tag değişmedi.

## 1.0.0

İlk adlandırılmış sürüm; önceki logo-master üretim yardımcıları ve açık çağrı
politikası korunur. Sürüm kimliği, commit'ten paketleme, yönetilen kurulum,
geri dönüş/kurtarma ve ayrı portable/full test profilleri eklenir.

Canva font binary/sürüm eşitliği ve otomatik çift yönlü senkronizasyon vaat
edilmez. Fiziksel telefon, başka makine/renderer ve baskı/nakış kabulü kapsam
dışıdır. Önceki Canva ve logo üretim kabulü yeni yapılmış sayılmaz.
