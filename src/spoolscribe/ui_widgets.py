"""Small visual components with height-for-width support on native macOS too."""
from functools import lru_cache
import re
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QEvent
from PySide6.QtGui import QPalette, QColor, QPainter, QPen, QFont, QPixmap, QIcon, QRadialGradient, QLinearGradient, QPainterPath
from PySide6.QtWidgets import (QLabel, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QSizePolicy, QGridLayout,
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QComboBox, QDialog, QLineEdit,
    QDialogButtonBox, QScrollArea, QStyleOptionComboBox)

from .i18n import tr
from .colour_distance import display_delta
from .ui_surfaces import fit_dialog
from .ui_reading import PrinterCategoryDialog, PrinterCategoryPicker

CONTROL_HEIGHT = 32


def printer_visual(info, size=80, dark=False):
    """Use the documented photo, otherwise an explicitly generic device pictogram."""
    if info.get('photo'):
        photo = _product_photo(info['photo'], tuple(info.get('photo_bounds', ())), size)
        if not photo.isNull():return photo
    return _generic_printer_visual(info.get('visual_kind', 'enclosed'), size, dark)


@lru_cache(maxsize=64)
def _product_photo(path, bounds, size):
    """Fit the visible object in the UI; original files and colours stay untouched."""
    photo = QPixmap(path)
    if photo.isNull():return photo
    if len(bounds)==4:
        left,top,right,bottom=bounds
        if 0<=left<right<=photo.width() and 0<=top<bottom<=photo.height():
            photo=photo.copy(left,top,right-left,bottom-top)
    photo=photo.scaled(size*2,size*2,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    photo.setDevicePixelRatio(2)
    return photo


@lru_cache(maxsize=64)
def _generic_printer_visual(kind, size, dark):
    """Vector artwork, not a manufacturer logo or a model-specific photograph."""
    image = QPixmap(size*2, size*2); image.setDevicePixelRatio(2); image.fill(Qt.transparent)
    painter = QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size/80, size/80)
    ink = QColor('#acc9dc' if dark else '#48677a')
    accent = QColor('#58c3ce' if dark else '#168a99')
    painter.setPen(QPen(ink, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(QColor('#2b3943' if dark else '#eaf0f3'))
    if kind == 'reader':
        painter.drawRoundedRect(QRectF(16, 15, 46, 52), 7, 7)
        painter.setBrush(Qt.NoBrush); painter.setPen(QPen(accent, 2.5, Qt.SolidLine, Qt.RoundCap))
        for inset in (0, 8, 16):
            painter.drawArc(QRectF(27-inset/2, 30-inset/2, 14+inset, 14+inset), -55*16, 110*16)
        painter.drawLine(30, 58, 48, 58)
    else:
        if kind == 'enclosed':
            painter.drawRoundedRect(QRectF(10, 10, 60, 60), 5, 5)
            painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(QRectF(17, 20, 46, 42), 2, 2)
            painter.drawLine(53, 15, 61, 15)
        else:
            painter.drawRoundedRect(QRectF(9, 63, 62, 8), 2, 2)
            painter.drawLine(17, 63, 17, 14); painter.drawLine(63, 63, 63, 14)
            painter.drawLine(17, 14, 63, 14)
        painter.drawLine(21, 29, 59, 29); painter.drawLine(40, 29, 40, 40)
        painter.setPen(QPen(accent, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(36, 40, 44, 40); painter.drawLine(40, 40, 40, 44)
        painter.setBrush(accent); painter.drawRoundedRect(QRectF(30, 49, 20, 10), 2, 2)
        painter.setPen(QPen(ink, 2.5, Qt.SolidLine, Qt.RoundCap)); painter.drawLine(23, 61, 57, 61)
    painter.end()
    return image


class ChoiceButtons(QWidget):
    """Small exclusive choices; several groups form one readable setup."""
    choiceChanged=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QButtonGroup
        self.group=QButtonGroup(self);self.group.setExclusive(True)
        self.buttons={};self._choices=[]
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(8)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1)
    def setChoices(self,choices):
        from PySide6.QtWidgets import QToolButton
        choices=list(choices)
        if choices==self._choices:return
        self._choices=choices
        for button in self.buttons.values():
            self.group.removeButton(button);self.grid.removeWidget(button);button.hide();button.deleteLater()
        self.buttons={}
        for i,(label,key) in enumerate(choices):
            button=QToolButton(self);button.setText(label);button.setCheckable(True)
            button.setFixedHeight(CONTROL_HEIGHT);button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
            button.setAccessibleName(label);button.clicked.connect(lambda _checked=False,value=key:self.choiceChanged.emit(value))
            self.group.addButton(button);self.buttons[key]=button
            self.grid.addWidget(button,i//2,i%2,1,2 if i==len(choices)-1 and i%2==0 else 1)
    def setChoice(self,key):
        self.group.setExclusive(False)
        for value,button in self.buttons.items():button.setChecked(value==key)
        self.group.setExclusive(True)


class SearchField(QLineEdit):
    """A clear action with a stable hit area, centred independently of native QSS."""
    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QToolButton
        self.clear_button = QToolButton(self)
        self.clear_button.setObjectName('searchClear')
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setToolTip(tr('Effacer la recherche'))
        self.clear_button.setAccessibleName(tr('Effacer la recherche'))
        self.clear_button.setFixedSize(24, 24)
        self.clear_button.setAutoRaise(True)
        self.clear_button.setStyleSheet('QToolButton#searchClear { border:none; padding:0; margin:0; background:transparent; }')
        self.clear_button.clicked.connect(self._clear_search)
        self.textChanged.connect(lambda text: self.clear_button.setVisible(bool(text)))
        self.setTextMargins(0, 0, 30, 0)
        self.clear_button.hide()
        self._refresh_clear_icon()

    def setClearButtonEnabled(self, enabled):
        # Do not let Qt introduce its own platform-dependent trailing action.
        super().setClearButtonEnabled(False)

    def _clear_search(self):
        self.clear(); self.setFocus(Qt.OtherFocusReason)

    def _refresh_clear_icon(self):
        dpr = self.devicePixelRatioF()
        canvas = QPixmap(round(18*dpr), round(18*dpr)); canvas.setDevicePixelRatio(dpr); canvas.fill(Qt.transparent)
        painter = QPainter(canvas); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.PlaceholderText), 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(5, 5, 13, 13); painter.drawLine(13, 5, 5, 13); painter.end()
        self.clear_button.setIcon(QIcon(canvas)); self.clear_button.setIconSize(QSize(18,18))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.clear_button.move(self.width()-self.clear_button.width()-5, (self.height()-self.clear_button.height())//2)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange) and hasattr(self, 'clear_button'):
            self._refresh_clear_icon()



class DetailScrollArea(QScrollArea):
    viewportChanged = Signal()
    def __init__(self, parent=None):
        super().__init__(parent);self.viewport().installEventFilter(self)
    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type()==QEvent.Resize:self.viewportChanged.emit()
        return super().eventFilter(watched,event)


class PrinterPicker(QComboBox):
    """A normal labelled choice that opens a visual, searchable browser."""
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('printerPicker')
    def paintEvent(self,event):
        super().paintEvent(event)
        # QSS suppresses the native arrow on some macOS editable controls.
        # Paint our own affordance, with the same palette and size on every OS.
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().text().color(),1.7,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        x=self.width()-18;y=self.height()/2
        path=QPainterPath();path.moveTo(x-4,y-2);path.lineTo(x,y+2);path.lineTo(x+4,y-2);painter.drawPath(path);painter.end()
    def showPopup(self):
        browser=PrinterBrowser(self,self.window())
        if browser.exec()==QDialog.Accepted and browser.selected_index is not None:
            self.setCurrentIndex(browser.selected_index)
        browser.deleteLater()


class PrinterChoiceDelegate(QStyledItemDelegate):
    """Paint compact rows; no child widget minimum heights accumulate on resize."""
    def __init__(self,entries,parent=None):
        super().__init__(parent);self.entries=entries
    def _metrics(self,index,width,font):
        info=self.entries[index.data(Qt.UserRole)];name_font=QFont(font);name_font.setBold(True)
        from PySide6.QtGui import QFontMetrics
        text_width=max(140,width-110)
        name_height=QFontMetrics(name_font).boundingRect(0,0,text_width,1000,Qt.TextWordWrap,info['title']).height()
        detail_height=QFontMetrics(font).boundingRect(0,0,text_width,1000,Qt.TextWordWrap,info['description']).height()
        return info,name_font,text_width,name_height,detail_height
    def sizeHint(self,option,index):
        width=max(300,self.parent().viewport().width()-12)
        _,_,_,name_height,detail_height=self._metrics(index,width,option.font)
        return QSize(width,max(88,name_height+detail_height+30))
    def paint(self,painter,option,index):
        rect=QRectF(option.rect).adjusted(2,2,-2,-2);selected=bool(option.state&QStyle.State_Selected)
        info,name_font,text_width,name_height,detail_height=self._metrics(index,int(rect.width()),option.font)
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        ink=option.palette.text().color();dark=ink.lightness()>128;accent=option.palette.highlight().color()
        base=QColor('#252d34' if dark else '#ffffff');border=QColor('#434c55' if dark else '#d1d9df')
        painter.setPen(QPen(accent if selected else border,2 if selected else 1));painter.setBrush(base);painter.drawRoundedRect(rect,10,10)
        photo=QRectF(rect.left()+12,rect.top()+12,64,64);pixmap=printer_visual(info,64,dark)
        size=pixmap.size().scaled(128,128,Qt.KeepAspectRatio);target=QRectF(photo.center().x()-size.width()/4,photo.center().y()-size.height()/4,size.width()/2,size.height()/2)
        painter.drawPixmap(target,pixmap,QRectF(pixmap.rect()))
        x=rect.left()+90;y=rect.top()+12
        painter.setFont(name_font);painter.setPen(ink);painter.drawText(QRectF(x,y,text_width,name_height),Qt.TextWordWrap|Qt.AlignTop,info['title'])
        painter.setFont(option.font);painter.setPen(option.palette.text().color());painter.drawText(QRectF(x,y+name_height+6,text_width,detail_height),Qt.TextWordWrap|Qt.AlignTop,info['description'])
        painter.restore()


class PrinterBrowser(QDialog):
    def __init__(self,combo,parent=None):
        super().__init__(parent)
        from . import printer_profiles
        from .printer_presentations import presentation
        self.setWindowTitle(tr('Choisir mon imprimante'));self.resize(620,540);self.setMinimumSize(440,320)
        self.selected_index=None;self._cards=[]
        body=QVBoxLayout(self);body.setContentsMargins(16,16,16,16);body.setSpacing(12)
        title=QLabel(tr('Votre imprimante'));font=title.font();font.setPointSizeF(font.pointSizeF()+3);font.setBold(True);title.setFont(font);body.addWidget(title)
        self.search=QLineEdit();self.search.setPlaceholderText(tr('Marque ou modèle : Snapmaker, Prusa, X1…'));self.search.setClearButtonEnabled(True);self.search.setFixedHeight(CONTROL_HEIGHT);body.addWidget(self.search)
        self.category=PrinterCategoryPicker();self.category.setAccessibleName(tr('Catégorie de compatibilité'));self.category.setFixedHeight(CONTROL_HEIGHT)
        for label,key in ((tr('Toutes les imprimantes et lecteurs'),'all'),(tr('Au moins une configuration exportable'),'compatible'),
                          (tr('Lecteur USB ajouté'),'usb'),(tr('Lecteur réseau ajouté'),'network'),
                          (tr('Export possible · firmware constructeur'),'stock'),(tr('Export possible · firmware modifié'),'modified'),
                          (tr('Format lu, non exporté'),'rfid'),(tr('Aucune intégration confirmée'),'none')):self.category.addItem(label,key)
        body.addWidget(self.category)
        self.category_hint=WrapLabel(tr('La lecture dépend du logiciel installé ou d’un lecteur externe.'));self.category_hint.setObjectName('fieldvalue');body.addWidget(self.category_hint)
        self.list=QListWidget();self.list.setSpacing(4);self.list.setObjectName('printerChoices');body.addWidget(self.list,1)
        self.entries={}
        for i in range(combo.count()):
            profile=printer_profiles.PROFILES[combo.itemData(i)];info=presentation(profile)
            item=QListWidgetItem(info['title']);item.setData(Qt.UserRole,i)
            item.setToolTip(info.get('caption', info['title']))
            item.setData(Qt.AccessibleDescriptionRole, info.get('caption', info['description']))
            searchable=' '.join(' '.join(str(f.get(key,''))+' '+tr(f.get(key,'')) for key in ('label','reader','notes')) for f in profile['firmwares'])
            item.setData(Qt.UserRole+1,(combo.itemText(i)+' '+info['title']+' '+searchable).casefold())
            item.setData(Qt.UserRole+2,printer_profiles.categories(combo.itemData(i)));self.entries[i]=info;self.list.addItem(item)
            if i==combo.currentIndex():self.list.setCurrentItem(item)
        self.delegate=PrinterChoiceDelegate(self.entries,self.list);self.list.setItemDelegate(self.delegate)
        self.empty=QLabel(tr('Aucune imprimante trouvée. Essayez une autre marque ou un autre modèle.'));self.empty.setWordWrap(True);self.empty.hide();body.addWidget(self.empty)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok);buttons.button(QDialogButtonBox.Cancel).setText(tr('Annuler'));buttons.button(QDialogButtonBox.Ok).setText(tr('Choisir'))
        for button in buttons.buttons():button.setFixedHeight(CONTROL_HEIGHT)
        buttons.rejected.connect(self.reject);buttons.accepted.connect(self._choose);body.addWidget(buttons)
        self.list.itemDoubleClicked.connect(lambda *_:self._choose())
        self.search.textChanged.connect(self._filter)
        self._accept_button=buttons.button(QDialogButtonBox.Ok);self.search.setFocus()
        self.category.currentIndexChanged.connect(lambda *_:self._filter(self.search.text()))
        self.category.counts_provider=self._category_counts
        self.list.viewport().installEventFilter(self)
    def showEvent(self,event):
        super().showEvent(event);fit_dialog(self,preferred_width=720,preferred_height=min(760,200+self.list.count()*92))

    def _category_counts(self):
        counts={key:0 for key in ('all','compatible','usb','network','stock','modified','rfid','none')}
        query=self.search.text().casefold().strip()
        for i in range(self.list.count()):
            item=self.list.item(i)
            if query not in item.data(Qt.UserRole+1):continue
            counts['all']+=1
            for key in item.data(Qt.UserRole+2):
                if key in counts:counts[key]+=1
        return counts
    def eventFilter(self,watched,event):
        if watched is self.list.viewport() and event.type()==QEvent.Resize:
            self.list.doItemsLayout()
        return super().eventFilter(watched,event)
    def _filter(self,text):
        visible=[]
        self.category_hint.setText({'rfid':tr('Un lecteur utilise un format non exporté ici. Une autre installation peut être proposée.'),
            'none':tr('Fiches consultables ; aucune intégration de lecture confirmée.'),
            'usb':tr('USB avec logiciel et pilote documentés ; pas de prise en charge universelle au branchement.'),
            'network':tr('Le scanner transmet par réseau. Son câble USB peut ne servir qu’à l’alimentation.'),
            'stock':tr('Firmware constructeur conservé ; accessoires, mode LAN ou automatisations peuvent être requis.')}.get(self.category.currentData(),tr('Choisissez ensuite votre installation réelle. Le résultat peut se limiter à l’inventaire externe.')))
        for i in range(self.list.count()):
            item=self.list.item(i);category=self.category.currentData()
            item.setHidden(text.casefold().strip() not in item.data(Qt.UserRole+1) or category!='all' and category not in item.data(Qt.UserRole+2))
            if not item.isHidden():visible.append(item)
        if self.list.currentItem() not in visible:self.list.setCurrentItem(visible[0] if visible else None)
        self.empty.setVisible(not visible);self._accept_button.setEnabled(bool(visible))
    def _choose(self):
        item=self.list.currentItem()
        if item and not item.isHidden():self.selected_index=item.data(Qt.UserRole);self.accept()


def report_metrics(values):
    panel=QWidget();grid=QGridLayout(panel);grid.setContentsMargins(0,0,0,0);grid.setSpacing(8)
    for i,(label,value) in enumerate(values):
        tile=QFrame();tile.setObjectName('metricTile');body=QVBoxLayout(tile);body.setContentsMargins(12,10,12,10)
        number=QLabel(str(value));number.setObjectName('reportMetricValue');font=number.font();font.setPointSizeF(font.pointSizeF()+5);font.setBold(True);number.setFont(font)
        caption=WrapLabel(tr(label));caption.setObjectName('fieldvalue');body.addWidget(number);body.addWidget(caption);grid.addWidget(tile,i//3,i%3)
    for col in range(3):grid.setColumnStretch(col,1)
    return panel


def product_label(text, brand):
    """Remove repeated leading manufacturer names for display; source data stays intact."""
    if not brand:return text
    pattern=re.compile(r'^'+re.escape(brand)+r'\s+(?='+re.escape(brand)+r'\b)',re.IGNORECASE)
    previous=None
    while text!=previous:previous=text;text=pattern.sub('',text,count=1)
    return text


def card_product_label(text, brand):
    """The manufacturer is already in the card header; keep the product range."""
    text = product_label(text, brand)
    if brand:
        pattern = re.compile(r'^' + re.escape(brand) + r'(?:[™®])?\s+', re.IGNORECASE)
        while pattern.match(text): text = pattern.sub('', text, count=1)
    return text


class WrapLabel(QLabel):
    """A scroll area's child must reserve the height of the wrapped text."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)

    def fit_height(self):
        if self.width() > 0:
            height = max(self.fontMetrics().height(), self.heightForWidth(self.width()))
            if self.minimumHeight() != height:
                self.setMinimumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_height()

    def setText(self, text):
        super().setText(text)
        self.fit_height()


def paint_spool(painter, bounds, hex_color=None, dark=False):
    """Project every reel part from the same circular sections and physical axis."""
    import math
    painter.save();painter.setRenderHint(QPainter.Antialiasing)
    scale=min(bounds.width()/170,bounds.height()/160)
    painter.translate(bounds.center().x()-85*scale,bounds.center().y()-80*scale);painter.scale(scale,scale)
    color=QColor('#'+hex_color) if hex_color else QColor('#8b98a2')
    theta=math.radians(38);tilt=math.radians(-10)
    def point(radius,angle,z=0):
        a=math.radians(angle);x=math.cos(theta)*radius*math.cos(a)+math.sin(theta)*z;y=radius*math.sin(a)
        return (65+math.cos(tilt)*x-math.sin(tilt)*y,82+math.sin(tilt)*x+math.cos(tilt)*y)
    def loop(radius,z=0,start=0,end=360):
        return [point(radius,start+(end-start)*i/96,z) for i in range(97)]
    def path(points):
        result=QPainterPath();result.moveTo(*points[0])
        for p in points[1:]:result.lineTo(*p)
        result.closeSubpath();return result
    painter.setPen(Qt.NoPen);painter.setBrush(QColor(0,0,0,22));painter.drawEllipse(QRectF(19,136,127,9))
    plastic=QLinearGradient(20,25,130,130);plastic.setColorAt(0,QColor('#95a6af' if dark else '#6b7c87'));plastic.setColorAt(.45,QColor('#566670' if dark else '#364751'));plastic.setColorAt(1,QColor('#26333c'))
    painter.setBrush(plastic);painter.setPen(QPen(QColor('#91a0aa'),.7));painter.drawPath(path(loop(52,68)))
    tube=path([point(43,-90,0)]+loop(43,68,-90,90)+[point(43,90,0)])
    winding=QLinearGradient(30,25,110,130);winding.setColorAt(0,color.lighter(130));winding.setColorAt(.42,color);winding.setColorAt(1,color.darker(150))
    painter.setBrush(winding);painter.setPen(Qt.NoPen);painter.drawPath(tube)
    shade=color.darker(145);shade.setAlpha(110)
    for z in range(3,68,3):
        line=QPainterPath();line.moveTo(*point(43,-90,z))
        for x,y in loop(43,z,-90,90)[1:]:line.lineTo(x,y)
        painter.setPen(QPen(shade,.55));painter.drawPath(line)
    painter.setPen(Qt.NoPen);painter.setBrush(winding);painter.drawPath(path(loop(43)))
    for radius in range(18,44,4):
        painter.setBrush(Qt.NoBrush);painter.setPen(QPen(shade,.6));painter.drawPath(path(loop(radius)))
    # Broad moulded spokes and apertures, rather than bicycle-wheel spokes.
    flange=path(loop(52))
    for angle in range(0,360,60):
        opening=path(loop(45,0,angle-22,angle+22)+list(reversed(loop(20,0,angle-22,angle+22))))
        flange=flange.subtracted(opening)
    painter.setPen(QPen(QColor('#a4b1b9'),.7));painter.setBrush(plastic);painter.drawPath(flange)
    painter.setBrush(QColor('#192832'));painter.setPen(QPen(QColor('#97a7b0'),.7));painter.drawPath(path(loop(10)))
    tail=QPainterPath();tail.moveTo(*point(43,0,68));tail.cubicTo(151,91,130,118,151,134)
    painter.setBrush(Qt.NoBrush);painter.setPen(QPen(color,1.8,Qt.SolidLine,Qt.RoundCap));painter.drawPath(tail)
    if hex_color is None:
        painter.setPen(QColor('#edf3f6'));font=QFont();font.setPixelSize(12);font.setBold(True);painter.setFont(font)
        painter.drawText(QRectF(58,70,14,24),Qt.AlignCenter,'?')
    painter.restore()


@lru_cache(maxsize=256)
def spool_icon(hex_color, size=112, dpr=1, dark=False):
    image=QPixmap(round(size*dpr),round(size*dpr));image.fill(Qt.transparent)
    image.setDevicePixelRatio(dpr);p=QPainter(image)
    paint_spool(p,QRectF(0,0,size,size),hex_color,dark);p.end()
    return QIcon(image)


class SpoolPreview(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.hex_color=None;self.dark=False
        self.setFixedSize(128,136);self.setAccessibleName(tr('Aperçu de la bobine'))
    def set_filament(self, hex_color, dark=False):
        self.hex_color=hex_color;self.dark=dark
        self.setToolTip(tr('Couleur source #')+hex_color if hex_color else tr('Couleur à préciser : aucune teinte choisie'))
        self.update()
    def paintEvent(self,event):
        painter=QPainter(self);paint_spool(painter,QRectF(self.rect()),self.hex_color,self.dark);painter.end()


class MetricGrid(QWidget):
    columns=2
    def __init__(self,parent=None):
        super().__init__(parent);grid=QGridLayout(self);grid.setContentsMargins(0,0,0,0);grid.setSpacing(8)
        self.values={};self.labels={}
        for i,(key,title) in enumerate((('Nozzle','BUSE'),('Bed','PLATEAU'),('Diamètre',tr('DIAMÈTRE')),('Densité',tr('DENSITÉ')))):
            tile=QFrame();tile.setObjectName('metricTile');body=QVBoxLayout(tile);body.setContentsMargins(12,10,12,10);body.setSpacing(3)
            label=QLabel(tr(title));label.setObjectName('metricLabel');label.setProperty('field_key',key)
            value=WrapLabel('—');value.setObjectName('metricValue');font=value.font();font.setPointSize(14);font.setBold(True);value.setFont(font)
            body.addWidget(label);body.addWidget(value);grid.addWidget(tile,i//2,i%2)
            self.values[key]=value;self.labels[key]=label
        grid.setColumnStretch(0,1);grid.setColumnStretch(1,1)


class BrandDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        selected=bool(option.state & QStyle.State_Selected);hovered=bool(option.state & QStyle.State_MouseOver)
        painter.save();painter.setFont(option.font)
        base=option.palette.highlight().color() if selected else option.palette.base().color()
        if hovered and not selected:base=base.lighter(112) if base.lightness()<128 else base.darker(103)
        painter.fillRect(option.rect,base)
        ink=option.palette.highlightedText().color() if selected else option.palette.text().color();painter.setPen(ink)
        text_rect=option.rect.adjusted(6,0,-28,0)
        painter.drawText(text_rect,Qt.AlignVCenter,option.fontMetrics.elidedText(index.data() or '',Qt.ElideRight,text_rect.width()))
        if index.data(Qt.UserRole) and (index.data(Qt.UserRole+1) or hovered):
            painter.setPen(ink)
            painter.drawText(option.rect.adjusted(option.rect.width()-26,0,-2,0),Qt.AlignCenter,'★' if index.data(Qt.UserRole+1) else '☆')
        painter.restore()


class FavoriteBrandList(QListWidget):
    favoriteRequested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.setItemDelegate(BrandDelegate(self));self.setMouseTracking(True)
    def mousePressEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        if item and item.data(Qt.UserRole) and event.button()==Qt.LeftButton:
            if event.position().x()>self.visualItemRect(item).right()-26:
                self.favoriteRequested.emit(item.data(Qt.UserRole));return
        super().mousePressEvent(event)


class FilamentDelegate(QStyledItemDelegate):
    """Cards lead with the colour; product and brand stay readable but quieter.

    Selection (solid accent frame), keyboard focus (dashed inner frame) and hover
    (accent-tinted border) are distinct, and data state is written, not only tinted.
    """
    dark=False
    def __init__(self,parent=None):
        super().__init__(parent);self.rows={};self.context={}
    @staticmethod
    def footer_rects(box,font,delta):
        from PySide6.QtGui import QFontMetrics
        row=QRectF(box.left()+10,box.bottom()-(32 if delta is not None else 25),box.width()-20,20)
        if delta is None:return row,QRectF()
        value=QFont(font);value.setPointSize(10);value.setBold(True)
        label=QFont(font);label.setPointSize(8)
        width=QFontMetrics(value).horizontalAdvance(display_delta(delta))+QFontMetrics(label).horizontalAdvance('ΔE')+21
        badge=QRectF(row.right()-width,row.top(),width,row.height())
        meta=QRectF(row.left(),row.top(),max(0,row.width()-width-8),row.height())
        return meta,badge

    def paint(self,painter,option,index):
        row=self.rows.get(index.data(Qt.UserRole),{});dark=self.dark
        box=QRectF(option.rect).adjusted(5,5,-5,-5)
        selected=bool(option.state & QStyle.State_Selected);focused=bool(option.state & QStyle.State_HasFocus)
        hovered=bool(option.state & QStyle.State_MouseOver)
        accent=QColor('#26c6da' if dark else '#007f91');ink=QColor('#edf1f5' if dark else '#24303a')
        quiet=QColor('#9eafb9' if dark else '#61717d')
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        border=accent if selected else (accent.darker(130) if dark else accent.lighter(160)) if hovered else QColor('#45515b' if dark else '#d6dfe5')
        painter.setPen(QPen(border,2 if selected else 1))
        painter.setBrush(QColor('#263139' if dark else '#ffffff'));painter.drawRoundedRect(box,12,12)
        if focused:
            painter.setPen(QPen(accent,1,Qt.DashLine));painter.setBrush(Qt.NoBrush);painter.drawRoundedRect(box.adjusted(3,3,-3,-3),9,9)
        brand=row.get('brand','')
        # The brand is already given by an active manufacturer filter: keep it, quieter.
        painter.setPen(quiet if brand and self.context.get('brand')==brand else ink)
        font=QFont(option.font);font.setPointSize(9);painter.setFont(font)
        painter.drawText(box.adjusted(11,8,-30,-8),Qt.AlignTop,painter.fontMetrics().elidedText(brand,Qt.ElideRight,int(box.width()-48)))
        font.setPointSize(10);painter.setFont(font)
        painter.setPen(accent if row.get('_favorite') else QColor('#87939b'))
        painter.drawText(QRectF(box.right()-25,box.top()+6,20,22),Qt.AlignCenter,'★' if row.get('_favorite') else '☆')
        icon=index.data(Qt.DecorationRole)
        if icon:icon.paint(painter,int(box.center().x()-50),int(box.top()+24),100,92)
        colour=row.get('color_name') or tr('Couleur à renseigner')
        colour+=' ⚠' if row.get('hex_variants',0)>1 else ''
        painter.setPen(ink);font.setBold(True);font.setPointSize(13);painter.setFont(font)
        colour_rect=QRectF(box.left()+10,box.top()+118,box.width()-20,36)
        lines=painter.fontMetrics().elidedText(colour,Qt.ElideRight,int(2*colour_rect.width()-8))
        painter.drawText(colour_rect,Qt.TextWordWrap|Qt.AlignHCenter|Qt.AlignTop,lines)
        font.setBold(False);font.setPointSize(11);painter.setFont(font);painter.setPen(quiet)
        product=card_product_label(row.get('product',''),brand)
        painter.drawText(QRectF(box.left()+10,box.top()+155,box.width()-20,18),Qt.AlignHCenter|Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(product,Qt.ElideRight,int(box.width()-20)))
        state='' if row.get('ready') else tr('à vérifier') if 'vérifier' in str(row.get('quality','')).casefold() else tr('à compléter')
        bits=[f"{row['diameter']:g} mm" if row.get('diameter') else '',state]
        delta=row.get('_delta');meta,badge=self.footer_rects(box,option.font,delta)
        font.setPointSize(9);font.setBold(False);painter.setFont(font);painter.setPen(quiet)
        painter.drawText(meta,Qt.AlignVCenter|(Qt.AlignLeft if delta is not None else Qt.AlignHCenter),
                         painter.fontMetrics().elidedText(' · '.join(b for b in bits if b),Qt.ElideRight,int(meta.width())))
        if delta is not None:
            painter.setPen(Qt.NoPen);painter.setBrush(QColor('#174955' if dark else '#d9f1f3'));painter.drawRoundedRect(badge,6,6)
            painter.setPen(QColor('#b5f4fa' if dark else '#005460'))
            font.setPointSize(8);painter.setFont(font);painter.drawText(badge.adjusted(7,0,0,0),Qt.AlignVCenter|Qt.AlignLeft,'ΔE')
            font.setPointSize(10);font.setBold(True);painter.setFont(font)
            painter.drawText(badge.adjusted(0,0,-7,0),Qt.AlignVCenter|Qt.AlignRight,display_delta(delta))
        painter.restore()


class PrinterCard(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('printerCard');self.setMinimumHeight(150);self.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Maximum)
        layout=QHBoxLayout(self);layout.setContentsMargins(14,12,14,12);layout.setSpacing(16)
        photo_col=QVBoxLayout();self.photo=QLabel();self.photo.setFixedSize(112,110);self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setFixedSize(80,80)
        self.photo_caption=WrapLabel();self.photo_caption.setStyleSheet('font-size:10px;');self.photo_caption.setMaximumWidth(80)
        photo_col.addWidget(self.photo);photo_col.addWidget(self.photo_caption);photo_col.addStretch(1);layout.addLayout(photo_col)
        body=QVBoxLayout();body.setSpacing(8)
        self.name=WrapLabel();font=QFont();font.setPointSize(15);font.setBold(True);self.name.setFont(font)
        self.description=WrapLabel();self.status=WrapLabel();self.reader=WrapLabel();self.reader.hide()
        body.addWidget(self.name);body.addWidget(self.description);body.addWidget(self.status);body.addStretch(1);layout.addLayout(body,1)
    def update_profile(self,profile,status,can_export,dark=False):
        from .printer_presentations import presentation
        info=presentation(profile)
        accent='#31cadd' if dark else '#007f91';border='#434c55' if dark else '#d1d9df';background='#252d34' if dark else '#ffffff'
        self.setStyleSheet(f'QFrame#printerCard {{ background:{background}; border:1px solid {border}; border-radius:12px; }}')
        self.name.setText(info['title']);self.description.setText(info['description'])
        self.status.setText(status);self.status.setStyleSheet(f'color:{accent};font-weight:600;')
        self.reader.setText(profile.get('reader',''))
        self.photo.setPixmap(printer_visual(info,80,dark));self.photo.show();self.setMinimumHeight(108)
        caption=info.get('caption','') if info.get('photo') else tr('Illustration générique')
        self.photo.setToolTip(caption);self.photo.setAccessibleName(info['title'])
        self.photo_caption.setText(caption)
        self.photo_caption.setVisible(bool(caption) and caption!=info['title'])
        self.description.setToolTip(info.get('source',''))
