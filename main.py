from database.setup import crear_tabla
from gui.app import AnimeTrackerApp

if __name__ == "__main__":
    crear_tabla()
    app = AnimeTrackerApp()
    app.mainloop()
