# Ortak kaynak modeli — sürüm 1

Model dosyası proje kökünde JSON'dur. `load_project(path)` JSON'u okur; `validate_project(project, root)` salt okunur `status`, `errors`, `warnings`, `assets` raporu verir. Kaynak varlıkları modelin bulunduğu köke göre göreceli yolla ve SHA-256 ile tanımlanır. Makineye özgü yürütülebilirler modelin marka verisi değildir; çalışma ortamından sağlanır.

## Kimlik ve aşamalar

- Kök: `schema_version: 1`, sabit `project_id`, `brand` ve `designs`.
- Tasarım: `id`, pozitif `approach` ve `case`, `name` ve `variants`. Yaklaşım/case birleşimi proje içinde tekildir.
- Varyant: proje içinde tekil `id`, case içinde tekil pozitif `number`, aynı tasarımdan `parent_id` veya null, `active`, `selection`, `source`, `canvas`, `components`, `colors`, `artifacts`.
- `selection.status`: candidate / selected / approved / rejected. selected/approved için `evidence` gerekir; teknik kontrol veya model varsayımı kullanıcı seçimi değildir.
- `source`: `path`, `sha256`, `kind` (vector/hybrid/raster). SVG içinde bitmap bulunması gerçek vektör teslimi olarak adlandırılmaz.
- `canvas`: kaynak koordinat sistemindeki `width`, `height`; kök viewBox ve bileşen transform'ları SVG'de korunur.
- Bileşen: `id`, kaynak düğümünü gösteren `svg_id`, `kind` (vector/raster/live_text/outlined). `protected_properties` ve renk rolleri ihtiyaca göre eklenebilir. `live_text` ayrıca `text` ve gerçek `font` kaydı taşır.
- `font`: family, weight, style, path, sha256, source_url, license, version ve status. `license_file:{path,sha256}` lisans dosyasını, `redistribution:{allowed:true,evidence:"..."}` pakete font ekleme için doğrulanmış dağıtım kararını taşır; bilinmeyen izin true yapılmaz. Renderer çözümlemesi ayrı kanıttır; modelde isim yazması yeterli değildir. Kontur kaynağında family:null/status:unknown dürüstçe korunabilir; canlı font değişimine uygun diye sunulmaz.
- `colors`: primary/accent/legal gibi anlamlı roller ve renk değerleri. Renk değişiminde bütün dolguları aynı renge çevirmek varsayılan değildir; hedef bileşen ve korunacak roller belirtilir.
- `artifacts`: her çıktı için path, sha256, format, width, height, dpi ve üretim kaydı. Format/ölçü/DPI başka tasarım varyantı yaratmaz; görünüm değişikliği yeni varyant oluşturur. Eski çıktılar korunur.

Örnek en küçük seçilmiş kaynak:

```json
{
  "schema_version": 1,
  "project_id": "ornek-marka",
  "brand": {"name": "Örnek"},
  "designs": [{
    "id": "ozel-yazi-1", "approach": 1, "case": 1,
    "variants": [{
      "id": "ozel-yazi-1-v1", "number": 1, "parent_id": null,
      "active": true,
      "selection": {"status": "selected", "evidence": "Kullanıcının aday için açık düzenleme isteği"},
      "source": {"path": "sources/logo.svg", "sha256": "dosyanin-gercek-sha256-degeri", "kind": "vector"},
      "canvas": {"width": 1000, "height": 600},
      "components": [{"id": "amblem", "svg_id": "emblem", "kind": "vector"}],
      "colors": {"primary": "#2584c9"}, "artifacts": []
    }]
  }]
}
```

Bu şema anlatımıdır; örneğin hash'i çalıştırılabilir test verisi değildir. Gerçek kullanım örnekleri işlem raporunda dosyalarıyla üretilir.

## Canva eşlemesi

Varyantın `canva` alanı design_id, page_id, element_map, source_sha256, mapped_at, direction ve sync_status tutabilir. direction local_to_canva/canva_to_local; sync_status synced/pending/local_changed/canva_changed. Bilinmeyen sayfa/öğe kimliği tahmin edilmez. source_sha256 yerel kaynakla uyuşmuyorsa doğrulama `canva_source_mismatch` verir; yanlış varyanta otomatik aktarım yapılmaz. Bu kayıt gerçek zamanlı çift yönlü senkronizasyon değildir. Her gerçek aktarımın dosyası ve uygulama kanıtı ayrıca tutulur.

## Yetkili kayıtlar

Model yeni çalışmaların üretim kaynağıdır. Mevcut projede daha önceki envanter otoritesi varsa önce salt okunur eşlemesini çıkar ve çalışma kopyasında doğrula. Bir anda bütün tarihsel dosyaları göç ettirme. Yeni yardımcıların tekrar çalışması numara çakışması, ebeveyn kaybı veya elenenlerin aktifleşmesiyle sonuçlanmamalı.
