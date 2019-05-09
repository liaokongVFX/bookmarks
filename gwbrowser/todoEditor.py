# -*- coding: utf-8 -*-

"""Defines the widgets needed to add and modify notes and todo-type annotions
for an Bookmark or an Asset.

`TodoEditorWidget` is the top widget. It reads the asset configuration file
and loads stored todo items. The todo items support basic HTML elements but
embedding media resources are not supported.

Methods:
    TodoEditorWidget.add_item(): Main function to add a new todo item.

"""

import uuid
import functools
from PySide2 import QtWidgets, QtGui, QtCore

from gwbrowser.imagecache import ImageCacheWorker
from gwbrowser import common
from gwbrowser.settings import AssetSettings
from gwbrowser.settings import local_settings
from gwbrowser.imagecache import ImageCache


class PaintedLabel(QtWidgets.QLabel):
    """Custom label used to paint the elements of the ``AddBookmarksWidget``."""

    def __init__(self, text, size=common.MEDIUM_FONT_SIZE, parent=None):
        super(PaintedLabel, self).__init__(text, parent=parent)
        self._font = QtGui.QFont(common.PrimaryFont)
        self._font.setPointSize(size)
        metrics = QtGui.QFontMetrics(self._font)
        self.setFixedHeight(metrics.height())

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )

    def paintEvent(self, event):
        """Custom paint event to use the aliased paint method."""
        painter = QtGui.QPainter()
        painter.begin(self)
        color = common.FAVOURITE
        common.draw_aliased_text(
            painter, self._font, self.rect(), self.text(), QtCore.Qt.AlignCenter, color)
        painter.end()


class Highlighter(QtGui.QSyntaxHighlighter):
    """Class responsible for highlighting urls"""

    def highlightBlock(self, text):
        """The highlighting cases are defined in the common module.
        In general we're tying to replicate the ``Markdown`` syntax rendering.

        Args:
            case (str): HIGHLIGHT_RULES dicy key.
            text (str): The text to assess.

        Returns:
            tuple: int, int, int

        """
        start = 0
        end = len(text)

        flags = common.NoHighlightFlag
        for case in common.HIGHLIGHT_RULES:
            match = u''
            search = common.HIGHLIGHT_RULES[case][u're'].search(text)
            if not search:
                continue

            flags = flags | common.HIGHLIGHT_RULES[case][u'flag']
            for group in search.groups():
                if not group:
                    continue
                group = u'{}'.format(group)
                group.encode(u'utf-8')
                match += group

            if not match:
                continue

            match.rstrip()
            start = text.find(match)
            end = len(match)

            char_format = QtGui.QTextCharFormat()
            char_format.setFont(self.document().defaultFont())

            if flags == common.NoHighlightFlag:
                self.setFormat(start, end, char_format)
                break

            if flags & common.HeadingHighlight:
                char_format.setFontWeight(QtGui.QFont.Bold)
                char_format.setFontPointSize(
                    self.document().defaultFont().pointSize() + 0 + (6 - len(match)))
                char_format.setFontCapitalization(QtGui.QFont.AllUppercase)
                if len(match) > 1:
                    char_format.setUnderlineStyle(
                        QtGui.QTextCharFormat.SingleUnderline)
                    char_format.setFontPointSize(
                        self.document().defaultFont().pointSize() + 1)
                self.setFormat(0, len(text), char_format)
                break
            elif flags & common.QuoteHighlight:
                char_format.setForeground(QtGui.QColor(100, 100, 100))
                char_format.setBackground(QtGui.QColor(230, 230, 230))
                self.setFormat(0, len(text), char_format)
                break

            if flags & common.CodeHighlight:
                char_format.setFontWeight(QtGui.QFont.Bold)
                char_format.setForeground(common.FAVOURITE)
                self.setFormat(start, end, char_format)
            if flags & common.BoldHighlight:
                char_format.setFontWeight(QtGui.QFont.Bold)
                self.setFormat(start, end, char_format)
            if flags & common.ItalicHighlight:
                char_format.setFontItalic(True)
                self.setFormat(start, end, char_format)
        return


class TodoItemEditor(QtWidgets.QTextBrowser):
    """Custom QTextBrowser widget for writing `Todo`'s.

    The editor automatically sets its size to accommodate the contents of the document.
    Some of the code has been lifted and implemented from Cameel's implementation.

    https://github.com/cameel/auto-resizing-text-edit/

    """

    def __init__(self, text=None, checked=False, parent=None):
        super(TodoItemEditor, self).__init__(parent=parent)
        self.setDisabled(checked)
        self.document().setDocumentMargin(common.MARGIN)
        # option
        option = QtGui.QTextOption()
        option.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        option.setUseDesignMetrics(True)
        self.document().setDefaultTextOption(option)
        # font
        font = QtGui.QFont(common.SecondaryFont)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        font.setPointSizeF(common.MEDIUM_FONT_SIZE)
        self.document().setDefaultFont(font)

        self.highlighter = Highlighter(self.document())
        self.setOpenExternalLinks(True)
        self.setOpenLinks(False)
        self.setReadOnly(False)
        self.setTextInteractionFlags(
            QtCore.Qt.TextBrowserInteraction | QtCore.Qt.TextEditorInteraction)

        metrics = QtGui.QFontMetrics(self.document().defaultFont())
        metrics.width(u'  ')
        self.setTabStopWidth(common.MARGIN)

        self.setUndoRedoEnabled(True)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Fixed
        )
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)

        self.document().contentsChanged.connect(self.contentChanged)
        self.document().setHtml(text)

        self.anchorClicked.connect(self.open_url)

    def setDisabled(self, b):
        super(TodoItemEditor, self).setDisabled(b)
        font = QtGui.QFont(common.SecondaryFont)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        font.setPointSizeF(common.MEDIUM_FONT_SIZE)
        if b:
            font.setStrikeOut(True)
        self.document().setDefaultFont(font)

    @QtCore.Slot()
    def contentChanged(self):
        """Sets the height of the editor."""
        self.setFixedHeight(
            self.heightForWidth(self.width())
        )

    def get_minHeight(self):
        """Returns the desired minimum height of the editor."""
        margins = self.contentsMargins()
        metrics = QtGui.QFontMetrics(self.document().defaultFont())
        line_height = (metrics.height() + metrics.leading()) * 1  # Lines tall
        return line_height + margins.top() + margins.bottom()

    def get_maxHeight(self):
        """Returns the desired minimum height of the editor."""
        margins = self.contentsMargins()
        metrics = QtGui.QFontMetrics(self.document().defaultFont())
        line_height = (metrics.height() + metrics.leading()) * 35  # Lines tall
        return line_height + margins.top() + margins.bottom()

    def heightForWidth(self, width):
        """https://raw.githubusercontent.com/cameel/auto-resizing-text-edit/master/auto_resizing_text_edit/auto_resizing_text_edit.py"""
        margins = self.contentsMargins()

        if width >= margins.left() + margins.right():
            document_width = width - margins.left() - margins.right()
        else:
            # If specified width can't even fit the margin, there's no space left for the document
            document_width = 0

        document = self.document().clone()
        document.setTextWidth(document_width)
        height = margins.top() + document.size().height() + margins.bottom()

        if height < self.get_minHeight():
            return self.get_minHeight()
        if height > self.get_maxHeight():
            return self.get_maxHeight()
        return height

    def keyPressEvent(self, event):
        """I'm defining custom key events here, the default behaviour is pretty poor.

        In a dream-scenario I would love to implement most of the functions
        of how atom behaves.

        """
        cursor = self.textCursor()
        cursor.setVisualNavigation(True)

        no_modifier = event.modifiers() == QtCore.Qt.NoModifier
        control_modifier = event.modifiers() == QtCore.Qt.ControlModifier
        shift_modifier = event.modifiers() == QtCore.Qt.ShiftModifier

        if event.key() == QtCore.Qt.Key_Backtab:
            cursor.movePosition(
                QtGui.QTextCursor.Start,
                QtGui.QTextCursor.MoveAnchor,
                cursor.position() - 4,
            )
            return
        super(TodoItemEditor, self).keyPressEvent(event)

    def sizeHint(self):
        return QtCore.QSize(200, self.heightForWidth(200))

    def dragEnterEvent(self, event):
        """Checking we can consume the content of the drag data..."""
        if not self.canInsertFromMimeData(event.mimeData()):
            return
        event.accept()

    def dropEvent(self, event):
        """Custom drop event to add content from mime-data."""
        index = self.window().index
        if not index.isValid():
            return

        if not self.canInsertFromMimeData(event.mimeData()):
            return
        event.accept()

        mimedata = event.mimeData()
        self.insertFromMimeData(mimedata)

    def canInsertFromMimeData(self, mimedata):
        """Checks if we can insert from the given mime-type."""
        if mimedata.hasUrls():
            return True
        if mimedata.hasHtml():
            return True
        if mimedata.hasText():
            return True
        if mimedata.hasImage():
            return True
        return False

    def insertFromMimeData(self, mimedata):
        """We can insert media using our image-cache - eg any image-content from
        the clipboard we will save into our cache folder.

        """
        index = self.window().index
        if not index.isValid():
            return

        def img(url): return '<p><img src="{url}" width="{width}" alt="{url}"><br><a href="{url}">{url}</a></p>'.format(
            url=url.toLocalFile(),
            width=560)

        def href(url): return '<p><a href="{url}">{url}</a></p>'.format(
            style='align:left;',
            url=url.toLocalFile())

        # We save our image into the cache for safe-keeping
        if mimedata.hasUrls():
            settings = AssetSettings(index)
            thumbnail_info = QtCore.QFileInfo(settings.thumbnail_path())
            for url in mimedata.urls():
                file_info = QtCore.QFileInfo(url.path())
                if file_info.suffix() in common.get_oiio_extensions():
                    dest = '{}/{}.{}'.format(
                        thumbnail_info.dir().path(),
                        uuid.uuid4(),
                        thumbnail_info.suffix()
                    )
                    ImageCacheWorker.process_index(
                        QtCore.QModelIndex(),
                        source=url.toLocalFile(),
                        dest=dest
                    )
                    url = QtCore.QUrl.fromLocalFile(dest)
                    self.insertHtml(img(url))
                else:
                    self.insertHtml(href(url))

        if mimedata.hasHtml():
            html = mimedata.html()
            self.insertHtml(u'<br>{}<br>'.format(html))
        elif mimedata.hasText():
            text = mimedata.text()
            self.insertHtml(u'<br>{}<br>'.format(text))

        # If the mime has any image data we will save it as a temp image file
        if mimedata.hasImage():
            image = mimedata.imageData()
            if not image.isNull():
                settings = AssetSettings(index)
                thumbnail_info = QtCore.QFileInfo(settings.thumbnail_path())
                dest = '{}/{}.{}'.format(
                    thumbnail_info.dir().path(),
                    uuid.uuid4(),
                    thumbnail_info.suffix()
                )
                if image.save(dest):
                    url = QtCore.QUrl.fromLocalFile(dest)
                    self.insertHtml(img(url))

    def open_url(self, url):
        """We're handling the clicking of anchors here manually."""
        if not url.isValid():
            return
        file_info = QtCore.QFileInfo(url.url())
        if file_info.exists():
            common.reveal(file_info.filePath())
            QtGui.QClipboard().setText(file_info.filePath())
        else:
            QtGui.QDesktopServices.openUrl(url)


class AddButton(QtWidgets.QLabel):
    """Custom icon button to add a new todo item."""
    pressed = QtCore.Signal()

    def __init__(self, parent=None):
        super(AddButton, self).__init__(parent=parent)
        self.setMouseTracking(True)

        pixmap = ImageCache.get_rsc_pixmap(
            u'todo_add', common.SECONDARY_BACKGROUND, common.INLINE_ICON_SIZE)
        self.setPixmap(pixmap)

        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setFixedHeight(common.INLINE_ICON_SIZE)

    def mouseReleaseEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.pressed.emit()


class RemoveButton(QtWidgets.QLabel):
    """Custom icon button to remove an item or close the editor."""

    def __init__(self, parent=None):
        super(RemoveButton, self).__init__(parent=parent)

        pixmap = ImageCache.get_rsc_pixmap(
            u'todo_remove', common.FAVOURITE, 32)
        self.setPixmap(pixmap)

        self.setFixedHeight(common.ROW_BUTTONS_HEIGHT)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    def mouseReleaseEvent(self, event):
        """We're handling the close event here."""
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.parent().parent().close()

    def dragEnterEvent(self, event):
        """Accepting the drag operation."""
        if event.mimeData().hasFormat(u'browser/todo-drag'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Drop event responsible for deleting an item from the todo list."""
        self.setUpdatesEnabled(False)

        editors_widget = self.parent().parent().editors
        idx = editors_widget.items.index(event.source())
        row = editors_widget.items.pop(idx)
        editors_widget.layout().removeWidget(row)
        row.deleteLater()

        self.setUpdatesEnabled(True)


class DragIndicatorButton(QtWidgets.QLabel):
    """Dotted button indicating a draggable item.

    The button is responsible for initiating a QDrag operation and setting the
    mime data. The data is populated with the `TodoEditor`'s text and the
    custom mime type (u'browser/todo-drag'). The latter is needed to accept the drag operation
    in the target drop widet.
    """

    def __init__(self, checked=False, parent=None):
        super(DragIndicatorButton, self).__init__(parent=parent)
        self.dragStartPosition = None

        self.setDisabled(checked)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setDisabled(self.isEnabled())

    def setDisabled(self, b):
        """Custom disabled function."""
        if b:
            pixmap = ImageCache.get_rsc_pixmap(
                u'drag_indicator', common.FAVOURITE, common.INLINE_ICON_SIZE)
        else:
            pixmap = ImageCache.get_rsc_pixmap(
                u'drag_indicator', common.SECONDARY_BACKGROUND, common.INLINE_ICON_SIZE)

        self.setPixmap(pixmap)

    def mousePressEvent(self, event):
        """Setting the starting drag position here."""
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.dragStartPosition = event.pos()

    def mouseMoveEvent(self, event):
        """The drag operation is initiated here."""
        if not isinstance(event, QtGui.QMouseEvent):
            return
        app = QtWidgets.QApplication.instance()
        left_button = event.buttons() & QtCore.Qt.LeftButton
        if not left_button:
            return

        parent_widget = self.parent()
        editor = parent_widget.findChild(TodoItemEditor)
        drag = QtGui.QDrag(parent_widget)

        # Setting Mime Data
        mime_data = QtCore.QMimeData()
        mime_data.setData(u'browser/todo-drag', QtCore.QByteArray(''))
        drag.setMimeData(mime_data)

        # Drag pixmap
        # Transparent image
        image = QtGui.QImage(editor.size(), QtGui.QImage.Format_ARGB32)
        editor.render(image)
        for x in xrange(image.width()):
            for y in xrange(image.height()):
                color = QtGui.QColor(image.pixel(x, y))
                color.setAlpha(150)
                image.setPixel(x, y, color.rgba())

        pixmap = QtGui.QPixmap()
        pixmap = pixmap.fromImage(image)

        drag.setPixmap(pixmap)
        drag.setHotSpot(QtCore.QPoint(0, pixmap.height() / 2.0))

        # Drag origin indicator
        pixmap = QtGui.QPixmap(parent_widget.size())

        painter = QtGui.QPainter()
        painter.begin(pixmap)
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200, 255)))
        painter.drawRect(pixmap.rect())
        painter.end()

        overlay_widget = QtWidgets.QLabel(parent=parent_widget)
        overlay_widget.setFixedSize(parent_widget.size())
        overlay_widget.setPixmap(pixmap)

        # Preparing the drag...
        remove_button = parent_widget.parent().parent(
        ).parent().parent().findChild(RemoveButton)
        # Ugh, ugly code...
        add_button = parent_widget.parent().parent().parent().parent().findChild(AddButton)
        pixmap = pixmap = ImageCache.get_rsc_pixmap(
            u'todo_remove', QtGui.QColor(255, 0, 0), 32)
        remove_button.setPixmap(pixmap)
        add_button.setHidden(True)
        parent_widget.parent().separator.setHidden(False)
        overlay_widget.show()

        # Starting the drag...
        drag.exec_(QtCore.Qt.CopyAction)

        # Cleanup after drag has finished...
        overlay_widget.close()
        overlay_widget.deleteLater()
        parent_widget.parent().separator.setHidden(True)
        pixmap = ImageCache.get_rsc_pixmap(
            u'todo_remove', common.FAVOURITE, 32)
        remove_button.setPixmap(pixmap)
        add_button.setHidden(False)


class CheckBoxButton(QtWidgets.QLabel):
    """Custom checkbox used for Todo Items."""

    clicked = QtCore.Signal(bool)

    def __init__(self, checked=False, parent=None):
        super(CheckBoxButton, self).__init__(parent=parent)
        self._checked = checked
        self._checked_pixmap = None
        self._unchecked_pixmap = None

        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.set_pixmap(self._checked)

        self._connectSignals()

    @property
    def checked(self):
        return self._checked

    def _connectSignals(self):
        self.clicked.connect(self.set_pixmap)

    def set_pixmap(self, checked):
        if checked:
            pixmap = ImageCache.get_rsc_pixmap(
                u'checkbox_unchecked', common.SECONDARY_BACKGROUND, 18)
            self.setPixmap(pixmap)
        else:
            pixmap = ImageCache.get_rsc_pixmap(
                u'checkbox_checked', common.FAVOURITE, 18)
            self.setPixmap(pixmap)

    def mouseReleaseEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self._checked = not self._checked
        self.clicked.emit(self._checked)


class Separator(QtWidgets.QLabel):
    def __init__(self, parent=None):
        super(Separator, self).__init__(parent=parent)
        pixmap = QtGui.QPixmap(QtCore.QSize(4096, 2))
        pixmap.fill(common.FAVOURITE)
        self.setPixmap(pixmap)

        self.setHidden(True)

        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        self.setFixedWidth(1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(u'browser/todo-drag'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Calling the parent's drop event, when the drop is on the separator."""
        self.parent().dropEvent(event)


class TodoEditors(QtWidgets.QWidget):
    """This is a convenience widget for storing the added todo items.

    As this is the container widget, it is responsible for handling the dragging
    and setting the order of the contained child widgets.

    Attributes:
        items (list):       The added todo items.

    """

    def __init__(self, parent=None):
        super(TodoEditors, self).__init__(parent=parent)
        QtWidgets.QVBoxLayout(self)
        self.layout().setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        self.layout().setContentsMargins(8, 8, 8, 8)
        self.layout().setSpacing(8)

        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.separator = Separator(parent=self)
        self.drop_target_index = -1

        self.items = []

        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def dragEnterEvent(self, event):
        """Accepting the drag operation."""
        if event.mimeData().hasFormat(u'browser/todo-drag'):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Custom drag move event responsible for indicating the drop area."""
        # Move indicator
        idx, y = self._separator_pos(event)

        if y == -1:
            self.separator.setHidden(True)
            self.drop_target_index = -1
            event.ignore()
            return

        event.accept()
        self.drop_target_index = idx

        self.separator.setHidden(False)
        pos = self.mapToGlobal(QtCore.QPoint(self.geometry().x(), y))
        self.separator.move(pos)
        self.separator.setFixedWidth(self.width())

    def dropEvent(self, event):
        if self.drop_target_index == -1:
            event.ignore()
            return

        event.accept()

        # Drag from another todo list
        if event.source() not in self.items:
            text = event.source().findChild(TodoItemEditor).document().toHtml()
            self.parent().parent().parent().add_item(idx=0, text=text, checked=False)
            self.separator.setHidden(True)
            return

        # Change internal order
        self.setUpdatesEnabled(False)

        self.items.insert(
            self.drop_target_index,
            self.items.pop(self.items.index(event.source()))
        )
        self.layout().removeWidget(event.source())
        self.layout().insertWidget(self.drop_target_index, event.source(), 0)

        self.setUpdatesEnabled(True)

    def _separator_pos(self, event):
        """Returns the position of"""
        idx = 0
        dis = []

        y = event.pos().y()

        # Collecting the available hot-spots for the drag operation
        lines = []
        for n in xrange(len(self.items)):
            if n == 0:  # first
                line = self.items[n].geometry().top()
                lines.append(line)
                continue

            line = (
                self.items[n - 1].geometry().bottom() +
                self.items[n].geometry().top()
            ) / 2.0
            lines.append(line)

            if n == len(self.items) - 1:  # last
                line = ((
                    self.items[n - 1].geometry().bottom() +
                    self.items[n].geometry().top()
                ) / 2.0)
                lines.append(line)
                line = self.items[n].geometry().bottom()
                lines.append(line)
                break

        # Finding the closest
        for line in lines:
            dis.append(y - line)

        # Cases when items is dragged from another editor instance
        if not dis:
            return 0, 0

        idx = dis.index(min(dis, key=abs))  # The selected line
        if event.source() not in self.items:
            source_idx = idx + 1
        else:
            source_idx = self.items.index(event.source())

        if idx == 0:  # first item
            return (0, lines[idx])
        elif source_idx == idx:  # order remains unchanged
            return (source_idx, lines[idx])
        elif (source_idx + 1) == idx:  # order remains unchanged
            return (source_idx, lines[idx])
        elif source_idx < idx:  # moves up
            return (idx - 1, lines[idx])
        elif source_idx > idx:  # move down
            return (idx, lines[idx])


class MoveWidget(QtWidgets.QWidget):
    """Widget used to move the editor window."""
    widgetMoved = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None):
        super(MoveWidget, self).__init__(parent=parent)
        self.setMouseTracking(True)

        self.move_in_progress = False
        self.move_start_event_pos = None
        self.move_start_widget_pos = None

    def mousePressEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.move_in_progress = True
        self.move_start_event_pos = event.pos()
        self.move_start_widget_pos = self.mapToGlobal(
            self.geometry().topLeft())

    def mouseMoveEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        if event.buttons() == QtCore.Qt.NoButton:
            return
        if self.move_start_widget_pos:
            offset = (event.pos() - self.move_start_event_pos)
            pos = self.mapToGlobal(self.geometry().topLeft()) + offset
            self.parent().move(pos)
            self.widgetMoved.emit(pos)


class TodoItemWidget(QtWidgets.QWidget):
    """The item-wrapper widget holding the checkbox, drag indicator and editor widgets."""

    def __init__(self, parent=None):
        super(TodoItemWidget, self).__init__(parent=parent)
        self.effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.effect.setOpacity(1.0)

        self.animation = QtCore.QPropertyAnimation(
            self.effect, QtCore.QByteArray('opacity'))
        self.animation.setDuration(1500)
        self.animation.setKeyValueAt(0, 0)
        self.animation.setKeyValueAt(0.5, 0.8)
        self.animation.setKeyValueAt(1, 1.0)

        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setGraphicsEffect(self.effect)
        self.setAutoFillBackground(True)

        self._createUI()

    def _createUI(self):
        QtWidgets.QHBoxLayout(self)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(6)


class ResizeWidget(QtWidgets.QWidget):
    """Widget used to move the editor window."""

    def __init__(self, parent=None):
        super(ResizeWidget, self).__init__(parent=parent)
        self.setMouseTracking(True)
        self.setFixedHeight(12)
        self.move_in_progress = False
        self.move_start_event_pos = None
        self.move_start_geo = None

    def mousePressEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.move_in_progress = True
        self.move_start_event_pos = event.pos()
        self.move_start_geo = self.parent().rect()

    def mouseMoveEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        if event.buttons() == QtCore.Qt.NoButton:
            return

        offset = (event.pos() - self.move_start_event_pos)
        if self.move_start_geo:
            rect = self.parent().geometry()
            rect.setRight(
                rect.left() + self.move_start_geo.width() + offset.x())
            rect.setBottom(rect.bottom() + offset.y())
            self.parent().setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if not isinstance(event, QtGui.QMouseEvent):
            return
        self.move_in_progress = False
        self.move_start_event_pos = None
        self.move_start_geo = None


class TodoEditorWidget(QtWidgets.QWidget):
    """Main widget containing the Todo items."""

    def __init__(self, index, parent=None):
        super(TodoEditorWidget, self).__init__(parent=parent)

        self.editors = None
        self._index = index

        self.setObjectName(u'todoitemswrapper')
        self.setWindowTitle(u'Todo Editor')
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.FramelessWindowHint
        )
        self.setMinimumWidth(640)
        self.setMinimumHeight(800)

        self._createUI()
        self.installEventFilter(self)

        if not index.isValid():
            return

        settings = AssetSettings(index)
        items = settings.value(u'config/todos')
        if not items:
            return

        for k in items:
            self.add_item(
                text=items[k][u'text'],
                checked=items[k][u'checked']
            )

        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.save_timer = QtCore.QTimer(parent=self)
        self.save_timer.setInterval(2000)
        self.save_timer.setSingleShot(False)
        self.save_timer.timeout.connect(self.save_settings)
        self.save_timer.start()

    @property
    def index(self):
        """The path used to initialize the widget."""
        return self._index

    def eventFilter(self, widget, event):
        """Using the custom event filter to paint the background."""
        if event.type() == QtCore.QEvent.Paint:
            painter = QtGui.QPainter()
            painter.begin(self)
            font = QtGui.QFont(common.SecondaryFont)
            font.setPointSize(common.MEDIUM_FONT_SIZE)
            painter.setFont(font)

            rect = QtCore.QRect(self.rect())
            center = rect.center()
            rect.setWidth(rect.width() - common.MARGIN)
            rect.setHeight(rect.height() - common.MARGIN)
            rect.moveCenter(center)

            text = u'No todo items in the list. Yet.\nYou can add a new item by clikcing the pencil icon on the top.'
            text = text if not len(self.editors.items) else u''
            common.draw_aliased_text(
                painter, font, rect, text, QtCore.Qt.AlignCenter, common.FAVOURITE)
            painter.end()
        return False

    def _get_next_enabled(self, n):
        hasEnabled = False
        for i in xrange(len(self.editors.items)):
            item = self.editors.items[i]
            editor = item.findChild(TodoItemEditor)
            if editor.isEnabled():
                hasEnabled = True
                break

        if not hasEnabled:
            return -1

        # Finding the next enabled editor
        for _ in xrange(len(self.editors.items) - n):
            n += 1
            if n >= len(self.editors.items):
                return self._get_next_enabled(-1)
            item = self.editors.items[n]
            editor = item.findChild(TodoItemEditor)
            if editor.isEnabled():
                return n

    def key_tab(self):
        """Defining tabbing forward between items."""
        if not self.editors.items:
            return

        n = 0
        for n, item in enumerate(self.editors.items):
            editor = item.findChild(TodoItemEditor)
            if editor.hasFocus():
                break

        n = self._get_next_enabled(n)
        if n > -1:
            item = self.editors.items[n]
            editor = item.findChild(TodoItemEditor)
            editor.setFocus()
            self.scrollarea.ensureWidgetVisible(
                editor, ymargin=editor.height())

    def key_return(self,):
        """Control enter toggles the state of the checkbox."""
        for item in self.editors.items:
            editor = item.findChild(TodoItemEditor)
            checkbox = item.findChild(CheckBoxButton)
            if editor.hasFocus():
                if not editor.document().toPlainText():
                    idx = self.editors.items.index(editor.parent())
                    row = self.editors.items.pop(idx)
                    self.editors.layout().removeWidget(row)
                    row.deleteLater()
                checkbox.clicked.emit(not checkbox.checked)
                break

    def keyPressEvent(self, event):
        """Custom keypresses."""
        no_modifier = event.modifiers() == QtCore.Qt.NoModifier
        control_modifier = event.modifiers() == QtCore.Qt.ControlModifier
        shift_modifier = event.modifiers() == QtCore.Qt.ShiftModifier

        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

        if shift_modifier:
            if event.key() == QtCore.Qt.Key_Tab:
                return True
            if event.key() == QtCore.Qt.Key_Backtab:
                return True

        if control_modifier:
            if event.key() == QtCore.Qt.Key_S:
                self.save_settings()
                return True
            elif event.key() == QtCore.Qt.Key_N:
                self.add_button.pressed.emit()
                return True
            elif event.key() == QtCore.Qt.Key_Tab:
                self.key_tab()
                return True
            elif event.key() == QtCore.Qt.Key_Return:
                self.key_return()

    def add_item(self, idx=None, text=None, checked=False):
        """Creates a new widget containing the checkbox, editor and drag widgets.

        The method is responsible for adding the item the EditorsWidget layout
        and the EditorsWidget.items property.

        """
        checkbox = CheckBoxButton(checked=not checked)
        checkbox.setFocusPolicy(QtCore.Qt.NoFocus)
        editor = TodoItemEditor(text, checked=not checked)
        editor.setFocusPolicy(QtCore.Qt.StrongFocus)
        drag = DragIndicatorButton(checked=False)
        drag.setFocusPolicy(QtCore.Qt.NoFocus)

        def toggle_disabled(b, widget=None):
            widget.setDisabled(not b)

        checkbox.clicked.connect(
            functools.partial(toggle_disabled, widget=editor))
        checkbox.clicked.connect(
            functools.partial(toggle_disabled, widget=drag))

        item = TodoItemWidget()
        item.layout().addWidget(checkbox)
        item.layout().addWidget(drag)
        item.layout().addWidget(editor, 1)

        if idx is None:
            self.editors.layout().addWidget(item, 0)
            self.editors.items.append(item)
        else:
            self.editors.layout().insertWidget(idx, item, 0)
            self.editors.items.insert(idx, item)

        item.animation.start()
        checkbox.clicked.emit(checkbox._checked)

        editor.setFocus()

        item.editor = editor
        return item

    @QtCore.Slot()
    def save_settings(self):
        """Saves the current list of todo items to the assets configuration file."""
        if not self.index.isValid():
            return
        settings = AssetSettings(self.index)
        todos = self._collect_data()
        settings.setValue(u'config/todos', todos)

        model = self.index.model()
        model.setData(self.index, len(todos), role=common.TodoCountRole)

    @QtCore.Slot()
    def add_new_item(self):
        """Adds a new item with some default styling."""
        html = u'<p>Edit me...</p>'
        self.add_item(text=html, idx=0)

    def _createUI(self):
        """Creates the ui layout."""
        QtWidgets.QVBoxLayout(self)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.remove_button = RemoveButton()
        self.remove_button.setFocusPolicy(QtCore.Qt.NoFocus)

        row = MoveWidget()
        row.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Minimum
        )
        row.setFocusPolicy(QtCore.Qt.NoFocus)

        QtWidgets.QHBoxLayout(row)
        self.add_button = AddButton()
        self.add_button.pressed.connect(self.add_new_item)
        self.add_button.pressed.connect(self.update)
        self.add_button.setFocusPolicy(QtCore.Qt.NoFocus)
        self.add_button.setFixedWidth(32)
        self.add_button.setFixedHeight(32)
        self.add_button.setAlignment(QtCore.Qt.AlignCenter)
        pixmap = ImageCache.get_rsc_pixmap(u'todo', common.FAVOURITE, 32)
        self.add_button.setPixmap(pixmap)
        row.layout().addWidget(self.add_button, 0)

        if self.index.isValid():
            parent = self.index.data(common.ParentRole)[-1]
            text = u'{} | Notes and Tasks'.format(parent.upper())
        else:
            text = u'Notes and Tasks'

        label = PaintedLabel(text, size=common.LARGE_FONT_SIZE)
        row.layout().addWidget(label, 1)
        row.layout().addWidget(self.remove_button, 0)

        self.editors = TodoEditors()
        self.setMinimumWidth(self.editors.minimumWidth() + 6)
        self.setMinimumHeight(100)

        self.scrollarea = QtWidgets.QScrollArea()
        self.scrollarea.setWidgetResizable(True)
        self.scrollarea.setWidget(self.editors)
        self.scrollarea.setFocusPolicy(QtCore.Qt.NoFocus)

        self.scrollarea.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.scrollarea.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.layout().addWidget(row)
        self.layout().addWidget(self.scrollarea)
        self.layout().addWidget(ResizeWidget())

        common.set_custom_stylesheet(self)

    def _collect_data(self):
        """Returns all the items found in the todo widget."""
        data = {}
        for n in xrange(len(self.editors.items)):
            item = self.editors.items[n]
            editor = item.findChild(TodoItemEditor)
            checkbox = item.findChild(CheckBoxButton)
            if not editor.document().toPlainText():
                continue
            data[n] = {
                u'checked': not checkbox.checked,
                u'text': editor.document().toHtml(),
            }
        return data

    def hideEvent(self, event):
        """Saving the contents on close/hide."""
        self.save_settings()

        cls = self.__class__.__name__
        local_settings.setValue(u'widget/{}/width'.format(cls), self.width())
        local_settings.setValue(u'widget/{}/height'.format(cls), self.height())

        pos = self.mapToGlobal(self.rect().topLeft())
        local_settings.setValue(u'widget/{}/x'.format(cls), pos.x())
        local_settings.setValue(u'widget/{}/y'.format(cls), pos.y())

    def focusOutEvent(self, event):
        if event.lostFocus():
            self.close()

    def sizeHint(self):
        return QtCore.QSize(800, 600)

    def showEvent(self, event):
        animation = QtCore.QPropertyAnimation(
            self, QtCore.QByteArray('windowOpacity'), parent=self)
        animation.setEasingCurve(QtCore.QEasingCurve.InQuad)
        animation.setDuration(150)
        animation.setStartValue(0.01)
        animation.setEndValue(1)
        animation.start(QtCore.QPropertyAnimation.DeleteWhenStopped)

        app = QtWidgets.QApplication.instance()
        geo = app.desktop().availableGeometry(self.parent())
        if geo:
            self.move(
                (geo.width() / 2) - (self.width() / 2),
                (geo.height() / 2) - (self.height() / 2)
            )

        cls = self.__class__.__name__
        width = local_settings.value(u'widget/{}/width'.format(cls))
        height = local_settings.value(u'widget/{}/height'.format(cls))
        x = local_settings.value(u'widget/{}/x'.format(cls))
        y = local_settings.value(u'widget/{}/y'.format(cls))

        if not all((width, height, x, y)):  # skip if not saved yet
            return
        size = QtCore.QSize(width, height)
        pos = QtCore.QPoint(x, y)

        self.move(pos)
        self.resize(size)
        common.move_widget_to_available_geo(self)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    index = QtCore.QModelIndex()
    widget = TodoEditorWidget(index)
    item = widget.add_item(
        text=u'This is a test link:\n\n\n\nClick this: file://gordo/jobs')
    widget.show()
    app.exec_()
