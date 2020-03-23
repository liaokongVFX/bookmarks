# -*- coding: utf-8 -*-
"""``common.py`` defines common methods and settings used across the project.

File-sequences are recognised using regexes defined in the module.
See :func:`.get_valid_filename`, :func:`.get_sequence`, :func:`.is_collapsed`,
:func:`.get_sequence_startpath`,  :func:`.get_ranges`.

"""

import os
import sys
import re
import time
import zipfile
import traceback
import cStringIO

from PySide2 import QtGui, QtCore, QtWidgets
import OpenImageIO

import bookmarks._scandir as _scandir

DEBUG_ON = False
STANDALONE = True # Standalone
PRODUCT = u'Bookmarks'
ABOUT_URL = ur'https://gergely-wootsch.com/bookmarks-about'


SynchronisedMode = 0
SoloMode = 1
"""Enum used to indicate the mode. When syncronised mode is on, the active path
selections will be syncronised across DCCs and desktop instances."""


# Flags
MarkedAsArchived = 0b1000000000
MarkedAsFavourite = 0b10000000000
MarkedAsActive = 0b100000000000
"""Item flags."""

InfoThread = 0
BackgroundInfoThread = 1
ThumbnailThread = 2
"""Thread types."""

ExportsFolder = u'exports'
DataFolder = u'data'
ReferenceFolder = u'references'
RendersFolder = u'renders'
ScenesFolder = u'scenes'
CompsFolder = u'comps'
ScriptsFolder = u'scripts'
TexturesFolder = u'textures'
"""Predefined folder names."""

ASSET_FOLDERS = {
    ExportsFolder: u'User exported animation, object and simulation cache files',
    CompsFolder: u'Final comp renders',
    DataFolder: u'System exported caches files',
    ReferenceFolder: u'Files used for research, reference',
    RendersFolder: u'Images rendered by the scene files',
    ScenesFolder: u'Project files for all 2D and 3D scenes',
    ScriptsFolder: u'Technical dependencies',
    TexturesFolder: u'Textures used by the 2D/3D projects',
    u'misc': u'',
}
"""Folder descriptions."""

UI_SCALE = 1.0
"""The global UI scale value. Depending on context, this should correspond to
any UI scaling set in the host DCC. In standalone mode the app factors in the
current DPI scaling and scales the UI accordingly."""


SMALL_FONT_SIZE = 8.5
MEDIUM_FONT_SIZE = 9.0
LARGE_FONT_SIZE = 12.0

ROW_HEIGHT = 34.0
BOOKMARK_ROW_HEIGHT = 42.0
ASSET_ROW_HEIGHT = 64.0
CONTROL_HEIGHT = 34.0
ROW_SEPARATOR = 1.0

MARGIN = 18.0

INDICATOR_WIDTH = 4.0
ROW_BUTTONS_HEIGHT = 36.0

WIDTH = 640.0
HEIGHT = 480.0

INLINE_ICON_SIZE = 18.0
THUMBNAIL_IMAGE_SIZE = 512.0
THUMBNAIL_FORMAT = u'png'


def proxy_path(v):
    """Returns a path where the original sequence element has been
    replaced with `[0]`.

    Accepts a data dict, index or filepath string.

    """
    if isinstance(v, dict):
        m = v[SequenceRole]
        k = v[QtCore.Qt.StatusTipRole]
        if m:
            k = m.group(1) + u'[0]' + m.group(3) + u'.' + m.group(4)
        return k

    if isinstance(v, QtCore.QModelIndex):
        m = v.data(SequenceRole)
        k = v.data(QtCore.Qt.StatusTipRole)
        if m:
            k = m.group(1) + u'[0]' + m.group(3) + u'.' + m.group(4)
        return k

    if not (isinstance, unicode):
        raise ValueError(
            'Invalid type. Expected <type \'QModelIndex\'> or `<type \'unicode\'>')

    m = get_sequence(v)
    if m:
        k = m.group(1) + u'[0]' + m.group(3) + u'.' + m.group(4)
        return k
    m = is_collapsed(v)
    if m:
        k = m.group(1) + u'[0]' + m.group(3)
        return k
    return v


class DataDict(dict):
    """Subclassed dict type for weakref compatibility."""
    pass


class Log:
    stdout = cStringIO.StringIO()

    HEADER = u'\033[95m'
    OKBLUE = u'\033[94m'
    OKGREEN = u'\033[92m'
    WARNING = u'\033[93m'
    FAIL = u'\033[91m'
    ENDC = u'\033[0m'
    BOLD = u'\033[1m'
    UNDERLINE = u'\033[4m'

    @classmethod
    def success(cls, s):
        if not DEBUG_ON:
            return
        t = u'{color}{ts} [Ok]:  {default}{message}'.format(
            ts=time.strftime(u'%H:%M:%S'),
            color=cls.OKGREEN,
            default=cls.ENDC,
            message=s
        )
        print >> cls.stdout, t

    @classmethod
    def debug(cls, s, source=u''):
        if not DEBUG_ON:
            return
        t = u'{color}{ts} [Debug]:{default}    {source}.{message}'.format(
            ts=time.strftime(u'%H:%M:%S'),
            color=cls.OKBLUE,
            default=cls.ENDC,
            message=s,
            source=source.__class__.__name__
        )
        print >> cls.stdout, t

    @classmethod
    def info(cls, s):
        if not DEBUG_ON:
            return
        t = u'{color}{ts} [Info]:{default}    {message}'.format(
            ts=time.strftime(u'%H:%M:%S'),
            color=cls.OKBLUE,
            default=cls.ENDC,
            message=s
        )
        print >> cls.stdout, t

    @classmethod
    def error(cls, s):
        t = u'{fail}{underline}{ts} [Error]:{default}{default}    {message}\n{fail}{traceback}\n'.format(
            ts=time.strftime(u'%H:%M:%S'),
            fail=cls.FAIL,
            underline=cls.UNDERLINE,
            default=cls.ENDC,
            message=s,
            traceback=u'\n\033[91m'.join(
                traceback.format_exc().strip(u'\n').split(u'\n'))
        )
        print >> cls.stdout, t


def k(s):
    return getattr(Log, s).replace(u'[', u'\\[')


class LogViewHighlighter(QtGui.QSyntaxHighlighter):
    """Class responsible for highlighting urls"""
    HEADER = 0b000000001
    OKBLUE = 0b000000010
    OKGREEN = 0b000000100
    WARNING = 0b000001000
    FAIL = 0b000010000
    FAIL_SUB = 0b000100000
    ENDC = 0b001000000
    BOLD = 0b010000000
    UNDERLINE = 0b100000000

    HIGHLIGHT_RULES = {
        u'OKBLUE': {
            u're': re.compile(
                u'{}(.+?)(?:{})(.+)'.format(k('OKBLUE'), k('ENDC')),
                flags=re.IGNORECASE | re.UNICODE),
            u'flag': OKBLUE
        },
        u'OKGREEN': {
            u're': re.compile(
                u'{}(.+?)(?:{})(.+)'.format(k('OKGREEN'), k('ENDC')),
                flags=re.IGNORECASE | re.UNICODE),
            u'flag': OKGREEN
        },
        u'FAIL': {
            u're': re.compile(
                u'{}{}(.+?)(?:{})(.+)'.format(
                    k('FAIL'), k('UNDERLINE'), k('ENDC')),
                flags=re.IGNORECASE | re.UNICODE),
            u'flag': FAIL
        },
        u'FAIL_SUB': {
            u're': re.compile(
                u'{}(.*)'.format(k('FAIL')),
                flags=re.IGNORECASE | re.UNICODE),
            u'flag': FAIL_SUB
        },
    }

    def highlightBlock(self, text):
        font = QtGui.QFont('Monospace')
        font.setStyleHint(QtGui.QFont.Monospace)

        char_format = QtGui.QTextCharFormat()
        char_format.setFont(font)
        char_format.setForeground(QtGui.QColor(0, 0, 0, 0))
        char_format.setFontPointSize(1)

        block_format = QtGui.QTextBlockFormat()
        block_format.setLineHeight(
            120, QtGui.QTextBlockFormat.ProportionalHeight)
        self.setFormat(0, len(text), char_format)

        _font = char_format.font()
        _foreground = char_format.foreground()
        _weight = char_format.fontWeight()
        _psize = char_format.font().pointSizeF()

        flag = 0

        position = self.currentBlock().position()
        cursor = QtGui.QTextCursor(self.currentBlock())
        cursor.mergeBlockFormat(block_format)
        cursor = QtGui.QTextCursor(self.document())

        for case in self.HIGHLIGHT_RULES.itervalues():
            if case[u'flag'] == self.OKGREEN:
                it = case[u're'].finditer(text)
                for match in it:
                    flag = flag | case['flag']
                    char_format.setFontPointSize(MEDIUM_FONT_SIZE)

                    char_format.setForeground(QtGui.QColor(80, 230, 80, 255))

                    self.setFormat(match.start(1), len(
                        match.group(1)), char_format)
                    cursor = self.document().find(match.group(1), position)
                    cursor.mergeCharFormat(char_format)

                    char_format.setForeground(QtGui.QColor(170, 170, 170, 255))

                    self.setFormat(match.start(2), len(
                        match.group(2)), char_format)
                    cursor = self.document().find(match.group(2), position)
                    cursor.mergeCharFormat(char_format)

            if case[u'flag'] == self.OKBLUE:
                it = case[u're'].finditer(text)
                for match in it:
                    flag = flag | case['flag']
                    char_format.setFontPointSize(MEDIUM_FONT_SIZE)
                    char_format.setForeground(QtGui.QColor(80, 80, 200, 255))

                    self.setFormat(match.start(1), len(
                        match.group(1)), char_format)
                    cursor = self.document().find(match.group(1), position)
                    cursor.mergeCharFormat(char_format)

                    char_format.setForeground(QtGui.QColor(170, 170, 170, 255))

                    self.setFormat(match.start(2), len(
                        match.group(2)), char_format)
                    cursor = self.document().find(match.group(2), position)
                    cursor.mergeCharFormat(char_format)

            if case[u'flag'] == self.FAIL:
                match = case[u're'].match(text)
                if match:
                    flag = flag | case['flag']
                    char_format.setFontPointSize(MEDIUM_FONT_SIZE)
                    char_format.setForeground(QtGui.QColor(230, 80, 80, 255))
                    char_format.setFontUnderline(True)

                    self.setFormat(match.start(1), len(
                        match.group(1)), char_format)
                    cursor = self.document().find(match.group(1), position)
                    cursor.mergeCharFormat(char_format)

                    char_format.setForeground(QtGui.QColor(170, 170, 170, 255))

                    self.setFormat(match.start(2), len(
                        match.group(2)), char_format)
                    cursor = self.document().find(match.group(2), position)
                    cursor.mergeCharFormat(char_format)

            if case[u'flag'] == self.FAIL_SUB:
                # continue
                it = case[u're'].finditer(text)
                for match in it:
                    if flag & self.FAIL:
                        continue
                    char_format.setFontUnderline(False)
                    char_format.setFontPointSize(MEDIUM_FONT_SIZE)
                    char_format.setForeground(QtGui.QColor(230, 80, 80, 255))

                    self.setFormat(match.start(1), len(
                        match.group(1)), char_format)
                    cursor = self.document().find(match.group(1), position)
                    cursor.mergeCharFormat(char_format)

            char_format.setFont(_font)
            char_format.setForeground(_foreground)
            char_format.setFontWeight(_weight)


class LogView(QtWidgets.QTextBrowser):

    format_regex = u'({h})|({b})|({g})|({w})|({f})|({e})|({o})|({u})'
    format_regex = format_regex.format(
        h=Log.HEADER,
        b=Log.OKBLUE,
        g=Log.OKGREEN,
        w=Log.WARNING,
        f=Log.FAIL,
        e=Log.ENDC,
        o=Log.BOLD,
        u=Log.UNDERLINE
    )
    format_regex = re.compile(format_regex.replace(u'[', '\\['))

    def __init__(self, parent=None):
        super(LogView, self).__init__(parent=parent)
        set_custom_stylesheet(self)
        self.setMinimumWidth(WIDTH)
        self.setUndoRedoEnabled(False)
        self._cached = u''
        self.highlighter = LogViewHighlighter(self.document())
        self.timer = QtCore.QTimer(parent=self)
        self.timer.setSingleShot(False)
        self.timer.setInterval(666)
        self.timer.timeout.connect(self.load_log)
        self.timer.start()
        self.setStyleSheet(
            """
* {{
    padding: 20px;
    padding: 20px;
    border-radius: 8px;
    font-size: {}pt;
    background-color: rgba({});
}}
""".format(
        psize(MEDIUM_FONT_SIZE),
        rgb(SEPARATOR)
    ))

    def showEvent(self, event):
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()

    def load_log(self):
        app = QtWidgets.QApplication.instance()
        if app.mouseButtons() != QtCore.Qt.NoButton:
            return

        self.document().blockSignals(True)
        v = Log.stdout.getvalue()
        if self._cached == v:
            return

        self._cached = v
        self.setText(v[-30000:])
        self.highlighter.rehighlight()
        v = self.format_regex.sub(u'', self.document().toHtml())
        self.setHtml(v)
        self.document().blockSignals(False)

        m = self.verticalScrollBar().maximum()
        self.verticalScrollBar().setValue(m)

    def sizeHint(self):
        return QtCore.QSize(460, 460)


def pxsize(n):
    return n * UI_SCALE


def psize(n):
    """There is a platform difference between font sizes on OSX and Win platforms."""
    n = n * (96.0 / 72.0) if get_platform() == u'mac' else n
    return n * UI_SCALE


def usize(n):
    return n * UI_SCALE


def rgb(color):
    """Returns an rgba string representation of the given color.

    Args:
        color (QtGui.QColor): The `QColor` to convert.

    Returns:
        unicode: The string representation of the color./

    """
    return u'{},{},{},{}'.format(*color.getRgb())


def get_username():
    n = QtCore.QFileInfo(os.path.expanduser(u'~')).fileName()
    n = re.sub(ur'[^a-zA-Z0-9]*', u'', n, flags=re.IGNORECASE | re.UNICODE)
    return n


def create_temp_dir():
    server, job, root = get_favourite_parent_paths()
    path = u'{}/{}/{}/.bookmark'.format(server, job, root)
    _dir = QtCore.QDir(path)
    if _dir.exists():
        return
    _dir.mkpath(u'.')


def get_favourite_parent_paths():
    server = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.GenericDataLocation)
    job = u'{}'.format(PRODUCT)
    root = u'local'
    return server, job, root


def export_favourites():
    """Saves all favourites including the descriptions and the thumbnails."""
    try:
        import uuid
        import bookmarks.settings as settings
        import bookmarks.bookmark_db as bookmark_db

        res = QtWidgets.QFileDialog.getSaveFileName(
            caption=u'Select where to save your favourites',
            filter=u'*.favourites',
            dir=QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.HomeLocation),
        )
        destination, _ = res
        if not destination:
            return

        favourites = settings.local_settings.favourites()
        server, job, root = get_favourite_parent_paths()
        db = bookmark_db.get_db(
            QtCore.QModelIndex(),
            server=server,
            job=job,
            root=root
        )

        zip_path = u'{}/{}/{}/{}.zip'.format(server, job, root, uuid.uuid4())

        # Make sure the temp folder exists
        QtCore.QFileInfo(zip_path).dir().mkpath(u'.')

        with zipfile.ZipFile(zip_path, 'a') as z:
            # Adding thumbnail to zip
            for favourite in favourites:
                file_info = QtCore.QFileInfo(db.thumbnail_path(favourite))
                if not file_info.exists():
                    continue
                z.write(file_info.filePath(), file_info.fileName())
            z.writestr(u'favourites', u'\n'.join(favourites))

        file_info = QtCore.QFileInfo(zip_path)
        if not file_info.exists():
            raise RuntimeError(
                u'Unexpected error occured: could not find the favourites file')

        QtCore.QDir().rename(file_info.filePath(), destination)
        if not QtCore.QFileInfo(destination).exists():
            raise RuntimeError(
                u'Unexpected error occured: could not find the favourites file')
        reveal(destination)

    except Exception as e:
        import bookmarks.common_ui as common_ui
        common_ui.ErrorBox(
            u'Could not save the favourites.',
            u'{}'.format(e)
        ).exec_()
        Log.error(u'Exporting favourites failed.')
        raise


def import_favourites(source=None):
    try:
        import bookmarks.settings as settings
        import bookmarks.bookmark_db as bookmark_db

        if not isinstance(source, unicode):
            res = QtWidgets.QFileDialog.getOpenFileName(
                caption=u'Select the favourites file to import',
                filter=u'*.favourites'
                # options=QtWidgets.QFileDialog.ShowDirsOnly
            )
            source, _ = res
            if not source:
                return

        current_favourites = settings.local_settings.favourites()
        create_temp_dir()

        with zipfile.ZipFile(source) as zip:
            namelist = zip.namelist()
            namelist = [f.lower() for f in namelist]

            if u'favourites' not in namelist:
                mbox = QtWidgets.QMessageBox()
                mbox.setWindowTitle(u'Invalid ".favourites" file')
                mbox.setText(u'This file does not seem to be valid, sorry!')
                mbox.setInformativeText(
                    u'The favourites list is missing from the archive.')
                return mbox.exec_()

            with zip.open(u'favourites') as f:
                favourites = f.readlines()
                favourites = [unicode(f).strip().lower() for f in favourites]

            server, job, root = get_favourite_parent_paths()
            db = bookmark_db.get_db(
                QtCore.QModelIndex(),
                server=server,
                job=job,
                root=root
            )

            for favourite in favourites:
                file_info = QtCore.QFileInfo(db.thumbnail_path(favourite))
                if file_info.fileName().lower() in namelist:
                    dest = u'{}/{}/{}/.bookmark'.format(server, job, root)
                    zip.extract(file_info.fileName(), dest)

                if favourite not in current_favourites:
                    current_favourites.append(favourite)

            current_favourites = sorted(list(set(current_favourites)))
            settings.local_settings.setValue(u'favourites', current_favourites)

    except Exception as e:
        import bookmarks.common_ui as common_ui
        common_ui.ErrorBox(
            u'Could not import the favourites.',
            u'{}'.format(e)
        ).exec_()
        Log.error(u'Import favourites failed.')
        raise


def clear_favourites():
    import bookmarks.settings as settings
    mbox = QtWidgets.QMessageBox()
    mbox.setWindowTitle(u'Clear favourites')
    mbox.setText(
        u'Are you sure you want to remove all of your favourites?'
    )
    mbox.setStandardButtons(
        QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
    mbox.setDefaultButton(QtWidgets.QMessageBox.Cancel)

    mbox.exec_()
    if mbox.result() == QtWidgets.QMessageBox.Cancel:
        return

    settings.local_settings.setValue(u'favourites', [])


def get_platform():
    """Returns the name of the current platform.

    Returns:
        unicode: *mac* or *win*, depending on the platform.

    Raises:
        NotImplementedError: If the current platform is not supported.

    """
    ptype = QtCore.QSysInfo().productType().lower()
    if ptype in (u'darwin', u'osx', u'macos'):
        return u'mac'
    if u'win' in ptype:
        return u'win'
    raise NotImplementedError(
        u'The platform "{}" is not supported'.format(ptype))


BACKGROUND_SELECTED = QtGui.QColor(140, 140, 140)
SECONDARY_BACKGROUND = QtGui.QColor(60, 60, 60)
BACKGROUND = QtGui.QColor(80, 80, 80)
THUMBNAIL_BACKGROUND = SECONDARY_BACKGROUND

TEXT = QtGui.QColor(220, 220, 220)
TEXT_SELECTED = QtGui.QColor(250, 250, 250)
TEXT_DISABLED = QtGui.QColor(140, 140, 140)

TEXT_NOTE = QtGui.QColor(150, 150, 255)
SECONDARY_TEXT = QtGui.QColor(170, 170, 170)

SEPARATOR = QtGui.QColor(45, 45, 45)
FAVOURITE = QtGui.QColor(107, 126, 180)
REMOVE = QtGui.QColor(219, 114, 114)
ADD = QtGui.QColor(90, 200, 155)


def get_oiio_extensions():
    """Returns a list of extension OpenImageIO is capable of reading."""
    extensions = []
    for f in OpenImageIO.get_string_attribute(u'extension_list').split(u';'):
        extensions = extensions + f.split(u':')[-1].split(u',')
    return frozenset(extensions)


def get_oiio_namefilters(as_array=False):
    """Gets all accepted formats from the oiio build as a namefilter list.
    Use the return value on the QFileDialog.setNameFilters() method.

    """
    extension_list = OpenImageIO.get_string_attribute("extension_list")
    namefilters = []
    arr = []
    for exts in extension_list.split(u';'):
        exts = exts.split(u':')
        _exts = exts[1].split(u',')
        e = [u'*.{}'.format(f) for f in _exts]
        namefilter = u'{} files ({})'.format(exts[0].upper(), u' '.join(e))
        namefilters.append(namefilter)
        for _e in _exts:
            arr.append(_e)
    if as_array:
        return arr

    allfiles = [u'*.{}'.format(f) for f in arr]
    allfiles = u' '.join(allfiles)
    allfiles = u'All files ({})'.format(allfiles)
    namefilters.insert(0, allfiles)
    return u';;'.join(namefilters)


creative_cloud_formats = [
    u'aep',
    u'ai',
    u'eps',
    u'fla',
    u'ppj',
    u'prproj',
    u'psb',
    u'psd',
    u'psq',
    u'xfl',
]
exports_formats = [
    u'abc',  # Alembic
    u'ass',  # Arnold
    u'bgeo',  # Houdini
    u'fbx',
    u'geo',  # Houdini
    u'obj',
    u'rs',  # Redshift cache file
    u'sim',  # Houdini
    u'sc',  # Houdini
    u'vdb',  # OpenVDB cache file
    u'ifd',  # Houdini
]
scene_formats = [
    u'c4d',
    u'hud',
    u'hip',
    u'ma',
    u'mb',
    u'nk',
    u'nk~',
    u'mocha',
    u'rv',
    u'autosave'
]
misc_formats = [
    u'pdf',
    u'zip',
    u'm4v',
    u'm4a',
    u'mov',
    u'mp4',
]
oiio_formats = get_oiio_namefilters(as_array=True)
all_formats = frozenset(
    scene_formats +
    oiio_formats +
    exports_formats +
    creative_cloud_formats +
    misc_formats
)

NameFilters = {
    ExportsFolder: all_formats,
    ScenesFolder: all_formats,
    CompsFolder: oiio_formats,
    RendersFolder: oiio_formats,
    TexturesFolder: all_formats,
}
"""A list of expected file - formats associated with the location."""

# Extending the
FlagsRole = 1024
"""Role used to store the path of the item."""
ParentPathRole = 1026
"""Role used to store the paths the item is associated with."""
DescriptionRole = 1027
"""Role used to store the description of the item."""
TodoCountRole = 1028
"""Asset role used to store the number of todos."""
FileDetailsRole = 1029
"""Special role used to save the information string of a file."""
SequenceRole = 1030  # SRE Match object
FramesRole = 1031  # List of frame names
FileInfoLoaded = 1032
FileThumbnailLoaded = 1033
StartpathRole = 1034
EndpathRole = 1035
ThumbnailRole = 1036
ThumbnailPathRole = 1037
ThumbnailBackgroundRole = 1038
DefaultThumbnailRole = 1039
DefaultThumbnailBackgroundRole = 1040
TypeRole = 1041
EntryRole = 1042
IdRole = 1043
AssetCountRole = 1043

SortByName = 2048
SortByLastModified = 2049
SortBySize = 2050

FileItem = 1100
SequenceItem = 1200

SORT_WITH_BASENAME = False


ValidFilenameRegex = re.compile(
    ur'^.*([a-zA-Z0-9]+?)\_(.*)\_(.+?)\_([a-zA-Z0-9]+)\_v([0-9]{1,4})\.([a-zA-Z0-9]+$)',
    flags=re.IGNORECASE | re.UNICODE)
IsSequenceRegex = re.compile(
    ur'^(.+?)(\[.*\])(.*)$', flags=re.IGNORECASE | re.UNICODE)
SequenceStartRegex = re.compile(
    ur'^(.*)\[([0-9]+).*\](.*)$',
    flags=re.IGNORECASE | re.UNICODE)
SequenceEndRegex = re.compile(
    ur'^(.*)\[.*?([0-9]+)\](.*)$',
    flags=re.IGNORECASE | re.UNICODE)
GetSequenceRegex = re.compile(
    ur'^(.*?)([0-9]+)([0-9\\/]*|[^0-9\\/]*(?=.+?))\.([^\.]{2,5})$',
    flags=re.IGNORECASE | re.UNICODE)

WindowsPath = 0
UnixPath = 1
SlackPath = 2
MacOSPath = 3




class FontDatabase(QtGui.QFontDatabase):

    def __init__(self, parent=None):
        if not QtWidgets.QApplication.instance():
            raise RuntimeError('FontDatabase must be created after a QApplication was initiated.')
        super(FontDatabase, self).__init__(parent=parent)

        self._fonts = {}
        self.add_custom_fonts()

    def add_custom_fonts(self):
        """Adds our custom fonts to the QApplication.
        """
        if u'bmRobotoMedium' in self.families():
            return

        p = u'{}/../rsc/fonts'.format(__file__)
        p = os.path.normpath(os.path.abspath(p))

        if not os.path.isdir(p):
            raise OSError('{} could not be found'.format(p))

        import bookmarks._scandir as scandir
        for entry in _scandir.scandir(p):
            if not entry.name.endswith(u'ttf'):
                continue
            idx = self.addApplicationFont(entry.path)
            if idx < 0:
                raise RuntimeError(u'Failed to add required font to the application')
            family = self.applicationFontFamilies(idx)
            if not family:
                raise RuntimeError(u'Failed to add required font to the application')

    def primary_font(self, point_size=MEDIUM_FONT_SIZE):
        k = u'bmRobotoBold' + unicode(float(point_size))
        if k in self._fonts:
            return self._fonts[k]
        self._fonts[k] = self.font(u'bmRobotoBold', u'Regular', psize(point_size))
        if self._fonts[k].family() != u'bmRobotoBold':
            raise RuntimeError(u'Failed to add required font to the application')
        return self._fonts[k]

    def secondary_font(self, point_size=SMALL_FONT_SIZE):
        k = u'bmRobotoMedium' + unicode(float(point_size))
        if k in self._fonts:
            return self._fonts[k]

        self._fonts[k] = self.font(u'bmRobotoRegular', u'Regular', psize(point_size))
        if self._fonts[k].family() != u'bmRobotoRegular':
            raise RuntimeError(u'Failed to add required font to the application')
        return self._fonts[k]

    def header_font(self, point_size=MEDIUM_FONT_SIZE + 2.0):
        k = u'bmRobotoBlack' + unicode(float(point_size))
        if k in self._fonts:
            return self._fonts[k]

        self._fonts[k] = self.font(u'bmRobotoBlack', u'Black', point_size)
        if self._fonts[k].family() != u'bmRobotoBlack':
            raise RuntimeError(u'Failed to add required font to the application')
        return self._fonts[k]


def qlast_modified(n): return QtCore.QDateTime.fromMSecsSinceEpoch(n * 1000)


def namekey(s):
    """Key function used to sort alphanumeric filenames."""
    if SORT_WITH_BASENAME:
        s = s.split(u'/').pop()  # order by filename
    else:
        n = len(s.split(u'/'))
        s = ((u'Ω' * n) + s)  # order by number of subfolders, then name
    return [int(f) if f.isdigit() else f for f in s]


def move_widget_to_available_geo(widget):
    """Moves the widget inside the available screen geomtery, if any of the edges
    fall outside.

    """
    app = QtWidgets.QApplication.instance()
    if widget.window():
        screenID = app.desktop().screenNumber(widget.window())
    else:
        screenID = app.desktop().primaryScreen()

    screen = app.screens()[screenID]
    screen_rect = screen.availableGeometry()

    # Widget's rectangle in the global screen space
    rect = QtCore.QRect()
    topLeft = widget.mapToGlobal(widget.rect().topLeft())
    rect.setTopLeft(topLeft)
    rect.setWidth(widget.rect().width())
    rect.setHeight(widget.rect().height())

    x = rect.x()
    y = rect.y()

    if rect.left() < screen_rect.left():
        x = screen_rect.x()
    if rect.top() < screen_rect.top():
        y = screen_rect.y()
    if rect.right() > screen_rect.right():
        x = screen_rect.right() - rect.width()
    if rect.bottom() > screen_rect.bottom():
        y = screen_rect.bottom() - rect.height()

    widget.move(x, y)


def set_custom_stylesheet(widget):
    """Applies the custom stylesheet to the given widget."""
    path = os.path.normpath(
        os.path.abspath(
            os.path.join(
                __file__,
                os.pardir,
                u'rsc',
                u'customStylesheet.css'
            )
        )
    )
    import bookmarks.images as images
    with open(path, 'r') as f:
        f.seek(0)
        qss = f.read()
        qss = qss.encode(encoding='UTF-8', errors='strict')

        try:
            qss = qss.format(
                PRIMARY_FONT=font_db.primary_font().family(),
                SECONDARY_FONT=font_db.secondary_font().family(),
                SMALL_FONT_SIZE=psize(SMALL_FONT_SIZE),
                MEDIUM_FONT_SIZE=psize(MEDIUM_FONT_SIZE),
                LARGE_FONT_SIZE=psize(LARGE_FONT_SIZE),
                BACKGROUND=rgb(BACKGROUND),
                BACKGROUND_SELECTED=rgb(BACKGROUND_SELECTED),
                SECONDARY_BACKGROUND=rgb(SECONDARY_BACKGROUND),
                TEXT=rgb(TEXT),
                SECONDARY_TEXT=rgb(SECONDARY_TEXT),
                TEXT_DISABLED=rgb(TEXT_DISABLED),
                TEXT_SELECTED=rgb(TEXT_SELECTED),
                ADD=rgb(ADD),
                REMOVE=rgb(REMOVE),
                SEPARATOR=rgb(SEPARATOR),
                FAVOURITE=rgb(FAVOURITE),
                BRANCH_CLOSED=images.ImageCache.get_rsc_pixmap(
                    u'branch_closed', None, None, get_path=True),
                BRANCH_OPEN=images.ImageCache.get_rsc_pixmap(
                    u'branch_open', None, None, get_path=True)
            )
        except KeyError as err:
            msg = u'Looks like there might be an error in the css file: {}'.format(
                err)
            raise KeyError(msg)
        widget.setStyleSheet(qss)


def byte_to_string(num, suffix=u'B'):
    """Converts a numeric byte - value to a human readable string."""
    for unit in [u'', u'K', u'M', u'G', u'T', u'P', u'E', u'Z']:
        if abs(num) < 1024.0:
            return u"%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return u"%.1f%s%s" % (num, u'Yi', suffix)


def reveal(path):
    """Reveals the specified folder in the file explorer.

    Args:
        name(str): A path to the file.

    """
    path = get_sequence_endpath(path)
    if get_platform() == u'win':
        args = [u'/select,', QtCore.QDir.toNativeSeparators(path)]
        return QtCore.QProcess.startDetached(u'explorer', args)

    if get_platform() == u'mac':
        args = [
            u'-e',
            u'tell application "Finder"',
            u'-e',
            u'activate',
            u'-e',
            u'select POSIX file "{}"'.format(
                QtCore.QDir.toNativeSeparators(path)), u'-e', u'end tell']
        return QtCore.QProcess.startDetached(u'osascript', args)

    raise NotImplementedError('{} os has not been implemented.'.format(
        QtCore.QSysInfo().productType()))


def get_ranges(arr, padding):
    """Given an array of numbers the method will return a string representation of
    the ranges contained in the array.

    Args:
        arr(list):       An array of numbers.
        padding(int):    The number of leading zeros before the number.

    Returns:
        unicode: A string representation of the given array.

    """
    arr = sorted(list(set(arr)))
    blocks = {}
    k = 0
    for idx, n in enumerate(arr):  # blocks
        zfill = unicode(n).zfill(padding)

        if k not in blocks:
            blocks[k] = []
        blocks[k].append(zfill)

        if idx + 1 != len(arr):
            if arr[idx + 1] != n + 1:  # break coming up
                k += 1
    return u','.join([u'-'.join(sorted(list(set([blocks[k][0], blocks[k][-1]])))) for k in blocks])


def is_valid_filename(text):
    """This method will check if the given text conforms Browser's enforced
    filenaming convention.

    The returned SRE.Match object will contain the groups descripbed below.

    .. code-block:: python

       f = u'000_pr_000_layout_gw_v0006.ma'
       match = get_valid_filename(f)
       match.groups()

    Args:
        group1 (SRE_Match object):        "000" - prefix name.
        group2 (SRE_Match object):        "pr_000" - asset name.
        group3 (SRE_Match object):        "layout" - mode name.
        group4 (SRE_Match object):        "gw" - user name.
        group5 (SRE_Match object):        "0006" - version without the 'v' prefix.
        group6 (SRE_Match object):        "ma" - file extension without the '.'.

    Returns:
        SRE_Match: A ``SRE_Match`` object if the filename is valid, otherwise ``None``

    """
    return ValidFilenameRegex.search(text)


def get_sequence(text):
    """This method will check if the given text contains a sequence element.

    Strictly speaking, a sequence is any file that has a valid number element.
    There can only be **one** incrementable element - it will always be the
    number closest to the end.

    The regex will understand sequences with the `v` prefix, eg *v001*, *v002*,
    but works without the prefix as well. Eg. **001**, **002**. In the case of a
    filename like ``job_sh010_animation_v002.c4d`` **002** will be the
    prevailing sequence number, ignoring the number in the extension.

    Likewise, in ``job_sh010_animation_v002.0001.c4d`` the sequence number will
    be **0001**, and not 010 or 002.

    Args:
        group 1 (SRE_Match):    All the characters **before** the sequence number.
        group 2 (SRE_Match):    The sequence number, as a string.
        group 3 (SRE_Match):    All the characters **after** the sequence number.

    .. code-block:: python

       filename = 'job_sh010_animation_v002_wgergely.c4d'
       match = get_sequence(filename)
       if match:
           prefix = match.group(1) # 'job_sh010_animation_v'
           sequence_number = match.group(2) # '002'
           suffix = match.group(3) # '_wgergely.c4d'

    Returns:
        ``SRE_Match``: ``None`` if the text doesn't contain a number or an ``SRE_Match`` object.

    """
    return GetSequenceRegex.search(text)


def is_collapsed(text):
    """This method will check for the presence of the bracket-enclosed sequence markers.

    When Bookmarks is displaying a sequence of files as a single item,
    the item is *collapsed*. Every collapsed item contains a start and an end number
    enclosed in brackets. For instance: ``image_sequence_[001-233].png``

    Args:
        group 1 (SRE_Match):    All the characters **before** the sequence marker.
        group 2 (SRE_Match):    The sequence marker(eg. ``[01-50]``), as a string.
        group 3 (SRE_Match):    All the characters **after** the sequence marker.

    .. code-block:: python

       filename = 'job_sh010_animation_[001-299]_wgergely.png'
       match = get_sequence(filename)
       if match:
           prefix = match.group(1) # 'job_sh010_animation_'
           sequence_string = match.group(2) # '[001-299]'
           suffix = match.group(3) # '_wgergely.png'

    Returns:
        ``SRE_Match``: If the given name is indeed collpased it returns a ``SRE_Match`` object, otherwise ``None``.

    """
    return IsSequenceRegex.search(text)


def get_sequence_startpath(path):
    """If the given path refers to a collapsed item, it will get the name of the
    the first item in the sequence. In the case of **[0-99]**, the first item is
    **0**.

    Returns:
        ``unicode``: The name of the first element in the sequence.

    """
    if not is_collapsed(path):
        return path

    match = SequenceStartRegex.search(path)
    if match:
        path = SequenceStartRegex.sub(ur'\1\2\3', path)
    return path


def get_sequence_endpath(path):
    """Checks the given string and if it denotes a seuqence returns the path for
    the last file.

    """
    if not is_collapsed(path):
        return path

    match = SequenceEndRegex.search(path)
    if match:
        path = SequenceEndRegex.sub(ur'\1\2\3', path)
    return path


def get_sequence_paths(index):
    """Given the index, returns a tuple of filenames referring to the
    individual sequence items.

    """
    path = index.data(QtCore.Qt.StatusTipRole)
    if not is_collapsed(path):
        return path

    sequence_paths = []
    for frame in index.data(FramesRole):
        seq = index.data(SequenceRole)
        seq = seq.group(1) + frame + seq.group(3) + u'.' + seq.group(4)
        sequence_paths.append(seq)
    return sequence_paths


def draw_aliased_text(painter, font, rect, text, align, color):
    """Allows drawing aliased text using *QPainterPath*.

    This is a slow to calculate but ensures the rendered text looks *smooth* (on
    Windows espcially, I noticed a lot of aliasing issues). We're also eliding
    the given text to the width of the given rectangle.

    Args:
        painter (QPainter):         The active painter.
        font (QFont):               The font to use to paint.
        rect (QRect):               The rectangle to fit the text in.
        text (unicode):             The text to paint.
        align (Qt.AlignmentFlag):   The alignment flags.
        color (QColor):             The color to use.

    Returns:
        int: The width of the drawn text in pixels.

    """
    painter.save()

    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)

    x, y = (rect.left(), rect.top())
    elide = None
    metrics = QtGui.QFontMetricsF(font)

    x = rect.left()
    y = rect.center().y() + (metrics.ascent() / 2.0)
    elide = QtCore.Qt.ElideLeft

    if QtCore.Qt.AlignLeft & align:
        elide = QtCore.Qt.ElideRight
    if QtCore.Qt.AlignRight & align:
        elide = QtCore.Qt.ElideLeft
    if QtCore.Qt.AlignHCenter & align:
        elide = QtCore.Qt.ElideMiddle

    text = metrics.elidedText(
        u'{}'.format(text),
        elide,
        rect.width() + 2)
    width = metrics.width(text)

    if QtCore.Qt.AlignLeft & align:
        x = rect.left()
    if QtCore.Qt.AlignRight & align:
        x = rect.right() - width
    if QtCore.Qt.AlignHCenter & align:
        x = rect.left() + (rect.width() / 2.0) - (width / 2.0)

    if QtCore.Qt.AlignTop & align:
        y = rect.top() + metrics.ascent()
    if QtCore.Qt.AlignVCenter & align:
        y = rect.center().y() + (metrics.ascent() / 2.0)
    if QtCore.Qt.AlignBottom & align:
        y = rect.bottom() - metrics.descent()

    # Making sure text fits the rectangle
    painter.setBrush(color)
    painter.setPen(QtCore.Qt.NoPen)

    path = QtGui.QPainterPath()
    path.addText(x, y, font, text)
    painter.drawPath(path)

    painter.restore()
    return width


def copy_path(path, mode=WindowsPath, first=True, copy=True):
    """Copies a path to the clipboard after converting it to `mode`.

    """
    if first:
        path = get_sequence_startpath(path)
    else:
        path = get_sequence_endpath(path)

    # Normalise path
    path = re.sub(ur'[\/\\]', ur'/', path,
                  flags=re.IGNORECASE | re.UNICODE).strip(u'/')

    if mode == WindowsPath:
        prefix = u'//' if u':' not in path else u''
    elif mode == UnixPath:
        prefix = u'//' if u':' not in path else u''
    elif mode == SlackPath:
        prefix = u'file://'
    elif mode == MacOSPath:
        prefix = u'smb://'
        path = path.replace(u':', u'')
    else:
        prefix = u''
    path = prefix + path
    if mode == WindowsPath:
        path = re.sub(ur'[\/\\]', ur'\\', path,
                      flags=re.IGNORECASE | re.UNICODE)

    if copy:
        QtGui.QClipboard().setText(path)
        Log.info(u'Copied {}'.format(path))

    return path


@QtCore.Slot(QtCore.QModelIndex)
def execute(index, first=False):
    """Given the model index, executes the index's path using QDesktopServices."""
    if not index.isValid():
        return
    path = index.data(QtCore.Qt.StatusTipRole)
    if first:
        path = get_sequence_startpath(path)
    else:
        path = get_sequence_endpath(path)

    url = QtCore.QUrl.fromLocalFile(path)
    QtGui.QDesktopServices.openUrl(url)


def walk(path):
    """This is a custom generator expression using scandir's `walk`.
    We're using the C module for performance's sake without python-native
    fallbacks. The method yields each found DirEntry.

    The used _scandir module itself is customized to contain the addittional
    ``DirEntry.relativepath(unicode: basepath)`` method and ``DirEntry.dirpath``
    attribute.

    Yields:
        DirEntry:   A ctype class.

    """
    # MacOS/Windows encoding error workaround
    try:
        top = unicode(path, u'utf-8')
    except TypeError:
        try:
            top = top.decode(sys.getfilesystemencoding())
        except:
            pass

    try:
        it = _scandir.scandir(path=path)
    except OSError as error:
        return

    while True:
        try:
            try:
                entry = next(it)
            except StopIteration:
                break
        except OSError as error:
            return

        try:
            is_dir = entry.is_dir()
        except OSError:
            is_dir = False

        if not is_dir:
            yield entry

        try:
            is_symlink = entry.is_symlink()
        except OSError:
            is_symlink = False
        if not is_symlink:
            for entry in walk(entry.path):
                yield entry


def rsc_path(f, n):
    """Helper function to retrieve a resource - file item"""
    path = u'{}/../rsc/{}.png'.format(f, n)
    path = os.path.normpath(os.path.abspath(path))
    return path


def ubytearray(ustring):
    """Helper function to convert a unicode string to a QByteArray object."""
    if not isinstance(ustring, unicode):
        raise TypeError('The provided string has to be a unicode string')
    # We convert the string to a hex array
    hstr = [r'\x{}'.format(f.encode('hex')) for f in ustring.encode('utf-8')]
    return QtCore.QByteArray.fromHex(''.join(hstr))


def create_asset_template(source, dest, overwrite=False):
    """Responsible for adding the files and folders of the given source to the
    given zip - file.

    """
    if not overwrite:
        if QtCore.QFileInfo(dest).exists():
            raise RuntimeError('{} exists already'.format(dest))

    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source):
            for d in dirs:
                arcname = os.path.join(root, d).replace(source, u'.')
                zipf.write(os.path.join(root, d), arcname=arcname)
            for f in files:
                arcname = os.path.join(root, f).replace(source, u'.')
                zipf.write(os.path.join(root, f), arcname=arcname)


def push_to_rv(path):
    """Pushes the given given path to RV."""
    import subprocess
    import bookmarks.settings as settings
    import bookmarks.common_ui as common_ui
    def get_preference(k): return settings.local_settings.value(
        u'preferences/{}'.format(k))

    rv_path = get_preference(u'rv_path')
    if not rv_path:
        common_ui.ErrorBox(
            u'Shotgun RV not yet set.',
            u'Set the RV executable path to Push to RV.'
        ).exec_()
        Log.error('RV not set')
        return

    rv_info = QtCore.QFileInfo(rv_path)
    if not rv_info.exists():
        common_ui.ErrorBox(
            u'Invalid Shotgun RV path set.',
            u'Make sure the currently set RV path is valid and try again!'
        ).exec_()
        Log.error('Invalid RV path set')
        return

    if get_platform() == u'win':
        rv_push_path = u'{}/rvpush.exe'.format(rv_info.path())
        if QtCore.QFileInfo(rv_push_path).exists():
            cmd = u'"{}" -tag {} set "{}"'.format(rv_push_path, PRODUCT, path)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            subprocess.Popen(cmd, startupinfo=startupinfo)


font_db = None
