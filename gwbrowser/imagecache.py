# -*- coding: utf-8 -*-
# pylint: disable=E1101, C0103, R0913, I1101, W0613, R0201, C0326


"""This modules defines most thumbnail-related classes and methods including
the image cache and the OpenImageIO-based thmbnail generator methods.

"""

import sys
import os

from PySide2 import QtWidgets, QtGui, QtCore

from gwbrowser.capture import ScreenGrabber
from gwbrowser.settings import AssetSettings
import gwbrowser.common as common

import OpenImageIO.OpenImageIO as OpenImageIO

from gwbrowser.threads import BaseThread
from gwbrowser.threads import BaseWorker
from gwbrowser.threads import Unique


class ImageCacheWorker(BaseWorker):
    """Note: This thread worker is a duplicate implementation of the FileInfoWorker."""
    queue = Unique(999999)

    @QtCore.Slot(QtCore.QModelIndex)
    @QtCore.Slot(unicode)
    @classmethod
    def process_index(cls, index, source=None, dest=None, dest_size=common.THUMBNAIL_IMAGE_SIZE):
        """The actual processing happens here."""
        if not source and not dest:
            if not index.isValid():
                return
            if not index.data(common.StatusRole):
                return

        if index.isValid():
            if not index.data(QtCore.Qt.StatusTipRole):
                return

        # If it's a sequence, we will find the largest file in the sequence and
        # generate the thumbnail for that item
        source = source if source else index.data(QtCore.Qt.StatusTipRole)
        if common.is_collapsed(source):
            source = common.find_largest_file(index)
        dest = dest if dest else index.data(common.ThumbnailPathRole)

        # First let's check if the file is competible with OpenImageIO
        i = OpenImageIO.ImageInput.open(source)
        if not i:
            return  # the file is not understood by OenImageIO
        i.close()

        img = OpenImageIO.ImageBuf(source)

        if img.has_error:
            return

        # Deep
        if img.spec().deep:
            img = OpenImageIO.ImageBufAlgo.flatten(img)

        size = int(dest_size)
        spec = OpenImageIO.ImageSpec(size, size, 4, "uint8")
        spec.channelnames = ('R', 'G', 'B', 'A')
        spec.alpha_channel = 3
        spec.attribute('oiio:ColorSpace', 'Linear')
        b = OpenImageIO.ImageBuf(spec)
        b.set_write_format('uint8')

        OpenImageIO.set_roi_full(img.spec(), OpenImageIO.get_roi(img.spec()))
        OpenImageIO.ImageBufAlgo.fit(b, img)

        spec = b.spec()
        if spec.get_string_attribute('oiio:ColorSpace') == 'Linear':
            roi = OpenImageIO.get_roi(b.spec())
            roi.chbegin = 0
            roi.chend = 3
            OpenImageIO.ImageBufAlgo.pow(b, b, 1.0 / 2.2, roi)

        if int(spec.nchannels) < 3:
            b = OpenImageIO.ImageBufAlgo.channels(
                b, (spec.channelnames[0], spec.channelnames[0], spec.channelnames[0]), ('R', 'G', 'B'))
        elif int(spec.nchannels) > 4:
            if spec.channelindex('A') > -1:
                b = OpenImageIO.ImageBufAlgo.channels(
                    b, ('R', 'G', 'B', 'A'), ('R', 'G', 'B', 'A'))
            else:
                b = OpenImageIO.ImageBufAlgo.channels(
                    b, ('R', 'G', 'B'), ('R', 'G', 'B'))

        # There seems to be a problem with the ICC profile exported from Adobe
        # applications and the PNG library. The sRGB profile seems to be out of date
        # and pnglib crashes when encounters an invalid profile.
        # Removing the ICC profile seems to fix the issue. Annoying!

        # First, rebuilding the attributes as a modified xml tree
        modified = False

        from xml.etree import ElementTree
        root = ElementTree.fromstring(b.spec().to_xml())
        for attrib in root.findall('attrib'):
            if attrib.attrib['name'] == 'ICCProfile':
                root.remove(attrib)
                modified = True
                break

        if modified:
            xml = ElementTree.tostring(root)
            # Initiating a new spec with the modified xml
            spec = OpenImageIO.ImageSpec()
            spec.from_xml(xml)

            # Lastly, copying the pixels over from the old to the new buffer.
            _b = OpenImageIO.ImageBuf(spec)
            pixels = b.get_pixels()
            _b.set_write_format('uint8')
            _b.set_pixels(OpenImageIO.get_roi(spec), pixels)
        else:
            _b = b

        # Ready to write
        if not _b.write(dest, dtype='uint8'):
            QtCore.QFile(dest).remove()  # removing failed thumbnail save
            return
        else:
            if not index.isValid():
                return

            if index.isValid():
                if not index.data(QtCore.Qt.SizeHintRole):
                    return
                if not index.data(common.ThumbnailPathRole):
                    return

            image = ImageCache.instance().get(
                index.data(common.ThumbnailPathRole),
                index.data(QtCore.Qt.SizeHintRole).height() - 2,
                overwrite=True)

            color = ImageCache.instance().get(
                index.data(common.ThumbnailPathRole),
                'BackgroundColor',
                overwrite=False)

            data = index.model().model_data()
            data[index.row()][common.ThumbnailRole] = image
            data[index.row()][common.ThumbnailBackgroundRole] = color

            index.model().dataChanged.emit(index, index)


class ImageCacheThread(BaseThread):
    Worker = ImageCacheWorker


class ImageCache(QtCore.QObject):
    """Utility class for setting, capturing and editing thumbnail and resource
    images.

    All cached images are stored in ``ImageCache._data`` `(dict)` object.
    To add an image to the cache you can use the ``ImageCache.get()`` method.
    Loading and caching ui resource items is done by ``ImageCache.get_rsc_pixmap()``.

    """
    # Data and instance container
    _data = {}
    __instance = None

    # Signals
    thumbnailChanged = QtCore.Signal(QtCore.QModelIndex)

    @staticmethod
    def instance():
        """ Static access method. """
        if ImageCache.__instance == None:
            ImageCache()
        return ImageCache.__instance

    @classmethod
    def initialize(cls, *args, **kwargs):
        """ Static create method. """
        cls(*args, **kwargs)
        return ImageCache.__instance

    def __init__(self, parent=None):
        """Init method.

        The associated ``ImageCacheThread`` control objects will be create and
        started here automatically.

        """
        if ImageCache.__instance != None:
            raise RuntimeError(u'\n# {} already initialized.\n# Use ImageCache.instance() instead.'.format(
                self.__class__.__name__))
        super(ImageCache, self).__init__(parent=parent)
        ImageCache.__instance = self

        # This will cache all the thumbnail images
        def rsc_path(f): return os.path.normpath(
            os.path.abspath(u'{}/../rsc/placeholder.png'.format(f)))
        ImageCache.instance().get(rsc_path(__file__), common.ROW_HEIGHT - 2)

        self.threads = {}
        for n in xrange(common.ITHREAD_COUNT):
            self.threads[n] = ImageCacheThread(self)
            self.threads[n].thread_id = n
            self.threads[n].start()

    @staticmethod
    def get(path, height, overwrite=False):
        """Saves a resized copy of path to the cache.

        Returns the cached image if it already is in the cache, or the placholder
        image if loading fails. In addittion, each cached entry
        will be associated with a backgroun- color based on the image's colours.

        Args:
            path (str):    Path to the image file.
            height (int):  Description of parameter `height`.

        Returns:
            QImage: The cached and resized QImage.

        """
        k = u'{path}:{height}'.format(
            path=path,
            height=height
        )

        # Return cached item if exsits
        if k in ImageCache._data and not overwrite:
            return ImageCache._data[k]

        # Checking if the file can be opened
        i = OpenImageIO.ImageInput.open(path)
        if not i:
            return None
        i.close()

        image = QtGui.QImage()
        image.load(path)
        if image.isNull():
            return None

        image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
        image = ImageCache.resize_image(image, height)

        # Saving the background color
        ImageCache._data[u'{k}:BackgroundColor'.format(
            k=path
        )] = ImageCache.get_color_average(image)
        ImageCache._data[k] = image

        return ImageCache._data[k]

    @staticmethod
    def resize_image(image, size):
        """Returns a scaled copy of the image fitting inside the square of ``size``.

        Args:
            image (QImage): The image to rescale.
            size (int): The width/height of the square.

        Returns:
            QImage: The resized copy of the original image.

        """
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

    @staticmethod
    def get_color_average(image):
        """Returns the average color of an image."""
        if image.isNull():
            return QtGui.QColor(common.SECONDARY_BACKGROUND)

        r = []
        g = []
        b = []

        for x in xrange(image.width()):
            for y in xrange(image.height()):
                if image.pixelColor(x, y).alpha() < 0.01:
                    continue
                r.append(image.pixelColor(x, y).red())
                g.append(image.pixelColor(x, y).green())
                b.append(image.pixelColor(x, y).blue())

        if not all([float(len(r)), float(len(g)), float(len(b))]):
            average_color = QtGui.QColor(common.SECONDARY_BACKGROUND)
        else:
            average_color = QtGui.QColor(
                sum(r) / float(len(r)),
                sum(g) / float(len(g)),
                sum(b) / float(len(b))
            )
        average_color.setAlpha(int(average_color.alpha() / 2))
        return average_color

    def generate_thumbnails(self, indexes, overwrite=False):
        """Takes a list of index values and generates thumbnails for them.

        Note:
            This method is affiliated with the main GUI thread, but the images
            are generated in worker threads.

        """

        def filtered(indexes, overwrite=None):
            """Filter method for making sure only acceptable files types will be querried."""
            for index in indexes:
                ext = index.data(QtCore.Qt.StatusTipRole).split('.')[-1]
                if ext not in common._oiio_formats:
                    continue
                if not index.data(common.StatusRole):
                    continue
                dest = AssetSettings(index).thumbnail_path()
                if not overwrite and QtCore.QFileInfo(dest).exists():
                    continue
                yield index

        ImageCacheWorker.add_to_queue(filtered(indexes, overwrite=overwrite))

    @classmethod
    def generate(cls, index, source=None):
        """OpenImageIO based method to generate sRGB thumbnails bound by ``THUMBNAIL_IMAGE_SIZE``."""
        raise DeprecationWarning('obsolete call, update!')

    def capture(self, index):
        """Uses ``ScreenGrabber to save a custom screen-grab."""
        if not index.isValid():
            return

        pixmap = ScreenGrabber.capture()
        if not pixmap:
            return
        if pixmap.isNull():
            return
        image = pixmap.toImage()
        image = self.resize_image(image, common.THUMBNAIL_IMAGE_SIZE)
        if image.isNull():
            return

        f = QtCore.QFile(index.data(common.ThumbnailPathRole))
        if f.exists():
            f.remove()
        if not image.save(index.data(common.ThumbnailPathRole)):
            sys.stderr.write('# Capture thumnail error: Error saving {}.\n'.format(
                index.data(common.ThumbnailPathRole)))
            return

        image = self.get(
            index.data(common.ThumbnailPathRole),
            index.data(QtCore.Qt.SizeHintRole).height() - 2,
            overwrite=True)
        color = self.get(
            index.data(common.ThumbnailPathRole),
            'BackgroundColor',
            overwrite=False)

        data = index.model().model_data()
        data[index.row()][common.ThumbnailRole] = image
        data[index.row()][common.ThumbnailBackgroundRole] = color
        index.model().dataChanged.emit(index, index)

    def remove(self, index):
        """Deletes the thumbnail file from storage and the cached entry associated
        with it.

        Emits ``thumbnailChanged`` signal.

        """
        if not index.isValid():
            return

        file_ = QtCore.QFile(index.data(common.ThumbnailPathRole))

        if file_.exists():
            file_.remove()

        keys = [k for k in self._data if index.data(
            common.ThumbnailPathRole).lower() in k.lower()]
        for key in keys:
            del self._data[key]

        data = index.model().model_data()
        data[index.row()][common.ThumbnailRole] = data[index.row()
                                                       ][common.DefaultThumbnailRole]
        data[index.row()][common.ThumbnailBackgroundRole] = data[index.row()
                                                                 ][common.DefaultThumbnailBackgroundRole]
        index.model().dataChanged.emit(index, index)

    @classmethod
    def pick(cls, index):
        """Opens a file-dialog to select an OpenImageIO compliant file."""
        dialog = QtWidgets.QFileDialog()
        common.set_custom_stylesheet(dialog)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setViewMode(QtWidgets.QFileDialog.List)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptOpen)
        dialog.setNameFilters(common.get_oiio_namefilters())
        dialog.setFilter(QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot)
        dialog.setLabelText(QtWidgets.QFileDialog.Accept, 'Pick thumbnail')
        dialog.setDirectory(QtCore.QFileInfo(
            index.data(QtCore.Qt.StatusTipRole)).filePath())

        if not dialog.exec_():
            return
        if not dialog.selectedFiles():
            return

        # Saving the thumbnail
        ImageCacheWorker.process_index(index, source=dialog.selectedFiles()[0])
        index.model().dataChanged.emit(index, index)

    @classmethod
    def get_rsc_pixmap(cls, name, color, size, opacity=1.0):
        """Loads a rescoure image and returns it as a re-sized and coloured QPixmap.

        Args:
            name (str): Name of the resource without the extension.
            color (QColor): The colour of the icon.
            size (int): The size of pixmap.

        Returns:
            QPixmap: The loaded image

        """

        k = u'{name}:{size}:{color}'.format(
            name=name, size=size, color=u'null' if not color else color.name())

        if k in cls._data:
            return cls._data[k]

        path = u'{}/../rsc/{}.png'.format(__file__, name)
        path = os.path.normpath(os.path.abspath(path))
        file_info = QtCore.QFileInfo(path)
        if not file_info.exists():
            return QtGui.QPixmap(size, size)

        image = QtGui.QImage()
        image.load(file_info.absoluteFilePath())

        if image.isNull():
            return QtGui.QPixmap(size, size)

        image = image.convertToFormat(QtGui.QImage.Format_ARGB32)
        if color is not None:
            painter = QtGui.QPainter()
            painter.begin(image)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            painter.setBrush(QtGui.QBrush(color))
            painter.drawRect(image.rect())
            painter.end()

        image = cls.resize_image(image, size)
        pixmap = QtGui.QPixmap()
        pixmap.convertFromImage(image)

        # Setting transparency
        if opacity < 1.0:
            image = QtGui.QImage(
                pixmap.size(), QtGui.QImage.Format_ARGB32)
            image.fill(QtCore.Qt.transparent)

            painter = QtGui.QPainter()
            painter.begin(image)
            painter.setOpacity(opacity)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            pixmap = QtGui.QPixmap()
            pixmap.convertFromImage(image)

        cls._data[k] = pixmap
        return cls._data[k]


# Initializing the ImageCache:
ImageCache.initialize()
