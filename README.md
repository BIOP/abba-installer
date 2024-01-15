# Full Repository for Creating an Installer for [ABBA](https://biop.github.io/ijp-imagetoatlas/)

Welcome to the repository designed to support the creation of standalone installers for [ABBA](https://biop.github.io/ijp-imagetoatlas/). This repository utilizes [conda constructor](https://github.com/conda/constructor) as its core tool. Currently, only Windows is supported, but if you are interested in contributing a standalone installer for other operating systems, please feel free to do so!

## Why Create an Installer?

I have a strong affinity for [Fiji](https://imagej.net/). I appreciate Java for its robustness, even if it can be a bit verbose, and its cross-platform compatibility. In most cases, you simply install it, add a few update sites, and it works seamlessly on Windows, Mac, and Linux.

However, in today's landscape, Java alone doesn't cut it. ABBA can be used as an update site in ImageJ/Fiji, but this "core ABBA" doesn't function seamlessly with:

- [elastix and transformix](https://github.com/SuperElastix/elastix), the software utilized for automated in-plane registration.
- [Brainglobe atlases](https://brainglobe.info/index.html).
- [DeepSlice](https://github.com/PolarBean/DeepSlice) for on-axis (and affine in-plane) registration.

While elastix, transformix, and DeepSlice can be integrated into Fiji with some effort and configuration, the Brainglobe atlases remain inaccessible.

In the end, failing to provide a convenient installation method frustrates everyone involved: users who struggle with installation (or give up before attempting), and developers who find themselves constantly addressing installation issues instead of focusing on documentation, bug fixes, or new features. Soon, you'll realize that you're spending all your time trying (and failing) to install tools.

Over the past few years, my primary focus has been simplifying the installation process for ABBA, and this repository represents the best solution I've achieved so far.

What's the trade-off? First, it's me investing time into creating an installer. Second, with a standalone application, you lose some modularity and the ability to easily add functionalities if you know how to do so. That's why I recommend sticking with "pip install" and configuring it manually if you want to add your own Python script and additional modules. However, it's worth noting that this installer adds a well-defined conda environment for ABBA, so you still have the option to modify the environment created by the installer. To locate it, you can use `conda env list` with Miniforge.

## The Challenge of Creating an Installer for ABBA

ABBA, being Java-based (ImageJ/Fiji), needs to communicate with Python (Brainglobe, DeepSlice) and a standalone application (elastix, transformix).

### Java Communicating with Python

For Fiji and Python, [pyimagej](https://py.imagej.net/en/latest/), backed by [jpype](https://jpype.readthedocs.io/en/latest/), has been developed. With this, ImageJ and Fiji can seamlessly communicate. Thanks to pyimagej, all Brainglobe atlases can be utilized in ABBA.

### Java Communicating with elastix

Elastix has a [Python wrapper](https://github.com/InsightSoftwareConsortium/ITKElastix), theoretically allowing us to avoid using the elastix standalone application. However, ITKElastix is available via pip, not conda, relies on binaries, and is slow to initialize in Python due to lazy loading. In the end, there was already a pre-existing Java wrapper that did the job well enough, so I chose to stick with it. This means ABBA needs to know the location of the standalone elastix (and transformix) executable.

### Working with DeepSlice

Although DeepSlice has a [pip repository](https://pypi.org/project/DeepSlice/) and could potentially work with pyimagej at some point, it depends on an [old TensorFlow version and is not easily updatable](https://github.com/PolarBean/DeepSlice/issues/41). To ensure compatibility with additional Python tools and to maintain flexibility, it's better to keep DeepSlice in a separate conda environment.

## How Does This Installer Work?

**NOTE: An internet connection is required for the installer to function, as it downloads some pip dependencies from PyPI.**

This installer leverages conda-constructor, a tool used to create standalone installers for conda environments on Windows, Mac, and Linux.

This installer creates two environments:

1. A primary conda environment for pyimagej and Brainglobe.
2. An additional environment for DeepSlice.

However, this alone is not sufficient. With the help of conda constructor and a post-installation script, the following components are added:

- The elastix/transformix standalone application.
- The models used by DeepSlice.
- Pip dependencies, including abba-python in the primary conda environment and DeepSlice in the extra environment.

Furthermore, an executable shortcut is included. This shortcut runs a Python script that configures ABBA just before launch:

- It sets the paths for elastix and transformix.
- It configures the DeepSlice conda environment.
- It designates an OS-wide folder for caching atlases to prevent redundant downloads.

The initial launch of ABBA may take some time since it needs to download most of Fiji's jars. Therefore, an internet connection is necessary.

## How to Create the Installer

### To do once: create an env for conda-constructor
```
conda create --name constructor-env constructor
conda activate constructor-env
```

### Use conda-constructor
The YAML file in this repository is required by conda-constructor. However, additional steps are needed to build the installer:

1. Clone this repository.
2. Create a conda environment, activate it, and then install conda-constructor within it.
3. (Optional) Copy the DeepSlice models you require to the `envs/deepslice/lib/site-packages/DeepSlice/metadata/weights/` subfolder. This prevents model downloads during the first DeepSlice execution, significantly improving startup time. Model URLs:
   - [xception_weights_tf_dim_ordering_tf_kernels.h5](https://data-proxy.ebrains.eu/api/v1/buckets/deepslice/weights/xception_weights_tf_dim_ordering_tf_kernels.h5)
   - [Allen_Mixed_Best.h5](https://data-proxy.ebrains.eu/api/v1/buckets/deepslice/weights/Allen_Mixed_Best.h5)
   - [Synthetic_data_final.hdf5](https://data-proxy.ebrains.eu/api/v1/buckets/deepslice/weights/Synthetic_data_final.hdf5)

Each operating system has its own requirements:

### Windows

Place the [elastix executables](https://github.com/SuperElastix/elastix/releases/tag/5.0.1) in the `win` subfolder under version 5.0.1: `win\elastix-5.0.1-win64`. Then run `prepare_win.bat`, which generates an `abba-pack-win.tar.gz` file. This file will be included in the installer and unpacked during installation using the post-install script.
TODO: add in prepare_win.sh script

### Mac

Please refer to [this issue](https://github.com/NicoKiaru/ABBA-Python/issues/16).

### Linux

Please refer to [this issue](https://github.com/NicoKiaru/ABBA-Python/issues/17).

## Actually Building the Installer

In the conda environment with conda constructor that you created, set the repository folder as your current directory, then execute `constructor .`. After a few minutes, an executable file will be generated - that's your installer! Keep in mind that if you need to create a Mac installer, you'll need a Mac machine, and for a Linux installer, you'll need a Linux machine.

## Potential Improvements

I would like to explore using the mamba solver because conda can be quite slow.

[Link to mamba.bat](C:\ProgramData\Miniconda3\condabin\mamba.bat) and [reference to issue](https://github.com/mamba-org/mamba/issues/1627).

### Note for using a local Fiji copy jars!

Initialize with a local Fiji.app installation, so that PyImageJ does not need to download anything else from the Internet. In this case you will also have to manually download the latest .jar files for imglib2-unsafe and imglib2-imglyb and place them in your local Fiji.app/jars directory, as these are required for PyImageJ but not part of the standard Fiji distribution

**TODO List**:
- Include a message informing users that a valid internet connection is required to run this installer (for pip dependencies).
- Consider including a local Fiji distribution.
- Explore adding dependencies for OMERO.
- DO NOT FORGET TO CHANGE THE VERSION IN THE SHORTCUT
