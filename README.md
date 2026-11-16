# Logo Master

Logo Master, logo tasarımı geliştiren Codex kullanıcılarının adayları gerçek fontlarla hazırlamasına, seçilen tasarımı düzenlenebilir SVG'ye dönüştürmesine ve kontrollü varyantlar üretmesine yardımcı olan bir skill'dir. Codex'te `$logo-master` ile çağrılır.

[Kurulum](INSTALL.md) · [İlk kullanım](#ilk-kullanım) · [Mimari ve iş akışı](docs/architecture.md) · [Değişiklik günlüğü](CHANGELOG.md)

## Ne yapabilirsiniz?

| İhtiyaç | Çıktı |
| --- | --- |
| Logo yönelimlerini karşılaştırmak | İsteğe göre Image Gen ile araştırılmış amblemler ve gerçek fontla dizilmiş aday önizlemeleri |
| Seçilen tasarımın rengini, yazısını veya yerleşimini değiştirmek | Korunan amblem geometrisi, düzenlenebilir metinli SVG ve konturlu teslim SVG'si |
| Bir logo dosyasını teknik olarak incelemek | SVG yapısı, kaynak türü, PNG boyutu, DPI ve saydamlık ölçümleri |
| Canva'da parçaları ayrı düzenlemek | Yükleme öncesi denetlenmiş kaynak ve kullanıcı hesabında ayrıca sınanan düzenleme, kaydetme ve dışa aktarma adımları |
| Birden çok varyantı paylaşmak | Yerel HTML karşılaştırma panosu, çalışma arşivi veya onay ve teknik kabul kanıtıyla hazırlanan teslim paketi |

## İlk kullanım

[Skill'i kurduktan](INSTALL.md) sonra Codex'e örneğin şunu yazın.

> $logo-master — Bir elektronik teknik servisi için biri harf amblemli, diğeri soyut amblemli iki logo önizlemesi hazırla. Firma adını gerçek fontla diz. Geliştirilecek adayı seçebilmem için ikisini yan yana göster.

Seçimden sonra, örneğin amblemin sadece dolgu rengini değiştiren bir varyant isteyin. Düzenleme kaynağı, konturlu SVG ve gerekiyorsa PNG, tasarım kararlarıyla birlikte proje klasöründe tutulur. Elle çalıştırabileceğiniz küçük bir SVG denetimi de [kurulum rehberinde](INSTALL.md#ilk-işlem) bulunur.

## Kurulum

Windows için [yönetilen ve tamamen elle kurulum adımları](INSTALL.md#kullanıcı-için-yönetilen-kurulum) doğrudan Git kaynağını kullanır. Python 3.12 ve Git ile sınanan yönetilen kurulum varsayılan olarak checkout'un commit edilmiş `HEAD` içeriğini kurar. [Ajan için kurulum görevi](INSTALL.md#ai-ajanı-ile-kurulum) kaynak seçimini, hedefi ve doğrulama adımlarını tarif eder.

SVG ve PNG işlemlerinin bağımlılıkları, gerçek fontlu render için Inkscape ve Pango, oturuma bağlı Canva ve Image Gen gereksinimleri [üretim araçları bölümünde](INSTALL.md#kurulumdan-sonra-üretim-araçları) açıklanır. [Güncelleme](INSTALL.md#güncelleme-ve-belirli-sürüm), [geri dönüş](INSTALL.md#geri-dönüş-kesinti-ve-eski-kurulum) ve [kaldırma](INSTALL.md#kaldırma-ve-veri-koruma) adımları kurulum rehberindedir.

## Mimari ve proje dosyaları

Codex, [skill yönergesini](skills/logo-master/SKILL.md) okur ve gerektikçe yerel logo CLI'sini veya bağlı araçları çağırır. Logo kaynakları, proje JSON'u ve çıktılar seçtiğiniz proje dizininde tutulur. Kurulum aracı ise Git'ten kullanıcı skill dizinine kopyalar ve kurulum makbuzu tutar. Bileşenler, tasarım adımları ve karar sorumlulukları [mimari belgesinde](docs/architecture.md) gösterilir.

| Yol | Sorumluluk |
| --- | --- |
| [`skills/logo-master/`](skills/logo-master/) | Codex yönergeleri, üretim CLI'si, referanslar ve skill testleri |
| [`tools/skillctl.py`](tools/skillctl.py) | Yönetilen kurulum, durum, geri dönüş ve kesinti kurtarma |
| [`tools/check.py`](tools/check.py) · [`tests/`](tests/) | Depo ve skill testlerini ayrı süreçlerde çalıştıran doğrulama |
| [`docs/versioning.md`](docs/versioning.md) | Git kaynağı, sürüm ve kurulum kayıtları |

## Doğrulama ve sınırlar

Repo kökünde, yeni bir rapor yolu kullanarak çalıştırın.

```powershell
python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Test bağımlılıkları kurulamadı.' }
python tools/check.py --profile portable --report .artifacts/portable-yeni.json
if ($LASTEXITCODE -ne 0) { throw 'Portable doğrulama başarısız.' }
```

Portable profil altı font/renderer testini adıyla atlar. Tam profil için repo kökünde UTF-8 kodlu `environment.local.json` oluşturun. Aşağıdaki yollar örnektir. Kendi ortamınızdaki mevcut dosyaların mutlak yollarını yazın.

```json
{
  "LOGO_INKSCAPE": "C:/ornek/inkscape/bin/inkscape.exe",
  "LOGO_FONT_PYTHON": "C:/ornek/pango/python.exe",
  "FONTCONFIG_FILE": "C:/ornek/fontconfig/fonts.conf",
  "PANGOCAIRO_BACKEND": "fc"
}
```

İlk üç alan zorunludur. `LOGO_FONT_PYTHON`, `gi`, Pango ve PangoCairo'yu yükleyebilen Python çalıştırıcısına işaret eder. Fontconfig yapılandırmasında gerçek **Exo 2 Regular ve Bold** dosyalarını içeren dizini tanımlayın. Tam testin italik geri dönüş denetimi için bu test ortamında Exo 2'nin italik yüzü bulunmamalıdır. Örnekteki isteğe bağlı `PANGOCAIRO_BACKEND=fc`, Pango'nun Fontconfig tabanlı yazı tipi haritasını kullanmasını sağlar. [Yerel vektör rehberi](skills/logo-master/references/local-vector.md)

```powershell
python tools/check.py --profile full --environment environment.local.json --report .artifacts/full-yeni.json
if ($LASTEXITCODE -ne 0) { throw 'Tam doğrulama başarısız.' }
```

Tam profil sıfır test atlaması ister. `environment.local.json` makineye özel bir dosyadır ve Git dışında tutulur.

SVG/PNG denetimi dosyanın teknik özelliklerini ölçer. Görsel seçim ve baskı/nakış kabulü ayrı değerlendirmelerdir. Canva ön kontrolü yerel dosyayı doğrular. Canva'daki düzenleme ve dışa aktarma için ilgili tasarım üzerinde [ayrı kontroller](skills/logo-master/references/canva.md) gerekir.

## Sürüm ve lisans

Bu kaynak ağacındaki paket sürümü [`VERSION`](skills/logo-master/VERSION) dosyasındadır. Dağıtım doğrudan Git üzerinden yapılır. [Sürüm sözleşmesi](docs/versioning.md) checkout'u, kurulu dosyaları ve açık Codex oturumunu ayrı ele alır.

Depoda bir lisans belirtilmemiştir.
