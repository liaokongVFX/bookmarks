# -*- coding: utf-8 -*-
# pylint: disable=E1101, C0103, R0913, I1101, R0903, C0330

"""Widget reponsible controlling the displayed list and the filter-modes."""

import functools
from PySide2 import QtWidgets, QtGui, QtCore

from browser.settings import Active
import browser.common as common
from browser.delegate import paintmethod
from browser.basecontextmenu import BaseContextMenu, contextmenu
from browser.baselistwidget import StackedWidget
from browser.baselistwidget import BaseModel

from browser.delegate import BaseDelegate
from browser.delegate import paintmethod

from browser.bookmarkswidget import BookmarksWidget
from browser.fileswidget import FilesWidget
from browser.editors import FilterEditor
from browser.editors import ClickableLabel
from browser.imagecache import ImageCache
from browser.settings import local_settings
from browser.settings import AssetSettings


class Progressbar(QtWidgets.QLabel):
    """The widget responsible displaying progress messages."""

    def __init__(self, parent=None):
        super(Progressbar, self).__init__(parent=parent)
        self.processmonitor = QtCore.QTimer()
        self.processmonitor.setSingleShot(False)
        self.processmonitor.setInterval(120)
        self.processmonitor.timeout.connect(self.set_visibility)
        self.processmonitor.start()

        self.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.setStyleSheet("""
            QLabel {{
                font-family: "{}";
                font-size: 8pt;
                color: rgba({});
                background-color: rgba(0,0,0,0);
            	border: 0px solid;
                padding: 0px;
                margin: 0px;
            }}
        """.format(
            common.SecondaryFont.family(),
            u'{},{},{},{}'.format(*common.FAVOURITE.getRgb()))
        )

        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self.setText(u'')
        common.ProgressMessage.instance().messageChanged.connect(
            self.setText, type=QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def set_visibility(self):
        """Sets the progressbar's visibility."""
        if self.text():
            self.show()
        else:
            self.hide()
            common.ProgressMessage.instance().clear_message()


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
            u'icon': ImageCache.get_rsc_pixmap(u'custom', None, common.INLINE_ICON_SIZE),
            u'text': u'Open...',
            u'action': self.parent().clicked.emit
        }
        return menu_set

    @contextmenu
    def add_toolbar_menu(self, menu_set):
        active_paths = Active.paths()
        bookmark = (active_paths[u'server'],
                    active_paths[u'job'], active_paths[u'root'])
        asset = bookmark + (active_paths[u'asset'],)
        location = asset + (active_paths[u'location'],)

        if all(bookmark):
            menu_set[u'bookmark'] = {
                u'icon': ImageCache.get_rsc_pixmap('bookmark', common.TEXT, common.INLINE_ICON_SIZE),
                u'disabled': not all(bookmark),
                u'text': u'Show active bookmark in the file manager...',
                u'action': functools.partial(common.reveal, u'/'.join(bookmark))
            }
            if all(asset):
                menu_set[u'asset'] = {
                    u'icon': ImageCache.get_rsc_pixmap(u'assets', common.TEXT, common.INLINE_ICON_SIZE),
                    u'disabled': not all(asset),
                    u'text': u'Show active asset in the file manager...',
                    u'action': functools.partial(common.reveal, '/'.join(asset))
                }
                if all(location):
                    menu_set[u'location'] = {
                        u'icon': ImageCache.get_rsc_pixmap(u'location', common.TEXT, common.INLINE_ICON_SIZE),
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
        pixmap = ImageCache.get_rsc_pixmap(
            u'custom', None, height)
        self.setPixmap(pixmap)

    def set_size(self, size):
        self.setFixedWidth(int(size))
        self.setFixedHeight(int(size))
        pixmap = ImageCache.get_rsc_pixmap(
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


class CustomButton(BrowserButton):
    def __init__(self, parent=None):
        self.context_menu_cls = BrowserButtonContextMenu
        super(CustomButton, self).__init__(
            height=common.INLINE_ICON_SIZE, parent=parent)
        self.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(r'https://gwbcn.slack.com/'))


class ControlButton(ClickableLabel):

    def __init__(self, parent=None):
        super(ControlButton, self).__init__(parent=parent)
        self._model = None

        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )
        self.clicked.connect(self.action)

    def pixmap(self, c):
        return QtGui.QPixmap(common.INLINE_ICON_SIZE, common.INLINE_ICON_SIZE)

    def model(self):
        return self._model

    def set_model(self, model):
        self._model = None

    def state(self):
        return False

    @QtCore.Slot()
    def action(self):
        return NotImplemented

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        color = common.FAVOURITE if self.state() else common.TEXT
        painter.drawPixmap(self.rect(), self.pixmap(color), self.rect())
        painter.end()


class TodosButton(ControlButton):
    def pixmap(self, c):
        return ImageCache.get_rsc_pixmap(u'todo', c, common.INLINE_ICON_SIZE)


class FilterButton(ControlButton):
    def pixmap(self, c):
        return ImageCache.get_rsc_pixmap(u'filter', c, common.INLINE_ICON_SIZE)


class CollapseSequenceButton(ControlButton):
    def pixmap(self, c):
        return ImageCache.get_rsc_pixmap(u'collapse', c, common.INLINE_ICON_SIZE)

class ToggleArchivedButton(ControlButton):
    """Custom QLabel with a `clicked` signal."""
    def pixmap(self, c):
        return ImageCache.get_rsc_pixmap(u'active', c, common.INLINE_ICON_SIZE)



class ToggleFavouriteButton(ControlButton):
    """Custom QLabel with a `clicked` signal."""
    def pixmap(self, c):
        return ImageCache.get_rsc_pixmap(u'favourite', c, common.INLINE_ICON_SIZE)



class CollapseSequenceMenu(BaseContextMenu):
    def __init__(self, parent=None):
        super(CollapseSequenceMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_collapse_sequence_menu()


class AddBookmarkButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(AddBookmarkButton, self).__init__(parent=parent)
        pixmap = ImageCache.get_rsc_pixmap(
            u'todo_add', common.TEXT, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)
        self.setFixedSize(
            common.INLINE_ICON_SIZE,
            common.INLINE_ICON_SIZE,
        )


class ListControlDelegate(BaseDelegate):
    def __init__(self, parent=None):
        super(ListControlDelegate, self).__init__(parent=parent)

    def paint(self, painter, option, index):
        """The main paint method."""
        args = self._get_paint_args(painter, option, index)
        self.paint_background(*args)
        if index.row() < 2:
            self.paint_thumbnail(*args)
        self.paint_name(*args)

    @paintmethod
    def paint_background(self, *args):
        """Paints the background."""
        painter, option, index, selected, _, _, _, _ = args
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))

        hover = option.state & QtWidgets.QStyle.State_MouseOver
        rect = QtCore.QRect(option.rect)

        if index.row() >= 2:
            color = common.SECONDARY_BACKGROUND
        else:
            color = common.BACKGROUND

        if selected or hover:
            color = common.BACKGROUND_SELECTED

        right_color = QtGui.QColor(color)
        right_color.setAlpha(200)
        gradient = QtGui.QLinearGradient(
            rect.topLeft(), rect.topRight())
        gradient.setColorAt(0.4, color)
        gradient.setColorAt(1, right_color)
        painter.setBrush(QtGui.QBrush(gradient))

        painter.drawRect(rect)

    @paintmethod
    def paint_name(self, *args):
        painter, option, index, _, _, _, _, _ = args

        hover = option.state & QtWidgets.QStyle.State_MouseOver
        color = common.TEXT_SELECTED if hover else common.TEXT

        if index.row() >= 2:
            current_key = index.data(
                QtCore.Qt.DisplayRole) == self.parent().model()._datakey
            color = common.FAVOURITE if current_key else color

        rect = QtCore.QRect(option.rect)
        rect.setLeft(
            common.INDICATOR_WIDTH +
            rect.height()
        )
        rect.setRight(rect.right() - common.MARGIN)
        if not index.data(QtCore.Qt.DisplayRole):
            text = u'Error.'
        else:
            text = index.data(QtCore.Qt.DisplayRole).upper()

        width = 0
        width = common.draw_aliased_text(
            painter, common.PrimaryFont, rect, text, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, color)
        rect.setLeft(rect.left() + width)

        active_item = None
        if index.row() == 0:
            if self.parent().model()._bookmark:
                active_item = self.parent().model()._bookmark[-1]
        if index.row() == 1:
            active_item = self.parent().model()._parent_item[-1]

        if active_item:
            text = u'  ({})'.format(active_item).upper()
            width = common.draw_aliased_text(
                painter, common.PrimaryFont, rect, text, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, common.FAVOURITE)
            rect.setLeft(rect.left() + width)

        if hover:
            text = u'  {}'.format(index.data(QtCore.Qt.StatusTipRole))
            width = common.draw_aliased_text(
                painter, common.SecondaryFont, rect, text, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, common.SECONDARY_TEXT)

    def sizeHint(self, option, index):
        if not index:
            return QtCore.QSize(common.WIDTH, common.BOOKMARK_ROW_HEIGHT / 2)

        if index.row() <= 1:
            return QtCore.QSize(common.WIDTH, common.BOOKMARK_ROW_HEIGHT)
        else:
            return QtCore.QSize(common.WIDTH, common.BOOKMARK_ROW_HEIGHT / 2)


class ListControlView(QtWidgets.QListView):
    listChanged = QtCore.Signal(int)
    dataKeyChanged = QtCore.Signal(unicode)

    def __init__(self, parent=None):
        super(ListControlView, self).__init__(parent=parent)
        common.set_custom_stylesheet(self)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # self.activated.connect(self.close)
        self.clicked.connect(self.activated)
        self.clicked.connect(self.close)
        self.clicked.connect(self.signal_dispatcher)

        self.setModel(ListControlModel())
        self.model().modelReset.connect(self.adjust_size)
        self.setItemDelegate(ListControlDelegate(parent=self))

    @QtCore.Slot(QtCore.QModelIndex)
    def signal_dispatcher(self, index):
        if index.row() < 2:
            self.listChanged.emit(index.row())
        else:
            self.listChanged.emit(2)
            self.dataKeyChanged.emit(index.data(QtCore.Qt.DisplayRole))


    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.hide()
            return
        super(ListControlView, self).keyPressEvent(event)

    @QtCore.Slot()
    def adjust_size(self):
        # Setting the height based on the conents
        height = 0
        for n in xrange(self.model().rowCount()):
            index = self.model().index(n, 0)
            height += index.data(QtCore.Qt.SizeHintRole).height()
        self.setFixedHeight(height)

    def focusOutEvent(self, event):
        """Closes the editor on focus loss."""
        if event.lostFocus():
            self.close()


class ListControlModel(BaseModel):
    """This model holds all the necessary data needed to display items to
    select for selecting the asset subfolders and/or bookmarks and assets.

    The model keeps track of the selections internally and is updated
    via the signals and slots."""

    def __init__(self, parent=None):
        super(ListControlModel, self).__init__(parent=parent)
        self._bookmark = None
        # Note: the asset is stored as `_active_item`
        self._datakey = None

        self.modelDataResetRequested.connect(self.__resetdata__)

    def __initdata__(self):
        """Bookmarks and assets are static. But files will be any number of """
        self._data[self.data_key()] = {
            common.FileItem: {}, common.SequenceItem: {}}

        rowsize = QtCore.QSize(common.WIDTH, common.BOOKMARK_ROW_HEIGHT)
        secondary_rowsize = QtCore.QSize(
            common.WIDTH, common.BOOKMARK_ROW_HEIGHT / 2)

        flags = (
            QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsDropEnabled
            | QtCore.Qt.ItemIsEditable
        )
        data = self.model_data()

        items = (
            (u'Bookmarks', u'Show the list of available bookmarks', lambda c: ImageCache.get_rsc_pixmap(
                'bookmark_sm', c, rowsize.height()).toImage()),
            (u'Assets', u'Show the list of available assets', lambda c: ImageCache.get_rsc_pixmap(
                'assets_sm', c, rowsize.height()).toImage()),
        )

        for item in items:
            data[len(data)] = {
                QtCore.Qt.DisplayRole: item[0],
                QtCore.Qt.EditRole: item[0],
                QtCore.Qt.StatusTipRole: item[1],
                QtCore.Qt.ToolTipRole: item[1],
                QtCore.Qt.SizeHintRole: rowsize,
                #
                common.DefaultThumbnailRole: item[2],
                common.DefaultThumbnailBackgroundRole: QtGui.QColor(0, 0, 0, 0),
                common.ThumbnailRole: item[2](common.TEXT),
                common.ThumbnailBackgroundRole: QtGui.QColor(0, 0, 0, 0),
                #
                common.FlagsRole: flags,
                common.ParentRole: None,
            }
        if not self._parent_item:
            self.endResetModel()
            return

        parent_path = u'/'.join(self._parent_item)
        dir_ = QtCore.QDir(parent_path)
        dir_.setFilter(QtCore.QDir.Dirs | QtCore.QDir.NoDotAndDotDot)

        for entry in sorted(dir_.entryList()):
            description = u'Show files'
            if entry == common.ExportsFolder:
                description = u'Folder for data and cache files'
            if entry == common.ScenesFolder:
                description = u'Folder for storing project and scene files'
            if entry == common.RendersFolder:
                description = u'Folder for storing output images'
            if entry == common.TexturesFolder:
                description = u'Folder for storing texture-files used by scenes'

            data[len(data)] = {
                QtCore.Qt.DisplayRole: entry,
                QtCore.Qt.EditRole: entry,
                QtCore.Qt.StatusTipRole: description,
                QtCore.Qt.ToolTipRole: description,
                QtCore.Qt.SizeHintRole: secondary_rowsize,
                #
                common.FlagsRole: flags,
                common.ParentRole: None,
            }
        self.endResetModel()

    @QtCore.Slot(QtCore.QModelIndex)
    def set_bookmark(self, index):
        """Stores the currently active bookmark."""
        if not index.isValid():
            self._bookmark = None
            return

        self._bookmark = index.data(common.ParentRole)

    @QtCore.Slot(unicode)
    def set_data_key(self, key):
        """Stores the currently active data key."""
        self._datakey = key

    @QtCore.Slot(int)
    def set_data_type(self, datatype):
        """Stores the currently active data type."""
        self._datatype = datatype


class ListControlButton(ClickableLabel):
    """Drop-down widget to switch between the list"""
    textChanged = QtCore.Signal(unicode)

    def __init__(self, parent=None):
        super(ListControlButton, self).__init__(parent=parent)
        self._view = None

        # self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet("""
        QLabel {margin: 0px; padding: 0px}
        """)
        self.setFixedWidth(100)
        self.clicked.connect(self.show_view)

        self.setText('uninitialized')

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        common.draw_aliased_text(
            painter, common.PrimaryFont, self.rect(), self.text(), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, common.TEXT)
        painter.end()

    def set_view(self, widget):
        self._view = widget

    @QtCore.Slot()
    def show_view(self):
        if not self._view:
            return
        pos = self._view.parent().mapToGlobal(self._view.parent().rect().bottomLeft())
        self._view.move(pos)

        self._view.setFixedWidth(self._view.parent().rect().width())
        self._view.show()

    @QtCore.Slot(unicode)
    def set_text(self, text):
        if text is None:
            return
        self.setText(text.title())
        metrics = QtGui.QFontMetrics(common.PrimaryFont)
        width = metrics.width(self.text()) + 2
        # width = width if width > 100 else 100
        # print width
        self.setFixedWidth(width)

    def showPopup(self):
        """Showing view."""


class ListControlWidget(QtWidgets.QWidget):
    """The bar above the list to control the mode, filters and sorting."""

    def __init__(self, parent=None):
        super(ListControlWidget, self).__init__(parent=parent)
        self._controlview = None
        self._controlbutton = None

        self._createUI()
        self._connectSignals()

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(common.INDICATOR_WIDTH * 3)
        self.layout().setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(common.ROW_BUTTONS_HEIGHT)

        # Control view/model/button
        self._controlbutton = ListControlButton(parent=self)
        self._controlview = ListControlView(parent=self)
        self._controlbutton.set_view(self._controlview)

        self.layout().addSpacing(common.MARGIN)
        self.layout().addWidget(self._controlbutton)
        self.layout().addStretch()
        self.layout().addWidget(Progressbar(parent=self), 1)
        self.layout().addWidget(AddBookmarkButton(parent=self))
        self.layout().addWidget(TodosButton(parent=self))
        self.layout().addWidget(FilterButton(parent=self))
        self.layout().addWidget(CollapseSequenceButton(parent=self))
        self.layout().addWidget(ToggleArchivedButton(parent=self))
        self.layout().addWidget(ToggleFavouriteButton(parent=self))
        self.layout().addWidget(CustomButton(parent=self))
        self.layout().addSpacing(common.MARGIN)



    def _connectSignals(self):
        pass

    def control_view(self):
        return self._controlview

    def control_button(self):
        return self.findChild(ListControlButton)
