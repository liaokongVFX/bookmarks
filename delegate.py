# -*- coding: utf-8 -*-
"""Delegate and editor classes for the list widgets.
"""
# pylint: disable=E1101, C0103, R0913, I1101, W0613, R0201

from PySide2 import QtWidgets, QtGui, QtCore

import mayabrowser.common as common
from mayabrowser.common import cmds
import mayabrowser.configparsers as configparser
from mayabrowser.configparsers import ProjectConfig
from mayabrowser.configparsers import FileConfig
from mayabrowser.configparsers import local_config


class BaseDelegate(QtWidgets.QAbstractItemDelegate):
    """Base delegate class."""

    def __init__(self, parent=None):
        super(BaseDelegate, self).__init__(parent=parent)

    def sizeHint(self, option, index):
        """Custom size hint."""
        return QtCore.QSize(common.WIDTH, common.ROW_HEIGHT)

    def get_thumbnail_path(self, index):
        """Abstract method to be overriden in the subclass.
        Should return the path to the thumbnail file.

        """
        raise NotImplementedError(
            'get_thumbnail_path() is abstract and has to be overriden in the subclass.'
        )

    def paint_favourite(self, *args):
        """Paints the little yellow dot, that marks items as the favourite item."""
        painter, option, _, selected, _, favourite = args
        if not favourite:
            return

        if selected:
            color = common.FAVORUITE_SELECTED
        else:
            color = common.FAVORUITE
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(color))

        size = 4
        rect = QtCore.QRect(option.rect)
        rect.setWidth(size)
        rect.setHeight(size)
        rect.moveLeft(option.rect.width() - size * 2)
        rect.moveTop(option.rect.top() + size)
        painter.drawRoundedRect(rect, size * 0.5, size * 0.5)

    def paint_background(self, *args):
        """Paints the background."""
        painter, option, _, selected, _, _ = args

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))

        if selected:
            color = common.BACKGROUND_SELECTED
        else:
            color = common.BACKGROUND
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(option.rect)

    def paint_separators(self, *args):
        """Paints horizontal separators."""
        painter, option, index, _, _, _ = args
        if index.row() == 0:
            return

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(common.SEPARATOR))
        rect = QtCore.QRectF(
            option.rect.left() + 4 + option.rect.height(),
            option.rect.top(),
            option.rect.width() - 4 - option.rect.height(),
            0.5
        )
        painter.drawRect(rect)

    def paint_selection_indicator(self, *args):
        """Paints the blue leading rectangle to indicate the current selection."""
        painter, option, _, selected, _, _ = args

        if not selected:
            return

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(common.SELECTION))
        rect = QtCore.QRect(option.rect)
        rect.setWidth(4)
        painter.drawRect(rect)

    def paint_active_indicator(self, *args):
        """Paints the yellow leading rectangle to indicate item is set as current."""
        painter, option, index, selected, _, _ = args

        if not self.parent().collector.active_item:
            return

        p = self.parent().collector.active_item.filePath()
        if p != index.data(QtCore.Qt.StatusTipRole):
            return

        if p != QtCore.QFileInfo(cmds.workspace(q=True, fn=True)).filePath():
            return

        rect = QtCore.QRect(option.rect)
        rect.setWidth(4)

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        if selected:
            color = common.FAVORUITE_SELECTED
        else:
            color = common.FAVORUITE
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(rect)

    def paint_thumbnail(self, *args):
        """Paints the thumbnail of the item.
        TODO: This method is slow. Needs to be optimized.

        """
        painter, option, index, selected, _, _ = args
        if selected:
            color = common.THUMBNAIL_BACKGROUND_SELECTED
        else:
            color = common.THUMBNAIL_BACKGROUND

        rect = QtCore.QRect(option.rect)
        rect.setWidth(rect.height())
        rect.moveLeft(rect.left() + 4)

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(rect)


        # Checking if the image has already been stored in the cache.
        if common.MAYA_THUMBNAIL in common.IMAGE_CACHE:
            placeholder = common.IMAGE_CACHE[common.MAYA_THUMBNAIL]
        else:
            placeholder = QtGui.QImage()
            placeholder.load(common.MAYA_THUMBNAIL)
            placeholder = ThumbnailEditor.smooth_copy(
                placeholder,
                option.rect.height()
            )
            common.IMAGE_CACHE[common.MAYA_THUMBNAIL] = placeholder


        path = self.get_thumbnail_path(index)
        image = placeholder

        if QtCore.QFileInfo(path).exists():
            if path in common.IMAGE_CACHE:
                image = common.IMAGE_CACHE[path]
            else:
                image = QtGui.QImage()
                image.load(path)
                if image.isNull():
                    image = placeholder
                else:
                    image = ThumbnailEditor.smooth_copy(
                        image,
                        option.rect.height()
                    )
                    common.IMAGE_CACHE[path] = image
        else:
            image = placeholder


        # Factoring aspect ratio in
        longer = float(max(image.rect().width(), image.rect().height()))
        factor = float(rect.width() / longer)
        if image.rect().width() < image.rect().height():
            rect.setWidth(float(image.rect().width()) * factor)
        else:
            rect.setHeight(float(image.rect().height()) * factor)

        rect.moveLeft(
            rect.left() + ((option.rect.height() - rect.width()) * 0.5))
        rect.moveTop(
            rect.top() + ((option.rect.height() - rect.height()) * 0.5))

        painter.setOpacity(0.85)
        painter.drawImage(
            rect,
            image,
            image.rect()
        )
        painter.setOpacity(1)

    def paint_data(self, *args):
        """Abstract method to be overriden in the subclass.
        Method should be responsible for displaying all the data elements.

        """
        raise NotImplementedError(
            'paint_data() is abstract and has to be overriden.'
        )

    def paint(self, painter, option, index):
        """The main paint method."""
        painter.setRenderHints(
            QtGui.QPainter.TextAntialiasing |
            QtGui.QPainter.Antialiasing |
            QtGui.QPainter.SmoothPixmapTransform,
            on=True
        )

        selected = option.state & QtWidgets.QStyle.State_Selected
        favourite = index.data(
            QtCore.Qt.UserRole) & configparser.MarkedAsFavourite
        archived = index.data(
            QtCore.Qt.UserRole) & configparser.MarkedAsArchived

        args = (painter, option, index, selected, archived, favourite)

        self.paint_background(*args)
        self.paint_thumbnail(*args)
        self.paint_data(*args)
        self.paint_favourite(*args)
        self.paint_archived(*args)
        self.paint_separators(*args)
        self.paint_filter_indicator(*args)
        self.paint_selection_indicator(*args)
        self.paint_active_indicator(*args)
        self.paint_custom(*args)

    def paint_custom(self, *args):
        """To define any custom paint action, override this method in the subclass."""
        return

    def paint_filter_indicator(self, *args):
        """Paints the leading color-bar if a filter is active."""
        painter, option, _, _, _, _ = args
        _filter = self.parent().current_filter.upper()
        if _filter == '/':
            return

        rect = QtCore.QRect(option.rect)
        rect.setWidth(4)
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(
            QtGui.QColor(common.ASSIGNED_LABELS[_filter])))
        painter.drawRect(rect)

    def paint_archived(self, *args):
        """Paints a `disabled` overlay on top of items marked as `archived`."""
        painter, option, _, _, archived, _ = args
        if not archived:
            return
        painter.setPen(QtCore.Qt.NoPen)
        brush = QtGui.QBrush(common.ARCHIVED_OVERLAY)
        painter.setBrush(brush)
        painter.drawRect(option.rect)

        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 50))
        brush.setStyle(QtCore.Qt.BDiagPattern)
        painter.setBrush(brush)
        painter.drawRect(option.rect)

    @staticmethod
    def get_thumbnaileditor_cls(*args, **kwargs):
        """Abstract method needs to be overriden in the subclass.
        Should return the Class Type of the editor.

        """
        raise NotImplementedError('get_thumbnaileditor_cls() is abstract.')

    @staticmethod
    def get_noteeditor_cls(*args, **kwargs):
        """Abstract method needs to be overriden in the subclass.
        Should return the Class Type of the editor.

        """
        raise NotImplementedError('get_noteeditor_cls() is abstract.')

    def custom_doubleclick_event(self, parent, option, index):
        """Abstract method needs to be overriden in the subclass.
        Action to perform on double-click.

        """
        raise NotImplementedError('custom_doubleclick_event() is abstract.')

    def get_name_rect(self, rect):
        """Returns the rectangle containing the name.

        Args:
            rect (QtCore.QRect): The QListWidgetItem's visual rectangle.

        Returns:            QtCore.QRect

        """
        painter = QtGui.QPainter()
        font = QtGui.QFont(painter.font())
        font.setBold(True)
        font.setItalic(False)
        font.setPointSize(8.0)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(painter.font())
        editor_rect = QtCore.QRect(rect)

        offset = 4 + rect.height() + common.MARGIN
        editor_rect.moveLeft(editor_rect.left() + offset)
        editor_rect.setWidth(editor_rect.width() - offset - common.MARGIN)
        editor_rect.setHeight(metrics.height())

        # Center rectangle
        editor_rect.moveTop(
            rect.top() +
            (rect.height() * 0.5) -
            (editor_rect.height() * 0.5)
        )
        return editor_rect, font, metrics

    def get_filename_rect(self, rect):
        """Returns the rectangle containing the name.

        Args:
            rect (QtCore.QRect): The QListWidgetItem's visual rectangle.

        Returns:            QtCore.QRect

        """
        painter = QtGui.QPainter()
        font = QtGui.QFont(painter.font())
        font.setBold(True)
        font.setItalic(False)
        font.setPointSize(7.0)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(painter.font())
        editor_rect = QtCore.QRect(rect)

        offset = 4 + rect.height() + common.MARGIN
        editor_rect.moveLeft(editor_rect.left() + offset)
        editor_rect.setWidth(editor_rect.width() - offset - common.MARGIN)
        editor_rect.setHeight(metrics.height())

        # Center rectangle
        editor_rect.moveTop(
            rect.top() +
            (rect.height() * 0.5) -
            (editor_rect.height() * 0.5)
        )
        return editor_rect, font, metrics

    def get_note_rect(self, rect):
        """Returns the rectangle, font and the font metrics used to draw the note text.

        Returns:            (QtCore.QRect(), QtGui.QFont(), QtGui.QFontMetrics())

        """
        painter = QtGui.QPainter()
        font = QtGui.QFont(painter.font())
        font.setBold(False)
        font.setItalic(True)
        font.setPointSize(8.0)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(painter.font())
        editor_rect = QtCore.QRect(rect)

        offset = 4 + rect.height() + common.MARGIN
        editor_rect.moveLeft(editor_rect.left() + offset)
        editor_rect.setWidth(editor_rect.width() - offset - common.MARGIN)
        editor_rect.setHeight(metrics.height())

        # Center rectangle
        editor_rect.moveTop(
            rect.top() +
            (rect.height() * 0.5) -
            (editor_rect.height() * 0.5)
        )
        editor_rect.moveTop(editor_rect.top() + metrics.height() + 2)
        return editor_rect, font, metrics

    def get_thumbnail_editor_rect(self, rect):
        """Returns the rectangle for the thumbnail editor."""
        rect = QtCore.QRect(rect)
        rect.moveLeft(4)
        rect.setWidth(rect.height())
        return rect

    def createEditor(self, parent, option, index):  # pylint: disable=W0613
        """Creates the custom editors needed to edit the thumbnail and the description.

        References:
        http: // doc.qt.io/qt-5/QItemEditorFactory.html  # standard-editing-widgets

        """
        cursorPos = QtGui.QCursor().pos()
        cursorPos = self.parent().mapFromGlobal(cursorPos)

        rect, _, _ = self.get_note_rect(option.rect)
        if rect.contains(cursorPos):
            return self.get_noteeditor_cls(index, rect, self.parent(), parent=parent)

        rect = self.get_thumbnail_editor_rect(option.rect)
        if rect.contains(cursorPos):
            return self.get_thumbnaileditor_cls(index, rect, self.parent(), parent=parent)

        # A bit hack-ish to include hide() in this function but why not! :/
        self.custom_doubleclick_event(parent, option, index)


class ProjectWidgetDelegate(BaseDelegate):
    """Delegate used by the ``ProjectWidget`` to display the collecteds projects."""

    def get_thumbnail_path(self, index):
        """The path to the thumbnail of the project."""
        return ProjectConfig.getThumbnailPath(index.data(QtCore.Qt.StatusTipRole))

    def get_config_path(self, index):
        """The path to the project's configuration file."""
        return ProjectConfig.getConfigPath(index.data(QtCore.Qt.StatusTipRole))

    @staticmethod
    def get_thumbnaileditor_cls(*args, **kwargs):
        """The widget used to edit the thumbnail of the project."""
        return ProjectThumbnailEditor(*args, **kwargs)

    @staticmethod
    def get_noteeditor_cls(*args, **kwargs):
        """The widget used to edit the description of the project."""
        return ProjectNoteEditor(*args, **kwargs)

    def paint_custom(self, *args):
        """Custom paint action to draw the buttons to trigger."""
    def paint_data(self, *args):
        """Paints the ``ProjectWidget``'s `QListWidgetItems`' names and notes."""
        painter, option, index, selected, _, _ = args

        if selected:
            color = common.TEXT_SELECTED
        elif not selected:
            color = common.TEXT

        rect, font, metrics = self.get_name_rect(option.rect)
        text = metrics.elidedText(
            index.data(QtCore.Qt.DisplayRole),
            QtCore.Qt.ElideRight,
            rect.width() - common.MARGIN
        )
        painter.setFont(font)

        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(color))
        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft | QtCore.Qt.TextWordWrap,
            text
        )

        config_info = QtCore.QFileInfo(self.get_config_path(index))
        if not config_info.exists():
            return

        text = None
        with open(self.get_config_path(index), 'r') as f:
            text = next((l for l in f if 'description' in l), None)

        if not text:
            return

        rect, font, metrics = self.get_note_rect(option.rect)
        text = metrics.elidedText(
            text.replace('description = ', '').lstrip().rstrip(),
            QtCore.Qt.ElideRight,
            rect.width()
        )
        painter.setPen(QtGui.QPen(common.TEXT_NOTE))
        painter.setFont(font)
        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft | QtCore.Qt.TextWordWrap,
            text
        )

    def custom_doubleclick_event(self, parent, option, index):
        self.parent().active_item = index
        self.parent().hide()
        self.parent().parent_.filesButton.clicked.emit()


class FilesWidgetDelegate(BaseDelegate):
    """QAbstractItemDelegate associated with ``FilesWidget``."""

    def paint_active_indicator(self, *args):
        """Paints the yellow leading rectangle to indicate item is set as current."""
        painter, option, index, selected, _, _ = args

        maya_file_info = QtCore.QFileInfo(cmds.file(q=True, expandName=True))
        file_info = QtCore.QFileInfo(index.data(QtCore.Qt.StatusTipRole))

        if maya_file_info.filePath() != file_info.filePath():
            return

        rect = QtCore.QRect(option.rect)
        rect.setWidth(4)

        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        if selected:
            color = common.FAVORUITE_SELECTED
        else:
            color = common.FAVORUITE
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(rect)

    def paint_data(self, *args):
        """Paints the ``FilesWidget``'s `QListWidgetItem` names, sub-directories and
        file informations.

        """
        painter, option, index, selected, _, _ = args
        if selected:
            color = common.TEXT_SELECTED
        elif not selected:
            color = common.TEXT

        file_info = QtCore.QFileInfo(index.data(QtCore.Qt.DisplayRole))
        rect, font, metrics = self.get_filename_rect(option.rect)
        filename = metrics.elidedText(
            file_info.fileName().upper(),
            QtCore.Qt.ElideMiddle,
            rect.width()
        )

        # Geting the base directories
        basedirs = file_info.dir().path()
        basedirs = basedirs.replace(
            self.parent().collector.root_info.filePath(), ''
        ).replace(
            local_config.project_scenes_folder, ''
        ).lstrip('/').rstrip('/')

        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setFont(font)
        painter.setPen(QtGui.QPen(color))

        # Iterating the base directories
        basedir_rect = QtCore.QRect(rect)
        available_width = rect.width() - metrics.width(filename) - common.MARGIN
        basedir_total_width = 0
        for idx, basedir in enumerate(basedirs.split('/')):
            if idx == 0:
                basedir = basedir.upper()
            else:
                basedir = basedir.lower()
            basedir_rect.setWidth(metrics.width(basedir))
            basedir_total_width += metrics.width(basedir) + common.MARGIN * 1

            # Skip folders that are too long to draw
            if available_width < basedir_total_width:
                painter.drawText(
                    basedir_rect,
                    QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                    '...'
                )
                break

            path = QtGui.QPainterPath()
            path.addRoundedRect(QtCore.QRectF(basedir_rect), 0.5, 0.5)
            if idx == 0:  # first subdir
                bgcolor = common.get_label(basedir)
                if selected:
                    bgcolor = QtGui.QColor(bgcolor)
                    bgcolor.setRed(bgcolor.red() + 20)
                    bgcolor.setGreen(bgcolor.green() + 20)
                    bgcolor.setBlue(bgcolor.blue() + 20)
                painter.fillPath(path, bgcolor)
                pen = QtGui.QPen(bgcolor, 2)
                painter.setPen(pen)
                painter.setBrush(QtGui.QBrush(bgcolor))
            else:  # secondary subdirs
                bgcolor = common.SECONDARY_BACKGROUND
                if selected:
                    bgcolor = common.BACKGROUND_SELECTED
                painter.fillPath(path, bgcolor)
                pen = QtGui.QPen(bgcolor, 2)
                painter.setPen(pen)
                painter.setBrush(QtGui.QBrush(bgcolor))
            painter.drawPath(path)

            # Draw name
            if idx == 0:  # first subdir
                data_color = common.TEXT
            elif idx > 0:  # secondary subdirs
                data_color = common.SECONDARY_TEXT

            painter.setPen(QtGui.QPen(data_color))
            painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
            painter.drawText(
                basedir_rect,
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter,
                basedir
            )

            # Move rect
            basedir_rect.moveLeft(
                basedir_rect.left() +
                basedir_rect.width() +
                common.MARGIN * 1
            )

        font = QtGui.QFont(painter.font())
        font.setBold(True)
        font.setItalic(False)
        font.setPointSize(8.0)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(painter.font())

        painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        painter.setPen(QtGui.QPen(color))
        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
            filename
        )

        rect.setHeight(metrics.height())
        rect.moveTop(
            option.rect.top() +
            (option.rect.height() * 0.5) -
            (rect.height() * 0.5) +
            metrics.height()
        )

        # File information

        font = QtGui.QFont(painter.font())
        font.setBold(False)
        font.setItalic(True)
        font.setPointSize(7.0)
        painter.setFont(font)

        metrics = QtGui.QFontMetrics(painter.font())

        info = QtCore.QFileInfo(index.data(QtCore.Qt.StatusTipRole))
        info_string = '{hour}:{minute}  -  {day}/{month}/{year}  -  {size}'.format(
            day=info.lastModified().toString('dd'),
            month=info.lastModified().toString('MM'),
            year=info.lastModified().toString('yyyy'),
            hour=info.lastModified().toString('hh'),
            minute=info.lastModified().toString('mm'),
            size=self._byte_to_string(info.size())
        )

        info_string = metrics.elidedText(
            info_string,
            QtCore.Qt.ElideRight,
            rect.width() - common.MARGIN
        )

        if selected:
            color = common.TEXT
        else:
            color = common.SECONDARY_TEXT
        painter.setPen(QtGui.QPen(color))
        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
            info_string
        )

        # Description
        config_info = QtCore.QFileInfo(self.get_config_path(index))
        if not config_info.exists():
            return

        text = None
        with open(self.get_config_path(index), 'r') as f:
            text = next((l for l in f if 'description' in l), None)

        if not text:
            return
        rect, font, metrics = self.get_note_rect(option.rect)
        text = metrics.elidedText(
            text.replace('description = ', '').lstrip().rstrip(),
            QtCore.Qt.ElideRight,
            rect.width() - common.MARGIN - metrics.width(info_string)
        )
        painter.setPen(QtGui.QPen(common.TEXT_NOTE))
        painter.setFont(font)
        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            text
        )

    @staticmethod
    def _byte_to_string(num, suffix='B'):
        for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    def custom_doubleclick_event(self, parent, option, index):
        """Opens the scene on double-click."""
        self.parent().action_on_enter_key()

    def get_thumbnail_path(self, index):
        return FileConfig.getThumbnailPath(index.data(QtCore.Qt.StatusTipRole))

    def get_config_path(self, index):
        """Returns the path to the file's configuration file."""
        return FileConfig.getConfigPath(index.data(QtCore.Qt.StatusTipRole))

    @staticmethod
    def get_thumbnaileditor_cls(*args, **kwargs):
        return SceneThumbnailEditor(*args, **kwargs)

    @staticmethod
    def get_noteeditor_cls(*args, **kwargs):
        return SceneNoteEditor(*args, **kwargs)


class ThumbnailEditor(QtWidgets.QWidget):
    """Thumbnail editor baseclass."""

    def __init__(self, index, rect, view, parent=None):
        super(ThumbnailEditor, self).__init__(parent=parent)
        self._index = index
        self._rect = rect
        self._view = view

        self.dialog = QtWidgets.QFileDialog()
        self.dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        self.dialog.setViewMode(QtWidgets.QFileDialog.List)
        self.dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
        self.dialog.setNameFilter('Image files (*.png *.jpg  *.jpeg)')

        if not self.dialog.exec_():
            return
        if not self.dialog.selectedFiles():
            return

        image = QtGui.QImage()
        image.load(self.dialog.selectedFiles()[0])
        image = self.smooth_copy(image, 512)


        path = self.get_thumbnail_path(index)

        # Deleting the thumbnail from the image cache
        if path in common.IMAGE_CACHE:
            del common.IMAGE_CACHE[path]

        if image.save(path):
            ProjectConfig.set_hidden(path, hide=True)
            self.parent().update()

    @staticmethod
    def smooth_copy(image, size):
        """Returns an aspect-ratio aware smooth scaled copy of the image."""
        longer = float(max(image.width(), image.height()))
        factor = float(float(size) / float(longer))
        if image.width() < image.height():
            image = image.smoothScaled(
                float(image.width()) * factor,
                size
            )
            return image
        image = image.smoothScaled(
            size,
            float(image.height()) * factor
        )
        return image

    def get_thumbnail_path(self, index):
        """Abstract."""
        raise NotImplementedError(
            'Method is abstract and has to be overwritten.')


class ProjectThumbnailEditor(ThumbnailEditor):
    """Edits the project's thumbnail."""

    def get_thumbnail_path(self, index):
        """The path of the project's thumbnail."""
        return ProjectConfig.getThumbnailPath(index.data(QtCore.Qt.StatusTipRole))


class SceneThumbnailEditor(ThumbnailEditor):
    """Edits the project's thumbnail."""

    def get_thumbnail_path(self, index):
        """The path of the project's thumbnail."""
        return FileConfig.getThumbnailPath(index.data(QtCore.Qt.StatusTipRole))


class NoteEditor(QtWidgets.QWidget):
    """Note editor baseclass."""

    def __init__(self, index, rect, view, parent=None):
        super(NoteEditor, self).__init__(parent=parent)
        self._index = index
        self._rect = rect
        self._view = view

        self.config = self.get_config_instance(
            self._index.data(QtCore.Qt.StatusTipRole))

        self.editor = None
        self._createUI()
        self.editor.installEventFilter(self)
        self._connectSignals()

    def eventFilter(self, widget, event):
        """We're filtering the enter key event here, otherwise, the
        list widget would close open finishing editing.

        """
        if not event.type() == QtCore.QEvent.KeyPress:
            return False

        if event.modifiers() == QtCore.Qt.NoModifier:
            if (event.key() == QtCore.Qt.Key_Return) or event.key() == QtCore.Qt.Key_Enter:
                self.action()
                return True
            elif event.key() == QtCore.Qt.Key_Tab:
                self.action()
                self._view.key_down()
                self._view.key_tab()
                return True
            elif event.key() == QtCore.Qt.Key_Backtab:
                self.action()
                self._view.key_up()
                self._view.key_tab()
                return True
            elif event.key() == QtCore.Qt.Key_Escape:
                try:  # Older versions of Qt5 seems to require a QlistWidgetItem, not a QModelIndex.
                    self._view.closePersistentEditor(self._index)
                except TypeError:
                    item = self._view.itemFromIndex(self._index)
                    self._view.closePersistentEditor(item)
                return True

        if event.modifiers() == QtCore.Qt.ShiftModifier:
            if event.key() == QtCore.Qt.Key_Tab:
                self.action()
                self._view.key_up()
                self._view.key_tab()
                return True
            elif event.key() == QtCore.Qt.Key_Backtab:
                self.action()
                self._view.key_up()
                self._view.key_tab()
                return True
        return False

    def focusOutEvent(self, event):
        """Closes the editor on focus loss."""
        if event.lostFocus():
            try:  # Older versions of Qt5 seems to require a QlistWidgetItem, not a QModelIndex.
                self._view.closePersistentEditor(self._index)
            except TypeError:
                item = self._view.itemFromIndex(self._index)
                self._view.closePersistentEditor(item)

    def _connectSignals(self):
        """Connects signals."""
        self.editor.editingFinished.connect(self.action)

    def _createUI(self):
        """Creates the layout."""
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        self.editor = QtWidgets.QLineEdit()
        self.editor.focusOutEvent = self.focusOutEvent
        self.editor.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.layout().addWidget(self.editor)
        self.setFocusProxy(self.editor)

        self.setStyleSheet(
            """
        QWidget {
            background-color: rgb(50,50,50);
            color: rgb(230, 230, 230);
            border: none;
            outline: none;
            border-radius: 3px;
            padding: 3 3 3 3;
            margin: 0;
        }
        """
        )

        self.editor.setStyleSheet(
            """
        QLineEdit {
            padding: 0 0 0 0;
            margin: 0 0 0 0;
        }
        """
        )

    @staticmethod
    def get_config_instance(*args, **kwargs):
        """Abstract method."""
        raise NotImplementedError(
            'Action is abstract and needs to be overwritten in the subclass.')

    def showEvent(self, event):  # pylint: disable=W0613
        """Show event."""
        self.move(
            self._rect.left(),
            self._rect.top()
        )
        self.setFixedWidth(self._rect.width())
        self.editor.setText(self.config.description)
        self.editor.selectAll()

    def action(self):
        """Main actions to run when the return key is pressed."""
        if self.config.description == self.editor.text():
            return

        self.config.description = self.editor.text()
        self.config.write_ini()

        # Older (<5.10?) versions of Qt5 seems to require a QlistWidgetItem, not a QModelIndex.
        try:
            self._view.closePersistentEditor(self._index)
        except TypeError:
            item = self._view.itemFromIndex(self._index)
            self._view.closePersistentEditor(item)


class ProjectNoteEditor(NoteEditor):
    """Edits the notes of projects."""

    @staticmethod
    def get_config_instance(*args, **kwargs):
        return ProjectConfig(*args, **kwargs)


class SceneNoteEditor(NoteEditor):
    """Edits the notes of projects."""

    @staticmethod
    def get_config_instance(*args, **kwargs):
        return FileConfig(*args, **kwargs)
