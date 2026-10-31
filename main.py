# -*- coding: utf-8 -*-
"""
RÜN KULESİ — El İşareti Tanıma ile Gerçek Zamanlı Etkileşimli Oyun
Görüntü İşleme Dersi Projesi

Çalıştırma:  python main.py
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

from config import SCREEN_W, SCREEN_H, CAM_INDEX
from vision.camera import VisionWorker
from game.game import Game


def main():
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED)
    pygame.display.set_caption("Rün Kulesi — El İşaretiyle Büyü Savaşı")

    vision = VisionWorker(CAM_INDEX)
    vision.start()
    try:
        Game(screen, vision).run()
    finally:
        vision.stop()
        pygame.quit()


if __name__ == "__main__":
    main()
