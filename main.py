#from database.setup import crear_tabla
#from gui.app import AnimeTrackerApp

#if __name__ == "__main__":
   # crear_tabla()
   #app = AnimeTrackerApp()
   # app.mainloop()
import sys
from PyQt6.QtWidgets import QApplication
from ui.app_qt import AnimeTrackerApp

if __name__ == "__main__":
   app = QApplication(sys.argv)
   window = AnimeTrackerApp()
   window.show()
   sys.exit(app.exec())