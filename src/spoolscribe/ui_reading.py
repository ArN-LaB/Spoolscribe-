"""Presentation components: visual choices and grouped, responsive parameters.

No catalogue, compatibility or export decisions belong in this module.
"""
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget)
from .i18n import tr
from .ui_surfaces import fit_dialog


def reading_label(text='', name='guidanceNote'):
    label=QLabel(text);label.setWordWrap(True);label.setTextFormat(Qt.PlainText)
    label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);label.setObjectName(name)
    return label


class CardGrid(QWidget):
    """Cards flow in one or two columns; the last odd card spans both."""
    def __init__(self,cards,threshold=500,parent=None):
        super().__init__(parent);self.cards=cards;self.threshold=threshold;self.columns=0
        self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(8)
        policy=QSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);policy.setHeightForWidth(True);self.setSizePolicy(policy)
        self._reflow(1)
    def resizeEvent(self,event):
        super().resizeEvent(event);self._reflow(2 if self.width()>=self.threshold else 1)
    def _reflow(self,columns):
        if columns==self.columns:return
        self.columns=columns
        for card in self.cards:self.grid.removeWidget(card)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1 if columns==2 else 0)
        for i,card in enumerate(self.cards):
            span=2 if columns==2 and i==len(self.cards)-1 and i%2==0 else 1
            self.grid.addWidget(card,i//columns,i%columns,1,span)
        self.updateGeometry()


CATEGORY_TEXT={
 'all':('Tous les modèles','Parcourir les imprimantes et lecteurs.'),
 'compatible':('Export possible','Avec le logiciel et le lecteur adaptés.'),
 'usb':('Lecteur USB','Un lecteur ajouté reconnu par votre installation.'),
 'network':('Lecteur réseau','Une liaison Wi-Fi ou réseau déjà intégrée.'),
 'stock':('Logiciel d’origine','Export possible avec une configuration constructeur.'),
 'modified':('Logiciel modifié','Export possible avec une modification compatible.'),
 'rfid':('Autre format RFID','Format lu, mais non exporté par SpoolScribe.'),
 'none':('À vérifier','Aucune intégration de lecture confirmée.'),
}


class CategoryTile(QAbstractButton):
    """A keyboard-operable card with a vector symbol, title, note and count."""
    def __init__(self,key,count,parent=None):
        super().__init__(parent);self.key=key;self.model_count=count
        title,note=CATEGORY_TEXT[key];self.setText(tr(title));self.note=tr(note)
        self.setCheckable(True);self.setFocusPolicy(Qt.StrongFocus);self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(self.text());self.setAccessibleDescription(self.note+' '+tr('{v0} choix',v0=count))
        policy=QSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);policy.setHeightForWidth(True);self.setSizePolicy(policy)
        self.setMinimumHeight(108);self.setMinimumWidth(0)
    def heightForWidth(self,width):
        f=QFont(self.font());f.setBold(True);w=max(120,width-56)
        title=QFontMetrics(f).boundingRect(0,0,w,2000,Qt.TextWordWrap,self.text()).height()
        note=QFontMetrics(self.font()).boundingRect(0,0,max(120,width-24),2000,Qt.TextWordWrap,self.note).height()
        return max(108,title+note+60)
    def sizeHint(self):return QSize(255,self.heightForWidth(255))
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter):self.click();event.accept();return
        super().keyPressEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        ink=self.palette().text().color();dark=ink.lightness()>128
        accent=QColor('#2fd0e4' if dark else '#127f8e');base=QColor('#262b31' if dark else '#ffffff')
        edge=QColor('#3a414a' if dark else '#d2d6db')
        if self.isChecked():base=QColor('#293f46' if dark else '#eaf3f4')
        p.setPen(QPen(accent if self.isChecked() else edge,2 if self.isChecked() else 1));p.setBrush(base)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),9,9)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush);p.setPen(QPen(accent,1,Qt.DashLine));p.drawRoundedRect(QRectF(self.rect()).adjusted(4,4,-4,-4),6,6)
        p.save();p.translate(13,13);p.setPen(QPen(accent,1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
        if self.key=='usb':
            p.drawRoundedRect(QRectF(5,3,12,15),2,2);p.drawLine(8,0,8,3);p.drawLine(14,0,14,3);p.drawLine(11,18,11,23)
        elif self.key=='network':
            for x,y in ((8,0),(0,16),(16,16)):p.drawRoundedRect(QRectF(x,y,7,6),1,1)
            p.drawLine(11,6,11,12);p.drawLine(3,12,19,12);p.drawLine(3,12,3,16);p.drawLine(19,12,19,16)
        elif self.key in ('compatible','stock','modified'):
            p.drawRoundedRect(QRectF(2,1,19,21),3,3)
            if self.key=='modified':p.drawLine(7,17,17,7);p.drawEllipse(QRectF(12,3,7,7))
            else:p.drawLine(6,11,10,15);p.drawLine(10,15,17,7)
        elif self.key=='rfid':
            p.drawRoundedRect(QRectF(1,4,20,15),3,3)
            for n in (0,5):p.drawArc(QRectF(7-n/2,7-n/2,7+n,7+n),-65*16,130*16)
        elif self.key=='none':p.drawEllipse(QRectF(1,1,21,21));p.drawText(QRectF(1,0,21,22),Qt.AlignCenter,'?')
        else:
            for x,y in ((0,0),(13,0),(0,13),(13,13)):p.drawRoundedRect(QRectF(x,y,9,9),1,1)
        p.restore();p.setPen(ink);f=QFont(self.font());f.setBold(True);p.setFont(f)
        title_rect=QRectF(46,12,self.width()-58,2000)
        title_height=QFontMetrics(f).boundingRect(0,0,int(title_rect.width()),2000,Qt.TextWordWrap,self.text()).height()
        title_rect.setHeight(title_height);p.drawText(title_rect,Qt.TextWordWrap|Qt.AlignTop,self.text())
        p.setFont(self.font());p.setPen(QColor('#c3cad2' if dark else '#41454a'))
        p.drawText(QRectF(12,max(43,title_rect.bottom()+8),self.width()-24,self.height()-67),Qt.TextWordWrap|Qt.AlignTop,self.note)
        p.setPen(accent);p.drawText(QRectF(12,self.height()-28,self.width()-24,18),Qt.AlignLeft|Qt.AlignVCenter,tr('{v0} choix',v0=self.model_count));p.end()


class PrinterCategoryDialog(QDialog):
    def __init__(self,selected,counts,parent=None):
        super().__init__(parent);self.selected_key=selected
        self.setWindowTitle(tr('Quel type d’installation recherchez-vous ?'));self.setMinimumSize(400,340)
        height=QApplication.primaryScreen().availableGeometry().height() if QApplication.primaryScreen() else 800
        self.resize(650,min(640,height-60));box=QVBoxLayout(self);box.setContentsMargins(16,16,16,16);box.setSpacing(12)
        title=reading_label(tr('Votre installation'),'guidanceHeading');box.addWidget(title)
        box.addWidget(reading_label(tr('Choisissez une catégorie, puis votre modèle. La compatibilité dépend du lecteur et du logiciel installés.')))
        self.tiles={key:CategoryTile(key,counts.get(key,0)) for key in CATEGORY_TEXT}
        for key,tile in self.tiles.items():
            tile.setChecked(key==selected);tile.clicked.connect(lambda checked=False,k=key:self._choose(k))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.cards=CardGrid(list(self.tiles.values()),500);scroll.setWidget(self.cards);box.addWidget(scroll,1)
        buttons=QDialogButtonBox(QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Cancel).setText(tr('Annuler'));buttons.button(QDialogButtonBox.Cancel).setFixedHeight(32);buttons.rejected.connect(self.reject);box.addWidget(buttons)
        self.tiles.get(selected,self.tiles['all']).setFocus()
    def showEvent(self,event):
        super().showEvent(event);fit_dialog(self,preferred_width=720)
    def _choose(self,key):self.selected_key=key;self.accept()


class PrinterCategoryPicker(QComboBox):
    def __init__(self,parent=None):
        super().__init__(parent);self.counts_provider=lambda:{}
    def showPopup(self):
        dialog=PrinterCategoryDialog(self.currentData(),self.counts_provider(),self.window())
        if dialog.exec()==QDialog.Accepted:
            index=self.findData(dialog.selected_key)
            if index>=0:self.setCurrentIndex(index)
        dialog.deleteLater()


class ParameterCard(QFrame):
    def __init__(self,title,fields,cells,parent=None):
        super().__init__(parent);self.setObjectName('parameterCard');self.setMinimumWidth(0)
        box=QVBoxLayout(self);box.setContentsMargins(10,10,10,10);box.setSpacing(6)
        top=QHBoxLayout();top.addWidget(reading_label(tr(title),'comparisonHead'),1)
        self.badge=QLabel();self.badge.setObjectName('parameterState');top.addWidget(self.badge);box.addLayout(top)
        values=QHBoxLayout();values.setSpacing(5);self.values=[]
        for index,(key,caption) in enumerate(fields):
            cells[key][0].setParent(self);cells[key][0].setText(tr(caption));cells[key][0].hide()
            if index:
                dash=reading_label('–','guidanceNote');dash.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);values.addWidget(dash)
            value=cells[key][4];value.setObjectName('guidanceValue');value.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred)
            value.setAccessibleName(tr(title)+' · '+tr(caption));values.addWidget(value);self.values.append(value)
        unit='°C' if len(fields)>1 else fields[0][1] if fields[0][0]!='hex' else ''
        if unit:
            unit_label=reading_label(unit,'guidanceNote');unit_label.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);values.addWidget(unit_label)
        values.addStretch(1)
        if fields[0][0]=='hex':
            self.swatch=QFrame();self.swatch.setFixedSize(22,22);values.insertWidget(0,self.swatch)
        else:self.swatch=None
        box.addLayout(values)
        self.sources=QWidget();source_layout=QVBoxLayout(self.sources);source_layout.setContentsMargins(0,0,0,0);source_layout.setSpacing(4)
        self.source_rows={};self.source_notes={};self.origin_notes={}
        for key,caption in fields:
            self.source_rows[key]={}
            # Effective value's origin (what the export uses), always shown in the details.
            origin=reading_label('','guidanceNote');origin.setObjectName('effectiveOrigin');origin.setWordWrap(True)
            source_layout.addWidget(origin);self.origin_notes[key]=origin
            for column,name in ((1,'Référence'),(2,'Orca'),(3,'Personnel')):
                row=QWidget();line=QHBoxLayout(row);line.setContentsMargins(0,0,0,0);line.setSpacing(6)
                label=reading_label(tr(name)+(f' · {tr(caption)}' if len(fields)>1 else ''),'guidanceNote')
                line.addWidget(label,1)
                detail=QVBoxLayout();detail.setSpacing(2);detail.addWidget(cells[key][column])
                if column==1:
                    note=reading_label();detail.addWidget(note);self.source_notes[key]=note
                line.addLayout(detail,1);source_layout.addWidget(row);self.source_rows[key][column]=row
        box.addWidget(self.sources);self.sources.hide()
        self.keys=[key for key,_ in fields]
    def update_rows(self,rows,show_orca,show_personal):
        changed=any(rows[k]['differs'] for k in self.keys)
        suspect=any(rows[k]['reference'].get('suspect') for k in self.keys)
        unknown=any(rows[k]['effective']['value'] is None for k in self.keys)
        self.badge.setText(tr('À vérifier') if suspect else tr('Inconnue') if unknown else tr('Ajusté') if changed else tr('Référence'))
        self.badge.setVisible(suspect or unknown or changed)
        self.setProperty('tone','attention' if suspect or unknown else 'changed' if changed else 'neutral')
        self.style().unpolish(self);self.style().polish(self)
        for key in self.keys:
            self.source_rows[key][1].setVisible(rows[key]['differs'])
            self.source_rows[key][2].setVisible(show_orca);self.source_rows[key][3].setVisible(show_personal)
        if self.swatch is not None:
            hx=rows['hex']['effective']['value']
            valid=isinstance(hx,str) and len(hx)==6 and all(c in '0123456789abcdefABCDEF' for c in hx)
            self.swatch.setStyleSheet(f'background:#{hx};border:1px solid #89949c;border-radius:5px;' if valid else 'background:transparent;border:1px dashed #89949c;border-radius:5px;')
            self.swatch.setAccessibleName(tr('Couleur déclarée') if valid else tr('Couleur inconnue'))
