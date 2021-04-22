from __future__ import annotations

import PySide2.QtCore as QtC
import PySide2.QtGui as QtG
import PySide2.QtWidgets as QtW

import PIL # type: ignore

import rsi as RSIPy

from .Config import Config, ConfigEditor
from .ImageEditor import ImageEditor
from .ItemAction import ItemAction
from .Rsi import Rsi, iconSize
from .State import State
from .AnimationView import AnimationView
from .ListView import ListView
from .SizeDialog import SizeDialog

from typing import Dict, List, Optional, Tuple
from pathlib import Path

rsiFileFilter = 'Robust Station Image (*.rsi);;RSI JSON metadata (*.json)'
dmiFileFilter = 'DreamMaker Image (*.dmi)'
pngFileFilter = 'PNG (*.png)'

class EditorWindow(QtW.QMainWindow):
    def __init__(self : EditorWindow):
        QtW.QMainWindow.__init__(self)
        self.setWindowTitle("RSI editor[*]")

        self.config = Config.load()

        self.undoStack = QtW.QUndoStack(self)
        self.undoStack.cleanChanged.connect(lambda clean: self.setWindowModified(not clean))

        self.editorMenu()

        self.currentRsi : Optional[Rsi] = None
        self.currentState : Optional[State] = None

        self.contentLayout()

        self.contentMenus()

        self.reloadRsi()

    def editorMenu(self) -> None:
        fileMenu = self.menuBar().addMenu("&File")

        # Set up new RSI
        newAction = fileMenu.addAction("&New")
        newAction.setShortcut(QtG.QKeySequence.New)
        newAction.triggered.connect(self.newRsi)

        # Set up file opening
        openAction = fileMenu.addAction("&Open")
        openAction.setIcon(QtG.QIcon.fromTheme("document-open", self.style().standardIcon(QtW.QStyle.SP_DialogOpenButton)))
        openAction.setShortcut(QtG.QKeySequence.Open)
        openAction.triggered.connect(self.openRsi)

        # Set up file saving
        saveAction = fileMenu.addAction("&Save")
        saveAction.setIcon(QtG.QIcon.fromTheme("document-save", self.style().standardIcon(QtW.QStyle.SP_DialogSaveButton)))
        saveAction.setShortcut(QtG.QKeySequence.Save)
        saveAction.triggered.connect(self.saveRsi)

        saveAsAction = fileMenu.addAction("Save As")
        saveAsAction.setShortcut(QtG.QKeySequence.SaveAs)
        saveAsAction.triggered.connect(self.saveAsRsi)

        fileMenu.addSeparator()

        importDmiAction = fileMenu.addAction("&Import DMI")
        importDmiAction.triggered.connect(self.importDmi)

        importFolderAction = fileMenu.addAction("&Convert Folder To RSI")
        importFolderAction.triggered.connect(self.importFolder)

        fileMenu.addSeparator()

        # TODO: Set up preferences
        preferencesAction = fileMenu.addAction("Preferences")
        preferencesAction.setShortcut(QtG.QKeySequence.Preferences)
        preferencesAction.triggered.connect(self.editConfig)

        editMenu = self.menuBar().addMenu("&Edit")

        # Undo
        undoAction = editMenu.addAction("&Undo")
        undoAction.setIcon(QtG.QIcon.fromTheme("edit-undo", self.style().standardIcon(QtW.QStyle.SP_ArrowLeft)))
        undoAction.setShortcut(QtG.QKeySequence.Undo)
        undoAction.triggered.connect(self.undoStack.undo)

        # Redo
        redoAction = editMenu.addAction("&Redo")
        redoAction.setIcon(QtG.QIcon.fromTheme("edit-redo", self.style().standardIcon(QtW.QStyle.SP_ArrowRight)))
        redoAction.setShortcut(QtG.QKeySequence.Redo)
        redoAction.triggered.connect(self.undoStack.redo)

        # Undo history
        undoMenu = editMenu.addMenu("Undo history")

        undoHistory = QtW.QUndoView(parent=undoMenu)
        undoHistory.setStack(self.undoStack)
        undoAction = QtW.QWidgetAction(undoMenu)
        undoAction.setDefaultWidget(undoHistory)

        undoMenu.addAction(undoAction)

        editMenu.addSeparator()

        self.directionGroup = QtW.QActionGroup(editMenu)

        for direction in [1, 4, 8]:
            action = self.directionGroup.addAction(f'{direction} direction{"s" if direction > 1 else ""}')
            action.setData(direction)
            editMenu.addAction(action)

        self.directionGroup.setEnabled(False)
        self.directionGroup.triggered.connect(lambda action: self.undoStack.push(SetDirectionsCommand(self, action.data())))

    def contentMenus(self) -> None:
        self.stateContentsMenu()
        self.stateListMenu()

    def stateContentsMenu(self) -> None:
        editorAction = self.stateContents.addItemAction("Open in editor...")
        # Can only edit frames which exist
        # and while there is an editor configured
        editorAction.setEnableIf(lambda index: self.stateContents.model().frame(index) is not None and self.config.hasEditor())
        editorAction.indexTriggered.connect(self.stateContentsEdit)

        insertFrameAction = self.stateContents.addItemAction("Add frame")
        insertFrameAction.indexTriggered.connect(self.stateContentsAddFrame)

        deleteFrameAction = self.stateContents.addItemAction("Delete frame")
        deleteFrameAction.setEnableIf(lambda index: self.stateContents.model().frame(index) is not None)
        deleteFrameAction.indexTriggered.connect(self.stateContentsDeleteFrame)

    def stateListMenu(self) -> None:
        # Action stuff

        newStateAction = self.stateList.addItemAction("Add new state")
        newStateAction.setCheckValid(False)
        newStateAction.triggered.connect(lambda _index: self.undoStack.push(NewStateCommand(self)))

        importPngAction = self.stateList.addItemAction("Import PNG")
        importPngAction.triggered.connect(self.importPng)

        deleteStateAction = self.stateList.addItemAction("Delete state")
        deleteStateAction.setAllowMultiple(True)
        deleteStateAction.setShortcut(QtG.QKeySequence.Delete)
        deleteStateAction.indexTriggered.connect(self.deleteStates)

    def contentLayout(self) -> None:
        splitter = QtW.QSplitter()
        splitter.setOrientation(QtC.Qt.Vertical)

        self.stateContents = AnimationView(parent=splitter)
        self.stateContents.setIconSize(iconSize)

        stateContentsLayout = QtW.QHBoxLayout()
        stateContentsLayout.addWidget(self.stateContents)
        stateContentsWidget = QtW.QWidget()
        stateContentsWidget.setLayout(stateContentsLayout)

        self.stateList = ListView()
        self.stateList.setViewMode(QtW.QListView.IconMode)
        self.stateList.setIconSize(iconSize)
        self.stateList.setMovement(QtW.QListView.Snap)
        self.stateList.setSelectionRectVisible(True)
        self.stateList.setUniformItemSizes(True)
        self.stateList.setWordWrap(True)
        self.stateList.setSelectionMode(QtW.QAbstractItemView.ExtendedSelection)
        self.stateList.setContextMenuPolicy(QtC.Qt.ActionsContextMenu)
        self.stateList.clicked.connect(self.stateListDrillDown)

        stateLayout = QtW.QHBoxLayout()
        stateLayout.addWidget(self.stateList)
        stateWidget = QtW.QWidget()
        stateWidget.setLayout(stateLayout)
        
        self.sizeInfo = QtW.QLabel()

        self.licenseInput = QtW.QLineEdit()
        self.licenseInput.setEnabled(False)
        self.licenseInput.editingFinished.connect(self.updateLicense)

        self.copyrightInput = QtW.QLineEdit()
        self.copyrightInput.setEnabled(False)
        self.copyrightInput.editingFinished.connect(self.updateCopyright)
        
        configLayout = QtW.QFormLayout()
        configLayout.addRow("Size:", self.sizeInfo)
        configLayout.addRow("License:", self.licenseInput)
        configLayout.addRow("Copyright:", self.copyrightInput) 

        self.configGroupBox = QtW.QGroupBox("Metadata")
        self.configGroupBox.setLayout(configLayout)

        splitter.addWidget(stateContentsWidget)
        splitter.addWidget(stateWidget)
        splitter.addWidget(self.configGroupBox)


        self.setCentralWidget(splitter)

    def reloadRsi(self) -> None:
        if self.currentRsi is not None:
            self.stateList.setModel(self.currentRsi)
            self.stateList.setEnabled(True)

            self.currentRsi.stateRenamed.connect(self.renameState)

            (x, y) = self.currentRsi.size
            self.sizeInfo.setText(f'x: {x}, y: {y}')

            license = self.currentRsi.license
            if license is not None:
                self.licenseInput.setText(license)
            self.licenseInput.setEnabled(True)
            self.currentRsi.licenseChanged.connect(
                    lambda : self.licenseInput.setText(self.currentRsi.license) if self.currentRsi.license is not None else None)

            copyright = self.currentRsi.copyright
            if copyright is not None:
                self.copyrightInput.setText(copyright)
            self.copyrightInput.setEnabled(True)
            self.currentRsi.copyrightChanged.connect(
                    lambda : self.copyrightInput.setText(self.currentRsi.copyright) if self.currentRsi.copyright is not None else None)

        else:
            self.stateList.setModel(None)
            self.stateList.setEnabled(False)

            self.sizeInfo.setText('')
            self.licenseInput.setEnabled(False)
            self.copyrightInput.setEnabled(False)

        self.reloadState()

    def reloadState(self) -> None:

        if self.currentState is not None:
            self.stateContents.setModel(self.currentState)
            self.stateContents.setEnabled(True)

            self.currentState.delayChanged.connect(self.setFrameDelay)

            self.directionGroup.setEnabled(True)

            for action in self.directionGroup.actions():
                if action.data() == self.currentState.directions():
                    action.setChecked(True)

        else:
            self.stateContents.setModel(None)
            self.stateContents.setEnabled(False)



    def newRsi(self) -> None:
        if not self.closeCurrentRsi():
            return

        sizeDialog = SizeDialog(parent = self)
        size = sizeDialog.size()

        if size is None:
            return

        self.currentRsi = Rsi.new(size.width(), size.height())
        self.setWindowFilePath('')
        self.reloadRsi()

    def openRsi(self) -> None:
        if not self.closeCurrentRsi():
            return

        rsiFile = QtW.QFileDialog.getExistingDirectory(self, 'Open RSI')

        if rsiFile == '':
            return

        self.currentRsi = Rsi.fromFile(rsiFile)
        self.setWindowFilePath(rsiFile)

        self.reloadRsi()

    def saveRsi(self) -> bool:
        if self.currentRsi is None:
            return False

        if self.windowFilePath() == '' and not self.setRsiPath():
            return False

        indent = None
        if self.config.formatMetadata:
            indent = self.config.metadataIndent

        self.currentRsi.save(self.windowFilePath(), indent)
        self.undoStack.setClean()
        return True

    def saveAsRsi(self) -> bool:
        if self.currentRsi is None:
            return False

        if not self.setRsiPath():
            return False

        return self.saveRsi()

    def importDmi(self) -> None:
        if not self.closeCurrentRsi():
            return

        (dmiFile, _) = QtW.QFileDialog.getOpenFileName(self, 'Import DMI', filter=dmiFileFilter)

        if dmiFile == '':
            return

        self.currentRsi = Rsi.fromDmi(dmiFile)
        self.setWindowFilePath('')

        self.reloadRsi()
    
    def importPng(self) -> None:
        (pngFile, _) = QtW.QFileDialog.getOpenFileName(self, 'Import PNG', filter=pngFileFilter)

        if pngFile == '':
            return
        
        fileName = Path(pngFile).stem
        
        self.currentRsi.addState(fileName)

        self.currentState = State(self.currentRsi, fileName)
        self.stateContentsAddFrame(self.currentState.createIndex(0,0))
        self.setFrameDelay(self.currentState.createIndex(0,0), 1.0)

        load_image = PIL.Image.open(Path(pngFile))
        self.currentState.setFrame(self.currentState.createIndex(0,0), load_image)


        self.reloadState()

        self.reloadRsi()

    def importFolder(self) -> None:
	
        if not self.closeCurrentRsi():
            return

        folder = QtW.QFileDialog.getExistingDirectory(self, 'Select Folder')

        if folder == '':
            return

        self.currentRsi = Rsi.fromFolder(folder)
        self.setWindowFilePath(folder)
        self.reloadRsi()

    def setRsiPath(self) -> bool:
        rsiPath = QtW.QFileDialog.getExistingDirectory(self, 'Save RSI')

        if rsiPath == '':
            return False

        self.setWindowFilePath(rsiPath)
        return True

    def closeCurrentRsi(self) -> bool:
        if self.currentRsi is not None and not self.undoStack.isClean():
            confirmCloseReply = QtW.QMessageBox.question(
                    self,
                    'Close without saving?',
                    'The RSI has unsaved changes - close it anyways?',
                    buttons=QtW.QMessageBox.Save|QtW.QMessageBox.Discard|QtW.QMessageBox.Cancel,
                    defaultButton=QtW.QMessageBox.Save)

            if confirmCloseReply == QtW.QMessageBox.Save:
                response = self.saveRsi()
            if confirmCloseReply == QtW.QMessageBox.Discard:
                response = True
            if confirmCloseReply == QtW.QMessageBox.Cancel:
                response = False
        else:
            response = True

        if response:
            self.currentRsi = None
            self.currentState = None
            self.reloadRsi()

            self.undoStack.clear()

        return response

    def stateListDrillDown(self, stateListIndex : QtC.QModelIndex) -> None:
        assert self.currentRsi is not None

        state = self.currentRsi.getState(stateListIndex)
        self.currentState = State(self.currentRsi, state.name)
        self.reloadState()

    def stateContentsEdit(self, stateIndex : QtC.QModelIndex) -> None:
        image = self.stateContents.model().frame(stateIndex)
        assert image is not None
        assert self.config.editorCommand is not None

        edited = ImageEditor.editImage(image, self.config.editorCommand)

        if edited is not None:
            self.undoStack.push(EditFrameCommand(self, stateIndex, image, edited))

    def stateContentsAddFrame(self, frameIndex : QtC.QModelIndex) -> None:
        self.undoStack.push(NewFrameCommand(self, frameIndex))

    def stateContentsDeleteFrame(self, frameIndex : QtC.QModelIndex) -> None:
        self.undoStack.push(DeleteFrameCommand(self, frameIndex))

    def setFrameDelay(self, frameIndex : QtC.QModelIndex, delay : float) -> None:
        assert self.currentState is not None

        if self.currentState.delay(frameIndex) != delay:
            self.undoStack.push(EditDelayCommand(self, frameIndex, delay))

    def renameState(self, oldStateName : str, newStateName : str) -> None:
        if oldStateName != newStateName:
            self.undoStack.push(RenameStateCommand(self, oldStateName, newStateName))

    def deleteStates(self, states : List[QtC.QModelIndex]) -> None:
        assert self.currentRsi is not None
        
        stateNames = [ self.currentRsi.getState(index).name for index in states ]

        for stateName in stateNames:
            if self.currentState is not None and self.currentState.name() == stateName:
                self.currentState = None
                self.reloadState()

        self.undoStack.push(DeleteStatesCommand(self, stateNames))

    def updateLicense(self) -> None:
        assert self.currentRsi is not None

        if self.licenseInput.text() != self.currentRsi.license:
            self.undoStack.push(SetLicenseCommand(self, self.currentRsi.license, self.licenseInput.text()))

    def updateCopyright(self) -> None:
        assert self.currentRsi is not None

        if self.copyrightInput.text() != self.currentRsi.copyright:
            self.undoStack.push(SetCopyrightCommand(self, self.currentRsi.copyright, self.copyrightInput.text()))

    def editConfig(self) -> None:
        configEdited = ConfigEditor(self.config, self).edit()

        if configEdited:
            self.config.save()

##############################
### COMMANDS FOR UNDO/REDO ###
#############################

SetLicenseCommandId = 100
SetCopyrightCommandId = 101

class SetLicenseCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, oldLicense : Optional[str], newLicense : Optional[str]):
        QtW.QUndoCommand.__init__(self)
        self.editor = editor
        self.oldLicense = oldLicense
        self.newLicense = newLicense

        self.setText('Edit license')

    def id(self) -> int:
        return SetLicenseCommandId

    def mergeWith(self, other : QtW.QUndoCommand) -> bool:
        if other.id() != self.id():
            return False

        self.newLicense = other.newLicense
        return True

    def redo(self) -> None:
        assert self.editor.currentRsi is not None

        self.editor.currentRsi.setLicense(self.newLicense)

    def undo(self) -> None:
        assert self.editor.currentRsi is not None

        self.editor.currentRsi.setLicense(self.oldLicense)

class SetCopyrightCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, oldCopyright : Optional[str], newCopyright : Optional[str]):
        QtW.QUndoCommand.__init__(self)
        self.editor = editor
        self.oldCopyright = oldCopyright
        self.newCopyright = newCopyright

        self.setText('Edit copyright')

    def id(self) -> int:
        return SetCopyrightCommandId

    def mergeWith(self, other : QtW.QUndoCommand) -> bool:
        if other.id() != self.id():
            return False

        self.newCopyright = other.newCopyright
        return True

    def redo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.editor.currentRsi.setCopyright(self.newCopyright)

    def undo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.editor.currentRsi.setCopyright(self.oldCopyright)

class NewStateCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        
        assert self.editor.currentRsi is not None
        states = self.editor.currentRsi.states

        newStateNumber = 1
        while f'NewState{newStateNumber}' in states:
            newStateNumber = newStateNumber + 1

        self.newStateName = f'NewState{newStateNumber}'
        
        self.setText('Create new state')

    def id(self) -> int:
        return -1


    def redo(self) -> None: 
        assert self.editor.currentRsi is not None
        
        self.editor.currentRsi.addState(self.newStateName)

    def undo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.editor.currentRsi.removeState(self.newStateName)

class DeleteStatesCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, stateNames : List[str]):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.stateNames = stateNames

        # Deliberately don't define this, because redo() is always called first!
        self.deleted : Optional[Dict[str, RSIPy.State]] = None
        
        self.setText('Delete state')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.deleted = self.editor.currentRsi.removeStates(self.stateNames)

    def undo(self) -> None:
        assert self.editor.currentRsi is not None
        assert self.deleted is not None

        for name, state in self.deleted.items():
            self.editor.currentRsi.addState(name, state)

class RenameStateCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, oldStateName : str, newStateName : str):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.oldStateName = oldStateName
        self.newStateName = newStateName
        self.overwritten : Optional[RSIPy.State] = None
        
        self.setText('Rename state')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.overwritten = self.editor.currentRsi.removeState(self.newStateName)
        self.editor.currentRsi.renameState(self.oldStateName, self.newStateName)

    def undo(self) -> None:
        assert self.editor.currentRsi is not None
        
        self.editor.currentRsi.renameState(self.newStateName, self.oldStateName)
        if self.overwritten != None:
            self.editor.currentRsi.addState(self.newStateName, self.overwritten)

class SetDirectionsCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, numDirections : int):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.numDirections = numDirections

        self.oldDirections = 0
        self.oldIcons : List[List[PIL.Image.Image]] = []
        self.oldDelays : List[List[float]] = []
        
        self.setText('Set number of directions')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentState is not None
        
        self.oldDirections = self.editor.currentState.directions()
        self.oldIcons, self.oldDelays = self.editor.currentState.setDirections(self.numDirections)

    def undo(self) -> None:
        assert self.editor.currentState is not None
        
        self.editor.currentState.setDirections(self.oldDirections)

        for i in range(self.numDirections, self.oldDirections):
            for j in range(len(self.oldIcons[i - self.numDirections])):
                self.editor.currentState.setFrame(self.editor.currentState.index(i, j), self.oldIcons[i - self.numDirections][j])
                self.editor.currentState.setDelay(self.editor.currentState.index(i, j), self.oldDelays[i - self.numDirections][j])


class NewFrameCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, frameIndex : QtC.QModelIndex):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.frameIndex = frameIndex
        
        self.setText('Add frame')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentState is not None

        self.editor.currentState.addFrame(self.frameIndex)

    def undo(self) -> None:
        assert self.editor.currentState is not None

        self.editor.currentState.deleteFrame(self.frameIndex)

class DeleteFrameCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, frameIndex : QtC.QModelIndex):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.frameIndex = frameIndex

        # Deliberately don't define this, because redo() is always called first!
        self.deleted : Optional[Tuple[PIL.Image.Image, float]] = None
        
        self.setText('Delete frame')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentState is not None

        self.deleted = self.editor.currentState.deleteFrame(self.frameIndex)

    def undo(self) -> None:
        assert self.editor.currentState is not None
        assert self.deleted is not None

        self.editor.currentState.addFrame(self.frameIndex, self.deleted[0], self.deleted[1])

class EditDelayCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, frameIndex : QtC.QModelIndex, delay : float):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.frameIndex = frameIndex
        self.newDelay = delay
        self.oldDelay : Optional[float] = None
        
        self.setText('Set frame delay')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentState is not None

        self.oldDelay = self.editor.currentState.delay(self.frameIndex)
        assert self.oldDelay is not None 
        
        self.editor.currentState.setDelay(self.frameIndex, self.newDelay)

    def undo(self) -> None:
        assert self.editor.currentState is not None
        assert self.oldDelay is not None 
        
        self.editor.currentState.setDelay(self.frameIndex, self.oldDelay)

class EditFrameCommand(QtW.QUndoCommand):
    def __init__(self, editor : EditorWindow, frameIndex : QtC.QModelIndex, unedited : PIL.Image.Image, edited : PIL.Image.Image):
        QtW.QUndoCommand.__init__(self)

        self.editor = editor
        self.frameIndex = frameIndex
        self.unedited = unedited
        self.edited = edited
        
        self.setText('Edit frame')

    def id(self) -> int:
        return -1

    def redo(self) -> None:
        assert self.editor.currentState is not None

        self.editor.currentState.setFrame(self.frameIndex, self.edited)

    def undo(self) -> None:
        assert self.editor.currentState is not None

        self.editor.currentState.setFrame(self.frameIndex, self.unedited)

def editor() -> None:
    app = QtW.QApplication([])

    window = EditorWindow()
    window.showMaximized()

    exit(app.exec_())
