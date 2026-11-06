# Logo Master kurulumu

Dağıtım kaynağı bu Git reposudur. Release indirme veya paket arşivi gerekmez.
Kurulum aracı Windows/Python 3.12+ ve Git ile sınanmıştır. Diğer işletim
sistemlerinde yönetilen kurulum desteği doğrulanmamıştır.

Repo private: kullanıcı veya ajan, repo erişimi olan hesabın mevcut Git
kimlik doğrulamasını kullanır. Token'ı komuta, dosyaya veya konuşmaya yazmayın.
Erişim reddedilirse hesabın repo yetkisini çözün; Release yolu alternatif değildir.

## Kullanıcı için yönetilen kurulum

PowerShell'de, tek bir geliştirme/kurulum kaynağı olarak kullanacağınız dizinde:

```powershell
git clone https://github.com/Zehelit/logo-master.git
cd logo-master
python tools/skillctl.py status
python tools/skillctl.py install
python tools/skillctl.py status
```

Mevcut klonunuz varsa tekrar klonlamayın; o klasöre geçin. İlk kurulumda
`status` sonucu `unmanaged`, başarılı kurulum sonunda `clean` olur.
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
python (Join-Path $logoCodexRoot 'skills/logo-master/scripts/logo.py') --version
```

Bu komutun sürümü `status` sürümüyle eşleşmelidir. Skill'in mevcut oturuma
anında yeniden yüklendiği varsayılmaz; sonraki açık çağrıda güncel dosyanın
okunduğunu doğrulayın. Sadece kurulum için Python standart kitaplığı yeterlidir.

### Güncelleme ve belirli sürüm

Repo kökünden:

```powershell
git status --short
git pull --ff-only
python tools/skillctl.py install
python tools/skillctl.py status
```

Checkout'ta kişisel değişiklik varsa önce inceleyin; `reset --hard`, zorla
checkout veya otomatik stash yapmayın. `pull --ff-only` dallar ayrılmışsa durur.
Kurulu skill'de değiştirilmiş/eklenmiş/silinmiş kaynak varsa kurulum da durur.
`python tools/skillctl.py status --details` etkilenen yolları gösterir.

Yalnız seçilen sürümün Git tag'i veya tam commit SHA'sı kurulabilir:

```powershell
git fetch origin --tags
python tools/skillctl.py install --ref v1.1.0
# veya: python tools/skillctl.py install --ref <40-karakterli-commit-SHA>
```

Tag bir Git işaretidir; GitHub Release gerektirmez. Eski `--tag v1.1.0`
seçeneği de çalışır ve tag adının VERSION ile eşleşmesini ayrıca denetler.
Aynı commit yeniden kurulursa dosyalar değiştirilmeden `noop: true` döner.

### Geri dönüş, kesinti ve eski kurulum

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
New-Item -ItemType Directory -Path (Join-Path $logoCodexRoot 'skills') -Force | Out-Null
Copy-Item -LiteralPath './skills/logo-master' -Destination $logoSkillTarget -Recurse
python (Join-Path $logoSkillTarget 'scripts/logo.py') --version
```

Bu yöntem çalışma klasörünü kopyalar; temiz checkout kullanın. Makbuz ve
otomatik geri dönüş oluşturmaz; `skillctl status` bunu `unmanaged` gösterir.
Güncellemelerde dosya karşılaştırması ve koruma kullanıcıya aittir.
Takip edilebilir güncelleme için yukarıdaki yönetilen kurulum tercih edilir.

## AI ajanı ile kurulum

Kullanıcı kurulum istediğinde bu bölüm yeterlidir; tüm skill referanslarını
ve geçmiş raporları baştan yüklemeyin.

1. Windows, Python 3.12+, Git ve repo erişimini kontrol et. Eksik aracı
   kurma veya sistem ayarlarını değiştirme izni varmış gibi davranma.
2. Varsa mevcut repo checkout'ını kullan. Yoksa kullanıcının uygun çalışma
   dizinine `git clone https://github.com/Zehelit/logo-master.git` yap.
   `origin` bu repo olmalı; HTTPS ve standart GitHub SSH biçimleri desteklenir.
3. Kullanıcının gerçek Codex kökünü kullan (`CODEX_HOME`, yoksa `.codex`).
   İzole test istenmişse hem `CODEX_HOME` hem yedek profil yolunu test
   dizinine yönlendir; gerçek skill kurulumunu test hedefi yapma.
4. Repo kökünden `python tools/skillctl.py status` çalıştır. Var olan
   kaynak/kurulum değişikliklerini incele. `modified`, `invalid` veya
   `recovery_required` sonucunu `clean` diye sunma ve zorla aşma.
5. Kullanıcı belirli tag/commit istemişse `install --ref <referans>` kullan.
   Aksi halde mevcut kaynak checkout'ı uygunsa `install` çalıştır; kullanıcı
   güncelleme istemişse temiz checkout'ta önce `git pull --ff-only` yap.
   Gerekli tag yerelde yoksa onu açıkça `git fetch origin --tags` ile getir.
6. Komut sonucuyla yetinme: yeniden `status` çalıştır, hedefteki `SKILL.md`
   ve `VERSION` dosyalarını kontrol et; **kurulu** `scripts/logo.py --version`
   çıktısını makbuzla karşılaştır. Sonuç `clean` olmalı.
7. Sürüm, tam commit, kurulum yolu ve kontrolleri kısa bildir. Bu işlem
   logo üretimi, Canva oturum testi veya baskı kabulü yapılmış anlamına gelmez.

Release, ZIP, `gh release download`, zorla dosya ezme veya kullanıcı token'ı
isteme bu akışın parçası değildir. Yönetilen kurulum insan ve ajan için aynı
komuttur; ayrıca bir servis veya arka plan güncelleyici çalıştırılmaz.

## Kurulumdan sonra üretim araçları

Logo yardımcılarının görüntü işlemleri Pillow/NumPy; geliştirme testleri
ayrıca PyYAML ister. Gerekli ortamda `python -m pip install -r requirements-dev.txt`
kullanılabilir. Gerçek fontlu render/outline için Inkscape ve Pango/PangoCairo
ayrıca gerekir; makineye uygun yolları
[yerel vektör rehberine](skills/logo-master/references/local-vector.md) göre
doğrulayın. Canva ve Image Gen mevcut oturumun araçlarıdır; bu repo onları
yüklemez veya hesap erişimi sağlamaz.
