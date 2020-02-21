# -*- coding: utf-8 -*-
"""The threads and the associated workers are defined here.

GWBrowser does OpenImageIO and file-load operations on separate threads
controlled by QThread objects.

Each thread is assigned a single Worker - usually responsible for taking
*QModelIndexes* from the thread's python Queue.

"""
import sys
import traceback
import Queue
from PySide2 import QtCore

import gwbrowser.common as common


class Unique(Queue.Queue):
    """A queue for queuing only unique items.
    https://stackoverflow.com/questions/16506429/check-if-element-is-already-in-a-queue"""

    def _init(self, maxsize):
        self.queue = set()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()


class BaseWorker(QtCore.QObject):
    """The base for all workers associated with a QThread.
    `exec_` is a blocking function and will take any QModelIndexes in
    in `BaseWorker.Unique` queue.

    """
    queue = Unique(999999)
    shutdown_requested = False
    indexes_in_progress = []

    queueFinished = QtCore.Signal()
    finished = QtCore.Signal()

    def __init__(self, parent=None):
        super(BaseWorker, self).__init__(parent=parent)
        self.model = None

    @QtCore.Slot()
    def shutdown(self):
        """Quits the index-processing block. We're using the built-in python
        Queue.get(True) method ehich blocks the executing thread until there's
        an available worker to fetch the next queued item.

        To break the lock, it is necessary to add an invalid `QModelIndex` to
        the queue.

        """
        self.queue.put(QtCore.QModelIndex())
        self.shutdown_requested = True

    @QtCore.Slot(tuple)
    @classmethod
    def add_to_queue(cls, indexes):
        """Adds the given list of indexes to the worker's queue."""
        current_queue = cls.queue.queue
        indexes = [f for f in indexes if f not in current_queue]
        for index in indexes:
            if not index.isValid():
                continue
            if not index.data(QtCore.Qt.StatusTipRole):
                continue
            if not index.data(common.ParentPathRole):
                continue
            cls.queue.put(index)

    @classmethod
    def reset_queue(cls):
        """Empties the queue"""
        try:
            while cls.queue.qsize() > 0:
                cls.queue.get(False)
        except Queue.Empty:
            return
        except Exception:
            sys.stderr.write(u'{}\n'.format(traceback.format_exc()))

    @QtCore.Slot()
    def begin_processing(self):
        """Starts the processing queue of this worker.

        Each worker class is assigned a Queue, the process will automatically
        take the item as it becomes available.

        Note:
            get(True) will block the thread until a new item is available in
            the queue. On any Exceptions the function will call itself again.

        """
        try:
            # We will keep taking items from the queue until shutdown had been requested
            while not self.shutdown_requested:
                # Take the next available index from the queue
                # It is possible however, that the index has been added back into
                # the queue after a thread has taken it.
                # Let's check if this is the case and take the next index instead
                index = self.queue.get(True)
                mutex.lock()
                while index in self.indexes_in_progress:
                    index = self.queue.get(True)
                mutex.unlock()

                # This thread is the first to take the item, we will add the index
                # to the list
                mutex.lock()
                if index not in self.indexes_in_progress:
                    self.indexes_in_progress.append(index)
                mutex.unlock()

                # Finally, we process the index
                self.process_index(index)

                # We'll remove the index from the currently processing items
                mutex.lock()
                if index in self.indexes_in_progress:
                    self.indexes_in_progress.remove(index)
                mutex.unlock()
        except Queue.Empty:
            return
        finally:
            if self.shutdown_requested:
                self.finished.emit()
            else:
                self.begin_processing()

    @QtCore.Slot(QtCore.QModelIndex)
    def process_index(self, index, update=True, make=True):
        """The actual processing happens here.
        Make sure this overriden in the subclass.

        """
        raise NotImplementedError('Abstract method.')


class BaseThread(QtCore.QThread):
    """Base thread controller used across GWBrowser.
    Threads are responsible for updating the file-list with the missing
    information and generating thumbnails.

    Note:
        I can't get threads to work using the documented way -
        depending on conditions I don't understand, the thread sometimes executes
        the worker, sometimes the `started` signal doesn't fire when the Worker is
        created outside the thread.

        This is a custom implementation - the worker is created in start() making sure
        it is affiliated with the thread (qobject.moveToThread didn't work for me).

    """
    _instances = {}
    __worker = None
    Worker = BaseWorker

    def __init__(self, parent=None):
        super(BaseThread, self).__init__(parent=parent)
        BaseThread._instances[repr(self)] = self
        self.setTerminationEnabled(True)

        self.thread_id = None
        self.worker = None

    def run(self):
        """Run() is guaranteed to be executed in the thread controlled by QThread instances.

        To guarantee thread affinity, we're initiating the thread's worker here.
        I opted
        """
        self.worker = self.Worker()
        self.worker.finished.connect(self.quit)
        self.started.emit()
        self.worker.begin_processing()
