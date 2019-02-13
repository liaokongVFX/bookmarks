# -*- coding: utf-8 -*-
# pylint: disable=E1101, C0103, R0913, I1101, R0903, C0330

"""``BrowserWidget`` is the plug-in's main widget.
When launched from within Maya it inherints from MayaQWidgetDockableMixin baseclass,
otherwise MayaQWidgetDockableMixin is replaced with a ``common.LocalContext``, a dummy class.

Example:

.. code-block:: python
    :linenos:

    from browser.toolbar import BrowserWidget
    widget = BrowserWidget()
    widget.show()

The asset and the file lists are collected by the ``collector.AssetCollector``
and ```collector.FilesCollector`` classes. The gathered files then are displayed
in the ``listwidgets.AssetsListWidget`` and ``listwidgets.FilesListWidget`` items.

"""

import functools
from PySide2 import QtWidgets, QtGui, QtCore

import browser.common as common
from browser.delegate import paintmethod
from browser.baselistwidget import BaseContextMenu, contextmenu
from browser.bookmarkswidget import BookmarksWidget
from browser.assetwidget import AssetWidget
from browser.fileswidget import FilesWidget
from browser.editors import FilterEditor, ClickableLabel
from browser.settings import local_settings, Active, active_monitor


class BrowserButtonContextMenu(BaseContextMenu):
    """The context-menu associated with the BrowserButton."""

    def __init__(self, parent=None):
        super(BrowserButtonContextMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_show_menu()
        self.add_toolbar_menu()

    @contextmenu
    def add_show_menu(self, menu_set):
        if not hasattr(self.parent(), 'clicked'):
            return menu_set
        menu_set[u'show'] = {
            u'icon': common.get_rsc_pixmap(u'custom', None, common.INLINE_ICON_SIZE),
            u'text': u'Open...',
            u'action': self.parent().clicked.emit
        }
        return menu_set

    @contextmenu
    def add_toolbar_menu(self, menu_set):
        active_paths = Active.get_active_paths()
        bookmark = (active_paths[u'server'],
                    active_paths[u'job'], active_paths[u'root'])
        asset = bookmark + (active_paths[u'asset'],)
        location = asset + (active_paths[u'location'],)

        if all(bookmark):
            menu_set[u'bookmark'] = {
                u'icon': common.get_rsc_pixmap('bookmark', common.TEXT, common.INLINE_ICON_SIZE),
                u'disabled': not all(bookmark),
                u'text': u'Show active bookmark in the file manager...',
                u'action': functools.partial(common.reveal, u'/'.join(bookmark))
            }
            if all(asset):
                menu_set[u'asset'] = {
                    u'icon': common.get_rsc_pixmap(u'assets', common.TEXT, common.INLINE_ICON_SIZE),
                    u'disabled': not all(asset),
                    u'text': u'Show active asset in the file manager...',
                    u'action': functools.partial(common.reveal, '/'.join(asset))
                }
                if all(location):
                    menu_set[u'location'] = {
                        u'icon': common.get_rsc_pixmap(u'location', common.TEXT, common.INLINE_ICON_SIZE),
                        u'disabled': not all(location),
                        u'text': u'Show active location in the file manager...',
                        u'action': functools.partial(common.reveal, '/'.join(location))
                    }

        return menu_set


class BrowserButton(ClickableLabel):
    """Small widget to embed into the context to toggle the BrowserWidget's visibility."""

    def __init__(self, height=common.ROW_HEIGHT, parent=None):
        super(BrowserButton, self).__init__(parent=parent)
        self.context_menu_cls = BrowserButtonContextMenu
        self.setFixedWidth(height)
        self.setFixedHeight(height)

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setWindowFlags(
            QtCore.Qt.Widget |
            QtCore.Qt.FramelessWindowHint
        )
        pixmap = common.get_rsc_pixmap(
            u'custom', None, height)
        self.setPixmap(pixmap)

    def set_size(self, size):
        self.setFixedWidth(int(size))
        self.setFixedHeight(int(size))
        pixmap = common.get_rsc_pixmap(
            u'custom', None, int(size))
        self.setPixmap(pixmap)

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()

    def paintEvent(self, event):
        option = QtWidgets.QStyleOption()
        option.initFrom(self)

        painter = QtGui.QPainter()
        painter.begin(self)
        brush = self.pixmap().toImage()

        painter.setBrush(brush)
        painter.setPen(QtCore.Qt.NoPen)

        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        painter.setOpacity(0.8)
        if option.state & QtWidgets.QStyle.State_MouseOver:
            painter.setOpacity(1)

        painter.drawRoundedRect(self.rect(), 2, 2)
        painter.end()

    def contextMenuEvent(self, event):
        """Context menu event."""
        # Custom context menu
        shift_modifier = event.modifiers() & QtCore.Qt.ShiftModifier
        alt_modifier = event.modifiers() & QtCore.Qt.AltModifier
        control_modifier = event.modifiers() & QtCore.Qt.ControlModifier
        if shift_modifier or alt_modifier or control_modifier:
            self.customContextMenuRequested.emit()
            return

        widget = self.context_menu_cls(parent=self)
        widget.move(self.mapToGlobal(self.rect().bottomLeft()))
        widget.setFixedWidth(300)
        common.move_widget_to_available_geo(widget)
        widget.exec_()


class StackFaderWidget(QtWidgets.QWidget):
    """Overlay widget responsible for the `stackedwidget` cross-fade effect."""

    def __init__(self, old_widget, new_widget):
        super(StackFaderWidget, self).__init__(parent=new_widget)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.old_pixmap = QtGui.QPixmap(new_widget.size())
        self.old_pixmap.fill(common.SEPARATOR)
        self.opacity = 1.0

        self.timeline = QtCore.QTimeLine()
        self.timeline.valueChanged.connect(self.animate)
        self.timeline.finished.connect(self.close)
        self.timeline.setDuration(100)
        self.timeline.start()

        self.resize(new_widget.size())
        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setOpacity(self.opacity)
        painter.drawPixmap(0, 0, self.old_pixmap)
        painter.end()

    def animate(self, value):
        self.opacity = 1.0 - value
        self.repaint()


class OverlayWidget(QtWidgets.QWidget):
    """Widget shown over the stackedwidget when picking the current list."""

    def __init__(self, new_widget):
        super(OverlayWidget, self).__init__(parent=new_widget)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.old_pixmap = QtGui.QPixmap(new_widget.size())
        self.old_pixmap.fill(common.SEPARATOR)
        self.opacity = 0.0

        self.timeline = QtCore.QTimeLine()
        self.timeline.setDuration(150)

        self.resize(new_widget.size())
        self.show()

    def show(self):
        self.timeline.valueChanged.connect(self.animate_show)
        self.timeline.start()
        super(OverlayWidget, self).show()

    def close(self):
        try:
            self.timeline.valueChanged.disconnect()
        except:
            pass
        self.timeline.valueChanged.connect(self.animate_hide)
        self.timeline.finished.connect(super(OverlayWidget, self).close)
        self.timeline.start()

    @QtCore.Slot(float)
    def animate_show(self, value):
        self.opacity = (0.0 + value) * 0.8
        self.repaint()

    @QtCore.Slot(float)
    def animate_hide(self, value):
        self.opacity = 0.8 - (value * 0.8)
        self.repaint()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setOpacity(self.opacity)
        painter.drawPixmap(0, 0, self.old_pixmap)
        painter.end()


class ListStackWidget(QtWidgets.QStackedWidget):
    """Stacked widget to switch between the Bookmark-, Asset - and File lists."""

    def __init__(self, parent=None):
        super(ListStackWidget, self).__init__(parent=parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )

    def setCurrentIndex(self, idx):
        local_settings.setValue(u'widget/current_index', idx)
        super(ListStackWidget, self).setCurrentIndex(idx)

    def sizeHint(self):
        return QtCore.QSize(common.WIDTH, common.HEIGHT)


class LocationsMenu(BaseContextMenu):
    def __init__(self, parent=None):
        super(LocationsMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_location_toggles_menu()

    @contextmenu
    def add_location_toggles_menu(self, menu_set):
        """Adds the menu needed to change context"""
        locations_icon_pixmap = common.get_rsc_pixmap(
            u'location', common.TEXT_SELECTED, common.INLINE_ICON_SIZE)
        item_on_pixmap = common.get_rsc_pixmap(
            u'item_on', common.TEXT_SELECTED, common.INLINE_ICON_SIZE)

        for k in sorted(list(common.NameFilters)):
            checked = self.parent().model().sourceModel().get_location() == k
            menu_set[k] = {
                u'text': k.title(),
                u'checkable': True,
                u'checked': checked,
                u'icon': item_on_pixmap if checked else QtGui.QPixmap(),
                u'action': functools.partial(self.parent().model().sourceModel().set_location, k)
            }
        return menu_set


class FilterButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(FilterButton, self).__init__(parent=parent)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.clicked.connect(self.action)

    def action(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        filterstring = widget.currentWidget().model().get_filterstring()
        editor = FilterEditor(filterstring, parent=widget)
        editor.finished.connect(
            widget.currentWidget().model().set_filterstring)
        editor.finished.connect(lambda: self.update_(widget.currentIndex()))
        editor.editor.textChanged.connect(
            widget.currentWidget().model().invalidate)
        editor.editor.textChanged.connect(
            widget.currentWidget().model().set_filterstring)
        editor.editor.textChanged.connect(
            lambda s: self.update_(widget.currentIndex()))

        pos = self.rect().center()
        pos = self.mapToGlobal(pos)
        editor.move(
            pos.x() - editor.width() + (self.width() / 2.0),
            pos.y() - (editor.height() / 2.0)
        )
        editor.show()

    def update_(self, idx):
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        if stackwidget.widget(idx).model().get_filterstring() != u'/':
            pixmap = common.get_rsc_pixmap(
                u'filter', common.FAVOURITE, common.INLINE_ICON_SIZE)
        else:
            pixmap = common.get_rsc_pixmap(
                u'filter', common.TEXT, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)


class LocationsButton(QtWidgets.QWidget):
    """Button responsible for switching and displaying the current location of the list widget."""

    def __init__(self, parent=None):
        super(LocationsButton, self).__init__(parent=parent)
        self.icon = None
        self.text = None
        self.setToolTip('Select the asset location to browse')
        self._createUI()

        pixmap = common.get_rsc_pixmap(
            u'location', common.FAVOURITE, common.INLINE_ICON_SIZE)
        self.icon.setPixmap(pixmap)

        self.text.setText(self.location.title())

    @property
    def location(self):
        return self.parent().window().findChild(FilesWidget).model().sourceModel().get_location()

    def mousePressEvent(self, event):
        self.clicked()

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(common.INDICATOR_WIDTH * 3)

        self.icon = ClickableLabel(parent=self)
        self.icon.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.icon.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.layout().addWidget(self.icon)
        self.text = QtWidgets.QLabel()
        self.text.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.layout().addWidget(self.text)

    def setPixmap(self, pixmap):
        self.label.setPixmap(pixmap)

    def clicked(self):
        parent = self.parent().parent().findChild(FilesWidget)
        menu = LocationsMenu(parent=parent)
        # left =
        left = self.parent().mapToGlobal(self.parent().rect().bottomLeft())
        menu.move(left)
        right = self.parent().mapToGlobal(self.parent().rect().bottomRight())
        menu.setFixedWidth((right - left).x())
        overlay = OverlayWidget(
            self.parent().parent().stackedwidget)

        menu.exec_()
        self.text.setText(self.location.title())
        overlay.close()


class CollapseSequenceButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(CollapseSequenceButton, self).__init__(parent=parent)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.clicked.connect(self.toggle)
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        self.clicked.connect(lambda: self.update_(stackwidget.currentIndex()))

    def toggle(self):
        filewidget = self.parent().parent().findChild(FilesWidget)
        grouped = filewidget.model().sourceModel().is_grouped()
        filewidget.model().sourceModel().set_grouped(not grouped)

    def update_(self, idx):
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        if stackwidget.widget(idx).model().sourceModel().is_grouped():
            pixmap = common.get_rsc_pixmap(
                u'collapse', common.FAVOURITE, common.INLINE_ICON_SIZE)
        else:
            pixmap = common.get_rsc_pixmap(
                u'expand', common.TEXT, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)


class ToggleArchivedButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(ToggleArchivedButton, self).__init__(parent=parent)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.clicked.connect(self.toggle)
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        self.clicked.connect(lambda: self.update_(stackwidget.currentIndex()))

    def toggle(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        archived = widget.currentWidget().model().get_filtermode(u'archived')
        widget.currentWidget().model().set_filtermode(u'archived', not archived)

    def update_(self, idx):
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        if stackwidget.widget(idx).model().get_filtermode(u'archived'):
            pixmap = common.get_rsc_pixmap(
                u'active', common.TEXT, common.INLINE_ICON_SIZE)
        else:
            pixmap = common.get_rsc_pixmap(
                u'archived', common.FAVOURITE, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)


class ToggleFavouriteButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(ToggleFavouriteButton, self).__init__(parent=parent)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.clicked.connect(self.toggle)
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        self.clicked.connect(lambda: self.update_(stackwidget.currentIndex()))

    def toggle(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        favourite = widget.currentWidget().model().get_filtermode(u'favourite')
        widget.currentWidget().model().set_filtermode(u'favourite', not favourite)

    def update_(self, idx):
        stackwidget = self.parent().parent().findChild(ListStackWidget)
        if stackwidget.widget(idx).model().get_filtermode(u'favourite'):
            pixmap = common.get_rsc_pixmap(
                u'favourite', common.FAVOURITE, common.INLINE_ICON_SIZE)
        else:
            pixmap = common.get_rsc_pixmap(
                u'favourite', common.TEXT, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)


class CollapseSequenceMenu(BaseContextMenu):
    def __init__(self, parent=None):
        super(CollapseSequenceMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_collapse_sequence_menu()


class AddBookmarkButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(AddBookmarkButton, self).__init__(parent=parent)
        pixmap = common.get_rsc_pixmap(
            u'todo_add', common.TEXT, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )


class SortButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(SortButton, self).__init__(parent=parent)


class ListControlWidget(QtWidgets.QWidget):
    """The bar above the list to control the mode, filters and sorting."""

    modeChanged = QtCore.Signal(int)
    """Mode changed is the main signal emited when the listwidget in view changes."""

    def __init__(self, parent=None):
        super(ListControlWidget, self).__init__(parent=parent)
        self._createUI()
        self._connectSignals()

        idx = local_settings.value(u'widget/current_index')
        idx = idx if idx else 0
        self.modeChanged.emit(idx)

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(common.INDICATOR_WIDTH * 3)
        self.layout().setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(common.ROW_BUTTONS_HEIGHT)

        # Listwidget
        self.layout().addSpacing(common.MARGIN)
        self.layout().addWidget(ChangeListWidget(parent=self))
        self.layout().addWidget(LocationsButton(parent=self))
        self.layout().addStretch(1)
        self.layout().addWidget(AddBookmarkButton(parent=self))
        self.layout().addWidget(FilterButton(parent=self))
        self.layout().addWidget(CollapseSequenceButton(parent=self))
        self.layout().addWidget(ToggleArchivedButton(parent=self))
        self.layout().addWidget(ToggleFavouriteButton(parent=self))
        self.layout().addSpacing(common.MARGIN)

    def _connectSignals(self):
        addbookmarkbutton = self.findChild(AddBookmarkButton)
        combobox = self.findChild(ChangeListWidget)
        bookmarkswidget = self.parent().findChild(BookmarksWidget)

        combobox.currentIndexChanged.connect(self.modeChanged.emit)
        self.modeChanged.connect(self.setCurrentMode)
        self.modeChanged.connect(combobox.setCurrentIndex)
        self.modeChanged.connect(combobox.apply_flags)

        addbookmarkbutton.clicked.connect(
            bookmarkswidget.show_add_bookmark_widget)

    def setCurrentMode(self, idx):
        """Sets the current mode of ``ListControlWidget``."""
        addbookmark = self.findChild(AddBookmarkButton)
        locations = self.findChild(LocationsButton)
        filterbutton = self.findChild(FilterButton)
        collapsesequence = self.findChild(CollapseSequenceButton)
        togglearchived = self.findChild(ToggleArchivedButton)
        togglefavourite = self.findChild(ToggleFavouriteButton)

        if idx == 0:  # Bookmarks
            addbookmark.setHidden(False)
            locations.setHidden(True)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(True)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)
        elif idx == 1:  # Assets
            addbookmark.setHidden(True)
            togglearchived.setHidden(True)
            locations.setHidden(True)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(True)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)
        elif idx == 2:  # Files
            addbookmark.setHidden(True)
            locations.setHidden(False)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(False)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)

        togglearchived.update_(idx)
        filterbutton.update_(idx)
        collapsesequence.update_(idx)
        togglefavourite.update_(idx)


class ChangeListWidgetDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(ChangeListWidgetDelegate, self).__init__(parent=parent)

    def sizeHint(self, option, index):
        return QtCore.QSize(self.parent().parent().width(), common.ROW_BUTTONS_HEIGHT)

    def paint(self, painter, option, index):
        """The main paint method."""
        painter.setRenderHints(
            QtGui.QPainter.TextAntialiasing |
            QtGui.QPainter.Antialiasing |
            QtGui.QPainter.SmoothPixmapTransform,
            on=True
        )
        selected = option.state & QtWidgets.QStyle.State_Selected
        args = (painter, option, index, selected)

        self.paint_background(*args)
        self.paint_name(*args)

    @paintmethod
    def paint_name(self, *args):
        painter, option, index, _ = args
        active = self.parent().currentIndex() == index.row()
        hover = option.state & QtWidgets.QStyle.State_MouseOver

        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(10)

        rect = QtCore.QRect(option.rect)
        rect.setLeft(rect.left() + common.MARGIN)

        color = common.TEXT
        if hover:
            color = common.TEXT_SELECTED
        if index.flags() == QtCore.Qt.NoItemFlags:
            color = common.TEXT_DISABLED
        if active:
            color = common.TEXT

        text = index.data(QtCore.Qt.DisplayRole)
        common.draw_aliased_text(painter, font, rect, text, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, color)


    @paintmethod
    def paint_background(self, *args):
        """Paints the background."""
        painter, option, index, selected = args
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        color = common.BACKGROUND
        if selected:
            color = common.BACKGROUND_SELECTED
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(option.rect)

    @paintmethod
    def paint_thumbnail(self, *args):
        """Paints the thumbnail of the item."""
        painter, option, index, selected = args
        active = self.parent().currentIndex() == index.row()
        hover = option.state & QtWidgets.QStyle.State_MouseOver

        rect = QtCore.QRect(option.rect)
        rect.setWidth(rect.height())

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        color = common.TEXT
        if active:
            color = common.FAVOURITE
        if index.flags() == QtCore.Qt.NoItemFlags:
            color = common.TEXT_DISABLED

        if index.row() == 0:
            pixmap = common.get_rsc_pixmap(u'bookmark', color, rect.height())
        if index.row() == 1:
            pixmap = common.get_rsc_pixmap(u'package', color, rect.height())
        if index.row() == 2:
            pixmap = common.get_rsc_pixmap(u'file', color, rect.height())

        painter.drawPixmap(
            rect,
            pixmap,
            pixmap.rect()
        )


class ChangeListWidget(QtWidgets.QComboBox):
    """Drop-down widget to switch between the list"""

    def __init__(self, parent=None):
        super(ChangeListWidget, self).__init__(parent=parent)
        self.overlay = None

        self.currentTextChanged.connect(self._adjustSize)

        self.setItemDelegate(ChangeListWidgetDelegate(parent=self))
        self.addItem(u'Bookmarks')
        self.addItem(u'Assets')
        self.addItem(u'Files')

        idx = local_settings.value(u'widget/current_index')
        idx = idx if idx else 0
        self.setCurrentIndex(idx)
        self.apply_flags()

    def _adjustSize(self, text):
        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(11)
        metrics = QtGui.QFontMetrics(font)
        width = metrics.width(text)
        self.setFixedWidth(width)

    def apply_flags(self):
        """Sets the item flags based on the set active paths."""
        active_paths = Active.get_active_paths()
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        bookmark = (active_paths[u'server'],
                    active_paths[u'job'], active_paths[u'root'])
        for n in xrange(self.model().rowCount()):
            item = self.model().item(n)
            if n == 1 and not all(bookmark):
                item.setFlags(QtCore.Qt.NoItemFlags)
                continue
            if n == 2 and not active_paths[u'asset']:
                item.setFlags(QtCore.Qt.NoItemFlags)
                continue
            item.setFlags(flags)

    def showPopup(self):
        """Toggling overlay widget when combobox is shown."""

        self.overlay = OverlayWidget(
            self.parent().parent().stackedwidget)
        popup = self.findChild(QtWidgets.QFrame)

        pos = self.parent().mapToGlobal(self.parent().rect().bottomLeft())
        popup.move(pos)
        popup.setFixedWidth(self.parent().rect().width())
        popup.setFixedHeight(self.itemDelegate().sizeHint(
            None, None).height() * self.model().rowCount())
        # Selecting the current item
        index = self.view().model().index(self.currentIndex(), 0)
        self.view().selectionModel().setCurrentIndex(
            index,
            QtCore.QItemSelectionModel.ClearAndSelect
        )

        self.overlay.show()
        popup.show()

    def hidePopup(self):
        """Toggling overlay widget when combobox is shown."""
        if self.overlay:
            self.overlay.close()
        super(ChangeListWidget, self).hidePopup()


class BrowserWidget(QtWidgets.QWidget):
    """Main widget to browse pipline data."""

    def __init__(self, parent=None):
        super(BrowserWidget, self).__init__(parent=parent)
        self.setObjectName(u'BrowserWidget')
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint
        )

        pixmap = common.get_rsc_pixmap(u'custom', None, 64)
        self.setWindowIcon(QtGui.QIcon(pixmap))
        self._contextMenu = None

        self.stackedfaderwidget = None
        self.stackedwidget = None
        self.bookmarkswidget = None
        self.assetswidget = None
        self.fileswidget = None

        # Applying the initial config settings.
        active_paths = Active.get_active_paths()
        self.bookmarkswidget = BookmarksWidget()
        self.assetswidget = AssetWidget((
            active_paths[u'server'],
            active_paths[u'job'],
            active_paths[u'root']
        ))
        self.fileswidget = FilesWidget((
            active_paths[u'server'],
            active_paths[u'job'],
            active_paths[u'root'],
            active_paths[u'asset'])
        )

        # Create layout
        self._createUI()
        self._connectSignals()

        idx = local_settings.value(u'widget/current_index')
        idx = idx if idx else 0
        self.activate_widget(idx)

        # Let's start the monitor
        active_monitor.timer.start()

    def _createUI(self):
        common.set_custom_stylesheet(self)

        # Main layout
        QtWidgets.QVBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Preferred
        )

        self.stackedwidget = ListStackWidget(parent=self)
        self.stackedwidget.addWidget(self.bookmarkswidget)
        self.stackedwidget.addWidget(self.assetswidget)
        self.stackedwidget.addWidget(self.fileswidget)

        self.listcontrolwidget = ListControlWidget(parent=self)

        self.statusbar = QtWidgets.QStatusBar()
        self.statusbar.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.statusbar.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.statusbar.setFixedHeight(common.ROW_BUTTONS_HEIGHT / 2.0)
        self.statusbar.setSizeGripEnabled(True)
        self.statusbar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum
        )

        self.layout().addWidget(self.listcontrolwidget)
        self.layout().addWidget(self.stackedwidget)
        self.layout().addWidget(self.statusbar)

    def _connectSignals(self):
        self.listcontrolwidget.modeChanged.connect(self.activate_widget)
        # Bookmark
        self.bookmarkswidget.model().sourceModel().activeBookmarkChanged.connect(
            self.assetswidget.model().sourceModel().set_bookmark)
        active_monitor.activeBookmarkChanged.connect(
            self.assetswidget.model().sourceModel().set_bookmark)

        combobox = self.listcontrolwidget.findChild(ChangeListWidget)
        filterbutton = self.listcontrolwidget.findChild(FilterButton)
        locationsbutton = self.listcontrolwidget.findChild(LocationsButton)

        # Show bookmarks shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(u'Alt+1'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(0))
        # Show asset shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(u'Alt+2'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(1))
        # Show files shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(u'Alt+3'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(2))
        # Search
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(u'Alt+F'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(filterbutton.clicked)
        # Search
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(u'Alt+L'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(locationsbutton.clicked)

        self.bookmarkswidget.model().sourceModel(
        ).activeBookmarkChanged.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(1))

        active_monitor.activeBookmarkChanged.connect(
            self.bookmarkswidget.refresh)

        # Asset
        # A new asset has been activated and all the data has to be re-initialized
        self.assetswidget.model().sourceModel().activeAssetChanged.connect(
            self.fileswidget.model().sourceModel().set_asset)
        # First, clear the data
        self.assetswidget.model().sourceModel().modelDataResetRequested.connect(
            self.fileswidget.model().sourceModel().modelDataResetRequested.emit)
        # Re-populates the data for the current location
        self.assetswidget.model().sourceModel(
        ).modelDataResetRequested.connect(self.fileswidget.refresh)

        # Shows the FilesWidget
        self.assetswidget.model().sourceModel().activeAssetChanged.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(2))
        # Updates the controls above the list

        active_monitor.activeAssetChanged.connect(self.assetswidget.refresh)
        active_monitor.activeAssetChanged.connect(
            self.fileswidget.model().sourceModel().set_asset)
        active_monitor.activeAssetChanged.connect(
            self.fileswidget.model().sourceModel().__resetdata__)
        active_monitor.activeAssetChanged.connect(self.fileswidget.refresh)

        # Statusbar
        self.bookmarkswidget.entered.connect(self.entered)
        self.assetswidget.entered.connect(self.entered)
        self.fileswidget.entered.connect(self.entered)

        self.fileswidget.model().sourceModel().activeLocationChanged.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(2))
        self.fileswidget.model().sourceModel().grouppingChanged.connect(
            lambda: self.listcontrolwidget.modeChanged.emit(2))

    def entered(self, index):
        """Custom itemEntered signal."""
        message = index.data(QtCore.Qt.StatusTipRole)
        self.statusbar.showMessage(message, timeout=1500)

    def activate_widget(self, idx):
        """Method to change between views."""
        self.stackedfaderwidget = StackFaderWidget(
            self.stackedwidget.currentWidget(),
            self.stackedwidget.widget(idx))
        self.stackedwidget.setCurrentIndex(idx)

    def sizeHint(self):
        return QtCore.QSize(common.WIDTH, common.HEIGHT)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = BrowserWidget()
    widget.show()
    app.exec_()
