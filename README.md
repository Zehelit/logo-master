# Logo Master

Logo keşfi, gerçek fontlarla tipografi, vektör ve Canva üretimi için kişisel Codex skill paketi. Referans belgelerini, Python yardımcılarını ve mevcut testlerini içerir.

## İçerik

Skill paketi `skills/logo-master/` altındadır. Ana yönerge `skills/logo-master/SKILL.md` dosyasıdır.

## Yerel kullanım

Windows/Python3.12+ ve skill'in araç/font gereksinimlerini inceleyin.
Yayımlanmış sürümü repo kökünden yönetin:

```powershell
python tools/skillctl.py status
python tools/skillctl.py install --tag v1.0.0
python skills/logo-master/scripts/logo.py --version
```

İlk mevcut unversioned kurulumu benimsemek için exact commit ile
`--adopt-baseline <tam-commit>` gerekir; değişmiş dosyaların üzerine yazılmaz.
GitHub private repo erişimi için mevcut `gh` oturumu ve Git gereklidir.

## Geliştirme ve test

```powershell
python -m pip install -r requirements-dev.txt
python tools/check.py --profile portable --report .artifacts/portable-yeni.json
python tools/check.py --profile full --environment environment.local.json --report .artifacts/full-yeni.json
```

Her makbuz yolu yeni olmalıdır. Portable profil mevcut 50 skill testinin beş
font/renderer testini açıkça atlar; yönetim aracı testlerini de çalıştırır.
Full profil gerçek Inkscape/Pango ortamı ister ve hiçbir atlamayı kabul etmez.
Makine yollarını `environment.local.json` içinde tutun; Git'e eklemeyin.

Release kaynağı çalışma ağacı değil exact commit'tir:
`python tools/skill_release.py --commit <tam-commit> --out .artifacts/release-yeni`.
VERSION, tag, commit, manifest ve kurulum makbuzu birlikte doğrulanır.

Bu private depo sürüm geçmişinin merkezidir. Kalıcı geliştirme kopyası
`C:/Users/Doruk/Projects/logo-master`; eski tarihli staging artık geliştirme
kaynağı olarak kullanılmaz. Kurulu skill klasöründe doğrudan geliştirme yapmayın.

Sürüm/kurulum sözleşmesi: [docs/versioning.md](docs/versioning.md).
Python önbellekleri, yerel ortam dosyaları ve çalışma raporları Git'e eklenmez.
