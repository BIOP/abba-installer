TODO : You should unzip elastix-5.2.0 in this folder, windows version

The folder hierarchy should be:
abba-installer/win/elastix-5.2.0-win64
and for instance the file
abba-installer/win/elastix-5.2.0-win64/elastix.exe should exist

You can build ImageToAtlasRegister from an IDE and set the correct path in properties:

<scijava.app.directory>C:/Users/chiarutt/Dropbox/BIOP/abba-installer/win/Fiji.app</scijava.app.directory>

Then remove imagej updater (optional)
Add scijava dependencies:
- imglib2-imglyb-1.1.0
- imglib2-unsafe-1.0.0