from __future__ import annotations

from collections import OrderedDict

import PySide2.QtCore as QtC
import PySide2.QtGui as QtG

import PIL as PIL # type: ignore
import PIL.ImageQt as PILQt # type: ignore

import rsi as RSIPy

from typing import Dict, List, Optional

# TODO: Have this be configured by zooming in and out
iconSize = QtC.QSize(100, 100)

# Wrapper class around the RSI API, for use in the editor
class Rsi(QtC.QAbstractListModel):
    stateRenamed = QtC.Signal(str, str)

    licenseChanged = QtC.Signal()
    copyrightChanged = QtC.Signal()

    # Constructors
    def __init__(self, rsi : RSIPy.Rsi, parent : Optional[QtC.QObject] =None):
        QtC.QAbstractListModel.__init__(self, parent)
        self.states = OrderedDict(rsi.states.items())
        self.size = rsi.size
        self.license = rsi.license
        self.copyright = rsi.copyright

    def fromFile(self, rsiPath : str) -> Rsi:
        return Rsi(RSIPy.Rsi.open(rsiPath))

    def fromDmi(self, dmiPath : str) -> Rsi:
        return Rsi(RSIPy.Rsi.from_dmi(dmiPath))

    def fromFolder(self, folder : str) -> Rsi:
        return Rsi(RSIPy.Rsi.from_folder(folder))

    def new(self, x : int, y : int) -> Rsi:
        return Rsi(RSIPy.Rsi((x, y)))

    # Convenience function

    def save(self, path : str, jsonIndent : Optional[int]) -> bool:
        rsi = RSIPy.Rsi(self.size)
        rsi.states = self.states
        rsi.license = self.license
        rsi.copyright = self.copyright
        rsi.write(path, indent = jsonIndent)
        return True

    # Setters - return True if the RSI is changed

    def setLicense(self, licenseText : Optional[str]) -> bool:
        if self.license != licenseText:
            self.license = licenseText
            self.licenseChanged.emit()
            return True
        return False

    def setCopyright(self, copyrightText : Optional[str]) -> bool:
        if self.copyright != copyrightText:
            self.copyright = copyrightText
            self.copyrightChanged.emit()
            return True
        return False

    def addState(self, stateName : str, state : Optional[RSIPy.State] = None) -> bool:
        if state is not None:
            if not stateName in self.states:
                currentFinalRow = self.rowCount(QtC.QModelIndex())

                self.beginInsertRows(QtC.QModelIndex(), currentFinalRow, currentFinalRow)
                self.states[stateName] = state
                self.endInsertRows()
            else:
                self.states[stateName] = state
                currentIndex = self.getStateIndex(stateName)
                self.dataChanged.emit(currentIndex, currentIndex)
            return True
        else:
            if stateName in self.states:
                return False

            state = RSIPy.State(stateName, self.size, 1)

            currentFinalRow = self.rowCount(QtC.QModelIndex())

            self.beginInsertRows(QtC.QModelIndex(), currentFinalRow, currentFinalRow)
            self.states[stateName] = state
            self.endInsertRows()

            return True

    def removeState(self, stateName : str) -> Optional[RSIPy.State]:
        if not stateName in self.states:
            return None

        currentRow = self.getStateIndex(stateName).row()

        self.beginRemoveRows(QtC.QModelIndex(), currentRow, currentRow)
        state = self.states.pop(stateName)
        self.endRemoveRows()

        return state

    def removeStates(self, stateNames : List[str]) -> Dict[str, RSIPy.State]:
        stateDict = {}

        for name in stateNames:
            removed = self.removeState(name)

            if removed is not None:
                stateDict[name] = removed

        return stateDict

    def renameState(self, oldStateName : str, newStateName : str) -> bool:
        if not oldStateName in self.states:
            return False

        if oldStateName != newStateName:
            newRow = self.rowCount(QtC.QModelIndex()) - 1
            currentRow = self.getStateIndex(oldStateName).row()

            # If not the case, the row won't move, and endMoveRows() will actually
            # segfault
            if currentRow != newRow:
                self.beginMoveRows(QtC.QModelIndex(), currentRow, currentRow, QtC.QModelIndex(), newRow)

            state = self.states[oldStateName]
            self.states.pop(oldStateName)
            state.name = newStateName
            self.states[newStateName] = state

            if currentRow != newRow:
                self.endMoveRows()
            else:
                newIndex = self.getStateIndex(newStateName)
                self.dataChanged.emit(newIndex, newIndex)
            
            return True
        return False

    # Model methods

    def rowCount(self, _parent : QtC.QModelIndex = QtC.QModelIndex()) -> int:
        return len(self.states)

    def getState(self, index : QtC.QModelIndex) -> RSIPy.State:
        return list(self.states.values())[index.row()]

    def getStateIndex(self, stateName : str) -> QtC.QModelIndex:
        for index, name in enumerate(self.states.keys()):
            if name == stateName:
                return self.createIndex(index, 0)
        return QtC.QModelIndex()

    def data(self, index : QtC.QModelIndex, role : int = QtC.Qt.DisplayRole) -> object:
        state = self.getState(index)

        if role == QtC.Qt.DisplayRole or role == QtC.Qt.EditRole:
            return state.name
        if role == QtC.Qt.DecorationRole:

            if len(state.icons[0]) == 0:
                image = PIL.Image.new('RGBA', self.size)
            else:
                image = state.icons[0][0]

            statePixmap = QtG.QPixmap.fromImage(PILQt.ImageQt(image))
            statePixmap = statePixmap.scaled(iconSize)
            stateIcon = QtG.QIcon(statePixmap)

            return stateIcon

        return None

    def flags(self, _index : QtC.QModelIndex) -> QtC.Qt.ItemFlags:
        # All states have the same flags
        return QtC.Qt.ItemIsSelectable | QtC.Qt.ItemIsEditable | QtC.Qt.ItemIsEnabled | QtC.Qt.ItemNeverHasChildren

    # setData is intercepted to produce something on the undo stack and also
    # fix other data
    def setData(self, index : QtC.QModelIndex, value : object, role : int = QtC.Qt.EditRole) -> bool:
        if role == QtC.Qt.EditRole:
            state = self.getState(index)

            if not isinstance(value, str):
                return False

            self.stateRenamed.emit(self.data(index, role=role), value)
            return True
        return False

    # No header data right now


