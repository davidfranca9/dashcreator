import sys

from PySide6.QtWidgets import QApplication

from ugc_management.main_window import MainWindow
from ugc_management.theme import apply_app_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema de Gestao UGC")
    app.setOrganizationName("David Studio")
    apply_app_style(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
