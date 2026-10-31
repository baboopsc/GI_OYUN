# -*- coding: utf-8 -*-
"""
RÜN KULESİ - Tüm ayarlar tek dosyada.
Oyun zorluğunu, kamera ayarlarını ve görüntü işleme eşiklerini buradan değiştirebilirsin.
"""

# ---------------- Ekran ----------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# ---------------- Kamera ----------------
CAM_INDEX = 0          # Birden fazla kamera varsa 1, 2 dene
CAM_W, CAM_H = 640, 480
PREVIEW_W, PREVIEW_H = 224, 168   # Sağ alttaki küçük kamera önizlemesi

# Kameradaki bu bölge ekranın tamamına eşlenir (normalize: x0, y0, x1, y1).
# Böylece elini az oynatarak tüm ekranı nişan alabilirsin.
AIM_REGION = (0.12, 0.10, 0.88, 0.80)

# ---------------- Hareket (gesture) filtreleri ----------------
GESTURE_WINDOW = 5        # Son kaç karede oylama yapılacak
GESTURE_MIN_VOTES = 3     # Bir işaretin "kararlı" sayılması için gereken oy
# One Euro filtresi (imleç titremesini önler)
EURO_MINCUTOFF = 1.7
EURO_BETA = 0.025
HAND_LOST_GRACE = 0.25   # el bir anlığına kaybolursa işaret bu süre korunur (sn)
AIM_ASSIST_RADIUS = 150  # nişan yardımı: imlece bu kadar yakın düşmana kilitlenir (px)

# ---------------- Klasik görüntü işleme ----------------
# YCrCb uzayında ten rengi aralığı (literatürde yaygın kullanılan değerler)
YCRCB_LOW = (0, 133, 77)
YCRCB_HIGH = (255, 173, 127)
# Klasik modda el bu kutunun içinde aranır (normalize; ayna görüntüde sağ taraf)
CLASSIC_ROI = (0.50, 0.08, 0.97, 0.92)
CLASSIC_MIN_AREA = 0.04      # ROI alanına oranla en küçük el alanı
DEFECT_MAX_ANGLE = 85        # Parmak arası açının üst sınırı (derece)
DEFECT_MIN_DEPTH = 0.12      # Kusur derinliği / kontur yüksekliği

# ---------------- Sahne yerleşimi ----------------
GROUND_Y = 610
TOWER_X = 170            # Kulenin orta noktası
TOWER_W = 120
TOWER_TOP = 300
WIZARD_POS = (170, 262)
WALL_X = 340             # Taş golemin durduğu x
ENEMY_STOP_X = 238       # Düşmanların kuleye vurduğu x

# ---------------- Oyun dengesi ----------------
TOWER_HP = 220
MANA_MAX = 100
MANA_REGEN = 13          # saniyede
START_GOLD = 60

FIST_CHARGE_TIME = 0.8   # Ateş topunun tam şarj süresi (sn)
SHIELD_HOLD_TIME = 0.6   # Kalkan için açık eli tutma süresi (sn)
ICE_INTERVAL = 0.28      # V işaretinde buz oku aralığı (sn)

COST_FIREBALL = 10
COST_ICE = 3
SHIELD_DRAIN = 22        # saniyede
COST_METEOR = 60
COST_LIGHTNING = 45

RUNE_MIN_POINTS = 18
RUNE_MIN_LENGTH = 260    # piksel
RUNE_MIN_SCORE = 0.76

# Menü / dükkân: bir işareti kaç saniye tutunca seçilsin
HOLD_TO_SELECT = 0.9
RUNE_DWELL_TIME = 0.45    # parmak bu kadar durursa rün otomatik denenir
