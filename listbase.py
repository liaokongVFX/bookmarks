# -*- coding: utf-8 -*-
"""Module defines the QListWidget items used to browse the projects and the files
found by the collector classes.

"""
# pylint: disable=E1101, C0103, R0913, I1101

import re
from PySide2 import QtWidgets, QtGui, QtCore

import mayabrowser.common as common
import mayabrowser.configparsers as configparser
from mayabrowser.configparsers import local_settings
from mayabrowser.configparsers import AssetSettings
from mayabrowser.actions import Actions
from mayabrowser.capture import ScreenGrabber
from mayabrowser.delegate import NoteEditor
from mayabrowser.delegate import ThumbnailEditor


class BaseContextMenu(Actions):
    """Base class for our custom context menu."""

    def __init__(self, index, parent=None):
        self.index = index
        super(BaseContextMenu, self).__init__(parent=parent)

    def add_actions(self):
        self.add_action_set(self.ActionSet)

    def favourite(self):
        """Toggles the favourite state of the item."""
        item = self.parent().currentItem()
        file_info = item.data(QtCore.Qt.PathRole)

        archived = item.flags() & configparser.MarkedAsArchived
        if archived: # Favouriting archived items are not allowed
            return

        favourites = local_settings.value('favourites')
        favourites = favourites if favourites else []
        if file_info.filePath() in favourites:
            item.setFlags(item.flags() & ~configparser.MarkedAsFavourite) # clears flag
            favourites.remove(file_info.filePath())
        else:
            favourites.append(file_info.filePath())
            item.setFlags(item.flags() | configparser.MarkedAsFavourite) # adds flag
        local_settings.setValue('favourites', favourites)

        self.parent().set_row_visibility()

    def isolate_favourites(self):
        """Hides all items except the items marked as favouire."""
        self.parent().show_favourites()

    def archived(self):
        """Marks the curent item as 'archived'."""
        data = self.index.data(QtCore.Qt.StatusTipRole)
        file_info = QtCore.QFileInfo(data)
        config = self.parent().Config(file_info.filePath())

        # Write the change to the config file.
        config.archived = not config.archived
        config.write_ini()

        # Set the flag
        flags = configparser.NoFlag
        if config.archived:
            flags = flags | configparser.MarkedAsArchived
        elif local_settings.is_favourite(file_info.fileName()):
            flags = flags | configparser.MarkedAsFavourite

        # Set the flag as custom user data
        item = self.parent().itemFromIndex(self.index)
        item.setData(
            QtCore.Qt.UserRole,
            flags
        )
        self.parent().set_row_visibility()

    def show_archived(self):
        self.parent().show_archived()


class BaseListWidget(QtWidgets.QListWidget):
    """Base class for the custom list widgets."""

    # Signals
    assetChanged = QtCore.Signal()
    sceneChanged = QtCore.Signal()
    sizeChanged = QtCore.Signal(QtCore.QSize)

    Delegate = NotImplementedError
    ContextMenu = NotImplementedError

    def __init__(self, parent=None):
        super(BaseListWidget, self).__init__(parent=parent)
        self._contextMenu = None

        self.fileSystemWatcher = QtCore.QFileSystemWatcher(parent=self)

        self.setItemDelegate(self.Delegate(parent=self))
        self.setSortingEnabled(False)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMouseTracking(True)
        self.installEventFilter(self)
        self.viewport().installEventFilter(self)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(True)

        # Scrollbar visibility
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Style
        common.set_custom_stylesheet(self)

        # Keyboard search timer and placeholder string.
        self.timer = QtCore.QTimer(parent=self)
        app = QtCore.QCoreApplication.instance()
        self.timer.setInterval(app.keyboardInputInterval())
        self.timer.setSingleShot(True)
        self.timed_search_string = ''

        self.add_items()
        self.set_row_visibility()
        self._connectSignals()

        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)


    @property
    def filter(self):
        """The current filter."""
        val = local_settings.value('widget/{}/filter'.format(self.__class__.__name__))
        return val if val else False

    @filter.setter
    def filter(self, val):
        local_settings.setValue('widget/{}/filter'.format(self.__class__.__name__), val)

    @property
    def show_favourites_mode(self):
        """The current show favourites state as saved in the local configuration file."""
        val = local_settings.value('widget/{}/show_favourites'.format(self.__class__.__name__))
        return val if val else False

    @show_favourites_mode.setter
    def show_favourites_mode(self, val):
        local_settings.setValue('widget/{}/show_favourites'.format(self.__class__.__name__), val)

    @property
    def show_archived_mode(self):
        """The current Show archived state as saved in the local configuration file."""
        val = local_settings.value('widget/{}/show_archived'.format(self.__class__.__name__))
        return val if val else False

    @show_archived_mode.setter
    def show_archived_mode(self, val):
        local_settings.setValue('widget/{}/show_archived'.format(self.__class__.__name__), val)

    @property
    def sort_order(self):
        val = local_settings.value('widget/{}/sort_order'.format(self.__class__.__name__))
        return val if val else False

    @sort_order.setter
    def sort_order(self, val):
        local_settings.setValue('widget/{}/sort_order'.format(self.__class__.__name__), val)

    def capture_thumbnail(self):
        """Captures a thumbnail for the current item using ScreenGrabber."""
        item = self.currentItem()

        if not item:
            return

        settings = AssetSettings(item.data(QtCore.Qt.PathRole).filePath())

        # Deleting the thumbnail from our image cache
        if settings.thumbnail_path() in common.IMAGE_CACHE:
            del common.IMAGE_CACHE[settings.thumbnail_path()]

        # Saving the image
        ScreenGrabber.screen_capture_file(output_path=settings.thumbnail_path())

        rect = self.visualRect(self.currentIndex())

        # Placeholder
        if common.PLACEHOLDER in common.IMAGE_CACHE:
            placeholder = common.IMAGE_CACHE[common.PLACEHOLDER]
        else:
            placeholder = QtGui.QImage()
            placeholder.load(common.PLACEHOLDER)
            placeholder = ThumbnailEditor.smooth_copy(
                placeholder,
                rect.height()
            )
            common.IMAGE_CACHE[common.PLACEHOLDER] = placeholder


        image = QtGui.QImage()
        image.load(settings.thumbnail_path())
        if image.isNull():
            image = placeholder
        else:
            image = ThumbnailEditor.smooth_copy(
                image,
                rect.height()
            )
            common.IMAGE_CACHE[settings.thumbnail_path()] = image
            common.IMAGE_CACHE[settings.thumbnail_path() + 'BG'] = common.get_color_average(image)


    def remove_thumbnail(self):
        """Deletes the given thumbnail."""
        item = self.currentItem()
        settings = AssetSettings(item.data(QtCore.Qt.PathRole).filePath())
        rect = self.visualRect(self.currentIndex())

        # Placeholder
        if common.PLACEHOLDER in common.IMAGE_CACHE:
            placeholder = common.IMAGE_CACHE[common.PLACEHOLDER]
        else:
            placeholder = QtGui.QImage()
            placeholder.load(common.PLACEHOLDER)
            placeholder = ThumbnailEditor.smooth_copy(
                placeholder,
                rect.height()
            )
            common.IMAGE_CACHE[common.PLACEHOLDER] = placeholder

        f = QtCore.QFile(settings.thumbnail_path())

        if f.exists():
            f.remove()

        if settings.thumbnail_path() in common.IMAGE_CACHE:
            del common.IMAGE_CACHE[settings.thumbnail_path()]

        image = QtGui.QImage()
        image.load(settings.thumbnail_path())
        if image.isNull():
            image = placeholder
        else:
            image = ThumbnailEditor.smooth_copy(
                image,
                rect.height()
            )
            common.IMAGE_CACHE[settings.thumbnail_path()] = image




    def _paint_widget_background(self):
        """Our list widgets arer see-through, because of their drop-shadow.
        Hence, we manually have to paint a solid background to them.

        """
        rect = QtCore.QRect(self.viewport().rect())
        rect.moveLeft(rect.left())

        painter = QtGui.QPainter()
        painter.begin(self)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(50, 50, 50)))
        painter.drawRect(rect)
        painter.end()

    def action_on_enter_key(self):
        raise NotImplementedError('Method is abstract.')

    def key_down(self):
        """Custom action tpo perform when the `down` arrow is pressed
        on the keyboard.

        """
        visible_items = [self.item(n) for n in xrange(
            self.count()) if not self.item(n).isHidden()]
        if visible_items:  # jumping to the beginning of the list after the last item
            if self.currentItem() is visible_items[-1]:
                self.setCurrentItem(
                    visible_items[0],
                    QtCore.QItemSelectionModel.ClearAndSelect
                )
                return
        for n in xrange(self.count()):
            if self.item(n).isHidden():
                continue
            if self.currentRow() >= n:
                continue

            self.setCurrentItem(
                self.item(n),
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            break

    def key_up(self):
        """Custom action to perform when the `up` arrow is pressed
        on the keyboard.

        """
        visible_items = [self.item(n) for n in xrange(
            self.count()) if not self.item(n).isHidden()]
        if visible_items:  # jumping to the end of the list after the first item
            if self.currentItem() is visible_items[0]:
                self.setCurrentItem(
                    visible_items[-1],
                    QtCore.QItemSelectionModel.ClearAndSelect
                )
                return
        if self.currentRow() == -1:
            self.setCurrentItem(
                visible_items[0],
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return
        for n in reversed(xrange(self.count())):
            if self.item(n).isHidden():
                continue
            if self.currentRow() <= n:
                continue

            self.setCurrentItem(
                self.item(n),
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            break

    def key_tab(self):
        self.setUpdatesEnabled(False)

        cursor = QtGui.QCursor()
        opos = cursor.pos()
        rect = self.visualRect(self.currentIndex())
        rect, _, _ = self.itemDelegate().get_description_rect(rect)
        pos = self.mapToGlobal(rect.topLeft())
        cursor.setPos(pos)
        self.editItem(self.currentItem())
        cursor.setPos(opos)

        self.setUpdatesEnabled(True)

    def keyPressEvent(self, event):
        """Customized key actions.

        We're defining the default behaviour of the list-items here, including
        defining the actions needed to navigate the list using keyboard presses.

        """
        numpad_modifier = event.modifiers() & QtCore.Qt.KeypadModifier
        no_modifier = event.modifiers() == QtCore.Qt.NoModifier
        if no_modifier or numpad_modifier:
            if event.key() == QtCore.Qt.Key_Escape:
                pass
            elif event.key() == QtCore.Qt.Key_Down:
                self.key_down()
            elif event.key() == QtCore.Qt.Key_Up:
                self.key_up()
            elif (event.key() == QtCore.Qt.Key_Return) or (event.key() == QtCore.Qt.Key_Enter):
                self.action_on_enter_key()
            elif event.key() == QtCore.Qt.Key_Tab:
                self.key_down()
                self.key_tab()
            elif event.key() == QtCore.Qt.Key_Backtab:
                self.key_up()
                self.key_tab()
            else:  # keyboard search and select
                if not self.timer.isActive():
                    self.timed_search_string = ''
                    self.timer.start()

                self.timed_search_string += event.text()
                self.timer.start()  # restarting timer on input

                visible_items = [self.item(n) for n in xrange(
                    self.count()) if not self.item(n).isHidden()]
                for item in visible_items:
                    # When only one key is pressed we want to cycle through
                    # only items starting with that letter:
                    if len(self.timed_search_string) == 1:
                        if self.row(item) <= self.row(self.currentItem()):
                            continue
                        if item.data(QtCore.Qt.DisplayRole)[0].lower() == self.timed_search_string.lower():
                            self.setCurrentItem(
                                item,
                                QtCore.QItemSelectionModel.ClearAndSelect
                            )
                            break
                    else:
                        match = re.search(
                            '{}'.format(self.timed_search_string),
                            item.data(QtCore.Qt.DisplayRole),
                            flags=re.IGNORECASE
                        )
                        if match:
                            self.setCurrentItem(
                                item,
                                QtCore.QItemSelectionModel.ClearAndSelect
                            )
                            break

        if event.modifiers() & QtCore.Qt.ControlModifier:
            self.action_on_custom_keys(event)
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            if event.key() == QtCore.Qt.Key_Tab:
                self.key_up()
                self.key_tab()
            elif event.key() == QtCore.Qt.Key_Backtab:
                self.key_up()
                self.key_tab()

    def count_visible(self):
        """Counts the visible list-items.

        Returns:
            int: The number of visible of items.

        """
        c = 0
        for n in xrange(self.count()):
            if not self.item(n).isHidden():
                c += 1
        return c

    def custom_doubleclick_event(self, index):
        """Action to perform on double-click. Abstract method needs to be overriden in the subclass.
        """
        raise NotImplementedError('custom_doubleclick_event() is abstract.')

    def mouseDoubleClickEvent(self, event):
        """Custom double-click event.

        A double click can `open` an item, or it can trigger an edit event.
        As each item is associated with multiple editors, we have to filter
        the double-click event before calling the item delegate's `createEditor`
        method.

        Finally `custom_doubleclick_event` is called - this method has to be implemented
        in the subclass.

        """
        super(BaseListWidget, self).mouseDoubleClickEvent(event)
        index = self.indexAt(event.pos())
        rect = self.visualRect(index)

        parent = self.viewport()
        option = self.viewOptions()

        note_rect, _, _ = self.itemDelegate().get_description_rect(rect)
        thumbnail_rect = self.itemDelegate().get_thumbnail_rect(rect)
        location_rect = self.itemDelegate().get_location_editor_rect(rect)

        if note_rect.contains(event.pos()):
            editor = NoteEditor(index, parent=self)
            editor.show()
        elif thumbnail_rect.contains(event.pos()):
            self.itemDelegate().createEditor(parent, option, index, editor=2)
        elif location_rect.contains(event.pos()):
            self.itemDelegate().createEditor(parent, option, index, editor=3)
        else:
            self.custom_doubleclick_event(index)


    def resizeEvent(self, event):
        """Custom resize event."""
        self.sizeChanged.emit(self.viewport().size())
        super(BaseListWidget, self).resizeEvent(event)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        self._contextMenu = self.ContextMenu(index, parent=self)
        if index.isValid():
            rect = self.visualRect(index)
            self._contextMenu.setFixedWidth(self.viewport().rect().width())
            self._contextMenu.show()
            self._contextMenu.move(
                self.viewport().mapToGlobal(rect.bottomLeft()))
        else:
            self._contextMenu.setFixedWidth(self.viewport().rect().width())
            self._contextMenu.show()
            cursor_pos = QtGui.QCursor().pos()
            self._contextMenu.move(
                self.viewport().mapToGlobal(self.viewport().rect().topLeft()).x(),
                cursor_pos.y()
            )
        self._contextMenu.move(self._contextMenu.x(), self._contextMenu.y())

        common.move_widget_to_available_geo(self._contextMenu)

    def _connectSignals(self):
        self.fileSystemWatcher.directoryChanged.connect(self.refresh)
        # self.fileSystemWatcher.fileChanged.connect(self.refresh)


    def set_current_item_as_active(self):
        """Sets the current item item as ``active``."""
        item = self.currentItem()

        if not item:
            return

        archived = item.flags() & configparser.MarkedAsArchived
        if archived:
            return

        # Set flags
        active_item = self.active_item()
        if active_item:
            active_item.setFlags(active_item.flags() & ~
                                 configparser.MarkedAsActive)
        item.setFlags(item.flags() | configparser.MarkedAsActive)


    def active_item(self):
        """Return the ``active`` item.

        The active item is indicated by the ``configparser.MarkedAsActive`` flag.
        If no item has been flagged as `active`, returns ``None``.
        """
        for n in xrange(self.count()):
            item = self.item(n)
            if item.flags() & configparser.MarkedAsActive:
                return item
        return None

    def set_row_visibility(self):
        """Sets the visibility of the list-items based on modes and options."""
        for n in xrange(self.count()):
            item = self.item(n)

            markedAsArchived = item.flags() & configparser.MarkedAsArchived
            markedAsFavourite = item.flags() & configparser.MarkedAsFavourite

            if self.show_archived_mode and self.show_favourites_mode:
                if markedAsFavourite:
                    item.setHidden(False)
                    continue
                item.setHidden(True)
                continue
            elif not self.show_archived_mode and self.show_favourites_mode:
                if markedAsFavourite:
                    item.setHidden(False)
                    continue
                item.setHidden(True)
                continue
            elif self.show_archived_mode and not self.show_favourites_mode:
                item.setHidden(False)
                continue
            elif not self.show_archived_mode and not self.show_favourites_mode:
                item.setHidden(markedAsArchived)

    def show_archived(self):
        self.show_archived_mode = not self.show_archived_mode
        self.set_row_visibility()

    def show_favourites(self):
        self.show_favourites_mode = not self.show_favourites_mode
        self.set_row_visibility()

    def paint_message(self, text):
        """Paints a custom message onto the list widget."""
        painter = QtGui.QPainter()
        painter.begin(self)
        rect = QtCore.QRect(self.viewport().rect())
        rect.moveLeft(rect.left())  # offsetting by the margin
        rect.setWidth(self.rect().width())

        painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        painter.setPen(QtGui.QPen(common.SECONDARY_TEXT))


        painter.drawText(
            rect,
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap,
            text
        )

        painter.end()
