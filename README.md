# Logo Master

Logo keşfi, gerçek fontlarla tipografi, vektör ve Canva üretimi için kişisel
Codex skill'i. Yalnız açıkça çağrıldığında çalışır.

## Doğrudan repodan kurulum

Windows, Python 3.12+ ve Git ile:

```powershell
git clone https://github.com/Zehelit/logo-master.git
cd logo-master
python tools/skillctl.py install
python tools/skillctl.py status
```

Repo private olduğundan hesabınızın repo erişimi olmalıdır. Kurulum Release,
ZIP veya GitHub CLI gerektirmez; yerel checkout'ın **commit edilmiş HEAD**
dosyalarını kurar. Sonraki güncelleme `git pull --ff-only` ve aynı `install`
komutudur. Seçili tag/commit için `install --ref <tag-veya-tam-commit>` kullanılır.

**[Kurulum rehberi: elle klasör kopyalama, yönetilen kurulum ve AI ajanı ile kurulum](INSTALL.md)**

AI ajanınıza verebileceğiniz talimat:

> https://github.com/Zehelit/logo-master reposundaki INSTALL.md dosyasının
> “AI ajanı ile kurulum” bölümünü uygula ve logo-master'ı kur. Mevcut yerel
> değişiklikleri koru; kurulan sürümü, commit'i ve doğrulama sonucunu bildir.

Skill `skills/logo-master/` içindedir. Ana yönergesi
[SKILL.md](skills/logo-master/SKILL.md); üretim araç/font gereksinimleri
[yerel vektör rehberinde](skills/logo-master/references/local-vector.md) açıklanır.
Skill kurulumu tek başına Inkscape, font veya Canva bağlantısı kurmaz.

## Geliştirme ve test

```powershell
python -m pip install -r requirements-dev.txt
python tools/check.py --profile portable --report .artifacts/portable-yeni.json
python tools/check.py --profile full --environment environment.local.json --report .artifacts/full-yeni.json
```

Her rapor yolu yeni olmalıdır. Portable profil mevcut 50 skill testinin beş
font/renderer testini açıkça atlar; kurulum aracı testlerini de çalıştırır.
Full profil gerçek Inkscape/Pango ortamı ister ve atlama kabul etmez.
Makine yollarını `environment.local.json` içinde tutun; Git'e eklemeyin.

Kaynak geçmişi GitHub'dadır; tek geliştirme checkout'ı ve ayrı kurulu skill
yeterlidir. Her sürüm için ayrı klasör tutulmaz. VERSION, tag, exact commit ve
kurulum makbuzu sürümü tanımlar; Release zorunlu değildir.
[Sürüm ve kurulum sözleşmesi](docs/versioning.md).
