# Logo Master kurulumu

Dağıtım kaynağı [Zehelit/logo-master](https://github.com/Zehelit/logo-master)
Git reposudur. Yönetilen kurulum Windows, Python 3.12 ve Git ile sınanır.
Diğer işletim sistemleri ve Python sürümleri için doğrulama kaydı
bulunmuyor. Komutlar kullanıcının yazabildiği dizinlerde çalışır.

## Kullanıcı için yönetilen kurulum

PowerShell'de, tek bir geliştirme/kurulum kaynağı olarak kullanacağınız dizinde:

```powershell
git clone https://github.com/Zehelit/logo-master.git
if ($LASTEXITCODE -ne 0) { throw 'Kaynak klonlanamadı.' }
Set-Location -LiteralPath ./logo-master
git status --short --branch
python tools/skillctl.py status --details
if ($LASTEXITCODE -ne 0) { throw 'Kurulum durumu okunamadı.' }
python tools/skillctl.py install
if ($LASTEXITCODE -ne 0) { throw 'Kurulum durdu. Çıktıdaki nedeni inceleyin.' }
$logoStateJson = python tools/skillctl.py status
if ($LASTEXITCODE -ne 0) { throw 'Kurulum durumu okunamadı.' }
$logoState = $logoStateJson | ConvertFrom-Json
if ($logoState.status -ne 'clean') { throw 'Makbuz veya kurulu dosyalar doğrulanamadı.' }
$logoState
```

Mevcut klonunuz varsa repo kökünden durum ve kurulum adımlarına başlayın.
Boş hedefte ilk `status` sonucu `unmanaged`, başarılı kurulum sonunda
`clean` olur. Hedef dolu ve makbuzsuzsa [eski kurulum](#geri-dönüş-kesinti-ve-eski-kurulum)
adımlarını izleyin.
`install` varsayılan olarak yerel `HEAD` commit'ini kurar; çalışma ağacındaki
commit edilmemiş değişiklikleri ve izlenmeyen dosyaları kurmaz. Repo dosyaları
Git nesnelerinden okunur, SHA-256 ile denetlenir. Kurulum komutu ağa bağlanmaz.

Varsayılan hedef `%USERPROFILE%\.codex\skills\logo-master` olur. Codex'inizi
başka bir dizinde kullanıyorsanız komutlardan önce `$env:CODEX_HOME` değerini
o **mutlak** klasör yoluna ayarlayın. Kurulum makbuzu ve en fazla bir önceki
kopya aynı Codex kökünün `skill-installations/logo-master/` klasöründe tutulur.

Kurulan CLI sürümünü doğrulamak için:

```powershell
$logoCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$logoCli = Join-Path $logoCodexRoot 'skills/logo-master/scripts/logo.py'
$logoVersion = python $logoCli --version
if ($LASTEXITCODE -ne 0 -or $logoVersion -ne $logoState.version) { throw 'Kurulan sürüm makbuzla eşleşmedi.' }
$logoVersion
```

Bu komutun sürümü `status` sürümüyle eşleşmelidir. Skill'in mevcut oturuma
anında yeniden yüklendiği varsayılmaz; sonraki açık çağrıda güncel dosyanın
okunduğunu doğrulayın. Sadece kurulum için Python standart kitaplığı yeterlidir.

## İlk işlem

Bu örnek kurulu CLI'yi geçici bir SVG üzerinde çalıştırır. Önceki
adımlarda tanımlanan `$logoCli` değişkenini kullanın. SVG denetimi için
PNG bağımlılıkları, Inkscape veya Canva gerekmez.

```powershell
$logoSmokeDir = Join-Path ([IO.Path]::GetTempPath()) ('logo-master-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $logoSmokeDir -ErrorAction Stop | Out-Null
$logoSmokeSvg = Join-Path $logoSmokeDir 'emblem.svg'
Set-Content -LiteralPath $logoSmokeSvg -Encoding utf8 -ErrorAction Stop -Value '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path id="emblem" fill="#315A94" d="M8 8h48v48H8z"/></svg>'
$logoAuditJson = python $logoCli audit $logoSmokeSvg
if ($LASTEXITCODE -ne 0) { throw 'SVG denetimi başarısız.' }
$logoAudit = $logoAuditJson | ConvertFrom-Json
if ($logoAudit.status -ne 'passed' -or $logoAudit.source_kind -ne 'vector' -or $logoAudit.counts.path -ne 1) {
    throw 'Beklenen tek vektör yol bulunamadı.'
}
$logoAudit | Select-Object status, source_kind, counts, sha256
```

Geçici dizindeki girdi için `passed`, `vector` ve bir `path` beklenir.
Bu kontrol kurulu CLI'nin SVG denetimini sınar. Codex çağrısı, gerçek fontlu
render ve Canva erişimi için ayrı kontrol gerekir.

## Güncelleme ve belirli sürüm

Repo kökünden:

```powershell
git status --short
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Kaynak güncellenemedi.' }
python tools/skillctl.py install
if ($LASTEXITCODE -ne 0) { throw 'Kurulum durdu. Durum ayrıntısını inceleyin.' }
python tools/skillctl.py status --details
```

Checkout'ta kişisel değişiklik varsa önce inceleyin; `reset --hard`, zorla
checkout veya otomatik stash yapmayın. `pull --ff-only` dallar ayrılmışsa durur.
Kurulu skill'de değiştirilmiş/eklenmiş/silinmiş kaynak varsa kurulum da durur.
`python tools/skillctl.py status --details` etkilenen yolları gösterir.

Yalnız seçilen sürümün Git tag'i veya tam commit SHA'sı kurulabilir:

```powershell
git fetch origin --tags
if ($LASTEXITCODE -ne 0) { throw 'Git tag bilgileri alınamadı.' }
python tools/skillctl.py install --ref v1.1.0
# veya: python tools/skillctl.py install --ref <40-karakterli-commit-SHA>
```

Tag bir Git işaretidir; GitHub Release gerektirmez. Eski `--tag v1.1.0`
seçeneği de çalışır ve tag adının VERSION ile eşleşmesini ayrıca denetler.
Aynı commit yeniden kurulursa dosyalar değiştirilmeden `noop: true` döner.

## Geri dönüş, kesinti ve eski kurulum

```powershell
python tools/skillctl.py rollback
python tools/skillctl.py status
```

`rollback` doğrulanmış tek önceki kopyayı geri getirir. Mevcut veya önceki
kurulumda yerel değişiklik varsa üzerine yazmaz. Kesinti sonrasında durum
`recovery_required` ise önce ayrıntıları inceleyin, sonra
`python tools/skillctl.py recover` çalıştırın. Journal veya kurtarma klasörlerini
elle silmeyin. Aynı kurulum klasörünü kullanan üretim işlerini güncellemeden önce bitirin.

Makbuzsuz mevcut klasör `unmanaged` kabul edilir ve otomatik ezilmez.
Eski, VERSION'sız kurulum ancak kaynak Git commit'iyle tüm dosyaları aynıysa
`install --adopt-baseline <tam-eski-commit>` ile açıkça benimsenebilir.
Bu seçenek genel bir üzerine yazma izni değildir. Elle kopyalanmış sürümlü
kurulumları benimseme bu aracın desteklediği yol değildir; bu durumda yerel
dosyaları incelemeden kaldırmayın veya yönetim makbuzu uydurmayın.

## Kullanıcı için tamamen elle kurulum

Kurulum betiği kullanmak istemiyorsanız repoyu klonlayın ve
`skills/logo-master` klasörünü Codex'in skill dizinine kopyalayın.
Hedefte `logo-master/SKILL.md` bulunmalıdır; repo kökünü veya fazladan bir
`logo-master/logo-master/` katmanını kopyalamayın.

Aşağıdaki örnek yalnız **ilk ve temiz kurulum** içindir, repo kökünden çalışır:

```powershell
$logoCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$logoSkillTarget = Join-Path $logoCodexRoot 'skills/logo-master'
if (Test-Path -LiteralPath $logoSkillTarget) { throw 'Hedef mevcut; dosyaları incelemeden üzerine kopyalamayın.' }
New-Item -ItemType Directory -Path (Join-Path $logoCodexRoot 'skills') -Force -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath './skills/logo-master' -Destination $logoSkillTarget -Recurse -ErrorAction Stop
$logoCli = Join-Path $logoSkillTarget 'scripts/logo.py'
$logoVersion = python $logoCli --version
if ($LASTEXITCODE -ne 0 -or $logoVersion -ne (Get-Content -LiteralPath ./skills/logo-master/VERSION -Raw).Trim()) {
    throw 'Elle kopyalanan sürüm kaynakla eşleşmedi.'
}
```

Bu yöntem çalışma klasörünü kopyalar; temiz checkout kullanın. Makbuz ve
otomatik geri dönüş oluşturmaz; `skillctl status` bunu `unmanaged` gösterir.
Güncellemelerde dosya karşılaştırması ve koruma kullanıcıya aittir.
Ardından [ilk işlemi](#ilk-işlem) çalıştırın.

## AI ajanı ile kurulum

Kullanıcı kurulum istediğinde bu bölüm yeterlidir; tüm skill referanslarını
ve geçmiş raporları baştan yüklemeyin.

1. Windows, Python 3.12 ve Git'i kontrol et. Eksik aracı
   kurma veya sistem ayarlarını değiştirme izni varmış gibi davranma.
2. Varsa mevcut repo checkout'ını kullan. Yoksa kullanıcının uygun çalışma
   dizinine `git clone https://github.com/Zehelit/logo-master.git` yap.
   `origin` bu repo olmalı; HTTPS ve standart GitHub SSH biçimleri desteklenir.
3. Kullanıcının gerçek Codex kökünü kullan (`CODEX_HOME`, yoksa `.codex`).
   İzole test istenmişse hem `CODEX_HOME` hem yedek profil yolunu test
   dizinine yönlendir; gerçek skill kurulumunu test hedefi yapma.
4. Repo kökünden `python tools/skillctl.py status` çalıştır. Var olan
   kaynak/kurulum değişikliklerini ve aynı hedefi kullanan etkin işleri incele.
   `modified` veya `invalid` durumunda dosyaları koru ve nedeni bildir. Durum
   `recovery_required` ise [kurtarma adımlarını](#geri-dönüş-kesinti-ve-eski-kurulum)
   izle. Yeniden denemeden önce `status --details` sonucunu oku.
5. Kullanıcı belirli tag/commit istemişse `install --ref <referans>` kullan.
   Aksi halde mevcut kaynak checkout'ı uygunsa `install` çalıştır; kullanıcı
   güncelleme istemişse temiz checkout'ta önce `git pull --ff-only` yap.
   Gerekli tag yerelde yoksa onu açıkça `git fetch origin --tags` ile getir.
6. Komut sonucuyla yetinme: yeniden `status` çalıştır, hedefteki `SKILL.md`
   ve `VERSION` dosyalarını kontrol et; **kurulu** `scripts/logo.py --version`
   çıktısını makbuzla karşılaştır. Sonuç `clean` olmalı. [İlk işlemi](#ilk-işlem)
   geçici SVG ile çalıştır ve SVG denetiminin sonucunu doğrula.
7. Sürümü, tam commit SHA'sını, kurulum yolunu ve test sonucunu bildir.
   Codex çağrısı, Canva ve üretim araçları için hangi kontrollerin yapıldığını belirt.

Görevin yetkisi kaynak edinme ve seçilen hedefteki skill dosyalarını
kurmayla sınırlıdır. Sistem ayarları, GitHub yayını ve gerçek proje
dosyaları ayrı işlemlerdir. Yönetilen kurulum insan ve ajan için aynı
komutu kullanır.

## Kaldırma ve veri koruma

Ayrı bir uninstall komutu bulunmuyor. Skill'i kullanan işler bittikten
sonra, varsa bekleyen kurtarmayı çözün. Codex kökü altında aşağıdaki kesin
hedefleri inceleyip skill keşif dizininin dışındaki bir yedek konumuna
taşıyabilirsiniz.

- `skills/logo-master` kurulu skill dosyalarını ve varsa Python cache'lerini
  içerir.
- Yönetilen kurulumda `skill-installations/logo-master` kurulum makbuzunu,
  önceki kopyayı ve varsa kurtarma durumunu içerir. İki dizini birlikte
  yedeklemek geri yükleme için makbuz ile kurulu dosyaların bağını korur.

Proje JSON'u, fontlar, SVG/PNG, üretim makbuzları ve Canva tasarımları kendi
konumlarında kalır. Sonraki Codex oturumunda skill keşfini kontrol edin.

## Kurulumdan sonra üretim araçları

Logo yardımcılarının görüntü işlemleri Pillow/NumPy; geliştirme testleri
ayrıca PyYAML ister. Gerekli ortamda `python -m pip install -r requirements-dev.txt`
kullanılabilir. Gerçek fontlu render/outline için Inkscape ve Pango/PangoCairo
ayrıca gerekir; makineye uygun yolları
[yerel vektör rehberine](skills/logo-master/references/local-vector.md) göre
doğrulayın. Canva ve Image Gen mevcut oturumun araçlarıdır; bu repo onları
yüklemez veya hesap erişimi sağlamaz.
