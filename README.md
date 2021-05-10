# RSI-editor
## A metadata editor for Robust Station Images - currently in alpha 

RSI-editor is a GUI for doing visual editing of [RSI files](https://github.com/space-wizards/RSI.py). It is intended to lower the barrier for creating new RSIs, and converting existing DMI files to the RSI format. Requires Python 3.7 or newer.

## Install

1. If you don't have `pipenv` installed, run `pip install pipenv` in a command line window.
2. In the RSI-Editor folder, open a command window and type `pipenv install`.
3. Use the start.bat to start the RSI-Editor.

## Usage

### Opening an RSI

To open an RSI, select `Open` from the `File` menu, and select the RSI **directory** in the file dialog.

### The layout

The RSI-editor application window has 3 parts: the top, which shows the contents of an individual state; the middle, which lists all the states in the RSI; and the bottom, which has other metadata like the license and copyright information.

When you first create or open an RSI, or import a DreamMaker DMI file, the state list will be populated with all the states in the file, including a preview image for each state. Clicking on a state will open it in the contents view, which will show the directional frames and delays for that state. It will also show a preview of how each direction looks when animated.

### Editing the state list

Editing the state list is done through the right-click menu. Using the menu, you can add and delete states from the list.

Double click on a state's name to rename it.

### Editing a state's contents

Editing the contents of a state is done through the right-click menu. Using the menu, you can add and delete frames from each direction in the state. If you have integrated RSI-editor with an image editor, you can also open the sprite for a frame in the editor.

Double click on a frame's delay to change it.

You can set the number of directions in the state from the `Edit` menu.

## Integration with an image editor

RSI-editor is *not* an image editor. It does *not*, and never will aim to, allow users to directly edit sprites. Image editing is best left to dedicated applications. For that reason, RSI-editor allows you to configure a command to invoke an external image editor. The command must

  * take a filepath as an argument. Use `{}` in the command to specify where the file should be substituted.
  * write the edited image back to the given filepath.
  * exit only once editing is complete.
  * exit succesfully (i.e. with code 0) if the edited file should be used.

### Example: Integration with GIMP

To use GIMP, simply set the image editor command to `gimp {}`. This will cause GIMP to open the image file for editing. When you've completed editing, **re-export and overwrite** the original image file, and exit the editor. RSI-editor will then read the contents of the file, and update the corresponding sprite in the state.

## Alpha status

### Supported features

Currently, RSI-editor supports the following features

  * directional delays
  * animation previews
  * adding, editing, and deleting states
  * adding, editing, and deleting directional sprites
  * editing license and copyright information

### Unsupported features

RSI-editor currently has *no* support for these features from the RSI spec:

  * version number
  * state flags

