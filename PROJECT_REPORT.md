# Beer Notes Proje Raporu

Hazirlanma tarihi: 2026-08-09

Bu rapor, Beer Notes projesinin mevcut amacini, bugune kadar yapilan gelistirmeleri, projenin bugunku teknik durumunu ve bundan sonra mantikli sirayla yapilmasi gereken eksikleri ozetler. Rapor, repoyu sonradan inceleyen bir gelistiricinin veya uygulamayi kuran bir kullanicinin projeyi hizlica anlamasi icin hazirlanmistir.

## 1. Proje Nedir?

Beer Notes, Python 3 ve PyQt6 ile gelistirilen masaustu not alma uygulamasidir. Uygulamanin temel hedefi, klasik bir not defterinden daha kullanisli, sade, modern ve yerel dosya odakli bir not sistemi sunmaktir.

Projenin ana prensipleri sunlardir:

- Notlar kullanicinin bilgisayarinda saklanir.
- Uygulama arayuzu sade, temiz ve son kullaniciya kolay gelecek sekilde tasarlanir.
- Gelismis ozellikler ana ekrani kalabaliklastirmadan, kullanicinin ihtiyacina gore acilip kapanabilir.
- Veri saklama mimarisi uygulamaya kilitli olmamalidir; kullanici notlarini dosya olarak okuyabilmeli ve yedekleyebilmelidir.
- Kod mimarisi controller, storage, localization ve ui katmanlari ayrimina sadik kalmalidir.

Mevcut paket yapisi genel olarak su sekildedir:

- `beernotes/controllers/`: Uygulama davranislarini ve is akisini yoneten controller katmani.
- `beernotes/storage/`: Notlarin, ayarlarin ve dosya tabanli verinin saklandigi katman.
- `beernotes/localization/`: Dil ve metin altyapisi.
- `beernotes/ui/`: PyQt6 arayuz bilesenleri, tema ve editor davranislari.
- `tests/`: Depolama, arayuz ve ozellik regresyon testleri.

## 2. Su Ana Kadar Yapilanlar

### 2.1. Arayuz ve Kullanim Kolayligi

Uygulama daha once klasik detayli not duzenleme mantigina sahipken, kullanimi kolaylastirmaya yonelik onemli kararlar alindi:

- Basit mod ve detayli mod ayrimi tasarlandi.
- Varsayilan deneyimin daha sade olmasi hedeflendi.
- Notlarin kutucuklar halinde gorunmesi, kullanicinin not secince basit bir yazma alanina gecmesi dusunuldu.
- Ana ekrandaki tum ozelliklerin ayni anda gosterilmemesi, bunun yerine ekstra ozelliklerin ust menuler veya araclar bolumunden secilmesi kararlastirildi.
- Folders ve All Notes alanlari arasinda kullanicinin genislik ayarlayabilecegi kaydirilabilir bolme fikri eklendi.
- Apple tarzina daha yakin, ince, sade ve zarif bir tema hedefi belirlendi.

Bu kisimda temel UX yonu netlestirildi. Arayuzun tam olgunlasmasi icin gelecekte daha fazla gorsel temizlik ve kullanici testi gereklidir.

### 2.2. Logo, Kisayol ve Kurulum Deneyimi

Uygulama icin kullanicinin klasore tasidigi PNG dosyasinin logo olarak kullanilmasi planlandi. Ayrica sadece tek bir bilgisayarda calisan yerel kisayol yerine, repoyu indiren herkesin kullanabilecegi daha tasinabilir bir baslatma/kisayol yapisi istendi.

Bu kapsamda hedeflenen anlayis:

- Uygulama ikonu repo icindeki asset olarak tutulmali.
- `.desktop` dosyasi veya paketleme ciktilari repodan gelen herkes tarafindan kullanilabilir olmali.
- Kisayol mutlak kullanici yoluna baglanmamali.
- Paketleme ileride AppImage gibi tasinabilir bir formatla desteklenmeli.

Bu alan henuz tamamen bitmis nihai paketleme deneyimi olarak degerlendirilmemelidir. Gelecekte AppImage paketleme adimi tamamlanmalidir.

### 2.3. Disa Aktarma ve Ice Aktarma

Notlarin disari aktarilmasi eklendi ve calisir hale getirildi. Daha sonra ice aktarma ihtiyaci da belirlendi. Mevcut hedef, kullanicinin yazdiklarini uygulama disina alabilmesi ve disaridan tekrar uygulamaya katabilmesidir.

Bu ozellik, Beer Notes'un kullanici verisini uygulamaya hapsetmemesi acisindan onemlidir.

### 2.4. Plain Text / Markdown Depolama Goc Isleri

Projedeki en kritik teknik gelistirmelerden biri yapildi: not depolama yapisi uygulamaya ozel JSON dosyalarindan, kullanici tarafindan okunabilir Markdown dosyalarina tasindi.

Yapilanlar:

- Eski notlarin `notes/*.json` olarak saklanmasi yerine, yeni kaynak format `notes/*.md` olarak belirlendi.
- Her Markdown dosyasinin basina YAML front matter eklendi.
- Front matter icinde baslik, etiketler, olusturma tarihi, guncelleme tarihi, sabitleme durumu ve klasor gibi metadata tutulacak sekilde mimari kuruldu.
- Eski JSON notlari ilk calistirmada otomatik olarak Markdown dosyalarina goc eden migration rutini eklendi.
- Eski JSON dosyalari kaybolmasin diye yedekleme mekanizmasi eklendi.
- Notlarin disaridan okunabilir ve duzenlenebilir olmasi saglandi.
- Ayarlanabilir not dizini destegi eklendi.
- Varsayilan not dizini XDG veri yolu olarak korunurken, kullanici isterse not dizinini baska bir klasore tasiyabilecek hale getirildi.
- Harici disk veya ortak bolum gibi yerlerde yanlis mount/dizin kullanimi riskini azaltmak icin not dizini kimlik kontrolu eklendi.

Bu, projenin uzun vadeli veri guvenligi ve tasinabilirlik acisindan en degerli adimlarindan biridir.

### 2.5. Markdown Editor ve Kod Vurgulama

Editor tarafinda Markdown destegi gelistirildi:

- Fenced code block icin editor icinde syntax highlighting eklendi.
- Pygments kullanilarak kod bloklari renklendirildi.
- Canli onizleme tarafinda kod bloklarinin ayni vurgulama mantigiyla render edilmesi saglandi.
- Markdown onizleme daha kullanisli hale getirildi.
- Tema degisimlerinde editor vurgulamasinin da guncellenmesi hedeflendi.

Bu adim, Beer Notes'u sadece basit duz metin not defteri olmaktan cikarip teknik not, kod parcasi ve dokumantasyon yazimi icin daha uygun hale getirdi.

### 2.6. Git Is Akisi

Proje gelistirmelerinde Git kullanimi esas alindi:

- Yapilan ozelliklerin atomik commitlerle kaydedilmesi hedeflendi.
- Tamamlanan ozelliklerin GitHub reposuna pushlanmasi is akisi olarak benimsendi.
- Kod degisikligi yaparken once test, sonra commit ve push yaklasimi izlendi.

Bilinen tamamlanmis commitler:

- `feat(storage): migrate notes to portable markdown`
- `feat(editor): add pygments markdown highlighting`

Bu rapor olusturulurken terminal araci gecici olarak calismadigi icin anlik commit hash ve calisma agaci durumu yeniden dogrulanamamistir. Bu nedenle son durum ayrica `git status` ve `git log --oneline -8` ile kontrol edilmelidir.

## 3. Mevcut Teknik Durum

Beer Notes su anda genel olarak su yeteneklere sahiptir:

- PyQt6 tabanli masaustu arayuz.
- Yerel dosya tabanli not saklama.
- Markdown kaynak dosyalari.
- YAML front matter ile metadata saklama.
- Legacy JSON notlar icin goc mekanizmasi.
- Ayarlanabilir not dizini.
- Not dizini kimlik kontrolu.
- Markdown editor destegi.
- Kod bloklari icin Pygments tabanli renklendirme.
- Markdown onizleme.
- Tema ve localization altyapisina sahip moduler UI.
- Controller ve storage ayrimina dayali kod organizasyonu.
- Test altyapisi.

Projenin yonu dogru: not verisi artik daha acik, okunabilir ve tasinabilir bir formata tasiniyor. Bu, ileride CLI, Git versiyonlama, AppImage paketleme ve LLM ozellikleri gibi gelismis adimlarin daha saglam zeminde eklenmesini kolaylastirir.

## 4. Bilinen Eksikler ve Riskler

### 4.1. Multi-Tab Sistemi Henuz Tamamlanmadi

Birden fazla notu ayni anda sekmelerde acma ozelligi planlandi. Bu ozellik cok degerli olsa da veri kaybi riski tasidigi icin dikkatli uygulanmalidir.

Ozellikle su konular garanti altina alinmalidir:

- Her sekmenin kendi autosave timer'i olmali.
- Bir sekmede yapilan degisiklik baska sekmenin dosyasina yazilmamali.
- Sekme kapatilirken kirli veri varsa once guvenli kayit yapilmali.
- Kayit hatasi olursa sekme kapanmamali.
- Harici dosya degisikligi olursa temiz sekme guncellenmeli, kirli sekme ezilmemeli.
- Simple Mode ile Detailed Mode arasinda ayni notun iki farkli kopyasi cakismamali.
- Not dizini degistirilirken tum acik sekmeler guvenli sekilde kapatilmali veya kaydedilmelidir.

Bu ozellik tamamlanmadan once kapsamli regresyon testleri yazilmalidir.

### 4.2. CLI Entegrasyonu Eksik

Terminalden not ekleme ve listeleme henuz tamamlanmasi gereken onemli bir ozelliktir.

Planlanan komutlar:

- `beernotes-cli add "Baslik"`
- `beernotes-cli list`
- `beernotes-cli list --tag X`

Bu CLI, GUI'den ayri bir depolama mantigi yazmamalidir. Mevcut `NoteController` ve `StorageEngine` kullanilmali, yani GUI ile ayni Markdown not dizinine yazmalidir.

### 4.3. Notlar Icin Git Versiyonlama Eksik

Uygulamanin kendi Git reposu ile kullanicinin not dizininin Git gecmisi birbirinden ayridir. Gelecekte not dizini kendi icinde Git repo haline getirilmeli ve her kayit debounced commit ile versiyonlanmalidir.

Bu sayede kullanici:

- Eski not versiyonlarina donebilir.
- Yanlislikla silinen veya degisen icerigi kurtarabilir.
- Not gecmisini uygulama kodundan bagimsiz takip edebilir.

### 4.4. LLM Entegrasyonu Eksik

Planlanan LLM ozellikleri:

- Groq API destegi.
- Yerel OpenAI uyumlu endpoint destegi.
- LM Studio gibi lokal modellerle calisma.
- Secili metin uzerinde ozetleme.
- Kod parcasi temizleme/duzeltme.
- Yaziyi devam ettirme veya taslak olusturma.
- Sonucu direkt degistirmeden once diff/onizleme popup'inda gosterme.

Bu ozellik guclu olabilir ama mutlaka kontrollu uygulanmalidir. Kullanicinin secili metni izinsiz buluta gonderilmemeli, provider secimi Preferences icinde acik olmalidir.

### 4.5. Command Palette Eksik

`Ctrl+Shift+P` ile acilan komut paleti planlandi ancak tamamlanmadi.

Bu palet sunlari arayabilmelidir:

- Yeni Not
- Dark Mode ac/kapat
- Zen Mode
- Export
- Import
- Backup
- Basit/Detayli mod gecisi
- Ayarlar

Komut paleti, ayni islemleri yeniden yazmak yerine mevcut action/menu nesnelerine baglanmalidir.

### 4.6. Split View ve Zen Mode Eksik

Gelecekte Pro Mode icin uc panelli bir yapi hedeflenmelidir:

- Dosya/klasor agaci
- Editor
- Onizleme

Bu alanlar `QSplitter` ile boyutlandirilabilir olmalidir.

Zen Mode ise:

- Sidebar'i gizlemeli.
- Toolbar'i gizlemeli.
- Tab bar ve menu bar'i gizlemeli.
- Yazmaya odakli temiz bir alan birakmali.
- Ayni kisayol tekrar basildiginda eski duzeni geri getirmelidir.

### 4.7. Floating Context Toolbar Eksik

Secili metin uzerinde beliren kucuk bir formatlama araci planlandi:

- Bold
- Italic
- Link
- Inline code

Bu arac, statik toolbar'i tamamen kalabaliklastirmadan temel bicimlendirmeyi hizlandirir.

### 4.8. Sistem Temasi ve Accent Entegrasyonu Eksik

Uygulama temasi su anda uygulama icinden yonetilmektedir. Gelecekte:

- KDE Plasma sistem temasini takip etme.
- Qt colorScheme sinyalini kullanma.
- Sistem accent rengini varsayilan olarak alma.
- Kullanici manuel accent secmisse bunu sistem renginin ustunde tutma.

gibi iyilestirmeler yapilmalidir.

### 4.9. AppImage Paketleme Eksik

Repoyu indiren veya uygulamayi kurmak isteyen son kullanici icin AppImage onemli bir eksiktir.

Planlanan script:

- `packaging/build_appimage.sh`
- PyInstaller ile bundle alma.
- AppDir yapisini kurma.
- `.desktop` dosyasini ekleme.
- Ikonu `beernotes/assets/beernotes.png` uzerinden alma.
- `AppRun` olusturma.
- `linuxdeploy` ve `linuxdeploy-plugin-qt` indirme.
- `Beer-Notes-x86_64.AppImage` uretme.

Bu tamamlandiginda kullanici uygulamayi daha kolay indirip calistirabilir.

## 5. Gelecek Icin Onerilen Yol Haritasi

### Asama 1: Stabilizasyon

Once mevcut tamamlanan ozellikler tekrar dogrulanmalidir:

- Tum testler calistirilmali.
- Markdown migration tekrar temiz bir test ortaminda denenmeli.
- Ayarlanabilir not dizini ve marker kontrolu test edilmeli.
- Export/import akisinda veri kaybi olmadigi dogrulanmali.
- Basit mod ve detayli mod gecislerinde not silinmedigi kontrol edilmeli.

Bu asama projenin guvenini saglar.

### Asama 2: Multi-Tab Sistemi

Bir sonraki en mantikli buyuk ozellik multi-tab sistemidir. Ancak bu ozellik veri kaybi riski tasidigi icin testlerle birlikte gelmelidir.

Tamamlanma kriterleri:

- Birden fazla not ayni anda acilir.
- Ayni not ikinci kez acilirsa yeni sekme degil mevcut sekme odaklanir.
- Sekme basligi not basligini ve kaydedilmemis degisiklik durumunu gosterir.
- Autosave sekme bazli calisir.
- Sekme kapatma ve pencere kapatma guvenli kayit yapar.
- Harici degisikliklerde kullanici verisi ezilmez.

### Asama 3: CLI

CLI, GUI kullanmadan not eklemek ve listelemek icin eklenmelidir.

Bu ozellik dusuk gorsel riskli ama yuksek faydalidir. Ayrica ileride otomasyon ve script kullanimini mumkun kilar.

### Asama 4: Not Dizini Git Versiyonlama

Not dizini kendi Git gecmisine sahip olmalidir. Bu, kullanicinin notlarini korumak icin cok guclu bir adimdir.

### Asama 5: Komut Paleti ve Zen Mode

Uygulamanin hizli kullanimi icin komut paleti, odakli yazim icin Zen Mode eklenmelidir.

### Asama 6: LLM Entegrasyonu

LLM ozellikleri en sona birakilmalidir. Cunku:

- API anahtari yonetimi gerekir.
- Gizlilik kararlari net olmalidir.
- Hata durumlari iyi tasarlanmalidir.
- Metin degistirme islemleri diff/onay akisi istemelidir.

## 6. Gelistirici Notlari

Projeye yeni ozellik eklerken su kurallara uyulmasi onerilir:

- Storage kodu GUI'den bagimsiz tutulmali.
- CLI ve GUI ayni controller/storage katmanini kullanmali.
- Not dosyalari insan tarafindan okunabilir kalmali.
- Veri kaybi riski olan her ozellik testle gelmeli.
- Ayar dosyasi geriye uyumlu sekilde genisletilmeli.
- Buyuk ozellikler atomik commitlerle ayrilmali.
- Her ozellikten sonra `git status`, testler ve gerekirse manuel smoke test yapilmali.

## 7. Kisa Sonuc

Beer Notes artik sadece basit bir not uygulamasi fikri degil; yerel dosya odakli, Markdown tabanli, genisleyebilir bir bilgi yonetim aracina donusmeye basladi.

Su ana kadar en kritik temel atildi:

- Notlar acik Markdown formatina tasindi.
- Metadata YAML front matter ile saklanmaya baslandi.
- Markdown editor ve kod vurgulama gelistirildi.
- Veri tasinabilirligi ve goc altyapisi guclendirildi.

Bundan sonraki en onemli is, yeni ozellik eklemekten once mevcut temeli koruyarak multi-tab ve mod gecislerini veri kaybi yaratmayacak sekilde tamamlamaktir. Projenin saglikli buyumesi icin aceleyle cok ozellik eklemek yerine, her ozelligi testli ve geri alinabilir sekilde ilerletmek en dogru yoldur.
