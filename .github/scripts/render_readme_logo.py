"""Export the repository's vector logo animation to a GitHub-compatible GIF.

Requires the existing development dependencies PySide6 and Pillow. No generated
artwork or external service: only the #disc group of the original SVG rotates.
"""
import io
import os
from pathlib import Path
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[2]
    svg = ET.fromstring((root / 'data/spoolscribe_logo_animated.svg').read_bytes())
    for node in list(svg):
        if node.tag.endswith('style'):
            svg.remove(node)
    disc = next(node for node in svg.iter() if node.get('id') == 'disc')
    frames = []
    for index in range(75):
        disc.set('transform', f'rotate({index*360/75} 256 252)')
        renderer = QSvgRenderer(QByteArray(ET.tostring(svg)))
        image = QImage(192,192,QImage.Format_ARGB32); image.fill(0)
        painter = QPainter(image);renderer.render(painter);painter.end()
        buffer = QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG')
        rgba = Image.open(io.BytesIO(bytes(buffer.data()))).convert('RGBA')
        # Reserve palette index 255 for transparent pixels outside the app tile.
        frame = rgba.convert('RGB').quantize(colors=255)
        frame.paste(255,mask=rgba.getchannel('A').point(lambda alpha:255 if alpha<128 else 0))
        frames.append(frame)
    target=root/'docs/images/spoolscribe-animated.gif'
    frames[0].save(target,save_all=True,append_images=frames[1:],loop=0,duration=40,
                   transparency=255,disposal=2,optimize=False)
    print(f'{target.relative_to(root)}: {len(frames)} frames, {target.stat().st_size} bytes')


if __name__ == '__main__':
    main()
