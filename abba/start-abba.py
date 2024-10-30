import os
import platform
import time

from abba_python import abba

import jpype  # in order to wait for a jvm shutdown
import imagej

# THIS FILE SETS MANY PATHS EXPLICITLY WHEN ABBA IS INSTALLED FROM THE INSTALLER

if __name__ == '__main__':
    directory_on_launch = os.path.dirname(os.getcwd())
    import scyjava

    # scyjava.config.add_option('-XX:+UseZGC') # Use ZGC
    scyjava.config.add_option('-Xmx8g') # 5 Gb

    # You can swap the lines below if you want to use a  Fiji instead of the maven downloaded one
    use_local_fiji = True
    if (use_local_fiji):
        if platform.system() == 'Windows':
            fiji_app_path = str(os.path.join(directory_on_launch, 'win', 'Fiji.app'))
        else:
            print('ERROR! ' + platform.system() + ' OS not supported yet.')
            exit()

        print('Starting Fiji located at ' + fiji_app_path)
        ij = imagej.init(fiji_app_path, mode="interactive")
    else:
        print('If this is the first start, please wait for ImageJ/Fiji to be downloaded...')
        ij = imagej.init(abba.get_java_dependencies(), mode="interactive")

    print('ImageJ/Fiji successfully initialized.')

    # Makes BrainGlobe atlases discoverable by ABBA in Fiji
    from abba_python.abba import add_brainglobe_atlases
    add_brainglobe_atlases(ij)

    from scyjava import jimport  # For importing java classes, do not put this import sooner

    from jpype.types import JString

    DebugTools = jimport('loci.common.DebugTools')
    # DebugTools.enableLogging('OFF') # less logging
    DebugTools.enableLogging("INFO")
    # DebugTools.enableLogging("DEBUG"); # more logging
    python_info = 'ABBA Python (installer) v0.9.6.dev0'
    ABBAForumHelpCommand = jimport('ch.epfl.biop.atlas.aligner.command.ABBAForumHelpCommand')
    ABBAForumHelpCommand.pythonInformation = JString(python_info)

    File = jimport('java.io.File')
    # Sets DeepSlice env path - hopefully it's a common location for all OSes
    deepslice_env_path = str(os.path.join(directory_on_launch, 'envs', 'deepslice'))
    deepslice_version = JString(str('1.1.5.1'))
    DeepSlice = jimport('ch.epfl.biop.wrappers.deepslice.DeepSlice')
    DeepSlice.setEnvDirPath(File(deepslice_env_path))
    DeepSlice.setVersion(deepslice_version)  # not autodetected. Do not matter for 1.1.5, but may matter later

    # For setting elastix and transformix location, OS dependent
    # File ch.epfl.biop.wrappers.elastix.Elastix exePath
    # File ch.epfl.biop.wrappers.transformix.Transformix exePath
    Elastix = jimport('ch.epfl.biop.wrappers.elastix.Elastix')
    Transformix = jimport('ch.epfl.biop.wrappers.transformix.Transformix')

    # For setting the atlas cache folder, OS dependent, we want this property to be system-wide
    AtlasLocationHelper = jimport('ch.epfl.biop.atlas.AtlasLocationHelper')

    if platform.system() == 'Windows':
        # Conda
        Conda = jimport('ch.epfl.biop.wrappers.Conda')
        condaPath = str(os.path.join(directory_on_launch, 'condabin', 'conda.bat'))
        Conda.windowsCondaCommand = JString(str(condaPath))  # Sets the conda path

        elastixPath = str(os.path.join(directory_on_launch, 'win', 'elastix-5.2.0-win64', 'elastix.exe'))
        transformixPath = str(os.path.join(directory_on_launch, 'win', 'elastix-5.2.0-win64', 'transformix.exe'))

        Elastix.exePath = JString(str(elastixPath))
        Elastix.setExePath(File(JString(str(elastixPath))))
        Transformix.exePath = JString(str(transformixPath))
        Transformix.setExePath(File(JString(str(transformixPath))))

        # Now let's set the atlas folder location in a folder that all users can access
        # create the directory with write access for all users
        try:
            directory = os.path.join(os.environ['ProgramData'], 'abba-atlas')
            print('Attempt to set ABBA Atlas cache directory to ' + directory)
            # //os.mkdir(directory)
            os.makedirs(directory, exist_ok=True)
            atlasPath = str(directory)
            AtlasLocationHelper.defaultCacheDir = File(JString(atlasPath))
            print('ABBA Atlas cache directory set to ' + directory)
        except OSError:
            print('ERROR! Could not set ABBA Atlas cache dir')
            # directory already exists ?
            pass

    else:
        print('ERROR! ' + platform.system() + ' OS not supported yet.')

    ij.ui().showUI()  # will showing the UI at the end fix Mac threading issues ?

    # Wait for the JVM to shut down
    while jpype.isJVMStarted():
        time.sleep(1)

    print("JVM has shut down")
