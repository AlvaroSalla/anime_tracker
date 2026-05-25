import sys, traceback

def excepthook(exc_type, exc_value, exc_tb):
   with open("error.log", "w") as f:
      traceback.print_exception(exc_type, exc_value, exc_tb, file=f)

sys.excepthook = excepthook


if __name__ == "__main__":
   from database.setup import crear_tablas_tracker

   if "--install-db" in sys.argv:
      crear_tablas_tracker()
      print("tracker.db created successfully.")
      sys.exit(0)

   from PyQt6.QtWidgets import QApplication
   from ui.app_qt import AnimeTrackerApp

   crear_tablas_tracker()
   app = QApplication(sys.argv)
   window = AnimeTrackerApp()
   window.show()
   sys.exit(app.exec())