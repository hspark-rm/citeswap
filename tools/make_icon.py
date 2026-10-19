"""CiteSwap 아이콘(assets/icon.png · icon.ico · icon.icns)을 그린다. 특정 프로그램 로고는 쓰지 않는다(상표).
둥근 사각형 위에 서로 반대로 도는 화살표 두 개(바꾸기)와 인용 부호.
사용: python tools/make_icon.py   (icns 는 macOS 의 iconutil 이 있을 때만)"""
import os
import shutil
import struct
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,  # noqa: E402
                           QPen, QPolygonF)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "assets")


def arrow(p, cx, cy, r, start, span, color, width):
    """원호 화살표: 중심 (cx, cy), 반지름 r, start 도에서 span 도만큼."""
    pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    p.drawArc(rect, int(start * 16), int(span * 16))
    import math
    end = math.radians(start + span)
    ex, ey = cx + r * math.cos(end), cy - r * math.sin(end)
    # 화살촉: 원호의 접선 방향
    d = 1 if span > 0 else -1
    tx, ty = -math.sin(end) * d, -math.cos(end) * d
    nx, ny = -ty, tx
    size = width * 1.6
    tip = QPointF(ex + tx * size, ey + ty * size)
    left = QPointF(ex + nx * size, ey + ny * size)
    right = QPointF(ex - nx * size, ey - ny * size)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([tip, left, right]))


def draw(size=1024):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    m = size * 0.06
    rect = QRectF(m, m, size - 2 * m, size - 2 * m)
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0, QColor("#2f6feb"))
    g.setColorAt(1, QColor("#7b3fe4"))
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.22, size * 0.22)
    p.fillPath(path, g)
    c = size / 2
    w = size * 0.075
    arrow(p, c, c, size * 0.29, 196, -128, QColor("white"), w)   # 위쪽: 왼쪽 → 오른쪽
    arrow(p, c, c, size * 0.29, 16, -128, QColor("#e4e1fb"), w)  # 아래쪽(불투명: 화살촉이 겹쳐도 진해지지 않게): 오른쪽 → 왼쪽
    f = QFont("Georgia")
    f.setPixelSize(int(size * 0.36))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, size * 0.04, size, size), Qt.AlignCenter, "“”")
    p.end()
    return img


def png_bytes(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def main():
    QGuiApplication(sys.argv)
    os.makedirs(OUT, exist_ok=True)
    big = draw(1024)
    big.save(os.path.join(OUT, "icon.png"))
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [png_bytes(big.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off, ents = 6 + 16 * len(sizes), b""
    for s, d in zip(sizes, pngs):
        ents += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(d), off)
        off += len(d)
    open(os.path.join(OUT, "icon.ico"), "wb").write(head + ents + b"".join(pngs))
    if shutil.which("iconutil"):
        iset = os.path.join(OUT, "icon.iconset")
        os.makedirs(iset, exist_ok=True)
        for s in (16, 32, 128, 256, 512):
            for k, name in ((1, f"icon_{s}x{s}.png"), (2, f"icon_{s}x{s}@2x.png")):
                big.scaled(s * k, s * k, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(os.path.join(iset, name))
        subprocess.run(["iconutil", "-c", "icns", iset, "-o", os.path.join(OUT, "icon.icns")], check=True)
        shutil.rmtree(iset)
    print("아이콘:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
