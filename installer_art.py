"""Original vector artwork for the offline installer. Requires the build Qt env."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage,QPainter,QColor,QFont,QLinearGradient,QPen
from PySide6.QtWidgets import QApplication
from app import load_fonts
from visuals import drug_icon

def generate(folder):
    q=QApplication.instance() or QApplication([]);load_fonts()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    image=QImage(492,942,QImage.Format.Format_RGB32)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.scale(3,3)
    gradient=QLinearGradient(0,0,164,314);gradient.setColorAt(0,QColor('#142d33'));gradient.setColorAt(1,QColor('#10191e'))
    p.fillRect(QRectF(0,0,164,314),gradient)
    p.setPen(QPen(QColor('#243d3e'),.5))
    for x in range(-150,330,22):p.drawLine(x,0,x+160,314)
    def line(text,x,y,size,color,bold=False):
        font=QFont('Segoe UI');font.setPixelSize(size);font.setBold(bold)
        p.setFont(font);p.setPen(QColor(color));p.drawText(x,y,text)
    p.fillRect(QRectF(16,24,22,3),QColor('#a7d8ba'))
    line('DOPE',16,66,31,'#f2f6ef',True)
    line('WARS',16,96,31,'#f2f6ef',True)
    line('BFT EDITION',17,117,11,'#cdd6ae',True)
    line('DANMARK EFTER MØRKET',17,137,7,'#8fa7a0')
    for i,key in enumerate(['hash','mdma','meth']):
        drug_icon(key).paint(p,QRectF(17+i*45,165,37,37).toRect())
    line('ÉN TASKE.',17,230,11,'#d9e3db',True)
    line('OTTE BYER.',17,247,11,'#d9e3db',True)
    line('DIN EGEN VEJ.',17,264,11,'#d9e3db',True)
    line('SINGLEPLAYER  /  LOKAL LAN',17,297,7,'#8fa7a0')
    p.end();image.save(str(folder/'wizard.bmp'))
    small=QImage(165,165,QImage.Format.Format_RGB32);small.fill(QColor('#182127'))
    p=QPainter(small);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font=QFont('Segoe UI');font.setPixelSize(55);font.setBold(True);p.setFont(font);p.setPen(QColor('#cdd6ae'));p.drawText(small.rect(),Qt.AlignmentFlag.AlignCenter,'BFT');p.end()
    small.save(str(folder/'wizard-small.bmp'))

if __name__=='__main__':generate(Path(__file__).parent/'installer-assets')
