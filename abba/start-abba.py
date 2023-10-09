import os
import platform
import time

from abba_python import abba
from abba_python.abba import add_brainglobe_atlases

import jpype # in order to wait for a jvm shutdown
import imagej

# THIS FILE SETS MANY PATHS EXPLICITLY WHEN ABBA IS INSTALLED FROM THE INSTALLER

if __name__ == '__main__':
    os.path.dirname(os.getcwd())
    import scyjava
    # scyjava.config.add_option('-XX:+UseZGC') # Use ZGC
    # You can swap the two next lines if you want to use a local Fiji instead of the maven downloaded one
    # fiji_app_path = str(os.path.join(os.path.dirname(os.getcwd()), 'Fiji.app'))
    print('If this is the first start, please wait for ImageJ/Fiji to be downloaded...')
    ij = imagej.init(abba.get_java_dependencies(), mode="interactive")
    print('ImageJ/Fiji successfully initialized.')

	# Makes BrainGlobe atlases discoverable by ABBA in Fiji
    add_brainglobe_atlases(ij)


    from scyjava import jimport # For importing java classes, do not put this import sooner

    from jpype.types import JString

    DebugTools = jimport('loci.common.DebugTools')
	# DebugTools.enableLogging('OFF') # less logging
    DebugTools.enableLogging("INFO");
    # DebugTools.enableLogging("DEBUG"); # more logging
	
    File = jimport('java.io.File')
    # Sets DeepSlice env path - hopefully it's a common location for all OSes
    deepslice_env_path = str(os.path.join(os.path.dirname(os.getcwd()), 'envs', 'deepslice'))
    deepslice_version = JString(str('1.1.5'))
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
        elastixPath = str(os.path.join(os.path.dirname(os.getcwd()), 'win', 'elastix-5.0.1-win64', 'elastix.exe'))
        transformixPath = str(os.path.join(os.path.dirname(os.getcwd()), 'win', 'elastix-5.0.1-win64', 'transformix.exe'))

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

        # TODO: Set DeepSlice conda env
    else:
        print('ERROR! '+platform.system()+' OS not supported yet.')

    ij.ui().showUI() # will showing the UI at the end fix Mac threading issues ?

    # Wait for the JVM to shut down
    while jpype.isJVMStarted():
        time.sleep(1)

    print("JVM has shut down")
