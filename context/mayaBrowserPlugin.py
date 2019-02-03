# -*- coding: utf-8 -*-
"""Browser - Maya plug-in.

This plug-in is a Maya front-end to 'Browser', a custom PyQt pipeline package.
Please note, this is a development release, and I can take no warranty for any
of the functionality.

Description:
    The plug-in is responsible for setting Maya projects and importing, opening and
    referencing maya scenes.
    Once installed and loaded, the browser window can be found in Maya's 'File'
    menu. The application-wide shortcut to show the panel is 'Ctrl+Shift+O'.

Installation:
    Place 'mayaBrowserPlugin.py' into one of the plug-in directories read by maya.
    The list of plug-in directories can be retrieved by running the following in
    the script editor:

    import os
    for path in os.environ['MAYA_PLUG_IN_PATH'].split(';'):
        print path

    By default, on windows, the default user plug-in paths are:
        C:/Users/[user name]/Documents/maya/[version]/plug-ins
        C:/Users/[user name]/Documents/maya/plug-ins

    Then, in Maya you have to load the plug-in via the Plug-in Manager.

Important:
    Before loading the plug-in make sure the main 'Browser' module is placed in
    one of the python script directories. You can get them by running:

    import sys
    for path in sys.path:
        print path

    By default, on windows, the default user script paths are:
        C:/Users/[user name]/Documents/maya/[version]/scripts
        C:/Users/[user name]/Documents/maya/scripts

    After copying, you can test by your setup by trying to import 'browser'
    by running in the script editor:

    import browser

    If you get any error messages something went south...

Credits:
    Gergely Wootsch, 2018, September.
    hello@gergely-wootsch.com
    http://gergely-wootsch.com

"""
# pylint: disable=E1101, C0103, R0913, I1101

import sys

def maya_useNewAPI():
    """
    The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.

    """
    pass


def initializePlugin(plugin):
    """Method is called by Maya when initializing the plug-in."""
    from PySide2 import QtWidgets

    import maya.api.OpenMaya as OpenMaya
    from browser.context.mayawidget import MayaToolbar

    pluginFn = OpenMaya.MFnPlugin(plugin, vendor='Gergely Wootsch', version='0.2.0')

    try:
        MayaToolbar()
        sys.stdout.write('# Browser: Plugin loaded.')
    except ImportError as err:
        sys.stderr.write(err)
        errStr = '# Browser:  Unable to import the "mayabrowser" from the "browser" module.\n'
        errStr = '# Browser:  Make sure the "browser" python module has been added to Maya\'s python path.'
        raise ImportError(errStr)
    except:
        sys.stderr.write('# Borwser: Unkown error occured.')
        raise


def uninitializePlugin(plugin):
    """Method is called by Maya when unloading the plug-in."""
    import maya.OpenMayaUI as OpenMayaUI
    import maya.api.OpenMaya as OpenMaya
    from maya.app.general.mayaMixin import mixinWorkspaceControls

    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance

    from browser.context.mayawidget import MayaToolbar

    pluginFn = OpenMaya.MFnPlugin(plugin, vendor='Gergely Wootsch', version='0.2.0')

    try:
        ptr = OpenMayaUI.MQtUtil.findControl('ToolBox')
        widget = wrapInstance(long(ptr), QtWidgets.QWidget)
        widget = widget.findChild(MayaToolbar)
        widget.deleteLater()

        # Deleting workspacecontrols
        for k in (f for f in mixinWorkspaceControls if 'MayaWidget' in f):
            mixinWorkspaceControls[k].deleteLater()
            mixinWorkspaceControls[k].parent().deleteLater()

        del MayaToolbar

        # Deleting the python modules
        for k, _ in sys.modules.items():
            if 'browser' in k:
                del sys.modules[k]

        sys.stdout.write('# Browser: Plugin un-loaded.')

    except Exception as err:
        sys.stderr.write(err)
        sys.stderr.write('# Browser: Failed to unregister plugin.')
        raise Exception()
