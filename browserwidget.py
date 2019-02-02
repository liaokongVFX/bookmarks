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
import collections
from PySide2 import QtWidgets, QtGui, QtCore

import browser.common as common
from browser.baselistwidget import BaseContextMenu
from browser.bookmarkswidget import BookmarksWidget
from browser.assetwidget import AssetWidget
from browser.fileswidget import FilesWidget
from browser.editors import FilterEditor
from browser.editors import ClickableLabel
from browser.settings import local_settings, path_monitor


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
        self.timeline.setDuration(300)

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
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )

    def setCurrentIndex(self, idx):
        local_settings.setValue('widget/current_index', idx)
        super(ListStackWidget, self).setCurrentIndex(idx)

    def sizeHint(self):
        return QtCore.QSize(common.WIDTH, common.HEIGHT)


class LocationsMenu(BaseContextMenu):
    def __init__(self, parent=None):
        super(LocationsMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_location_toggles_menu()

    def add_location_toggles_menu(self):
        """Adds the menu needed to change context"""
        locations_icon_pixmap = common.get_rsc_pixmap(
            'location', common.TEXT_SELECTED, common.INLINE_ICON_SIZE)
        item_on_pixmap = common.get_rsc_pixmap(
            'item_on', common.TEXT_SELECTED, common.INLINE_ICON_SIZE)
        item_off_pixmap = common.get_rsc_pixmap(
            'item_off', common.TEXT_SELECTED, common.INLINE_ICON_SIZE)

        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}

        for k in sorted(list(common.NameFilters)):
            checked = self.parent().model().sourceModel().get_location() == k
            menu_set[k] = {
                'text': k.title(),
                'checkable': True,
                'checked': checked,
                'icon': item_on_pixmap if checked else item_off_pixmap,
                'action': functools.partial(self.parent().model().sourceModel().set_location, k)
            }
        self.create_menu(menu_set)


class FilterButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(FilterButton, self).__init__(parent=parent)
        self.update_()

        self.clicked.connect(self.action)
        self.clicked.connect(self.update_)

    def action(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        filterstring = widget.currentWidget().model().get_filterstring()
        editor = FilterEditor(filterstring, parent=widget)
        editor.finished.connect(
            widget.currentWidget().model().set_filterstring)
        editor.finished.connect(self.update_)
        editor.editor.textChanged.connect(
            widget.currentWidget().model().invalidate)
        editor.editor.textChanged.connect(
            widget.currentWidget().model().set_filterstring)
        editor.show()

    def update_(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        filterstring = widget.currentWidget().model().get_filterstring()
        if filterstring != '/':
            pixmap = common.get_rsc_pixmap(
                'filter', common.FAVOURITE, common.ROW_BUTTONS_HEIGHT / 2)
        else:
            pixmap = common.get_rsc_pixmap(
                'filter', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)


class LocationsButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(LocationsButton, self).__init__(parent=parent)
        pixmap = common.get_rsc_pixmap(
            'location', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)
        self.clicked.connect(self.labelClicked)

    def labelClicked(self):
        parent = self.parent().parent().findChild(FilesWidget)
        menu = LocationsMenu(parent=parent)
        menu.setFixedWidth(120)
        pos = self.mapToGlobal(self.rect().bottomLeft())
        menu.move(pos)
        menu.show()


class CollapseSequenceButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(CollapseSequenceButton, self).__init__(parent=parent)
        self.update_()

        self.clicked.connect(self.toggle)
        self.clicked.connect(self.update_)

    def toggle(self):
        filewidget = self.parent().parent().findChild(FilesWidget)
        grouped = filewidget.model().sourceModel().is_grouped()
        filewidget.model().sourceModel().set_grouped(not grouped)

    def update_(self):
        filewidget = self.parent().parent().findChild(FilesWidget)
        collapsed = filewidget.model().sourceModel().is_grouped()
        if collapsed:
            pixmap = common.get_rsc_pixmap(
                'collapse', common.FAVOURITE, common.ROW_BUTTONS_HEIGHT / 2)
        else:
            pixmap = common.get_rsc_pixmap(
                'expand', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)


class ToggleArchivedButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(ToggleArchivedButton, self).__init__(parent=parent)
        self.update_()
        self.clicked.connect(self.toggle)
        self.clicked.connect(self.update_)

    def toggle(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        archived = widget.currentWidget().model().get_filtermode('archived')
        widget.currentWidget().model().set_filtermode('archived', not archived)

    def update_(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        archived = widget.currentWidget().model().get_filtermode('archived')
        if not archived:
            pixmap = common.get_rsc_pixmap(
                'archived', common.FAVOURITE, common.ROW_BUTTONS_HEIGHT / 2)
        else:
            pixmap = common.get_rsc_pixmap(
                'active', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)


class ToggleFavouriteButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(ToggleFavouriteButton, self).__init__(parent=parent)
        self.update_()
        self.clicked.connect(self.toggle)
        self.clicked.connect(self.update_)

    def toggle(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        favourite = widget.currentWidget().model().get_filtermode('favourite')
        widget.currentWidget().model().set_filtermode('favourite', not favourite)

    def update_(self):
        widget = self.parent().parent().findChild(ListStackWidget)
        favourite = widget.currentWidget().model().get_filtermode('favourite')
        if favourite:
            pixmap = common.get_rsc_pixmap(
                'favourite', common.FAVOURITE, common.ROW_BUTTONS_HEIGHT / 2)
        else:
            pixmap = common.get_rsc_pixmap(
                'favourite', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)


class CollapseSequenceMenu(BaseContextMenu):
    def __init__(self, parent=None):
        super(CollapseSequenceMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_collapse_sequence_menu()


class ModePickButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(ModePickButton, self).__init__(parent=parent)


class AddBookmarkButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(AddBookmarkButton, self).__init__(parent=parent)
        pixmap = common.get_rsc_pixmap(
            'todo_add', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)


class CloseButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(CloseButton, self).__init__(parent=parent)
        pixmap = common.get_rsc_pixmap(
            'close', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)


class MinimizeButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(MinimizeButton, self).__init__(parent=parent)
        pixmap = common.get_rsc_pixmap(
            'minimize', common.TEXT, common.ROW_BUTTONS_HEIGHT / 2)
        self.setPixmap(pixmap)

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)


class SortButton(ClickableLabel):
    """Custom QLabel with a `clicked` signal."""

    def __init__(self, parent=None):
        super(SortButton, self).__init__(parent=parent)


class HeaderWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(HeaderWidget, self).__init__(parent=parent)
        self.label = None
        self.closebutton = None
        self.move_in_progress = False
        self.move_start_event_pos = None
        self.move_start_widget_pos = None

        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._createUI()
        self.itemActivated()

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setPen(QtCore.Qt.NoPen)
        rect = event.rect()
        rect.setTop(rect.bottom())
        painter.setBrush(QtGui.QBrush(common.SEPARATOR))
        painter.drawRect(event.rect())
        painter.end()

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.layout().setAlignment(QtCore.Qt.AlignCenter)

        self.setFixedHeight(common.ROW_BUTTONS_HEIGHT)

        self.label = QtWidgets.QLabel()
        self.label.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        self.label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        self.label.setStyleSheet("""\
        QLabel {
            color: rgba(255,255,255,100);\
            font-family: "Roboto Black";\
            font-size: 8pt;\
        }\
        """)

        label = QtWidgets.QLabel()
        pixmap = common.get_rsc_pixmap(
            'custom', None, common.ROW_BUTTONS_HEIGHT / 2, opacity=0.5)
        label.setPixmap(pixmap)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setFixedHeight(common.ROW_BUTTONS_HEIGHT)
        label.setFixedWidth(common.ROW_BUTTONS_HEIGHT)

        self.layout().addWidget(label)
        self.layout().addWidget(self.label, 1)
        self.layout().addWidget(MinimizeButton())
        self.layout().addWidget(CloseButton())

    def mousePressEvent(self, event):
        self.move_in_progress = True
        self.move_start_event_pos = event.pos()
        self.move_start_widget_pos = self.mapToGlobal(
            self.geometry().topLeft())

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.NoButton:
            return
        if self.move_start_widget_pos:
            offset = (event.pos() - self.move_start_event_pos)
            self.parent().move(self.mapToGlobal(self.geometry().topLeft()) + offset)

    def itemActivated(self, *args, **kwargs):
        """Slot responsible for setting the header text."""
        active_paths = path_monitor.get_active_paths()
        text = 'Bookmark not activated'
        if all((active_paths['server'], active_paths['job'], active_paths['root'])):
            text = '{} | {}'.format(active_paths['job'], active_paths['root'])
        if active_paths['asset']:
            text = '{} | {}'.format(text, active_paths['asset'])
        if active_paths['location']:
            text = '{} | {}'.format(text, active_paths['location'])
        self.label.setText(text.upper())


class ListControlWidget(QtWidgets.QWidget):
    """The bar above the list to control the mode, filters and sorting."""

    modeChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(ListControlWidget, self).__init__(parent=parent)
        self._createUI()
        self._connectSignals()

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.layout().setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(common.ROW_BUTTONS_HEIGHT)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum
        )

        # Mode indicator button
        label = ModePickButton()

        # Listwidget
        self.layout().addWidget(label)  # QComboBox
        self.layout().addWidget(ChangeListWidget(parent=self))
        self.layout().addStretch(1)
        self.layout().addWidget(AddBookmarkButton(parent=self))
        self.layout().addWidget(FilterButton(parent=self))
        self.layout().addWidget(LocationsButton(parent=self))
        self.layout().addWidget(CollapseSequenceButton(parent=self))
        self.layout().addWidget(ToggleArchivedButton(parent=self))
        self.layout().addWidget(ToggleFavouriteButton(parent=self))

        idx = local_settings.value('widget/current_index')
        idx = idx if idx else 0
        self.setCurrentMode(idx)

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(common.SEPARATOR)
        painter.drawRect(event.rect())
        painter.end()

    def _connectSignals(self):
        modepickbutton = self.findChild(ModePickButton)
        addbookmarkbutton = self.findChild(AddBookmarkButton)

        combobox = self.findChild(ChangeListWidget)
        bookmarkswidget = self.parent().findChild(BookmarksWidget)

        filterbutton = self.findChild(FilterButton)
        collapsesequence = self.findChild(CollapseSequenceButton)
        togglearchived = self.findChild(ToggleArchivedButton)
        togglefavourite = self.findChild(ToggleFavouriteButton)

        combobox.currentIndexChanged.connect(self.modeChanged)

        self.modeChanged.connect(self.setCurrentMode)
        self.modeChanged.connect(togglearchived.update_)
        self.modeChanged.connect(filterbutton.update_)
        self.modeChanged.connect(collapsesequence.update_)
        self.modeChanged.connect(togglefavourite.update_)

        modepickbutton.clicked.connect(combobox.showPopup)
        addbookmarkbutton.clicked.connect(
            bookmarkswidget.show_add_bookmark_widget)

    def setCurrentMode(self, idx, *args, **kwargs):
        """Sets the current mode of ``ListControlWidget``."""
        combobox = self.findChild(ChangeListWidget)
        modepick = self.findChild(ModePickButton)
        addbookmark = self.findChild(AddBookmarkButton)
        locations = self.findChild(LocationsButton)
        filterbutton = self.findChild(FilterButton)
        collapsesequence = self.findChild(CollapseSequenceButton)
        togglearchived = self.findChild(ToggleArchivedButton)
        togglefavourite = self.findChild(ToggleFavouriteButton)

        combobox.setCurrentIndex(idx)
        combobox.apply_flags()

        if idx == 0:  # Bookmarks
            pixmap = common.get_rsc_pixmap(
                'bookmarks', common.SECONDARY_TEXT, common.ROW_BUTTONS_HEIGHT / 2)
            addbookmark.setHidden(False)
            locations.setHidden(True)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(True)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)
        elif idx == 1:  # Assets
            pixmap = common.get_rsc_pixmap(
                'assets', common.SECONDARY_TEXT, common.ROW_BUTTONS_HEIGHT / 2)
            addbookmark.setHidden(True)
            togglearchived.setHidden(True)
            locations.setHidden(True)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(True)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)
        elif idx == 2:  # Files
            pixmap = common.get_rsc_pixmap(
                'files', common.SECONDARY_TEXT, common.ROW_BUTTONS_HEIGHT / 2)
            addbookmark.setHidden(True)
            locations.setHidden(False)
            filterbutton.setHidden(False)
            collapsesequence.setHidden(False)
            togglearchived.setHidden(False)
            togglefavourite.setHidden(False)

        modepick.setPixmap(pixmap)
        filterbutton.update_()
        collapsesequence.update_()
        togglearchived.update_()
        togglefavourite.update_()


class ChangeListWidgetDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(ChangeListWidgetDelegate, self).__init__(parent=parent)

    def sizeHint(self, option, index):
        return QtCore.QSize(self.parent().parent().width(), common.ROW_HEIGHT)

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
        self.paint_thumbnail(*args)
        self.paint_name(*args)

    def paint_name(self, *args):
        painter, option, index, _ = args
        active = self.parent().currentIndex() == index.row()
        hover = option.state & QtWidgets.QStyle.State_MouseOver
        disabled = index.flags() == QtCore.Qt.NoItemFlags

        painter.save()

        font = QtGui.QFont('Roboto Black')
        font.setPointSize(9.0)
        font.setBold(True)
        painter.setFont(font)

        rect = QtCore.QRect(option.rect)
        rect.moveLeft(rect.left() + rect.height() + common.MARGIN)
        rect.setRight(rect.width() - (common.MARGIN * 2))

        painter.setPen(QtGui.QPen(common.TEXT))
        if hover:
            painter.setPen(QtGui.QPen(common.TEXT_SELECTED))
        if index.flags() == QtCore.Qt.NoItemFlags:
            painter.setPen(QtGui.QPen(common.TEXT_DISABLED))
        if active:
            painter.setPen(QtGui.QPen(common.FAVOURITE))

        painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))

        text = index.data(QtCore.Qt.DisplayRole)
        if index.row() == 1:
            text = 'Assets (bookmark not activated)' if disabled else text
        elif index.row() == 2:
            text = 'Files (asset not activated)' if disabled else text

        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            text
        )
        painter.restore()

    def paint_background(self, *args):
        """Paints the background."""
        painter, option, index, selected = args
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        color = common.BACKGROUND
        if selected:
            color = common.BACKGROUND_SELECTED
        if index.flags() == QtCore.Qt.NoItemFlags:
            color = common.SECONDARY_BACKGROUND
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(option.rect)

    def paint_thumbnail(self, *args):
        """Paints the thumbnail of the item."""
        painter, option, index, selected = args
        active = self.parent().currentIndex() == index.row()
        hover = option.state & QtWidgets.QStyle.State_MouseOver
        painter.save()

        rect = QtCore.QRect(option.rect)
        rect.setWidth(rect.height())

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))

        # Shadow next to the thumbnail
        shd_rect = QtCore.QRect(option.rect)
        shd_rect.setLeft(rect.left() + rect.width())

        gradient = QtGui.QLinearGradient(
            shd_rect.topLeft(), shd_rect.topRight())
        gradient.setColorAt(0, QtGui.QColor(0, 0, 0, 50))
        gradient.setColorAt(0.2, QtGui.QColor(68, 68, 68, 0))
        painter.setBrush(QtGui.QBrush(gradient))
        painter.drawRect(shd_rect)

        gradient = QtGui.QLinearGradient(
            shd_rect.topLeft(), shd_rect.topRight())
        gradient.setColorAt(0, QtGui.QColor(0, 0, 0, 50))
        gradient.setColorAt(0.02, QtGui.QColor(68, 68, 68, 0))
        painter.setBrush(QtGui.QBrush(gradient))
        painter.drawRect(shd_rect)

        color = common.TEXT
        if active:
            color = common.FAVOURITE
        if index.flags() == QtCore.Qt.NoItemFlags:
            color = common.TEXT_DISABLED

        if index.row() == 0:
            pixmap = common.get_rsc_pixmap('bookmark', color, rect.height())
        if index.row() == 1:
            pixmap = common.get_rsc_pixmap('package', color, rect.height())
        if index.row() == 2:
            pixmap = common.get_rsc_pixmap('file', color, rect.height())

        painter.drawPixmap(
            rect,
            pixmap,
            pixmap.rect()
        )
        painter.restore()


class ChangeListWidget(QtWidgets.QComboBox):
    """Drop-down widget to switch between the list"""

    def __init__(self, parent=None):
        super(ChangeListWidget, self).__init__(parent=parent)
        self.overlay = None

        self.setItemDelegate(ChangeListWidgetDelegate(parent=self))
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        self.addItem('Bookmarks')
        self.addItem('Assets')
        self.addItem('Files')

        idx = local_settings.value('widget/current_index')
        idx = idx if idx else 0
        self.setCurrentIndex(idx)
        self.apply_flags()

    def apply_flags(self):
        """Sets the item flags based on the set active paths."""
        active_paths = path_monitor.get_active_paths()
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        bookmark = (active_paths['server'],
                    active_paths['job'], active_paths['root'])
        for n in xrange(self.model().rowCount()):
            item = self.model().item(n)
            if n == 1 and not all(bookmark):
                item.setFlags(QtCore.Qt.NoItemFlags)
                continue
            if n == 2 and not active_paths['asset']:
                item.setFlags(QtCore.Qt.NoItemFlags)
                continue
            item.setFlags(flags)

    def showPopup(self):
        """Toggling overlay widget when combobox is shown."""

        self.overlay = OverlayWidget(
            self.parent().parent().stackedwidget)
        popup = self.findChild(QtWidgets.QFrame)

        self.setUpdatesEnabled(False)

        pos = self.parent().mapToGlobal(self.parent().rect().bottomLeft())
        popup.move(pos)
        popup.setFixedWidth(self.parent().rect().width())
        popup.setFixedHeight(common.ROW_HEIGHT * 3)
        # Selecting the current item
        index = self.view().model().index(self.currentIndex(), 0)
        self.view().selectionModel().setCurrentIndex(
            index,
            QtCore.QItemSelectionModel.ClearAndSelect
        )

        self.setUpdatesEnabled(True)

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
        self.setObjectName('BrowserWidget')
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint
        )

        pixmap = common.get_rsc_pixmap('custom', None, 64)
        self.setWindowIcon(QtGui.QIcon(pixmap))
        self._contextMenu = None

        self.stackedfaderwidget = None
        self.stackedwidget = None
        self.bookmarkswidget = None
        self.assetswidget = None
        self.fileswidget = None

        # Applying the initial config settings.
        active_paths = path_monitor.get_active_paths()
        self.bookmarkswidget = BookmarksWidget()
        self.assetswidget = AssetWidget((
            active_paths['server'],
            active_paths['job'],
            active_paths['root']
        ))
        self.fileswidget = FilesWidget((
            active_paths['server'],
            active_paths['job'],
            active_paths['root'],
            active_paths['asset'])
        )

        # Create layout
        self._createUI()
        self._connectSignals()

        idx = local_settings.value('widget/current_index')
        idx = idx if idx else 0
        self.activate_widget(idx)

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
        self.headerwidget = HeaderWidget(parent=self)

        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setFixedHeight(common.ROW_BUTTONS_HEIGHT / 2)
        self.status_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum
        )

        self.layout().addWidget(self.headerwidget)
        self.layout().addWidget(self.listcontrolwidget)
        self.layout().addWidget(self.stackedwidget)
        self.layout().addWidget(self.status_bar)

    def _connectSignals(self):
        self.listcontrolwidget.modeChanged.connect(self.activate_widget)

        # Bookmark
        self.bookmarkswidget.activeBookmarkChanged.connect(
            self.assetswidget.model().sourceModel().set_bookmark)

        combobox = self.listcontrolwidget.findChild(ChangeListWidget)
        filterbutton = self.listcontrolwidget.findChild(FilterButton)
        locationsbutton = self.listcontrolwidget.findChild(LocationsButton)

        # Show bookmarks shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Alt+1'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.setCurrentMode(0))
        # Show asset shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Alt+2'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.setCurrentMode(1))
        # Show files shortcut
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Alt+3'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(
            lambda: self.listcontrolwidget.setCurrentMode(2))
        # Search
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Alf+f'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(filterbutton.clicked)
        # Search
        shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence('Alt+l'), self)
        shortcut.setAutoRepeat(False)
        shortcut.setContext(QtCore.Qt.WindowShortcut)
        shortcut.activated.connect(locationsbutton.clicked)

        setCurrentMode = functools.partial(
            self.listcontrolwidget.setCurrentMode, 1)
        self.bookmarkswidget.activeBookmarkChanged.connect(setCurrentMode)
        self.bookmarkswidget.activeBookmarkChanged.connect(
            combobox.apply_flags)
        self.bookmarkswidget.activeBookmarkChanged.connect(
            self.headerwidget.itemActivated)

        # Asset
        setCurrentMode = functools.partial(
            self.listcontrolwidget.setCurrentMode, 2)
        self.assetswidget.activeAssetChanged.connect(
            self.fileswidget.model().sourceModel().set_asset)
        self.assetswidget.activeAssetChanged.connect(setCurrentMode)
        self.assetswidget.activeAssetChanged.connect(combobox.apply_flags)
        self.assetswidget.activeAssetChanged.connect(
            self.headerwidget.itemActivated)

        # Statusbar
        self.bookmarkswidget.entered.connect(self.entered)
        self.assetswidget.entered.connect(self.entered)
        self.fileswidget.entered.connect(self.entered)

        self.fileswidget.model().sourceModel().activeLocationChanged.connect(
            self.headerwidget.itemActivated)

        def func():  # refreshing the listcontrol widget
            self.listcontrolwidget.modeChanged.emit(combobox.currentIndex())
        self.fileswidget.model().sourceModel().activeLocationChanged.connect(func)
        self.fileswidget.model().sourceModel().grouppingChanged.connect(func)

        minimizebutton = self.headerwidget.findChild(MinimizeButton)
        closebutton = self.headerwidget.findChild(CloseButton)
        minimizebutton.clicked.connect(self.showMinimized)
        closebutton.clicked.connect(self.close)

        # Shortcuts

    def entered(self, index):
        """Custom itemEntered signal."""
        message = index.data(QtCore.Qt.StatusTipRole)
        self.status_bar.showMessage(message, timeout=1500)

    def activate_widget(self, idx):
        """Method to change between views."""
        self.stackedfaderwidget = StackFaderWidget(
            self.stackedwidget.currentWidget(),
            self.stackedwidget.widget(idx))
        self.stackedwidget.setCurrentIndex(idx)

    def hideEvent(self, event):
        cls = self.__class__.__name__
        local_settings.setValue('widget/{}/width'.format(cls), self.width())
        local_settings.setValue('widget/{}/height'.format(cls), self.height())

        pos = self.mapToGlobal(self.rect().topLeft())
        local_settings.setValue('widget/{}/x'.format(cls), pos.x())
        local_settings.setValue('widget/{}/y'.format(cls), pos.y())

        super(BrowserWidget, self).hideEvent(event)

    def showEvent(self, event):
        super(BrowserWidget, self).showEvent(event)

        cls = self.__class__.__name__

        width = local_settings.value('widget/{}/width'.format(cls))
        height = local_settings.value('widget/{}/height'.format(cls))
        x = local_settings.value('widget/{}/x'.format(cls))
        y = local_settings.value('widget/{}/y'.format(cls))

        size = QtCore.QSize(width, height)
        pos = QtCore.QPoint(x, y)

        self.resize(size)
        self.move(pos)

    def sizeHint(self):
        return QtCore.QSize(common.WIDTH, common.HEIGHT)
