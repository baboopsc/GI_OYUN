# 🔮 RÜN KULESİ — El İşareti Tanıma ile Gerçek Zamanlı Etkileşimli Oyun

**Görüntü İşleme Dersi Projesi**

Büyücü bir kulenin tepesinde duruyor. Sağdan dalga dalga goblin, iskelet, hayalet, kalkanlı dev ve her 5 dalgada bir **Gölge Lordu** geliyor.
Oyuncu klavye ve fare kullanmaz: **web kamerası karşısında el işaretleri yaparak** büyü yapar, havaya **rün çizer**, dükkânda **parmak sayısı göstererek** yardımcı satın alır.

---

## 1. Kurulum (adım adım)

> Önerilen Python sürümü: **3.11 veya 3.12**. MediaPipe çok yeni Python sürümlerine geç gelebiliyor.

1. Python sürümünü kontrol et:
   ```
   python --version
   ```
2. VS Code'da `GI_OYUN` klasörünü aç, terminali aç (`Ctrl + ö`).
3. Sanal ortam oluştur ve aktif et:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Kütüphaneleri kur:
   ```
   pip install -r requirements.txt
   ```
   Eğer `mediapipe` kurulumu hata verirse diğerlerini tek tek kur. Oyun o durumda otomatik olarak **klasik görüntü işleme motoruyla** çalışır.
   ```
   pip install opencv-python pygame numpy
   ```
5. Oyunu çalıştır:
   ```
   python main.py
   ```

İlk çalıştırmada (yeni MediaPipe sürümlerinde) el modeli `models/` klasörüne bir kere indirilir.

---

## 2. Nasıl oynanır?

| El işareti | Büyü |
|---|---|
| ✊ **Yumruk tut** → ✋ **eli aç** | Şarjlı **ATEŞ TOPU**, nişangâha uçar ve alan hasarı verir. Ne kadar uzun tutarsan o kadar güçlü olur. |
| ✌️ **V işareti** | Seri **BUZ OKLARI**, isabet ettiği düşmanı yavaşlatır. |
| ✋ **Açık eli tut** (~1 sn) | Büyülü **KALKAN**, kuleyi korur ama mana harcar. |
| ☝️ İşaret parmağıyla **DAİRE** çiz | **METEOR YAĞMURU** (60 mana) |
| ☝️ İşaret parmağıyla **ZİKZAK** çiz | **YILDIRIM**, en güçlü 6 düşmana çarpar ve onları sersemletir (45 mana). |

- **Nişan:** Avucunun ekrandaki konumu nişangâhtır. **Nişan yardımı** imlece en yakın düşmana kilitlenir, ateş topu hedefe yönelir.
- **Rün:** Çizimi bitirince parmağını indir ya da parmağını yarım saniye sabit tut, rün otomatik tanınır.
- **Kombo:** Arka arkaya öldürdükçe çarpan artar (en fazla x3 altın ve skor). Tam şarjlı ateş topu **KRİTİK** vurur.
- **Ruh küreleri:** Ölen düşmanlardan mavi (mana) ve sarı (altın) küreler düşer. İmleci yaklaştır, kendileri sana gelir.
- **Düşmanlar:** Goblin, iskelet, hayalet, yarasa sürüsü, Goblin Şaman (diğerlerini iyileştirir, önce onu vur!), kalkanlı dev, Gölge Lordu (boss).
- **Dükkân (dalga arası):** 1-5 parmak göster ve 1 saniye tut, o yardımcıyı satın alırsın. **Yumruğu tutarsan** sonraki dalga başlar.

| Parmak | Ürün |
|---|---|
| 1 | Çırak Büyücü: kendi kendine ateş eder |
| 2 | Elf Okçu: önce uçan düşmanları vurur |
| 3 | Taş Golem: kulenin önünde duvar olur |
| 4 | Şifacı Peri: kuleyi sürekli onarır |
| 5 | Kule Güçlendirme: +40 can, tam onarım, +büyü gücü |

### Klavye kısayolları
| Tuş | İşlev |
|---|---|
| **TAB** | Debug ekranı (görüntü işleme adımlarını canlı gösterir; sunum için) |
| **E** | Tanıma motorunu değiştir: MediaPipe ↔ Klasik |
| **C** | Ten rengi kalibrasyonu (klasik motor: elini mor kutuya koyup bas) |
| **M** | Fare modu (kamera yoksa test için) |
| **N** | Ses ve müziği aç/kapat |
| **P** | Duraklat |
| **F11** | Tam ekran |
| **ESC** | Çıkış |

---

## 3. Kullanılan görüntü işleme yöntemleri (rapor / sunum için)

### 3.1 Sistem mimarisi
```
Kamera (OpenCV) ──► [Görüntü thread'i] ──────────────────────────► [Oyun thread'i, 60 FPS]
                     ayna çevirme                                  işaret → büyü eşlemesi
                     el tespiti (Motor A veya B)                   One Euro imleç filtresi
                     işaret sınıflandırma                          $1 rün tanıma
                     çoğunluk oylaması (zamansal filtre)           oyun mantığı + çizim
```
Görüntü işleme ayrı bir thread'de çalışır, böylece kamera yavaş olsa bile oyun 60 FPS akar. İşleme süresi (ms) ve FPS değerleri ekranda gösterilir.

### 3.2 Motor A: MediaPipe Hands (öğrenme tabanlı)
- Avuç tespiti ve 21 el eklem noktasının (landmark) çıkarılması.
- **Kural tabanlı sınıflandırma** (`vision/gestures.py`): Bir parmağın açık sayılması için ucunun bilekten uzaklığı orta eklemin (PIP) bilekten uzaklığından fazla olmalı. Tüm mesafeler avuç boyuna bölünerek normalize edilir, bu sayede yöntem **ölçekten ve dönmeden bağımsız** olur.

### 3.3 Motor B: Klasik görüntü işleme (derin öğrenme yok) — `vision/classic_engine.py`
1. **ROI** (ilgi bölgesi) seçimi
2. **Gauss bulanıklaştırma** ile gürültü azaltma
3. **Ten rengi segmentasyonu:** YCrCb renk uzayında eşikleme (Cr: 133-173, Cb: 77-127). Kalibrasyondan sonra **HSV histogram geri izdüşümü** (back projection) kullanılır.
4. **Haar Cascade yüz tespiti:** Yüz de ten rengi olduğu için maskeden silinir.
5. **Morfolojik işlemler:** Açma (gürültü temizleme) ve kapama (delik doldurma).
6. **Kontur analizi:** En büyük kontur el kabul edilir.
7. **Konveks gövde (convex hull)** ve **konvekslik kusurları (convexity defects)**
8. **Kosinüs teoremi:** Kusur noktasında parmaklar arası açı hesaplanır. Açı < 85° ve derinlik yeterliyse bu bir parmak boşluğudur.
9. **Parmak sayısı = boşluk + 1.** Boşluk yoksa uç noktasının ağırlık merkezine uzaklığı / eşdeğer yarıçap oranına bakılarak 0 ile 1 ayrılır.

### 3.4 Zamansal filtreleme
- **Çoğunluk oylaması:** Son 5 karede en az 3 oy alan işaret "kararlı" sayılır. Tek karelik yanlış algılamalar büyü tetiklemez.
- **Kayıp toleransı:** El 0,25 sn'den kısa süre kaybolursa (hareket bulanıklığı) son işaret korunur.
- **One Euro filtresi** (Casiez ve ark., 2012): Hız uyarlamalı alçak geçiren filtre. El yavaşken titremeyi yok eder, hızlıyken gecikme yaratmaz.

### 3.5 Hava çizimi tanıma: $1 Unistroke Recognizer — `vision/rune.py`
(Wobbrock ve ark., 2007) İşaret parmağı ucunun izlediği yol:
1. 64 eşit aralıklı noktaya yeniden örneklenir.
2. Gösterge açısına göre döndürülür (başlangıç noktasından bağımsızlık).
3. Kareye ölçeklenir ve orijine ötelenir.
4. Şablonlarla (daire, zikzak varyantları) **altın oran araması** kullanılarak en iyi açıda ortalama nokta mesafesi ölçülür. Benzerlik %76'nın altındaysa rün reddedilir.

---

## 4. Dosya yapısı
```
GI_OYUN/
├── main.py                  # giriş noktası
├── config.py                # tüm ayarlar (eşikler, zorluk, kamera)
├── requirements.txt
├── vision/
│   ├── camera.py            # kamera + görüntü işleme thread'i
│   ├── mediapipe_engine.py  # Motor A
│   ├── classic_engine.py    # Motor B (klasik)
│   ├── gestures.py          # sınıflandırma, oylama, One Euro filtresi
│   └── rune.py              # $1 rün tanıyıcı
└── game/
    ├── game.py              # durumlar, büyüler, HUD, dükkân
    ├── world.py             # düşmanlar, yardımcılar, mermiler, dalgalar
    ├── scene.py             # arka plan, kule, büyücü çizimi
    ├── ui.py                # arayüz kiti: paneller, barlar, ikonlar, el piktogramları
    ├── fx.py                # parçacık / ışıma efektleri
    └── sfx.py               # numpy ile sentezlenen ses efektleri ve müzik
```
Tüm grafikler ve sesler kodla üretilir, dışarıdan hiçbir görsel ya da ses dosyası kullanılmaz.

## 5. Sorun giderme
- **Kamera açılmıyor:** `config.py` içinde `CAM_INDEX = 1` dene. Başka bir program (Zoom, Teams) kamerayı kullanıyor olabilir.
- **İşaretler zor algılanıyor:** Aydınlık bir ortamda ol, elini kameraya 40-70 cm uzaklıkta tut, avucunu kameraya dön.
- **Klasik motorda el bulunmuyor:** Elini sarı kutuya koy, mor kutuyu avucunla kapat ve **C**'ye bas. Düz renkli bir arka plan en iyisidir.
- **Nişangâh ekranın kenarına ulaşmıyor:** `config.py` içindeki `AIM_REGION` değerini daralt.
