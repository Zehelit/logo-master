# Canva çalışma ve doğrulama prosedürü

Doğru tasarımı ve hesabı doğrula. Testleri kaynak tasarımın çalışma kopyasında yap. Bağlayıcının güncel yeteneklerini keşfet; font ailesi veya SVG dolgu değişimi yoksa desteklenen tarayıcı arayüzünü kullan. İşlem onay gereksinimini başka yolla aşma.

## Kaynak eşlemesi ve güncel erişim

Yerel modelde varyantın canva kaydı design_id, page_id, element_map, source_sha256, mapped_at, direction ve sync_status taşır. Bilinmeyen öğe kimliği uydurulmaz. Canva'da yapılan değişiklik yerel kaynağa aktarılmadıysa canva_changed/pending olarak kalır; iki kaynağı eşit sayma. Yerel hash değiştiğinde eski eşleme canva_source_mismatch verir; hangi sürümden devam edileceği incelenir. Otomatik çift yönlü senkronizasyon yoktur.

Yerel renk/ölçek/export işlemi tamamlandıysa Canva zorunlu ek aşama değildir. Canva canlı dizgi, ayrıntılı kullanıcı düzenlemesi veya uygulama testi için seçilir. Bağlayıcının font ailesi ve graphic dolgu kontrolleri yoksa mevcut desteklenen tarayıcı gerekir; erişim/hesap yetkisini başka teknolojiyle aşma. Yeniden yetkilendirme veya kapalı tarayıcıda yerel işi sürdür, uygulama kabul testini açık bırak. Eski test makbuzunu bugünkü test diye kullanma.

Kaydetme aracı önizleme/onay istiyorsa önce somut test kopyası önizlemesini göster ve mevcut kullanıcı yetkisini değerlendir; gerekli onayı uydurma. Ücretli çıktı veya abonelik başlatma. Her aktarımda indirilen dosya, tasarım/sayfa/öğe kimlikleri ve yerel kaynak hash'i aynı makbuzla bağlanır.

SVG'nin kütüphaneye kabulü sayfaya yerleştirme değildir. Kütüphanede görünmeyen dosya için sebep uydurma; yükleme durumunu incele. Kullanıcı kapsamındaki dosyayı desteklenen dosya seçiciyle yükleyebilirsin.

## Modüler düzenleme

Amblem ayrı SVG, marka adı ve alt satırlar ayrı canlı metin öğeleri olsun. Her birinin fontunu, rengini, konumunu ve ölçüsünü kaydet. SVG'deki g gruplarının Canva'da otomatik bağımsız öğe olacağını varsayma. Gerekirse bileşenleri ayrı yükle.

Tam konturlu SVG görünümü sabitleyen teslim örneğidir. Graphic renk kontrolleri sunması, canlı font ailesi değişimine izin verdiği anlamına gelmez. Kaynak ve teslim arasındaki ilişkiyi koru.

## Uçtan uca test

1. Temiz amblemi ve gerçek fontlu metinleri ayrı yerleştir.
2. Amblem dolgusunu açık renge çevir; lekelenme ve konturları incele.
3. Metin rengini, boyutunu ve font ailesini değiştir. Yeni fontun gerçekten uygulandığını doğrula.
4. Amblemi ayrıca boyutlandır; amaçlanan oranı koru.
5. Kaydetme durumunu ve tasarım bağlantısını kaydet.
6. Çıktıyı indir; gerçek dosyanın ölçüsünü, görünümünü ve amaçlanan şeffaflığını incele.
7. Vektör teslimini oluşturup Canva'ya yeniden yerleştir; kaynakla görünümü karşılaştır.

Arayüz gecikirse DOM ile ekran çelişkisini yeni gözlemle çöz. Sayısal alan fill/Enter sonrası geri dönüyorsa normal seçme/yazma/odak değiştirme işlemini kullan; son değeri tekrar oku.

Alan DOM'dan ayrılırsa yeniden gözlem al. Son değeri tekrar oku; sürükleme sonrası X/Y ve oranı doğrula. Canva intrinsic ölçülerde yuvarlama yapabilir; son ölçüyü kaydet ve görünümü karşılaştır.

Font değişimi metin kutusunun ve harflerin kapladığı alanı değiştirebilir. Uygulamadan sonra alt satırlarla çakışma, kenar boşluğu ve hizalamayı tekrar kontrol et. Canva'da metin grubunun erişilebilirlik adına tıklamak bazen tuval seçimi oluşturmaz; araç çubuğunda font seçicisinin görünmesini doğrula, gerekirse güncel ekran görüntüsünden gerçek metni seç. Font adının seçicide değişmesi ve yazının görsel olarak değişmesi birlikte kanıttır.

## Dışa aktarma

Thumbnail yüksek çözünürlüklü çıktı değildir. İndirme tamamlandı mesajı sonrasında gerçek yerel dosyayı bul, ölçülerini ve hash'ini kaydet. Blob indirme yardımcısı çalışmıyorsa normal indirilen dosyayı doğrula.

SVG veya şeffaf PNG erişimini hesapta canlı kontrol et; abonelik başlatma. Vektör PDF alınabiliyorsa vektörlüğünü doğrulayıp yerel dönüşüm kullanılabilir. Kullanılamayan işlemi tamamlandı sayma. Ekran kanıtı, Canva kaydı ve indirilen dosyayı birbirine bağla.

PDF kaynağında gömülü raster bulunması tüm logonun raster olduğu anlamına gelmez. Tam sayfa arka plan görseli ve ayrı vektör logo birlikte bulunabilir. Görselin boyutunu, transform'unu ve katmanını incele. Şeffaf logo çıkarırken yalnız doğrulanmış arka planı kaldır; amblem ya da metin görsellerini kazara silme. Kimlikler her PDF'de değişebilir. Kalan vektör düğümlerinin aynılığını ve render görünümünü denetle.

Canva'dan gelen PDF'de `use` glyph referansları gerçek font eğrilerini taşıyabilir. Bunlar yerel font kurulumuna gerek kalmadan korunabilir. SVG içinde aynı glyph defs ve referanslar birlikte kalmalı; yalnız üstte görünen grupları kopyalamak harfleri kaybettirebilir.

Yerelde doğru render edilen SVG'nin Canva'da aynı görüneceğini varsayma. Güncel kabul testinde PDF glyph'lerinin `use` referansları içe alınırken üst gruptan gelen mavi/gri dolgular siyaha döndü. Çözüm fontu yeniden yazmak değildi: aynı glyph eğrilerini referanslardan çıkarıp her görünür path'e açık dolgu verildi; yerel önce/sonra render farkı ölçüldü ve yeni dosya tekrar Canva'da sınandı. Böyle bir durumda başarısız dosyayı kaynak kabul etme, bozuk aktarımı test sayfasından ayır ve renk/ölçü/harf biçimini gerçek indirilen çıktıda yeniden kontrol et. Bu dosyaya özgü dönüşüm betiğini her PDF'ye körlemesine uygulama; font eğrileri, transform sırası, boşluklar ve arka plan her kaynakta incelenir.
