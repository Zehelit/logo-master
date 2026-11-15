# Logo Master mimarisi ve iş akışı

## Mimari

Hangi bileşen hangi dosyayı okur veya yazar?

```mermaid
flowchart LR
    Git["Git checkout ve commit"] -->|kaynak blobları| Installer["skillctl.py"]
    Installer -->|dosyaları kurar| Skill["Kullanıcı skill dizini"]
    Installer -->|makbuz ve önceki kopya| State["Kurulum durum dizini"]
    Skill -->|yönerge ve yerel giriş noktası| Codex["Codex oturumu"]
    Codex -->|komut çağırır| CLI["logo.py"]
    Codex -->|mevcutsa kullanır| Tools["Image Gen ve Canva"]
    CLI -->|okur ve işlem kapsamında yazar| Project["Proje JSON'u, SVG ve çıktılar"]
    CLI -->|render ve font çözümleme| Renderer["Yerel Inkscape ve Pango"]
```

| Bileşen | Sorumluluk ve veri sınırı | Kaynak |
| --- | --- | --- |
| Kurulum | Git nesnelerini ve VERSION'ı okur. Kullanıcı skill dizinine dosya, ayrı durum dizinine makbuz ve önceki kopya yazar. | [Kurulum aracı](../tools/skillctl.py) · [Sürüm sözleşmesi](versioning.md) |
| Codex | Kullanıcının brief ve seçimine göre yönergeleri, yerel komutları ve oturumda mevcut bağlı araçları kullanır. | [Skill](../skills/logo-master/SKILL.md) |
| Yerel CLI | Proje JSON'unu ve varlıkları denetler. Komuta göre SVG, PNG, JSON makbuzu, yerel pano veya ZIP oluşturur. Çıktı konumları komut argümanlarından gelir. | [CLI](../skills/logo-master/scripts/logo.py) · [Üretim komutları](../skills/logo-master/references/production.md) |
| Geometri ve tipografi | Inkscape ile render ve kontur, Pango ile font çözümleme yapılır. Aynı dosya üzerindeki teknik kontrolleri yeniden çalıştırmak mümkündür. | [Renderer](../skills/logo-master/scripts/logo_core/render.py) · [Vektör rehberi](../skills/logo-master/references/local-vector.md) |
| Canva | Yerel CLI, aktarılacak dosyayı ve indirilen PDF'yi inceleyebilir. Canva'daki yerleştirme, düzenleme, kaydetme ve indirme Codex oturumundaki erişime bağlıdır. | [Yerel Canva işlemleri](../skills/logo-master/scripts/logo_core/canva.py) · [Canva rehberi](../skills/logo-master/references/canva.md) |

Çizim kurulu skill'in kullanıldığı yolu gösterir. Geliştirme testleri ise CLI'yi doğrudan checkout'tan çalıştırır.

## Tasarım ve üretim akışı

Skill çağrıldıktan sonra bir aday hangi adımlardan geçer?

```mermaid
flowchart TD
    Brief["Brief ve kullanım alanları"] --> Candidate["Aday önizlemeleri ve gerçek font"]
    Candidate --> Choice{"Aday seçildi mi?"}
    Choice -->|İnceleme sürüyor| Review["Kullanıcı geri bildirimi"]
    Review --> Candidate
    Choice -->|Seçim var| Source["Canlı metinli kaynak ve korunacak bileşenler"]
    Source --> Work["İstenen varyant, kontur, PNG veya Canva işlemi"]
    Work --> Check{"Hedefin teknik kontrolleri geçti mi?"}
    Check -->|Hayır| Finding["Bulguyu raporla ve çıktıyı incele"]
    Check -->|Evet| Approve{"Nihai teslim onayı var mı?"}
    Approve -->|Bekleniyor| Preview["Önizleme veya çalışma çıktısı"]
    Approve -->|Var| Delivery["Teslim paketi"]
```

Akış seçimden sonra yürütülen üretimi gösterir. Yerel CLI arşiv, sunum ve teslim kapsamlarını [ayrı kurallarla](../skills/logo-master/references/production.md) ele alır. Kurulum ve sürüm değiştirme adımları [kurulum rehberindedir](../INSTALL.md).

## Kim başlatır, kim karar verir?

```mermaid
sequenceDiagram
    actor User as Kullanıcı
    participant Codex as Codex oturumu
    participant CLI as Yerel logo CLI
    User->>Codex: Brief ve skill çağrısı
    Codex-->>User: Logo adayları
    User->>Codex: Seçim ve istenen değişiklik
    Codex->>CLI: Seçili kaynak ve işlem koşulları
    CLI-->>Codex: Çıktı ve denetim sonucu
    Codex-->>User: Önizleme ve bulgular
    User->>Codex: Nihai teslim kararı
```

Kullanıcı tasarımı seçer ve nihai teslimi onaylar. Codex teknik işlemleri sıralar ve sonuçlarını sunar. CLI her çağrıda kendi işleminin sonucunu döndürür. Kurulum aracı ayrı çağrılır. Logo işlerini yöneten kalıcı bir servis veya dahili ajan takımı bulunmaz.
