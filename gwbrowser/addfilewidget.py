# -*- coding: utf-8 -*-
"""This module defines. *GWBrowser*'s custom saver widget.

We're using the ``BookmarksWidget`` and ``AssetsWidget`` respectively, including
the associated models, to set the destination of the saved file.

We can use the widget to generate a new filename, or if the **currentfile**
argument is defined we can increment the given file's sequence element. The
saver will then try to factor in the given files current location and version
number - this will be incremented by +1.

Note:
    The widget itself will only return a filepath and is not performing any file
    operations. It is up to the context to connect to the ``fileSaveRequested``,
    ``fileThumbnailAdded`` and ``fileDescriptionAdded`` signals.

"""


import re
import sys
import uuid
import functools
import collections
import logging
from PySide2 import QtCore, QtWidgets, QtGui

import gwbrowser.common as common
from gwbrowser.editors import ClickableLabel
from gwbrowser.basecontextmenu import BaseContextMenu, contextmenu
from gwbrowser.standalonewidgets import HeaderWidget, CloseButton, MinimizeButton
from gwbrowser.capture import ScreenGrabber
from gwbrowser.imagecache import ImageCache
from gwbrowser.imagecache import ImageCacheWorker
from gwbrowser.addfilewidgetwidgets import SelectBookmarkButton
from gwbrowser.addfilewidgetwidgets import SelectBookmarkView
from gwbrowser.addfilewidgetwidgets import SelectAssetButton
from gwbrowser.addfilewidgetwidgets import SelectAssetView
from gwbrowser.addfilewidgetwidgets import SelectFolderButton
from gwbrowser.addfilewidgetwidgets import SelectFolderView
from gwbrowser.addfilewidgetwidgets import SelectFolderModel
import gwbrowser.editors as editors


log = logging.getLogger(__name__)


class ThumbnailContextMenu(BaseContextMenu):
    """Context menu associated with the thumbnail."""

    def __init__(self, parent=None):
        super(ThumbnailContextMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_thumbnail_menu()

    @contextmenu
    def add_thumbnail_menu(self, menu_set):
        """Menu for thumbnail operations."""
        capture_thumbnail_pixmap = ImageCache.get_rsc_pixmap(
            u'capture_thumbnail', common.SECONDARY_TEXT, common.INLINE_ICON_SIZE)
        pick_thumbnail_pixmap = ImageCache.get_rsc_pixmap(
            u'pick_thumbnail', common.SECONDARY_TEXT, common.INLINE_ICON_SIZE)
        remove_thumbnail_pixmap = ImageCache.get_rsc_pixmap(
            u'remove', common.FAVOURITE, common.INLINE_ICON_SIZE)

        menu_set[u'Capture thumbnail'] = {
            u'icon': capture_thumbnail_pixmap,
            u'action': self.parent().capture_thumbnail
        }
        menu_set['Add from library...'] = {
            u'text': 'Add from library...',
            u'icon': pick_thumbnail_pixmap,
            u'action': self.parent().show_thumbnail_picker
        }
        menu_set[u'Pick thumbnail'] = {
            u'icon': pick_thumbnail_pixmap,
            u'action': self.parent().pick_thumbnail
        }
        menu_set[u'separator'] = {}
        menu_set[u'Reset thumbnail'] = {
            u'icon': remove_thumbnail_pixmap,
            u'action': self.parent().reset_thumbnail
        }
        return menu_set


class SaverContextMenu(BaseContextMenu):
    """Context menu associated with the thumbnail."""

    def __init__(self, parent=None):
        super(SaverContextMenu, self).__init__(
            QtCore.QModelIndex(), parent=parent)
        self.add_fileformat_menu()

    @contextmenu
    def add_fileformat_menu(self, menu_set):
        """Menu for thumbnail operations."""
        menu_set[u'Change file-type'] = {
            u'text': u'Select file-type to save',
            u'disabled': True,
        }

        # Parent
        buttons = self.parent().window().findChildren(SelectFolderButton)
        foldersbutton = [f for f in buttons if f.objectName()
                         == u'SelectFolderButton'][-1]
        f = foldersbutton.view()

        key = u'Image formats'
        menu_set[key] = collections.OrderedDict()
        for ext in sorted(common.oiio_formats):
            menu_set[key][ext] = {
                u'action': functools.partial(f.model().fileTypeChanged.emit, ext)
            }
        menu_set[u'separator0'] = {}

        key = u'Cache formats'
        menu_set[key] = collections.OrderedDict()
        for ext in sorted(common.exports_formats):
            menu_set[key][ext] = {
                u'action': functools.partial(f.model().fileTypeChanged.emit, ext)
            }
        menu_set[u'separator1'] = {}

        key = u'Adobe Creative Cloud formats'
        menu_set[key] = collections.OrderedDict()
        for ext in sorted(common.creative_cloud_formats):
            menu_set[key][ext] = {
                u'action': functools.partial(f.model().fileTypeChanged.emit, ext)
            }
        menu_set[u'separator2'] = {}

        key = u'3D project formats'
        menu_set[key] = collections.OrderedDict()
        for ext in sorted(common.scene_formats):
            menu_set[key][ext] = {
                u'action': functools.partial(f.model().fileTypeChanged.emit, ext)
            }
        return menu_set


class ThumbnailButton(ClickableLabel):
    """Button used to select the thumbnail for this item."""
    doubleClicked = QtCore.Signal()

    def __init__(self, parent=None):
        super(ThumbnailButton, self).__init__(parent=parent)
        self.image = QtGui.QImage()

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self.reset_thumbnail()

    def enterEvent(self, event):
        self.repaint()

    def leaveEvent(self, event):
        self.repaint()

    def paintEvent(self, event):
        """Custom paint event."""
        painter = QtGui.QPainter()
        painter.begin(self)

        option = QtWidgets.QStyleOptionButton()
        option.initFrom(self)
        hover = option.state & QtWidgets.QStyle.State_MouseOver
        if hover:
            painter.setOpacity(1.0)
        else:
            painter.setOpacity(0.666)

        rect = self.pixmap().rect()
        rect.moveCenter(self.rect().center())
        painter.drawPixmap(rect, self.pixmap(), self.pixmap().rect())

        painter.end()

    def contextMenuEvent(self, event):
        menu = ThumbnailContextMenu(parent=self)
        pos = self.rect().center()
        pos = self.mapToGlobal(pos)
        menu.move(pos)
        menu.exec_()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()

    def reset_thumbnail(self):
        pixmap = ImageCache.get_rsc_pixmap(
            u'pick_thumbnail', common.FAVOURITE, common.ROW_HEIGHT)
        self.setPixmap(pixmap)
        self.setStyleSheet(
            u'background-color: rgba({});'.format(u'{}/{}/{}/{}'.format(*common.BACKGROUND.getRgb())))

        self.image = QtGui.QImage()

    def show_thumbnail_picker(self):
        """Shows the dialog used to select a thumbnail from the library."""

        @QtCore.Slot(unicode)
        def add_thumbnail_from_library(path):
            image = QtGui.QImage()
            if not image.load(path):
                return

            self.image = image
            self.update_thumbnail_preview()

        rect = QtWidgets.QApplication.instance().desktop().screenGeometry(self)
        widget = editors.ThumbnailsWidget(parent=self.parent())
        widget.thumbnailSelected.connect(add_thumbnail_from_library)
        widget.show()
        widget.setFocus(QtCore.Qt.PopupFocusReason)

        wpos = QtCore.QPoint(widget.width() / 2.0, widget.height() / 2.0)
        widget.move(rect.center() - wpos)
        common.move_widget_to_available_geo(widget)

    def pick_thumbnail(self):
        """Prompt to select an image file."""
        dialog = QtWidgets.QFileDialog(parent=self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setViewMode(QtWidgets.QFileDialog.List)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
        dialog.setNameFilter(common.get_oiio_namefilters())

        # Setting the dialog's root path
        dialog.setOption(
            QtWidgets.QFileDialog.DontUseCustomDirectoryIcons, True)

        if not dialog.exec_():
            return
        if not dialog.selectedFiles():
            return

        temp_path = u'{}/browser_temp_thumbnail_{}.png'.format(
            QtCore.QDir.tempPath(), uuid.uuid1())

        ImageCacheWorker.process_index(
            QtCore.QModelIndex(),
            source=next(f for f in dialog.selectedFiles()),
            dest=temp_path
        )

        image = QtGui.QImage()
        image.load(temp_path)
        if image.isNull():
            return

        self.image = image
        self.update_thumbnail_preview()

    def capture_thumbnail(self):
        """Captures a thumbnail."""
        pixmap = ScreenGrabber.capture()

        if not pixmap:
            return
        if pixmap.isNull():
            return

        image = ImageCache.resize_image(
            pixmap.toImage(), common.THUMBNAIL_IMAGE_SIZE)
        self.image = image
        self.update_thumbnail_preview()

    def update_thumbnail_preview(self):
        """Sets the label's pixmap to the currently set thumbnail image."""
        if not self.image:
            return
        if self.image.isNull():
            return

        # Resizing for display
        image = ImageCache.resize_image(
            self.image, self.height())

        pixmap = QtGui.QPixmap()
        pixmap.convertFromImage(image)
        background = ImageCache.get_color_average(image)

        self.setPixmap(pixmap)
        self.setStyleSheet("""QLabel {{background-color: rgba({});}}""".format(
            u'{},{},{},{}'.format(*background.getRgb())
        ))


class SaverHeaderWidget(HeaderWidget):
    def __init__(self, parent=None):
        super(SaverHeaderWidget, self).__init__(parent=parent)

    def paintEvent(self, event):
        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setPen(QtCore.Qt.NoPen)
        rect = event.rect()
        rect.setTop(rect.bottom())
        painter.setBrush(QtGui.QBrush(common.BACKGROUND))
        painter.drawRect(event.rect())
        painter.end()


class SaverFileInfo(QtCore.QObject):
    """A QFileInfo-like QObject responsible for getting the currently set file-path
    components.

    Methods:
        fileInfo():     QFileInfo instance with the current path choice.
        path():         The path of the current choice without the filename.
        fileName():     The filename without the path.

    """

    def __init__(self, parent):
        super(SaverFileInfo, self).__init__(parent=parent)

    def _new(self):
        """Creates a new filename based on the currently set properties."""
        job = None
        asset = None

        buttons = self.parent().window().findChildren(SelectFolderButton)
        assetbutton = [f for f in buttons if f.objectName() ==
                       u'SelectAssetButton'][-1]
        a = assetbutton.view()

        index = a.model().sourceModel().active_index()
        if index.isValid():
            job = index.data(common.ParentRole)[1]
            asset = index.data(common.ParentRole)[-1]

        custom = self.parent().window().findChild(Custom).text()
        regex = re.compile(r'[^0-9a-z]+', flags=re.IGNORECASE)
        job = regex.sub(u'', job)[
            :3] if job else u'gw'

        asset = regex.sub(u'', asset)[
            :12] if asset else u'sandbox'

        custom = custom if custom else u'untitled'
        custom = regex.sub(u'-', custom)[:25]

        version = u'001'

        user = next(f for f in QtCore.QStandardPaths.standardLocations(
            QtCore.QStandardPaths.HomeLocation))
        user = QtCore.QFileInfo(user).fileName()
        user = regex.sub(u'', user)
        # Numbers are not allowed in the username
        user = re.sub(r'[0-9]+', u'', user)

        return '{job}_{asset}_{custom}_{version}_{user}.{ext}'.format(
            job=job,
            asset=asset,
            custom=custom,
            version=version,
            user=user,
            ext=self.parent().window().extension,
        )

    def _increment_sequence(self, currentfile):
        """Increments the version of the current file by 1."""
        file_info = QtCore.QFileInfo(currentfile)
        match = common.get_sequence(file_info.fileName())

        if not match:
            return currentfile

        n = match.group(2)
        version = u'{}'.format(int(n) + 1).zfill(len(n))
        return match.expand(ur'\1{}\3.\4').format(version)

    def fileInfo(self):
        """Returns the path as a QFileInfo instance"""
        return QtCore.QFileInfo(u'{}/{}'.format(self.path(), self.fileName()))

    def path(self):
        """Returns the path() element of the set path."""
        buttons = self.parent().window().findChildren(SelectFolderButton)
        foldersbutton = [f for f in buttons if f.objectName()
                         == u'SelectFolderButton'][-1]
        return foldersbutton.view().model().destination()

    def fileName(self, style=common.LowerCase):
        """The main method to get the new file's filename."""
        currentfile = self.parent().window().currentfile

        if currentfile:
            match = common.get_valid_filename(currentfile)
            if match:
                n = match.group(4)
                filename = match.expand(ur'\1_\2_{}_{}_\5.\6')
                filename = filename.format(
                    match.group(3),
                    u'{}'.format(int(n) + 1).zfill(len(n))
                )
            else:
                filename = self._increment_sequence(currentfile)
        else:
            filename = self._new()

        if style == common.LowerCase:
            filename = filename.lower()
        elif style == common.UpperCase:
            filename = filename.upper()
        return filename


class DescriptionEditor(QtWidgets.QLineEdit):
    """Editor widget to input the description of the file."""

    def __init__(self, parent=None):
        super(DescriptionEditor, self).__init__(parent=parent)
        self.setPlaceholderText(u'Enter description...')
        self.setStyleSheet("""QLineEdit {{
            background-color: rgba(0,0,0,0);
            border-bottom: 2px solid rgba(0,0,0,50);
            padding: 0px;
            margin: 0px;
            color: rgba({});
            font-family: "{}";
            font-size: {}pt;
        }}""".format(
            '{},{},{},{}'.format(*common.TEXT_SELECTED.getRgb()),
            common.PrimaryFont.family(),
            common.psize(common.MEDIUM_FONT_SIZE)
        ))
        self.setFixedHeight(36)


class NameEditor(QtWidgets.QLineEdit):
    """Editor widget to input the description of the file."""

    def __init__(self, parent=None):
        super(NameEditor, self).__init__(parent=parent)
        self.setPlaceholderText(u'Enter name')
        self.setStyleSheet("""QLineEdit {{
            background-color: rgba(0,0,0,0);
            border-bottom: 2px solid rgba(0,0,0,50);
            padding: 0px;
            margin: 0px;
            color: rgba({});
            font-family: "{}";
            font-size: {}pt;
        }}""".format(
            '{},{},{},{}'.format(*common.TEXT_SELECTED.getRgb()),
            common.PrimaryFont.family(),
            common.psize(common.LARGE_FONT_SIZE)
        ))
        self.setFixedHeight(36)


class BaseNameLabel(QtWidgets.QLabel):
    """Baselabel to display the current filename."""

    def __init__(self, parent=None):
        super(BaseNameLabel, self).__init__(parent=parent)
        self.setTextFormat(QtCore.Qt.RichText)
        self.setOpenExternalLinks(False)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

        self.setStyleSheet(
            """QLabel{{
                background-color: rgba(0,0,0,0);
                font-family: "{}";
                font-size: {}pt;
            }}""".format(
                common.PrimaryFont.family(),
                common.psize(common.MEDIUM_FONT_SIZE)
            )
        )


class Prefix(BaseNameLabel):
    """Displays the first parth of the filename."""

    def __init__(self, parent=None):
        super(Prefix, self).__init__(parent=parent)
        self.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)


class Custom(QtWidgets.QLineEdit):
    """Widget for editing the custom filename component."""

    def __init__(self, parent=None):
        super(Custom, self).__init__(parent=parent)
        self.setAlignment(QtCore.Qt.AlignCenter)

        self.setMaxLength(25)
        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(common.LARGE_FONT_SIZE)
        metrics = QtGui.QFontMetrics(font)

        self.setPlaceholderText('untitled')
        self.setStyleSheet("""QLineEdit{{
            background-color: rgba(0,0,0,0);
            border-bottom: 2px solid rgba(255,255,255,255);
            padding: 0px;
            margin: 0px;
            color: rgba({});
            font-family: "{}";
            font-size: {}pt;
        }}""".format(
            '{},{},{},{}'.format(*common.TEXT_SELECTED.getRgb()),
            common.PrimaryFont.family(),
            common.psize(common.MEDIUM_FONT_SIZE)
        ))

        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(common.LARGE_FONT_SIZE)
        metrics = QtGui.QFontMetrics(font)
        self.setFixedWidth(metrics.width('untitled'))

        self.textChanged.connect(self.resizeLineEditToContents)
        self.textChanged.connect(self.verify)

    def verify(self, text):
        cpos = self.cursorPosition()
        text = re.sub(r'[^a-z0-9\-]+', '-', text, flags=re.IGNORECASE)
        text = re.sub(r'-{2,}', '-', text, flags=re.IGNORECASE)
        self.setText(text)
        self.setCursorPosition(cpos)

    def resizeLineEditToContents(self, text):
        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(common.LARGE_FONT_SIZE)
        metrics = QtGui.QFontMetrics(font)
        width = metrics.width(text)
        minwidth = metrics.width('untitled')
        width = minwidth if width < minwidth else width
        self.setFixedSize(width, self.height())


class Suffix(BaseNameLabel):
    """Label containing the end of the filename string."""

    def __init__(self, parent=None):
        super(Suffix, self).__init__(parent=parent)
        self.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)


class Check(ClickableLabel):
    """The checkbox button."""

    def __init__(self, parent=None):
        super(Check, self).__init__(parent=parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedSize(common.ASSET_ROW_HEIGHT, common.ASSET_ROW_HEIGHT)
        pixmap = ImageCache.get_rsc_pixmap(
            'check', common.FAVOURITE, common.ROW_HEIGHT / 1.5)
        self.setPixmap(pixmap)
        self.setStyleSheet("""
            QLabel {{background-color: rgba({});}}
        """.format(u'{}/{}/{}/{}'.format(*common.BACKGROUND.getRgb())))

    def paintEvent(self, event):
        """Custom paint event."""
        painter = QtGui.QPainter()
        painter.begin(self)

        option = QtWidgets.QStyleOptionButton()
        option.initFrom(self)
        hover = option.state & QtWidgets.QStyle.State_MouseOver
        if hover:
            painter.setOpacity(1.0)
        else:
            painter.setOpacity(0.666)

        rect = self.pixmap().rect()
        rect.moveCenter(self.rect().center())
        painter.drawPixmap(rect, self.pixmap(), self.pixmap().rect())

        painter.end()

    def enterEvent(self, event):
        self.repaint()

    def leaveEvent(self, event):
        self.repaint()


class AddFileWidget(QtWidgets.QDialog):
    """The dialog used to save a file. It contains the header and the saver widgets
    needed to select the desired path.

    When ``done()`` is called, the widget will emit the ``fileSaveRequested``,
    ``fileDescriptionAdded`` and ``fileThumbnailAdded`` signals.

    """

    # Signals
    fileSaveRequested = QtCore.Signal(basestring)
    fileDescriptionAdded = QtCore.Signal(tuple)
    fileThumbnailAdded = QtCore.Signal(tuple)

    def __init__(self, bookmark_model, asset_model, extension, currentfile=None, parent=None):
        super(AddFileWidget, self).__init__(parent=parent)
        self.extension = extension
        self.currentfile = currentfile

        self.description_editor_widget = None
        self.thumbnail_widget = None

        self.select_bookmark_button = None
        self.select_asset_button = None
        self.select_folder_button = None

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowFlags(
            QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self._createUI(bookmark_model, asset_model)
        self._connectSignals()
        self.initialize()

    @property
    def image(self):
        """Shortcut to the saved image"""
        return self.thumbnail_widget.image

    @QtCore.Slot(unicode)
    def set_extension(self, ext):
        self.extension = ext

    def contextMenuEvent(self, event):
        menu = SaverContextMenu(parent=self)
        pos = self.rect().center()
        pos = self.mapToGlobal(pos)
        menu.move(pos)
        menu.exec_()

    def _createUI(self, bookmark_model, asset_model):
        """Creates the ``AddFileWidget``'s ui and layout."""
        common.set_custom_stylesheet(self)
        #
        QtWidgets.QVBoxLayout(self)
        self.layout().setContentsMargins(
            common.MARGIN / 2, common.MARGIN / 2,
            common.MARGIN / 2, common.MARGIN / 2)
        self.layout().setSpacing(0)
        self.layout().setAlignment(QtCore.Qt.AlignCenter)
        #
        self.setFixedWidth(common.WIDTH * 1.5)
        #
        mainrow = QtWidgets.QWidget()
        QtWidgets.QHBoxLayout(mainrow)
        mainrow.layout().setContentsMargins(0, 0, 0, 0)
        mainrow.layout().setSpacing(common.INDICATOR_WIDTH)
        mainrow.layout().setAlignment(QtCore.Qt.AlignCenter)
        #
        self.thumbnail_widget = ThumbnailButton(parent=self)
        self.thumbnail_widget.setFixedSize(
            common.ASSET_ROW_HEIGHT, common.ASSET_ROW_HEIGHT)
        mainrow.layout().addWidget(self.thumbnail_widget)
        self.layout().addWidget(mainrow)
        #
        column = QtWidgets.QWidget()
        QtWidgets.QVBoxLayout(column)
        column.layout().setContentsMargins(0, 0, 0, 0)
        column.layout().setSpacing(0)
        column.layout().setAlignment(QtCore.Qt.AlignCenter)
        mainrow.layout().addWidget(column)

        # Row 1
        row = QtWidgets.QWidget()
        QtWidgets.QHBoxLayout(row)
        row.layout().setContentsMargins(0, 0, 0, 0)
        row.layout().setSpacing(common.INDICATOR_WIDTH)
        row.layout().setAlignment(QtCore.Qt.AlignCenter)
        column.layout().addWidget(row, 1)

        self.description_editor_widget = DescriptionEditor(parent=self)
        row.layout().addWidget(self.description_editor_widget, 1)

        # Bookmark
        view = SelectBookmarkView(parent=self)
        view.set_model(bookmark_model)
        self.select_bookmark_button = SelectBookmarkButton(parent=self)
        self.select_bookmark_button.set_view(view)
        row.layout().addWidget(self.select_bookmark_button)

        # Asset
        view = SelectAssetView(parent=self)
        view.set_model(asset_model)
        self.select_asset_button = SelectAssetButton(parent=self)
        self.select_asset_button.set_view(view)
        row.layout().addWidget(self.select_asset_button)

        # Folders
        view = SelectFolderView(parent=self)
        view.set_model(SelectFolderModel())
        self.select_folder_button = SelectFolderButton(parent=self)
        self.select_folder_button.set_view(view)
        row.layout().addWidget(self.select_folder_button)

        row = QtWidgets.QWidget()
        QtWidgets.QHBoxLayout(row)
        row.layout().setContentsMargins(0, 0, 0, 0)
        row.layout().setSpacing(0)
        row.layout().setAlignment(QtCore.Qt.AlignCenter)
        row.layout().addWidget(Prefix(parent=self))
        row.layout().addWidget(Custom(parent=self))
        row.layout().addWidget(Suffix(parent=self), 1)
        column.layout().addWidget(row, 1)

        mainrow.layout().addWidget(Check(parent=self))
        self.layout().insertWidget(0, SaverHeaderWidget(parent=self))

        minimizebutton = self.findChild(MinimizeButton)
        minimizebutton.setHidden(True)

        # Statusbar
        statusbar = QtWidgets.QStatusBar(parent=self)
        statusbar.setFixedHeight(common.ROW_BUTTONS_HEIGHT)
        statusbar.setSizeGripEnabled(False)
        statusbar.layout().setAlignment(QtCore.Qt.AlignRight)
        statusbar.setStyleSheet("""QStatusBar {{
            background-color: rgba(0,0,0,0);
            color: rgba({color});
            font-family: "{family}";
            font-size: {size}pt;
        }}""".format(
            color='{},{},{},{}'.format(*common.SECONDARY_TEXT.getRgb()),
            family=common.PrimaryFont.family(),
            size=common.psize(common.SMALL_FONT_SIZE)
        ))

        statusbar.layout().setContentsMargins(20, 20, 20, 20)

        statusbar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Minimum
        )

        self.layout().addSpacing(common.MARGIN)
        self.layout().addWidget(statusbar, 1)

    def _connectSignals(self):
        b = self.select_bookmark_button.view()
        a = self.select_asset_button.view()
        f = self.select_folder_button.view()

        b.widgetShown.connect(a.hide)
        b.widgetShown.connect(f.hide)

        a.widgetShown.connect(b.hide)
        a.widgetShown.connect(f.hide)

        f.widgetShown.connect(a.hide)
        f.widgetShown.connect(b.hide)

        header = self.findChild(SaverHeaderWidget)
        header.widgetMoved.connect(b.move)
        header.widgetMoved.connect(a.move)
        header.widgetMoved.connect(f.move)

        # Signal/slot connections for the primary bookmark/asset and filemodels
        b.model().sourceModel().modelReset.connect(
            lambda: a.model().sourceModel().set_active(b.model().sourceModel().active_index()))
        b.model().sourceModel().modelReset.connect(
            a.model().sourceModel().modelDataResetRequested)
        b.model().sourceModel().activeChanged.connect(
            a.model().sourceModel().set_active)
        b.model().sourceModel().activeChanged.connect(
            lambda x: a.model().sourceModel().modelDataResetRequested.emit())

        a.model().sourceModel().activeChanged.connect(f.set_root_index)
        a.model().sourceModel().activeChanged.connect(
            lambda i: f.model().fileTypeChanged.emit(self.extension))

        b.model().sourceModel().activeChanged.connect(
            lambda i: self.update_filename_display())
        b.model().sourceModel().activeChanged.connect(
            lambda i: self.update_filepath_display())
        a.model().sourceModel().activeChanged.connect(
            lambda i: self.update_filename_display())
        a.model().sourceModel().activeChanged.connect(
            lambda i: self.update_filepath_display())

        b.model().sourceModel().modelReset.connect(self.update_filename_display)
        b.model().sourceModel().modelReset.connect(self.update_filepath_display)
        a.model().sourceModel().modelReset.connect(self.update_filename_display)
        a.model().sourceModel().modelReset.connect(self.update_filepath_display)
        f.model().modelReset.connect(self.update_filename_display)
        f.model().modelReset.connect(self.update_filepath_display)

        closebutton = self.findChild(CloseButton)
        custom = self.findChild(Custom)
        check = self.findChild(Check)

        check.clicked.connect(lambda: self.done(
            QtWidgets.QDialog.Accepted), type=QtCore.Qt.QueuedConnection)
        closebutton.clicked.connect(
            lambda: self.done(QtWidgets.QDialog.Rejected), type=QtCore.Qt.QueuedConnection)
        # Picks a thumbnail
        self.thumbnail_widget.clicked.connect(
            self.thumbnail_widget.pick_thumbnail, type=QtCore.Qt.QueuedConnection)

        # Filename
        b.activated.connect(self.update_filename_display)
        a.activated.connect(self.update_filename_display)
        f.activated.connect(self.update_filename_display)

        f.model().fileTypeChanged.connect(self.set_extension)
        f.model().fileTypeChanged.connect(f.model().set_filetype)
        f.model().fileTypeChanged.connect(lambda x: self.update_filepath_display())
        f.model().fileTypeChanged.connect(lambda x: self.update_filename_display())

        f.model().destinationChanged.connect(f.model().set_destination)
        f.model().destinationChanged.connect(lambda x: self.update_filepath_display())
        f.model().destinationChanged.connect(lambda x: self.update_filename_display())

        custom.textChanged.connect(self.update_filepath_display)
        custom.textChanged.connect(self.update_filename_display)

        # Filepath
        b.activated.connect(self.update_filepath_display)
        a.activated.connect(self.update_filepath_display)
        f.activated.connect(self.update_filepath_display)

        b.activated.connect(self.update_filename_display)
        a.activated.connect(self.update_filename_display)
        f.activated.connect(self.update_filename_display)

    def initialize(self):
        """Checks the models' active items and sets the ui elements accordingly."""
        buttons = self.findChildren(SelectFolderButton)
        bookmarkbutton = [
            f for f in buttons if f.objectName() == u'SelectBookmarkButton'][-1]
        assetbutton = [f for f in buttons if f.objectName() ==
                       u'SelectAssetButton'][-1]
        foldersbutton = [f for f in buttons if f.objectName()
                         == u'SelectFolderButton'][-1]

        b = bookmarkbutton.view()
        a = assetbutton.view()
        f = foldersbutton.view()

        b.model().filterTextChanged.emit(b.model().filterText())
        a.model().filterTextChanged.emit(a.model().filterText())
        #
        b.model().filterFlagChanged.emit(common.MarkedAsActive,
                                         b.model().filterFlag(common.MarkedAsActive))
        b.model().filterFlagChanged.emit(common.MarkedAsArchived,
                                         b.model().filterFlag(common.MarkedAsArchived))
        b.model().filterFlagChanged.emit(common.MarkedAsFavourite,
                                         b.model().filterFlag(common.MarkedAsFavourite))
        #
        a.model().filterFlagChanged.emit(common.MarkedAsActive,
                                         a.model().filterFlag(common.MarkedAsActive))
        a.model().filterFlagChanged.emit(common.MarkedAsArchived,
                                         a.model().filterFlag(common.MarkedAsArchived))
        a.model().filterFlagChanged.emit(common.MarkedAsFavourite,
                                         a.model().filterFlag(common.MarkedAsFavourite))

        bookmarkbutton.view().model().sourceModel().modelDataResetRequested.emit()

        if self.currentfile:
            # We will check if the previous version had any description or
            # thumbnail added. We will add them here if so
            if self.parent():
                index = self.parent().fileswidget.selectionModel().currentIndex()
                if index.isValid():
                    # Thumbnail
                    if index.data(common.ThumbnailPathRole):
                        image = QtGui.QImage()
                        if image.load(index.data(common.ThumbnailPathRole)):
                            self.thumbnail_widget.image = image
                        common.get_sequence_endpath(
                            index.data(QtCore.Qt.StatusTipRole))
                    # Description
                    if index.data(common.DescriptionRole):
                        self.description_editor_widget.setText(
                            index.data(common.DescriptionRole))
                # Checking if the reference file has a valid pattern
            match = common.get_valid_filename(self.currentfile)
            if match:
                self.findChild(Custom).setHidden(False)
                self.findChild(Custom).setText(match.group(3))
            else:
                self.findChild(Custom).setHidden(True)
            self.findChild(Custom).setHidden(False)

            self.thumbnail_widget.update_thumbnail_preview()

            if f.model().asset().isValid():
                path = QtCore.QFileInfo(self.currentfile).dir().path()
                index = f.model().index(path)
                f.model().destinationChanged.emit(index)
        else:
            self.findChild(Custom).setHidden(False)

    def update_filepath_display(self, *args, **kwargs):
        """Slot responsible for updating the file-path display."""
        font = QtGui.QFont(common.PrimaryFont)
        font.setPointSize(common.MEDIUM_FONT_SIZE)
        metrics = QtGui.QFontMetrics(font)
        text = metrics.elidedText(
            SaverFileInfo(self).fileInfo().filePath(),
            QtCore.Qt.ElideLeft,
            self.window().rect().width() - common.MARGIN
        )
        self.findChild(QtWidgets.QStatusBar).showMessage(text)
        self.findChild(QtWidgets.QStatusBar).repaint()

    def update_filename_display(self, *args, **kwargs):
        """Slot responsible for updating the Prefix, Custom, and Suffix widgets."""
        f = SaverFileInfo(self)
        file_info = QtCore.QFileInfo(f.fileName(style=common.LowerCase))

        match = common.get_valid_filename(
            self.currentfile) if self.currentfile else None
        if self.currentfile and not match:
            self.findChild(Prefix).setText(file_info.completeBaseName())
            self.findChild(Suffix).setText(
                '.{}'.format(file_info.suffix()))
        elif self.currentfile and match:
            prefix, suffix = self.prefix_suffix(match, increment=True)
            self.findChild(Prefix).setText(prefix)
            self.findChild(Suffix).setText(suffix)
        else:  # New name
            match = common.get_valid_filename(
                '/{}'.format(f.fileName(style=common.LowerCase)))
            prefix, suffix = self.prefix_suffix(match, increment=False)
            self.findChild(Prefix).setText(prefix)
            self.findChild(Suffix).setText(suffix)

        self.findChild(Prefix).repaint()
        self.findChild(Suffix).repaint()

    def prefix_suffix(self, match, increment=True):
        """Returns the string used to display the filename before and after the
        custom name and the sequence number.

        """
        prefix = match.expand(ur'\1_\2_')
        n = match.group(4)
        suffix = match.expand(ur'_<span style="color:rgba({});">{}</span>_\5.\6'.format(
            u'{},{},{},{}'.format(*common.FAVOURITE.getRgb()),
            u'{}'.format(int(n) + int(increment)).zfill(len(n))
        ))
        return prefix, suffix

    def done(self, result):
        """Slot called by the check button to initiate the save."""
        if result == QtWidgets.QDialog.Rejected:
            return super(AddFileWidget, self).done(result)

        buttons = self.findChildren(SelectFolderButton)
        bookmarkbutton = [
            f for f in buttons if f.objectName() == u'SelectBookmarkButton'][-1]
        assetbutton = [f for f in buttons if f.objectName() ==
                       u'SelectAssetButton'][-1]
        foldersbutton = [f for f in buttons if f.objectName()
                         == u'SelectFolderButton'][-1]

        if not bookmarkbutton.view().active_index().isValid():
            return QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.NoIcon,
                u'', u'Unable to save as the destination bookmark has not yet been selected.', parent=self).exec_()
        elif not assetbutton.view().active_index().isValid():
            return QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.NoIcon,
                u'', u'Unable to save as the destination asset has not yet been selected.', parent=self).exec_()
        elif not foldersbutton.view().model().destination():
            return QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.NoIcon,
                u'', u'Unable to save as the destination folder inside not yet been selected.', parent=self).exec_()

        file_info = SaverFileInfo(self).fileInfo()

        # Let's check if we're not overwriding a file by accident
        if file_info.exists():
            mbox = QtWidgets.QMessageBox(parent=self)
            mbox.setWindowTitle(u'File exists already')
            mbox.setIcon(QtWidgets.QMessageBox.Warning)
            mbox.setText(
                u'{} already exists.'.format(file_info.fileName())
            )
            mbox.setInformativeText(
                u'If you decide to proceed the existing file will be overriden. Are you sure you want to continue?')
            mbox.setStandardButtons(
                QtWidgets.QMessageBox.Save
                | QtWidgets.QMessageBox.Cancel
            )
            mbox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
            if mbox.exec_() == QtWidgets.QMessageBox.Cancel:
                return None

        bookmark = bookmarkbutton.view().active_index().data(common.ParentRole)
        # Let's broadcast these settings
        self.fileSaveRequested.emit(file_info.filePath())
        self.fileThumbnailAdded.emit((
            bookmark[0],
            bookmark[1],
            bookmark[2],
            file_info.filePath(),
            self.thumbnail_widget.image))
        self.fileDescriptionAdded.emit((
            bookmark[0],
            bookmark[1],
            bookmark[2],
            file_info.filePath(),
            self.description_editor_widget.text()))

        return super(AddFileWidget, self).done(result)

    def showEvent(self, event):
        self.parent().stackedwidget.currentWidget().disabled_overlay_widget.show()

    def hideEvent(self, event):
        self.parent().stackedwidget.currentWidget().disabled_overlay_widget.hide()
