"""Resolution-independent game pictograms: original vector artwork, no external fonts."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QColor,QIcon,QPainter,QPixmap,QPolygonF,QPen
COLORS={'hash':'#34815c','cocaine':'#5b7a9a','amphetamine':'#ca8a39','mdma':'#9b5c95','ketamine':'#448e91','meth':'#5275ad'}

def drug_icon(key):
    pm=QPixmap(80,80);pm.setDevicePixelRatio(2);pm.fill(Qt.GlobalColor.transparent)
    p=QPainter(pm);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color=QColor(COLORS[key]);tint=QColor(color);tint.setAlpha(24)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(tint);p.drawRoundedRect(1,1,38,38,8,8)
    p.setBrush(color)
    if key=='hash':
        points=[(20,31),(8,23),(15,24),(6,14),(17,20),(15,8),(20,17),(24,5),(24,19),(33,12),(28,24),(35,21),(23,31)]
        p.drawPolygon(QPolygonF([QPointF(*v) for v in points]));p.setPen(QPen(color,2));p.drawLine(21,28,20,35)
    elif key=='mdma':
        p.drawEllipse(7,10,17,17);p.setBrush(color.lighter(125));p.drawEllipse(18,20,15,15)
        p.setPen(QPen(QColor('white'),2));p.drawLine(12,18,19,18);p.drawLine(23,27,28,27)
    elif key=='meth':
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in [(9,27),(13,10),(20,6),(25,16),(19,33)]]))
        p.setBrush(color.lighter(130));p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in [(22,31),(27,16),(33,20),(30,33)]]))
        p.setPen(QPen(QColor('white'),1));p.drawLine(19,10,16,28)
    else:
        p.setBrush(QColor('#f8fafc'));p.setPen(QPen(color,1.6));p.drawRoundedRect(10,8,20,25,3,3);p.drawLine(11,12,29,12)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in [(12,29),(16,23),(20,25),(24,19),(28,29)]]))
        if key=='ketamine':p.setPen(QPen(color,2));p.drawLine(16,17,24,17)
    p.end();return QIcon(pm)
