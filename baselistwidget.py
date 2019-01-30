# -*- coding: utf-8 -*-
# pylint: disable=E1101, C0103, R0913, I1101
"""Module defines the QListWidget items used to browse the projects and the files
found by the collector classes.

"""

import re
import functools
import collections
from PySide2 import QtWidgets, QtGui, QtCore

import mayabrowser.common as common
import mayabrowser.editors as editors
from mayabrowser.settings import MarkedAsActive, MarkedAsArchived, MarkedAsFavourite
from mayabrowser.settings import local_settings
from mayabrowser.settings import AssetSettings
from mayabrowser.capture import ScreenGrabber
from mayabrowser.spinner import Spinner

class BaseContextMenu(QtWidgets.QMenu):
    """Custom context menu associated with the BaseListWidget.
    The menu and the actions are always associated with a ``QModelIndex``
    from the list widget.

    The menu structure is defined by key/value pares stored in an OrderedDict.

    Properties:
        index (QModelIndex): The index the context menu is associated with.

    Methods:
        create_menu():  Populates the menu with actions based on the ``menu_set`` given.

    """

    def __init__(self, index, parent=None):
        super(BaseContextMenu, self).__init__(parent=parent)
        self.index = index
        self.setToolTipsVisible(True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowFlags(
            QtCore.Qt.NoDropShadowWindowHint |
            QtCore.Qt.Popup |
            QtCore.Qt.FramelessWindowHint
        )

    def create_menu(self, menu_set, parent=None):
        """This action populates the menu using the action-set dictionaries,
        and it automatically connects the action with a corresponding method based
        on the key/method-name.

        Args:
            menu_set (OrderedDict):    The set of menu items. See keys below.
            parent (QMenu):

        Implemented keys:
            action_set[k]['action'] (bool): The action to execute when the item is clicked.
            action_set[k]['text'] (str): The action's text
            action_set[k]['data'] (object): User data stored in the action
            action_set[k]['disabled'] (bool): Sets wheter the item is disabled.
            action_set[k]['tool_tip'] (str):The description of the action.
            action_set[k]['status_tip'] (str): The description of the action.
            action_set[k]['icon'] (QPixmap): The action's icon.
            action_set[k]['shortcut'] (QKeySequence): The action's icon.
            action_set[k]['checkable'] (bool): Sets wheter the item is checkable.
            action_set[k]['checked'] (bool): The state of the checkbox.
            action_set[k]['visible'] (bool): The visibility of the action.

        """
        if not parent:
            parent = self

        for k in menu_set:
            if ':' in k:  # Skipping `speudo` keys
                continue

            # Recursive menu creation
            if isinstance(menu_set[k], collections.OrderedDict):
                parent = QtWidgets.QMenu(k, parent=self)

                # width = self.parent().viewport().geometry().width()
                # width = (width * 0.5) if width > 400 else width
                # parent.setFixedWidth(width)

                if '{}:icon'.format(k) in menu_set:
                    icon = QtGui.QIcon(menu_set['{}:icon'.format(k)])
                    parent.setIcon(icon)
                self.addMenu(parent)
                self.create_menu(menu_set[k], parent=parent)
                continue

            if 'separator' in k:
                parent.addSeparator()
                continue

            action = parent.addAction(k)

            if 'data' in menu_set[k]:  # Skipping disabled items
                action.setData(menu_set[k]['data'])
            if 'disabled' in menu_set[k]:  # Skipping disabled items
                action.setDisabled(menu_set[k]['disabled'])
            if 'action' in menu_set[k]:
                if isinstance(menu_set[k]['action'], collections.Iterable):
                    for func in menu_set[k]['action']:
                        action.triggered.connect(func)
                else:
                    action.triggered.connect(menu_set[k]['action'])
            if 'text' in menu_set[k]:
                action.setText(menu_set[k]['text'])
            else:
                action.setText(k)
            if 'status_tip' in menu_set[k]:
                action.setStatusTip(menu_set[k]['status_tip'])
            if 'tool_tip' in menu_set[k]:
                action.setToolTip(menu_set[k]['tool_tip'])
            if 'checkable' in menu_set[k]:
                action.setCheckable(menu_set[k]['checkable'])
            if 'checked' in menu_set[k]:
                action.setChecked(menu_set[k]['checked'])
            if 'icon' in menu_set[k]:
                action.setIconVisibleInMenu(True)
                action.setIcon(menu_set[k]['icon'])
            if 'shortcut' in menu_set[k]:
                action.setShortcut(menu_set[k]['shortcut'])
            if 'visible' in menu_set[k]:
                action.setVisible(menu_set[k]['visible'])
            else:
                action.setVisible(True)

    def showEvent(self, event):
        """Elides the action text to fit the size of the widget upon showing."""
        for action in self.actions():
            if not action.text():
                continue

            metrics = QtGui.QFontMetrics(self.font())
            text = metrics.elidedText(
                action.text(),
                QtCore.Qt.ElideMiddle,
                self.width() - 32 - 10  # padding set in the stylesheet
            )
            action.setText(text)

    def add_sort_menu(self):
        """Creates the menu needed to set the sort-order of the list."""
        sort_menu_icon = common.get_rsc_pixmap('sort', common.FAVOURITE, 18.0)
        arrow_up_icon = common.get_rsc_pixmap(
            'arrow_up', common.FAVOURITE, 18.0)
        arrow_down_icon = common.get_rsc_pixmap(
            'arrow_down', common.FAVOURITE, 18.0)
        item_off_icon = common.get_rsc_pixmap('item_off', common.TEXT, 18.0)
        item_on_icon = common.get_rsc_pixmap(
            'item_on', common.TEXT_SELECTED, 18.0)

        sort_by_name = self.parent().model().sortkey == common.SortByName
        sort_modified = self.parent().model().sortkey == common.SortByLastModified
        sort_created = self.parent().model().sortkey == common.SortByLastCreated
        sort_size = self.parent().model().sortkey == common.SortBySize

        menu_set = collections.OrderedDict()
        menu_set['Sort'] = collections.OrderedDict()
        menu_set['Sort:icon'] = sort_menu_icon
        menu_set['Sort']['Order'] = {
            'text': 'Ascending' if self.parent().model().sortorder else 'Descending',
            'ckeckable': True,
            'checked': True if self.parent().model().sortorder else False,
            'icon': arrow_down_icon if self.parent().model().sortorder else arrow_up_icon,
            'action': functools.partial(self.parent().model().set_sortorder,
                                        not self.parent().model().sortorder)
        }

        menu_set['Sort']['separator'] = {}

        menu_set['Sort']['Name'] = {
            'icon': item_on_icon if sort_by_name else item_off_icon,
            'ckeckable': True,
            'checked': True if sort_by_name else False,
            'action': functools.partial(
                self.parent().model().set_sortkey, common.SortByName)
        }
        menu_set['Sort']['Date modified'] = {
            'icon': item_on_icon if sort_modified else item_off_icon,
            'ckeckable': True,
            'checked': True if sort_modified else False,
            'action': functools.partial(self.parent().model().set_sortkey,
                                        common.SortByLastModified)
        }
        menu_set['Sort']['Date created'] = {
            'icon': item_on_icon if sort_created else item_off_icon,
            'ckeckable': True,
            'checked': True if sort_created else False,
            'action': functools.partial(self.parent().model().set_sortkey,
                                        common.SortByLastCreated)
        }
        menu_set['Sort']['Size'] = {
            'icon': item_on_icon if sort_size else item_off_icon,
            'ckeckable': True,
            'checked': True if sort_size else False,
            'action': functools.partial(self.parent().model().set_sortkey,
                                        common.SortBySize)
        }
        menu_set['separator'] = {}
        self.create_menu(menu_set)

    def add_reveal_folder_menu(self):
        """Creates a menu containing"""
        folder_icon = common.get_rsc_pixmap(
            'folder', common.SECONDARY_TEXT, 18.0)
        folder_icon2 = common.get_rsc_pixmap('folder', common.FAVOURITE, 18.0)

        menu_set = collections.OrderedDict()

        key = 'Show in File Manager'
        menu_set['separator>'] = {}
        menu_set[key] = collections.OrderedDict()
        menu_set['{}:icon'.format(key)] = folder_icon

        if len(self.index.data(common.ParentRole)) >= 4:
            file_info = QtCore.QFileInfo(
                self.index.data(QtCore.Qt.StatusTipRole))
            menu_set[key]['file'] = {
                'text': 'Show file',
                'icon': folder_icon2,
                'action': functools.partial(
                    common.reveal,
                    '/'.join(self.index.data(common.ParentRole)))
            }
            path = '{}/{}/{}/{}'.format(
                self.index.data(common.ParentRole)[0],
                self.index.data(common.ParentRole)[1],
                self.index.data(common.ParentRole)[2],
                self.index.data(common.ParentRole)[3],
            )
            menu_set[key]['asset'] = {
                'text': 'Show asset',
                'icon': folder_icon2,
                'action': functools.partial(
                    common.reveal, path)
            }
        elif len(self.index.data(common.ParentRole)) == 3:
            menu_set[key]['asset'] = {
                'text': 'Show asset',
                'icon': folder_icon2,
                'action': functools.partial(common.reveal,
                                            self.index.data(QtCore.Qt.StatusTipRole))
            }
        menu_set[key]['root'] = {
            'text': 'Show bookmark',
            'icon': folder_icon2,
            'action': functools.partial(
                common.reveal,
                QtCore.QFileInfo('{}/{}/{}'.format(
                    self.index.data(common.ParentRole)[0],
                    self.index.data(common.ParentRole)[1],
                    self.index.data(common.ParentRole)[2]
                )).filePath()),
        }
        menu_set[key]['separator.'] = {}
        menu_set[key]['job'] = {
            'text': 'Show job folder',
            'icon': folder_icon2,
            'action': functools.partial(
                common.reveal,
                QtCore.QFileInfo('{}/{}'.format(
                    self.index.data(common.ParentRole)[0],
                    self.index.data(common.ParentRole)[1]
                )).filePath())
        }

        menu_set[key]['separator'] = {}

        it = QtCore.QDirIterator(
            '/'.join(self.index.data(common.ParentRole)),
            flags=QtCore.QDirIterator.NoIteratorFlags,
            filters=QtCore.QDir.NoDotAndDotDot |
            QtCore.QDir.Dirs |
            QtCore.QDir.NoSymLinks |
            QtCore.QDir.Readable
        )
        items = []
        while it.hasNext():
            path = it.next()
            file_info = QtCore.QFileInfo(path)
            items.append(file_info)

        if not self.parent().model().sortorder:
            items = sorted(
                items, key=common.sort_keys[self.parent().model().sortkey])
        else:
            items = list(
                reversed(sorted(items, key=common.sort_keys[self.parent().model().sortkey])))

        for file_info in items:
            if file_info.fileName()[0] == '.':
                continue
            if not file_info.isDir():
                continue

            menu_set[key][file_info.fileName()] = {
                'text': file_info.fileName().upper(),
                'icon': folder_icon,
                'action': functools.partial(
                    common.reveal,
                    file_info.filePath())
            }
        self.create_menu(menu_set)

    def add_copy_menu(self):
        """Menu containing the subfolders of the selected item."""
        copy_icon = common.get_rsc_pixmap('copy', common.SECONDARY_TEXT, 18.0)
        copy_icon2 = common.get_rsc_pixmap('copy', common.FAVOURITE, 18.0)

        menu_set = collections.OrderedDict()

        path = self.index.data(QtCore.Qt.StatusTipRole)
        url = QtCore.QUrl().fromLocalFile(path).toString()

        key = 'Copy path'
        menu_set[key] = collections.OrderedDict()
        menu_set['{}:icon'.format(key)] = copy_icon

        menu_set[key]['windows1'] = {
            'text': 'Windows  -  \\\\back\\slashes',
            'icon': copy_icon2,
            'action': functools.partial(
                QtGui.QClipboard().setText,
                QtCore.QDir.toNativeSeparators(path))
        }
        menu_set[key]['windows2'] = {
            'text': 'Windows  -  //forward/slashes',
            'icon': copy_icon2,
            'action': functools.partial(QtGui.QClipboard().setText, path)
        }
        menu_set[key]['slack'] = {
            'text': 'URL  -  file://Slack/friendly',
            'icon': copy_icon2,
            'action': functools.partial(QtGui.QClipboard().setText, url)
        }
        menu_set[key]['macos'] = {
            'text': 'SMB  -  smb://MacOS/path',
            'icon': copy_icon2,
            'action': functools.partial(
                QtGui.QClipboard().setText,
                url.replace('file://', 'smb://'))
        }
        self.create_menu(menu_set)

    def add_mode_toggles_menu(self):
        """Ads the menu-items needed to add set favourite or archived status."""
        favourite_on_icon = common.get_rsc_pixmap(
            'favourite', common.FAVOURITE, 18.0)
        favourite_off_icon = common.get_rsc_pixmap(
            'favourite', common.SECONDARY_TEXT, 18.0)
        archived_on_icon = common.get_rsc_pixmap(
            'archived', common.FAVOURITE, 18.0)
        archived_off_icon = common.get_rsc_pixmap(
            'archived', common.TEXT, 18.0)

        favourite = self.index.flags() & MarkedAsFavourite
        archived = self.index.flags() & MarkedAsArchived
        source_index = self.parent().model().mapToSource(self.index)

        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}
        if self.__class__.__name__ == 'BookmarksWidgetContextMenu':
            text = 'Remove bookmark'
        else:
            text = 'Enable' if archived else 'Disable'
        menu_set['archived'] = {
            'text': text,
            'icon': archived_off_icon if archived else archived_on_icon,
            'checkable': True,
            'checked': archived,
            'action': functools.partial(self.parent().toggle_archived, index=source_index, state=not archived)
        }
        menu_set['favourite'] = {
            'text': 'Remove from favourites' if favourite else 'Mark as favourite',
            'icon': favourite_off_icon if favourite else favourite_on_icon,
            'checkable': True,
            'checked': favourite,
            'action': functools.partial(self.parent().toggle_favourite, index=source_index, state=not favourite)
        }

        self.create_menu(menu_set)

    def add_display_toggles_menu(self):
        """Ads the menu-items needed to add set favourite or archived status."""
        item_on = common.get_rsc_pixmap(
            'item_on', common.TEXT_SELECTED, 18.0)
        item_off = common.get_rsc_pixmap(
            'item_off', common.SECONDARY_TEXT, 18.0)

        favourite = self.parent().model().get_filtermode('favourite')
        archived = self.parent().model().get_filtermode('archived')

        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}
        menu_set['toggle_favoruites'] = {
            'text': 'Show favourites only',
            'icon': item_on if favourite else item_off,
            'checkable': True,
            'checked': favourite,
            'action':
                functools.partial(
                    self.parent().model().set_filtermode,
                    'favourite',
                    not favourite
                ),
        }
        menu_set['toggle_archived'] = {
            'text': 'Show archived items',
            'icon': item_on if archived else item_off,
            'checkable': True,
            'checked': archived,
            'disabled': favourite,
            'action':
                functools.partial(
                    self.parent().model().set_filtermode,
                    'archived',
                    not archived
                ),
        }

        self.create_menu(menu_set)

    def add_refresh_menu(self):
        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}
        menu_set['Refresh'] = {
            'action': self.parent().refresh
        }
        if self.index:
            menu_set['Activate'] = {
                'action': self.parent().activate_current_index
            }

        self.create_menu(menu_set)

    def add_thumbnail_menu(self):
        """Menu for thumbnail operations."""
        capture_thumbnail_pixmap = common.get_rsc_pixmap(
            'capture_thumbnail', common.SECONDARY_TEXT, 18.0)
        pick_thumbnail_pixmap = common.get_rsc_pixmap(
            'pick_thumbnail', common.SECONDARY_TEXT, 18.0)
        pick_thumbnail_pixmap = common.get_rsc_pixmap(
            'pick_thumbnail', common.SECONDARY_TEXT, 18.0)
        revomove_thumbnail_pixmap = common.get_rsc_pixmap(
            'todo_remove', common.FAVOURITE, 18.0)
        show_thumbnail = common.get_rsc_pixmap(
            'active', common.FAVOURITE, 18.0)

        menu_set = collections.OrderedDict()
        key = 'Thumbnail'
        menu_set['separator'] = {}
        menu_set[key] = collections.OrderedDict()
        menu_set['{}:icon'.format(key)] = capture_thumbnail_pixmap

        settings = AssetSettings(self.index)

        if QtCore.QFileInfo(settings.thumbnail_path()).exists():
            menu_set[key]['Show thumbnail'] = {
                'icon': show_thumbnail,
                'action': functools.partial(
                    editors.ThumbnailViewer,
                    self.index,
                    parent=self.parent()
                )
            }
            menu_set[key]['separator'] = {}
        menu_set[key]['Capture new'] = {
            'icon': capture_thumbnail_pixmap,
            'action': self.parent().capture_thumbnail
        }
        menu_set[key]['Pick new'] = {
            'icon': pick_thumbnail_pixmap,
            'action': functools.partial(
                editors.ThumbnailEditor,
                self.index
            )
        }
        if QtCore.QFileInfo(settings.thumbnail_path()).exists():
            menu_set[key]['separator.'] = {}
            menu_set[key]['Remove'] = {
                'action': self.parent().remove_thumbnail,
                'icon': revomove_thumbnail_pixmap
            }

        self.create_menu(menu_set)

    def add_add_bookmark_menu(self):
        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}
        menu_set['Add bookmark'] = {
            'text': 'Add bookmark',
            'action': self.parent().show_add_bookmark_widget
        }

        self.create_menu(menu_set)

    def add_collapse_sequence_menu(self):
        """Adds the menu needed to change context"""
        if self.parent().model().sourceModel().get_location() == common.RendersFolder:
            return  # Render sequences are always collapsed

        expand_pixmap = common.get_rsc_pixmap(
            'expand', common.SECONDARY_TEXT, 18.0)
        collapse_pixmap = common.get_rsc_pixmap(
            'collapse', common.FAVOURITE, 18.0)

        collapsed = self.parent().model().sourceModel().is_grouped()

        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}

        menu_set['collapse'] = {
            'text': 'Show individual files' if collapsed else 'Group sequences together',
            'icon': expand_pixmap if collapsed else collapse_pixmap,
            'checkable': True,
            'checked': collapsed,
            'action': functools.partial(
                self.parent().model().sourceModel().set_grouped, not collapsed)
        }

        self.create_menu(menu_set)

    def add_location_toggles_menu(self):
        """Adds the menu needed to change context"""
        locations_icon_pixmap = common.get_rsc_pixmap(
            'location', common.TEXT_SELECTED, 18.0)
        item_on_pixmap = common.get_rsc_pixmap(
            'item_on', common.TEXT_SELECTED, 18.0)
        item_off_pixmap = common.get_rsc_pixmap(
            'item_off', common.TEXT_SELECTED, 18.0)

        menu_set = collections.OrderedDict()
        menu_set['separator'] = {}

        key = 'Switch location'

        menu_set[key] = collections.OrderedDict()
        menu_set['{}:icon'.format(key)] = locations_icon_pixmap

        for k in sorted(list(common.NameFilters)):
            checked = self.parent().model().sourceModel().get_location() == k
            menu_set[key][k] = {
                'text': k.title(),
                'checkable': True,
                'checked': checked,
                'icon': item_on_pixmap if checked else item_off_pixmap,
                'action': functools.partial(self.parent().model().sourceModel().set_location, k)
            }

        self.create_menu(menu_set)



class BaseModel(QtCore.QAbstractItemModel):
    """Flat base-model for storing items."""

    aboutToChange = QtCore.Signal()  # Emit before the model is about to change
    grouppingChanged = QtCore.Signal()  # The sequence view mode

    def __init__(self, parent=None):
        super(BaseModel, self).__init__(parent=parent)
        self._internal_data = {
            common.RendersFolder: {True: {}, False: {}},
            common.ScenesFolder: {True: {}, False: {}},
            common.TexturesFolder: {True: {}, False: {}},
            common.ExportsFolder: {True: {}, False: {}},
        }
        self.internal_data = {}
        spinner = Spinner()
        spinner.start()
        self.__initdata__()
        spinner.stop()

    def __initdata__(self):
        raise NotImplementedError('__initdata__ is abstract')

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 1

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(list(self.internal_data))

    def index(self, row, column, parent=QtCore.QModelIndex()):
        return self.createIndex(row, 0, parent=parent)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        if index.row() not in self.internal_data:
            return None

        if role in self.internal_data[index.row()]:
            return self.internal_data[index.row()][role]

    def flags(self, index):
        return index.data(common.FlagsRole)

    def parent(self, child):
        return QtCore.QModelIndex()

    def setData(self, index, data, role=QtCore.Qt.DisplayRole):
        self.internal_data[index.row()][role] = data
        self.dataChanged.emit(index, index)

    def switch_dataset(self):
        pass


class FilterProxyModel(QtCore.QSortFilterProxyModel):
    """Proxy model responsible for filtering and sorting data."""

    def __init__(self, parent=None):
        super(FilterProxyModel, self).__init__(parent=parent)

        self.sortkey = self.get_sortkey()  # Alphabetical/Modified...etc.
        self.sortorder = self.get_sortorder()  # Ascending/descending

        self.filter_mode = {
            'favourite': self.get_filtermode('favourite'),
            'archived': self.get_filtermode('archived')
        }

    def get_sortkey(self):
        """The sort-key used to determine the order of the list."""
        cls = self.parent().__class__.__name__
        val = local_settings.value('widget/{}/sortkey'.format(cls))
        return int(val) if val else common.SortByName

    def set_sortkey(self, val):
        """Sets and saves the sort-key."""
        cls = self.parent().__class__.__name__
        self.sortkey = val
        local_settings.setValue('widget/{}/sortkey'.format(cls), val)

        self.invalidate()

    def get_sortorder(self):
        cls = self.parent().__class__.__name__
        val = local_settings.value(
            'widget/{}/sortorder'.format(cls))
        return int(val) if val else False

    def set_sortorder(self, val):
        cls = self.parent().__class__.__name__
        self.sortorder = val
        local_settings.setValue('widget/{}/sortorder'.format(cls), val)
        self.invalidate()
        self.sort()

    def get_filtermode(self, mode):
        cls = self.parent().__class__.__name__
        val = local_settings.value('widget/{}/mode:{}'.format(cls, mode))
        return val if val else False

    def set_filtermode(self, mode, val):
        cls = self.parent().__class__.__name__
        self.filter_mode[mode] = val
        local_settings.setValue('widget/{}/mode:{}'.format(cls, mode), val)
        self.invalidateFilter()

    def filterAcceptsColumn(self, source_column, parent=QtCore.QModelIndex()):
        return True

    def filterAcceptsRow(self, source_row, parent=QtCore.QModelIndex()):
        """The main method used to filter the elements using the flags and the filter string."""
        index = self.sourceModel().index(source_row, 0, parent=QtCore.QModelIndex())
        archived = index.flags() & MarkedAsArchived
        favourite = index.flags() & MarkedAsFavourite

        if archived and not self.filter_mode['archived']:
            return False
        if not favourite and self.filter_mode['favourite']:
            return False
        return True

    def sort(self, column=0):
        if self.sortorder:
            super(FilterProxyModel, self).sort(
                column, order=QtCore.Qt.AscendingOrder)
        else:
            super(FilterProxyModel, self).sort(
                column, order=QtCore.Qt.DescendingOrder)

    def lessThan(self, source_left, source_right):
        """The main method responsible for sorting the items."""
        left_info = QtCore.QFileInfo(source_left.data(QtCore.Qt.StatusTipRole))
        right_info = QtCore.QFileInfo(
            source_right.data(QtCore.Qt.StatusTipRole))

        return common.sort_keys[self.sortkey](left_info) < common.sort_keys[self.sortkey](right_info)


class BaseListWidget(QtWidgets.QListView):
    """Defines the base of the ``Asset``, ``Bookmark`` and ``File`` list widgets."""

    # Signals
    sizeChanged = QtCore.Signal(QtCore.QSize)

    activeBookmarkChanged = QtCore.Signal(tuple)
    activeAssetChanged = QtCore.Signal(tuple)
    activeLocationChanged = QtCore.Signal(str)
    activeFileChanged = QtCore.Signal(str)

    def __init__(self, model, parent=None):
        super(BaseListWidget, self).__init__(parent=parent)
        proxy_model = FilterProxyModel(parent=self)
        proxy_model.setSourceModel(model)
        self.setModel(proxy_model)
        self.model().sort()

        self._previouspathtoselect = None
        self.model().sourceModel().aboutToChange.connect(self.store_previous_path)
        self.model().sourceModel().grouppingChanged.connect(self.reselect_previous_path)

        self._location = None

        self.collector_count = 0
        self._context_menu_cls = BaseContextMenu

        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(True)

        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.installEventFilter(self)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        common.set_custom_stylesheet(self)

        # Keyboard search timer and placeholder string.
        self.timer = QtCore.QTimer(parent=self)
        app = QtCore.QCoreApplication.instance()
        self.timer.setInterval(app.keyboardInputInterval())
        self.timer.setSingleShot(True)
        self.timed_search_string = ''

    def store_previous_path(self):
        """Saves the currently selected path."""
        index = self.selectionModel().currentIndex()
        if not index.isValid():
            self._previouspathtoselect = None
            return
        self._previouspathtoselect = index.data(QtCore.Qt.StatusTipRole)

    def get_item_filter(self):
        """A path segment used to filter the collected items."""
        val = local_settings.value(
            'widget/{}/filter'.format(self.__class__.__name__))
        return val if val else '/'

    def set_item_filter(self, val):
        cls = self.__class__.__name__
        local_settings.setValue('widget/{}/filter'.format(cls), val)

    def toggle_favourite(self, index=None, state=None):
        """Toggles the ``favourite`` state of the current item.
        If `item` and/or `state` are set explicity, those values will be used
        instead of the currentItem.

        Args:
            item (QListWidgetItem): The item to change.
            state (None or bool): The state to set.

        """
        if not index:
            index = self.selectionModel().currentIndex()
            index = self.model().mapToSource(index)

        if not index.isValid():
            return

        file_info = QtCore.QFileInfo(index.data(QtCore.Qt.StatusTipRole))

        # Favouriting archived items are not allowed
        archived = index.flags() & MarkedAsArchived
        if archived:
            return

        favourites = local_settings.value('favourites')
        favourites = favourites if favourites else []

        if file_info.filePath() in favourites:
            if state is None or state is False:  # clears flag
                self.model().sourceModel().setData(
                    index,
                    index.flags() & ~MarkedAsFavourite,
                    role=common.FlagsRole
                )
                favourites.remove(file_info.filePath())
        else:
            if state is None or state is True:  # adds flag
                favourites.append(file_info.filePath())
                self.model().sourceModel().setData(
                    index,
                    index.flags() | MarkedAsFavourite,
                    role=common.FlagsRole
                )

        local_settings.setValue('favourites', favourites)

    def toggle_archived(self, index=None, state=None):
        """Toggles the ``archived`` state of the current item.
        If `item` and/or `state` are set explicity, those values will be used
        instead of the currentItem.

        Note:
            Archived items are automatically removed from ``favourites``.

        Args:
            item (QListWidgetItem): The explicit item to change.
            state (None or bool): The explicit state to set.

        """
        if not index:
            index = self.selectionModel().currentIndex()
            index = self.model().mapToSource(index)

        if not index.isValid():
            return

        archived = index.flags() & MarkedAsArchived

        file_info = QtCore.QFileInfo(index.data(QtCore.Qt.StatusTipRole))
        settings = AssetSettings(index)

        favourites = local_settings.value('favourites')
        favourites = favourites if favourites else []

        if archived:
            if state is None or state is False:  # clears flag
                self.model().sourceModel().setData(
                    index,
                    index.flags() & ~MarkedAsArchived,
                    role=common.FlagsRole
                )
                settings.setValue('config/archived', False)
        else:
            if state is None or state is True:  # adds flag
                settings.setValue('config/archived', True)
                self.model().sourceModel().setData(
                    index,
                    index.flags() | MarkedAsArchived,
                    role=common.FlagsRole
                )
                if file_info.filePath() in favourites:
                    self.model().sourceModel().setData(
                        index,
                        index.flags() & ~MarkedAsFavourite,
                        role=common.FlagsRole
                    )
                    favourites.remove(file_info.filePath())
                    local_settings.setValue('favourites', favourites)

    def capture_thumbnail(self):
        """Captures a thumbnail for the current item using ScreenGrabber."""
        index = self.selectionModel().currentIndex()

        if not index.isValid():
            return

        settings = AssetSettings(index)
        path = ScreenGrabber.capture(
            output_path=settings.thumbnail_path())
        if not path:
            return

        common.delete_image(settings.thumbnail_path(), delete_file=False)
        height = self.visualRect(index).height() - 2
        common.cache_image(settings.thumbnail_path(), height)

        self.repaint()

    def remove_thumbnail(self):
        """Deletes the given thumbnail."""
        index = self.selectionModel().currentIndex()
        if not index.isValid():
            return

        settings = AssetSettings(index)
        common.delete_image(settings.thumbnail_path())
        height = self.visualRect(index).height() - 2
        common.cache_image(settings.thumbnail_path(), height)

        self.repaint()

    def refresh(self):
        """Refreshes the underlaying source model and resets the sorting."""
        index = self.selectionModel().currentIndex()

        self.model().sourceModel().aboutToChange.emit()
        self.model().sourceModel().beginResetModel()
        spinner = Spinner()
        spinner.start()
        self.model().sourceModel().__initdata__()
        self.model().sourceModel().switch_dataset()
        self.model().sourceModel().endResetModel()
        self.model().invalidate()
        spinner.stop()
        self.model().sort()

        self.reselect_previous_path()

    def reselect_previous_path(self):
        """Reselects the index based on the path given."""
        if not self._previouspathtoselect:
            return
        path = common.get_sequence_startpath(self._previouspathtoselect)
        for n in xrange(self.model().rowCount()):
            index = self.model().index(n, 0, parent=QtCore.QModelIndex())
            _path = index.data(QtCore.Qt.StatusTipRole)
            _path = common.get_sequence_startpath(_path)
            if path == _path:
                self.selectionModel().setCurrentIndex(
                    index,
                    QtCore.QItemSelectionModel.ClearAndSelect
                )
                self.scrollTo(index)
                break

    def action_on_enter_key(self):
        self.activate_current_index()

    def key_down(self):
        """Custom action tpo perform when the `down` arrow is pressed
        on the keyboard.

        """
        sel = self.selectionModel()
        current_index = self.selectionModel().currentIndex()
        first_index = self.model().index(0, 0, parent=QtCore.QModelIndex())
        last_index = self.model().index(self.model().rowCount() -
                                        1, 0, parent=QtCore.QModelIndex())

        if first_index == last_index:
            return

        if not current_index.isValid():  # No selection
            sel.setCurrentIndex(
                first_index,
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return
        if current_index == last_index:  # Last item is selected
            sel.setCurrentIndex(
                first_index,
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return
        for n in xrange(self.model().rowCount()):
            if current_index.row() >= n:
                continue
            sel.setCurrentIndex(
                self.model().index(n, 0, parent=QtCore.QModelIndex()),
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            break

    def key_up(self):
        """Custom action to perform when the `up` arrow is pressed
        on the keyboard.

        """
        sel = self.selectionModel()
        current_index = self.selectionModel().currentIndex()
        first_index = self.model().index(0, 0, parent=QtCore.QModelIndex())
        last_index = self.model().index(self.model().rowCount() -
                                        1, 0, parent=QtCore.QModelIndex())

        if first_index == last_index:
            return

        if not current_index.isValid():  # No selection
            sel.setCurrentIndex(
                last_index,
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return
        if current_index == first_index:  # First item is selected
            sel.setCurrentIndex(
                last_index,
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            return

        for n in reversed(xrange(self.model().rowCount())):  # Stepping back
            if current_index.row() <= n:
                continue
            sel.setCurrentIndex(
                self.model().index(n, 0, parent=QtCore.QModelIndex()),
                QtCore.QItemSelectionModel.ClearAndSelect
            )
            break

    def key_tab(self):
        index = self.selectionModel().currentIndex()
        if not index.isValid():
            index = self.model().index(0, 0, parent=QtCore.QModelIndex())

        widget = editors.DescriptionEditorWidget(index, parent=self)
        widget.show()

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

                sel = self.selectionModel()
                for n in xrange(self.model().rowCount()):
                    index = self.model().index(n, 0, parent=QtCore.QModelIndex())

                    # When only one key is pressed we want to cycle through
                    # only items starting with that letter:
                    if len(self.timed_search_string) == 1:
                        if n <= sel.currentIndex().row():
                            continue

                        if index.data(QtCore.Qt.DisplayRole)[0].lower() == self.timed_search_string.lower():
                            sel.setCurrentIndex(
                                index,
                                QtCore.QItemSelectionModel.ClearAndSelect
                            )
                            break
                    else:
                        match = re.search(
                            '{}'.format(self.timed_search_string),
                            index.data(QtCore.Qt.DisplayRole),
                            flags=re.IGNORECASE
                        )
                        if match:
                            sel.setCurrentIndex(
                                index,
                                QtCore.QItemSelectionModel.ClearAndSelect
                            )
                            break

        if event.modifiers() & QtCore.Qt.ControlModifier:
            pass

        if event.modifiers() & QtCore.Qt.ShiftModifier:
            if event.key() == QtCore.Qt.Key_Tab:
                self.key_up()
                self.key_tab()
            elif event.key() == QtCore.Qt.Key_Backtab:
                self.key_up()
                self.key_tab()

    def contextMenuEvent(self, event):
        """Custom context menu event."""
        index = self.indexAt(event.pos())
        widget = self._context_menu_cls(index, parent=self)

        width = self.viewport().geometry().width()
        width = (width * 0.5) if width > 400 else width
        width = width - common.INDICATOR_WIDTH

        if index.isValid():
            rect = self.visualRect(index)
            widget.move(
                self.viewport().mapToGlobal(rect.bottomLeft()).x(),
                self.viewport().mapToGlobal(rect.bottomLeft()).y() + 1,
            )
        else:
            cursor_pos = QtGui.QCursor().pos()
            widget.move(
                self.mapToGlobal(self.viewport().geometry().topLeft()).x(),
                cursor_pos.y() + 1
            )

        widget.setFixedWidth(width)
        widget.move(widget.x() + common.INDICATOR_WIDTH, widget.y())
        common.move_widget_to_available_geo(widget)
        widget.show()

    def active_index(self):
        """Return the ``active`` item.

        The active item is indicated by the ``MarkedAsActive`` flag.
        If no item has been flagged as `active`, returns ``None``.

        """
        for n in xrange(self.model().rowCount()):
            index = self.model().index(n, 0, parent=QtCore.QModelIndex())
            if index.flags() & MarkedAsActive:
                return index
        return QtCore.QModelIndex()

    def activate_current_index(self):
        """Sets the current index as ``active``.

        Note:
            The method doesn't alter the config files or emits signals,
            merely sets the item flags. Make sure to implement that in the subclass.

        """
        index = self.selectionModel().currentIndex()
        if not index.isValid():
            return False
        if index.flags() == QtCore.Qt.NoItemFlags:
            return False
        if index.flags() & MarkedAsActive:
            return False
        if index.flags() & MarkedAsArchived:
            return False

        source_index = self.model().mapToSource(self.active_index())
        if source_index.isValid():
            self.model().sourceModel().setData(
                source_index,
                source_index.flags() & ~MarkedAsActive,
                role=common.FlagsRole
            )

        source_index = self.model().mapToSource(index)
        self.model().sourceModel().setData(
            source_index,
            source_index.flags() | MarkedAsActive,
            role=common.FlagsRole
        )
        return True

    def select_active_index(self):
        """Selects the active item."""
        self.selectionModel().setCurrentIndex(
            self.active_index(),
            QtCore.QItemSelectionModel.ClearAndSelect
        )

    def showEvent(self, event):
        """Show event will set the size of the widget."""

        self.select_active_index()

        idx = local_settings.value(
            'widget/{}/selected_row'.format(self.__class__.__name__),
        )
        if not idx:
            idx = 0
        if self.model().rowCount():
            self.selectionModel().setCurrentIndex(
                self.model().index(idx, 0, parent=QtCore.QModelIndex()),
                QtCore.QItemSelectionModel.ClearAndSelect
            )

        super(BaseListWidget, self).showEvent(event)

    def hideEvent(self, event):
        """We're saving the selection upon hiding the widget."""
        local_settings.setValue(
            'widget/{}/selected_row'.format(self.__class__.__name__),
            self.selectionModel().currentIndex().row()
        )

    def resizeEvent(self, event):
        """Custom resize event will emit the ``sizeChanged`` signal."""
        self.sizeChanged.emit(event.size())
        super(BaseListWidget, self).resizeEvent(event)

    def mousePressEvent(self, event):
        """Deselecting item when the index is invalid."""
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.selectionModel().setCurrentIndex(
                QtCore.QModelIndex(),
                QtCore.QItemSelectionModel.ClearAndSelect
            )
        super(BaseListWidget, self).mousePressEvent(event)

    def eventFilter(self, widget, event):
        """Custom paint event used to paint the background of the list."""
        if widget is not self:
            return False

        if event.type() == QtCore.QEvent.Paint:
            painter = QtGui.QPainter()
            painter.begin(widget)

            sizehint = self.itemDelegate().sizeHint(
                self.viewOptions(), QtCore.QModelIndex())
            rect = QtCore.QRect(common.INDICATOR_WIDTH, 2, event.rect(
            ).width() - (common.INDICATOR_WIDTH * 2), sizehint.height() - 4)
            favourite_mode = self.model().filter_mode['favourite']
            text_rect = QtCore.QRect(rect)
            text_rect.setLeft(rect.left() + rect.height() + common.MARGIN)
            text_rect.setRight(rect.right() - common.MARGIN)

            filter_rect = QtCore.QRect(event.rect())
            filter_rect.setRight(event.rect().right())
            filter_rect.setLeft(event.rect().right() - (common.INDICATOR_WIDTH))
            filter_rect.setBottom(sizehint.height())

            painter.setRenderHints(
                QtGui.QPainter.TextAntialiasing |
                QtGui.QPainter.Antialiasing |
                QtGui.QPainter.SmoothPixmapTransform,
                on=True
            )

            painter.setPen(QtCore.Qt.NoPen)
            # painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 100, 100, 20)))
            font = QtGui.QFont('Roboto Black')
            font.setPointSize(8)
            painter.setFont(font)

            for n in xrange((self.height() / sizehint.height()) + 1):
                if n >= self.model().rowCount():  # Empty items
                    rect_ = QtCore.QRect(rect)
                    rect_.setWidth(sizehint.height() - 2)
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 100, 100, 5)))
                    painter.drawRect(rect_)
                    painter.drawRect(rect)
                    if favourite_mode:
                        painter.setBrush(common.FAVOURITE)
                        painter.drawRect(filter_rect)
                if n == 0 and not favourite_mode:  # Empty model
                    painter.setPen(common.TEXT_DISABLED)
                    painter.drawText(
                        text_rect,
                        QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                        '  No items to show.'
                    )
                    painter.setPen(QtCore.Qt.NoPen)
                elif n == self.model().rowCount():  # filter mode
                    if favourite_mode:
                        painter.setPen(common.FAVOURITE)
                        painter.drawText(
                            text_rect,
                            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
                            '(Showing favourites only)'
                        )
                        painter.setPen(QtCore.Qt.NoPen)

                text_rect.moveTop(text_rect.top() + sizehint.height())
                rect.moveTop(rect.top() + sizehint.height())
                filter_rect.moveTop(filter_rect.top() + sizehint.height())

            painter.end()
            return True
        return False


class BaseInlineIconWidget(BaseListWidget):
    """Multi-toggle capable widget with clickable in-line icons."""

    def __init__(self, model, parent=None):
        super(BaseInlineIconWidget, self).__init__(model, parent=parent)
        self.multi_toggle_pos = None
        self.multi_toggle_state = None
        self.multi_toggle_idx = None
        self.multi_toggle_item = None
        self.multi_toggle_items = {}

    def inline_icons_count(self):
        """The numberof inline icons."""
        raise NotImplementedError('method is abstract.')

    def _reset_multitoggle(self):
        self.multi_toggle_pos = None
        self.multi_toggle_state = None
        self.multi_toggle_idx = None
        self.multi_toggle_item = None
        self.multi_toggle_items = {}

    def mousePressEvent(self, event):
        """The custom mousePressEvent initiates the multi-toggle operation.
        Only the `favourite` and `archived` buttons are multi-toggle capable."""
        index = self.indexAt(event.pos())
        rect = self.visualRect(index)

        if self.viewport().width() < 360.0:
            return super(BaseInlineIconWidget, self).mousePressEvent(event)

        self._reset_multitoggle()

        for n in xrange(self.inline_icons_count()):
            _, bg_rect = self.itemDelegate().get_inline_icon_rect(
                rect, common.INLINE_ICON_SIZE, n)

            # Beginning multi-toggle operation
            if not bg_rect.contains(event.pos()):
                continue

            self.multi_toggle_pos = event.pos()
            if n == 0:  # Favourite button
                self.multi_toggle_state = not index.flags() & MarkedAsFavourite
            elif n == 1:  # Archive button
                self.multi_toggle_state = not index.flags() & MarkedAsArchived
            elif n == 2:  # Reveal button
                continue
            elif n == 3:  # Todo button
                continue

            self.multi_toggle_idx = n
            return True

        return super(BaseInlineIconWidget, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Inline-button methods are triggered here."""
        index = self.indexAt(event.pos())
        source_index = self.model().mapToSource(index)
        rect = self.visualRect(index)
        idx = index.row()

        if self.viewport().width() < 360.0:
            return super(BaseInlineIconWidget, self).mouseReleaseEvent(event)

        # Cheking the button
        if idx in self.multi_toggle_items:
            self._reset_multitoggle()
            return super(BaseInlineIconWidget, self).mouseReleaseEvent(event)

        for n in xrange(self.inline_icons_count()):
            _, bg_rect = self.itemDelegate().get_inline_icon_rect(
                rect, common.INLINE_ICON_SIZE, n)

            if not bg_rect.contains(event.pos()):
                continue

            if n == 0:
                self.toggle_favourite(index=source_index)
                break
            elif n == 1:
                self.toggle_archived(index=source_index)
                break
            elif n == 2:
                common.reveal(index.data(QtCore.Qt.StatusTipRole))
                break
            elif n == 3:
                self.show_todos()
                break

        self._reset_multitoggle()
        super(BaseInlineIconWidget, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Multi-toggle is handled here."""
        if self.viewport().width() < 360.0:
            return super(BaseInlineIconWidget, self).mouseMoveEvent(event)

        if self.multi_toggle_pos is None:
            return super(BaseInlineIconWidget, self).mouseMoveEvent(event)

        app_ = QtWidgets.QApplication.instance()
        if (event.pos() - self.multi_toggle_pos).manhattanLength() < app_.startDragDistance():
            return super(BaseInlineIconWidget, self).mouseMoveEvent(event)

        pos = event.pos()
        pos.setX(0)
        index = self.indexAt(pos)
        source_index = self.model().mapToSource(index)
        initial_index = self.indexAt(self.multi_toggle_pos)
        idx = index.row()

        favourite = index.flags() & MarkedAsFavourite
        archived = index.flags() & MarkedAsArchived

        # Filter the current item
        if index == self.multi_toggle_item:
            return

        self.multi_toggle_item = index

        # Before toggling the item, we're saving it's state

        if idx not in self.multi_toggle_items:
            if self.multi_toggle_idx == 0:  # Favourite button
                # A state
                self.multi_toggle_items[idx] = favourite
                # Apply first state
                self.toggle_favourite(
                    index=source_index,
                    state=self.multi_toggle_state
                )
            if self.multi_toggle_idx == 1:  # Archived button
                # A state
                self.multi_toggle_items[idx] = archived
                # Apply first state
                self.toggle_archived(
                    index=source_index,
                    state=self.multi_toggle_state
                )
        else:  # Reset state
            if index == initial_index:
                return
            if self.multi_toggle_idx == 0:  # Favourite button
                self.toggle_favourite(
                    index=source_index,
                    state=self.multi_toggle_items.pop(idx)
                )
            elif self.multi_toggle_idx == 1:  # Favourite button
                self.toggle_archived(
                    index=source_index,
                    state=self.multi_toggle_items.pop(idx)
                )
