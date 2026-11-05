# Yerel font ve bileşen işlemleri

Komutlar [üretim rehberinde](production.md), veri [kaynak sözleşmesinde](source-model.md). Tek renderer yolu logo_core/render.py'dir; her proje için aynı işlevi kopyalama.

LOGO_INKSCAPE mevcut Inkscape, LOGO_FONT_PYTHON gi/Pango/PangoCairo içeren Python'dur. Pango'nun Windows font haritası özel Fontconfig dizinini kullanmayabilir. Gerekiyorsa yalnız alt sürece FONTCONFIG_FILE ve PANGOCAIRO_BACKEND=fc ver. Araç/font dosyalarını kullanım anında doğrula; sistem genelinde kurulum gerekmez.

resolve_font(font_spec,text,env) istenen ve çözülen aile/ağırlık, glif sonucu, bulunabiliyorsa Fontconfig dosyası/hash'i verir. Exo 2 gibi rakam içeren aile set_family ile ele alınır. Font kaydında path/hash varsa gerçek dosya eşleşmesi aranır. Kaynak, lisans ve sürümü ayrıca kaydet; dosya adını lisans kanıtı sayma. Canva dosyasıyla aynı sürümü varsayma.

Normal/italic/oblique ve yerleşimdeki font run'ları da karşılaştırılır. Fontconfig dosya kanıtı Pango'nun çözdüğü descriptor üzerinden eşlemedir; düşük seviyeli Pango font nesnesinin dosya tanıtıcısının doğrudan okunması değildir. Farklı backend/makinede aynı sonucu varsayma. Canlı metindeki kuyruk metinleri ebeveyn stiliyle denetlenir; CSS seçicileri veya font shorthand tam çözümlenemediğinde işlem açık hata verir.

render_svg ve outline_svg canlı text/tspan fontunu kontrol eder; eksik fontta sessiz ikame yapmaz. Çözümleyici yoksa kanıtlanmış render diye sunmaz. Kontur Inkscape object-to-path kullanır, canlı metnin kalmadığını denetler. Amblem eğrileri ile canlı/konturlu render ayrıca karşılaştırılır.

RGBA karşılaştırması bütün kanalları ve açık/koyu kompozitte görünen farkı ayırır. Alfa0 altındaki RGB farkı görünür kusur değildir; aynı piksel sonucu estetik onay değildir. Renderer/yuvarlama farkını evrensel toleransla kusursuz ilan etme.

Bileşen ayırma ortak viewBox, ata bağlamı, defs ve çizim sırasını korur. Manifest/iskeleti parçalarla sakla. Tight crop veya Canva'da farklı konum için yeni koordinat eşlemesi gerekir. g grubu ya da ayrı SVG üretmek Canva'da bağımsız canlı öğe testinin yerine geçmez.
