"""Consistent overflow affordances and content-sized desktop dialogs.

Presentation only. Scroll buttons keep Qt's native navigation and focus handling.
"""
from PySide6.QtCore import Qt, QSize, QRect, QRectF, QTimer, QObject, QEvent
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QScrollArea, QSizePolicy,
    QWidget, QStyle, QStyleOptionTab, QStylePainter, QTabBar, QTabWidget, QToolButton)


class ReadingTabBar(QTabBar):
    """Identical wave cuts at either clipped edge, and visible scroll arrows."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False); self.setUsesScrollButtons(True); self.setDrawBase(False)
        self._arrow_cache={}
        self.setStyleSheet('QTabBar::scroller { width:48px; }'
            'QTabBar QToolButton { min-width:0; max-width:24px; padding:0; margin:0; border:0; border-radius:5px; }')

    def _scroll_buttons(self):
        return self.findChildren(QToolButton, options=Qt.FindDirectChildrenOnly)

    def _prepare_buttons(self):
        for button in self._scroll_buttons():
            direction=button.property('scrollDirection')
            if not direction:
                direction='left' if 'Left' in button.objectName() or button.arrowType()==Qt.LeftArrow else 'right'
                button.setProperty('scrollDirection',direction)
            color=self.palette().text().color()
            key=(direction,color.rgba(),self.devicePixelRatioF())
            if key not in self._arrow_cache:
                dpr=self.devicePixelRatioF();pm=QPixmap(round(18*dpr),round(18*dpr));pm.setDevicePixelRatio(dpr);pm.fill(Qt.transparent)
                p=QPainter(pm);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(color,1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
                x=7 if direction=='left' else 11;dx=4 if direction=='left' else -4
                path=QPainterPath();path.moveTo(x+dx,4);path.lineTo(x,9);path.lineTo(x+dx,14);p.drawPath(path);p.end()
                self._arrow_cache[key]=QIcon(pm)
            button.setArrowType(Qt.NoArrow)
            if button.property('arrowCache')!=str(key):
                button.setIcon(self._arrow_cache[key]);button.setIconSize(QSize(18,18));button.setProperty('arrowCache',str(key))

    def _tab_viewport(self):
        viewport=QRect(self.rect())
        for button in self._scroll_buttons():
            if button.isVisible():
                # Qt places its scroll-button pair at the trailing edge.
                if self.layoutDirection()==Qt.RightToLeft:viewport.setLeft(max(viewport.left(),button.geometry().right()+1))
                else:viewport.setRight(min(viewport.right(),button.geometry().left()-1))
        return viewport

    def overflow_edges(self):
        viewport=self._tab_viewport()
        if not self.count():return False,False
        rects=[self.tabRect(i) for i in range(self.count()) if self.isTabVisible(i)]
        return (any(r.left()<viewport.left() for r in rects),any(r.right()>viewport.right() for r in rects))

    def paintEvent(self,event):
        self._prepare_buttons();viewport=self._tab_viewport()
        painter=QStylePainter(self);painter.setClipRect(viewport)
        # Drawing the tab controls individually omits the platform's asymmetric
        # tear indicator. Tab geometry, scrolling and hit-testing remain native.
        indices=[i for i in range(self.count()) if i!=self.currentIndex()]+[self.currentIndex()]
        for index in indices:
            if index<0 or not self.isTabVisible(index) or not self.tabRect(index).intersects(viewport):continue
            option=QStyleOptionTab();self.initStyleOption(option,index);painter.drawControl(QStyle.CE_TabBarTab,option)
        painter.setRenderHint(QPainter.Antialiasing)
        background=self.palette().window().color();edge=self.palette().mid().color()
        for left,clipped in zip((True,False),self.overflow_edges()):
            if not clipped:continue
            painter.save();x=viewport.left() if left else viewport.right()+1
            painter.translate(x,0)
            if not left:painter.scale(-1,1)
            h=float(viewport.height());y=float(viewport.top())
            curve=QPainterPath();curve.moveTo(5,y)
            curve.cubicTo(12,y+h*.18,-2,y+h*.32,5,y+h*.5)
            curve.cubicTo(12,y+h*.68,-2,y+h*.82,5,y+h)
            mask=QPainterPath(curve);mask.lineTo(0,y+h);mask.lineTo(0,y);mask.closeSubpath()
            painter.fillPath(mask,background);painter.setPen(QPen(edge,1));painter.drawPath(curve);painter.restore()


def _content_height(widget,width):
    if isinstance(widget,QScrollArea) and widget.widget():return _content_height(widget.widget(),max(1,width-16))+4
    layout=widget.layout()
    if layout:
        height=layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.sizeHint().height()
        if height>=0:return height
    return max(widget.minimumSizeHint().height(),widget.sizeHint().height(),0)


class ReadingTabs(QTabWidget):
    """Size from the active page, not the tallest hidden tab; long pages scroll."""
    def __init__(self,parent=None):
        super().__init__(parent);self.setTabBar(ReadingTabBar(self))
        policy=QSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);policy.setHeightForWidth(True);self.setSizePolicy(policy)
        self.currentChanged.connect(self._page_changed)

    def addTab(self,page,*args):
        if not isinstance(page,QScrollArea):
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded);scroll.setWidget(page);page=scroll
        index=super().addTab(page,*args)
        self.setTabToolTip(index,self.tabText(index));return index

    def natural_tab_width(self):return self.tabBar().sizeHint().width()+8
    def heightForWidth(self,width):
        return (self.tabBar().sizeHint().height()+8+_content_height(self.currentWidget(),width)) if self.currentWidget() else 80
    def sizeHint(self):return QSize(max(480,self.natural_tab_width()),self.heightForWidth(max(480,self.width())))
    def minimumSizeHint(self):return QSize(280,120)
    def _page_changed(self,*_):
        self.updateGeometry()
        dialog=self.window()
        if isinstance(dialog,QDialog) and dialog.isVisible():
            QTimer.singleShot(0,dialog,lambda:fit_dialog(dialog,preferred_width=dialog.width()) if dialog.isVisible() else None)


def _dialog_height(dialog, width):
    custom = getattr(dialog, 'content_height_for_width', None)
    if custom is not None: return custom(width)
    height = _content_height(dialog, width)
    for scroll in dialog.findChildren(QScrollArea):
        if not scroll.widget() or not scroll.isVisibleTo(dialog): continue
        ancestor = scroll.parentWidget(); managed = False
        while ancestor and ancestor is not dialog:
            if isinstance(ancestor, (ReadingTabs, QScrollArea)): managed = True; break
            ancestor = ancestor.parentWidget()
        if not managed:
            height += _content_height(scroll, width - 32) - max(0, scroll.sizeHint().height())
    return height


class _DialogFitter(QObject):
    """Reflow on content changes in either direction; ignore unchanged user resizing."""
    def __init__(self,dialog):
        super().__init__(dialog);self.dialog=dialog;self.pending=False;self.usable=QRect();self.last_natural=None;self.last_width=None;self.fitting=False
        self.watched=set();self.hints={}
    def watch(self):
        for widget in [self.dialog]+[w for w in self.dialog.findChildren(QWidget) if w.layout()]+[s.widget() for s in self.dialog.findChildren(QScrollArea) if s.widget()]:
            if widget not in self.watched:widget.installEventFilter(self);self.watched.add(widget)
    def eventFilter(self,watched,event):
        if not self.fitting and event.type() in (QEvent.Show,QEvent.Hide,QEvent.LayoutRequest):self.schedule()
        return False
    def schedule(self):
        if self.pending:return
        self.pending=True;QTimer.singleShot(0,self,self.settle)
    def settle(self):
        self.pending=False;dialog=self.dialog
        if not dialog.isVisible() or self.usable.isEmpty():return
        self.watch()
        self.fitting = True
        try:
            for tabs in dialog.findChildren(ReadingTabs):
                hint = (tabs.currentIndex(), tabs.heightForWidth(dialog.width()))
                if self.hints.get(tabs) != hint:
                    self.hints[tabs] = hint; tabs.updateGeometry()
            for scroll in dialog.findChildren(QScrollArea):
                if not scroll.widget(): continue
                hint = _content_height(scroll.widget(), max(1, scroll.viewport().width()))
                if self.hints.get(scroll) != hint:
                    self.hints[scroll] = hint; scroll.updateGeometry()
            if dialog.layout(): dialog.layout().activate()
            natural = _dialog_height(dialog, dialog.width())
            if self.last_width != dialog.width():
                self.last_width = dialog.width(); self.last_natural = natural
                return  # A user width change is not a request to resize their window again.
            if self.last_natural is not None and abs(natural - self.last_natural) <= 1: return
            self.last_natural = natural
            height = min(self.usable.height(), max(dialog.minimumHeight(), natural, 120))
            if abs(height - dialog.height()) > 1:
                dialog.resize(dialog.width(), height)
                dialog.move(dialog.x(), max(self.usable.top(), min(dialog.y(), self.usable.bottom() - height + 1)))
        finally:
            self.fitting = False


def fit_dialog(dialog,*,preferred_width=640,preferred_height=None,available=None):
    """Use available content space without maximizing or keeping a blank tail.

    Called on opening or page changes, never continuously while the user resizes.
    The owning screen is used, including its origin on a multi-monitor desktop.
    """
    screen=dialog.screen() or QApplication.primaryScreen()
    available=QRect(available if available is not None else screen.availableGeometry() if screen else QRect(0,0,1280,800))
    usable=available.adjusted(24,40,-24,-40)
    max_width=max(1,usable.width());max_height=max(1,usable.height())
    dialog.ensurePolished()
    bars=dialog.findChildren(ReadingTabs)
    natural=max([tab.natural_tab_width()+40 for tab in bars] or [0])
    width=min(max_width,max(preferred_width,natural,dialog.minimumWidth()))
    # Set width first so native height-for-width text uses its actual line breaks.
    dialog.resize(width,min(dialog.height(),max_height))
    if dialog.layout():dialog.layout().invalidate();dialog.layout().activate()
    natural_height = _dialog_height(dialog, width)
    height = preferred_height if preferred_height is not None else natural_height
    height=min(max_height,max(height,dialog.minimumHeight(),120))
    # Existing layouts may impose a larger minimum than a small screen. Scroll
    # areas keep their content reachable; the dialog itself must remain bounded.
    dialog.setMinimumSize(min(dialog.minimumWidth(),max_width),min(dialog.minimumHeight(),max_height))
    dialog.resize(width,height)
    parent=dialog.parentWidget()
    centre=parent.frameGeometry().center() if parent and available.contains(parent.frameGeometry().center()) else usable.center()
    x=max(usable.left(),min(centre.x()-width//2,usable.right()-width+1))
    y=max(usable.top(),min(centre.y()-height//2,usable.bottom()-height+1))
    dialog.move(x,y)
    fitter=getattr(dialog,'_content_fitter',None)
    if fitter is None:fitter=dialog._content_fitter=_DialogFitter(dialog)
    fitter.usable=usable;fitter.last_natural=natural_height;fitter.last_width=width;fitter.watch();fitter.schedule()
    return dialog.size()
