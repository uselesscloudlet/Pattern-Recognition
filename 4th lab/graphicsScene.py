from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import (QObject, pyqtSignal)


class MouseSignals(QObject):
    send_press_pos = pyqtSignal(tuple)
    send_move_pos = pyqtSignal(tuple)
    send_release_pos = pyqtSignal(tuple)


class GraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super(GraphicsScene, self).__init__(parent)
        self.signals = MouseSignals()

    def mousePressEvent(self, event):
        x = int(event.scenePos().x())
        y = int(event.scenePos().y())
        self.signals.send_press_pos.emit((x, y))

    def mouseMoveEvent(self, event):
        x = int(event.scenePos().x())
        y = int(event.scenePos().y())
        self.signals.send_move_pos.emit((x, y))

    def mouseReleaseEvent(self, event):
        x = int(event.scenePos().x())
        y = int(event.scenePos().y())
        self.signals.send_release_pos.emit((x, y))
