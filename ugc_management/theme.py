from PySide6.QtGui import QColor, QFont, QPalette


def apply_app_style(app) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 10))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#eef3fb"))
    palette.setColor(QPalette.WindowText, QColor("#1a2649"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f5f8fd"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#1a2649"))
    palette.setColor(QPalette.Text, QColor("#1a2649"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#1a2649"))
    palette.setColor(QPalette.Highlight, QColor("#4d8cff"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QMainWindow,
        QDialog {
            background: #eef3fb;
        }

        QWidget {
            color: #1a2649;
            font-size: 14px;
        }

        QLabel {
            background: transparent;
        }

        QWidget#appRoot,
        QWidget#contentArea,
        QWidget#pageBody,
        QStackedWidget#pageStack {
            background: #eef3fb;
        }

        QFrame#sidebar {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #102642,
                stop: 1 #0d2039
            );
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }

        QLabel#brandTitle {
            color: #f4f8ff;
            font-size: 30px;
            font-weight: 700;
        }

        QLabel#brandSubtitle {
            color: #9cafcb;
            font-size: 13px;
        }

        QPushButton#navButton {
            background: transparent;
            border: none;
            border-radius: 18px;
            color: #edf5ff;
            font-size: 18px;
            font-weight: 600;
            padding: 16px 18px;
            text-align: left;
        }

        QPushButton#navButton:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        QPushButton#navButton:checked {
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        QLabel#pageTitle {
            color: #1a2649;
            font-size: 34px;
            font-weight: 700;
        }

        QLabel#pageSubtitle {
            color: #6a7e98;
            font-size: 14px;
        }

        QToolButton#headerAction {
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid #dde6f3;
            border-radius: 18px;
            color: #1a2649;
            font-size: 18px;
            font-weight: 700;
            min-width: 40px;
            min-height: 40px;
        }

        QToolButton#headerAction:hover {
            background: #ffffff;
        }

        QScrollArea {
            border: none;
            background: transparent;
        }

        QFrame#card {
            background: #ffffff;
            border: 1px solid #dce6f4;
            border-radius: 24px;
        }

        QFrame#softCard {
            background: #f8fbff;
            border: 1px solid #e2ebf7;
            border-radius: 20px;
        }

        QFrame#pipelineItem {
            background: #f7faff;
            border: 1px solid #e3ebf7;
            border-radius: 18px;
        }

        QFrame#pipelineHighlight {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 rgba(47, 185, 172, 0.10),
                stop: 1 rgba(47, 185, 172, 0.04)
            );
            border: 1px solid rgba(47, 185, 172, 0.18);
            border-radius: 18px;
        }

        QLabel#sectionTitle {
            color: #203a56;
            font-size: 17px;
            font-weight: 700;
        }

        QLabel#cardTitle {
            color: #5e738f;
            font-size: 15px;
            font-weight: 600;
        }

        QLabel#heroValue {
            color: #1f3553;
            font-size: 26px;
            font-weight: 700;
        }

        QLabel#smallTitle {
            color: #203a56;
            font-size: 16px;
            font-weight: 700;
        }

        QLabel#pipelineTitle {
            color: #203a56;
            font-size: 15px;
            font-weight: 700;
        }

        QLabel#amountLabel {
            color: #203a56;
            font-size: 16px;
            font-weight: 700;
        }

        QLabel#mutedText {
            color: #7488a3;
            font-size: 13px;
        }

        QLabel#mutedTextStrong {
            color: #5d708b;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#dateChip {
            color: #6c809b;
            background: #edf3fb;
            border-radius: 12px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 700;
        }

        QLabel#statusTag {
            color: #203a56;
            background: #edf3fb;
            border: 1px solid #dce7f5;
            border-radius: 11px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
        }

        QComboBox,
        QDateEdit,
        QDoubleSpinBox,
        QSpinBox {
            background: #f8fbff;
            border: 1px solid #d9e4f3;
            border-radius: 14px;
            padding: 8px 12px;
            min-height: 22px;
            selection-background-color: #4d8cff;
        }

        QComboBox,
        QDateEdit {
            padding-right: 32px;
            min-width: 150px;
        }

        QDoubleSpinBox,
        QSpinBox {
            padding-right: 12px;
        }

        QComboBox::drop-down,
        QDateEdit::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            border: none;
            width: 26px;
            background: transparent;
            margin: 0 10px 0 0;
        }

        QComboBox::down-arrow,
        QDateEdit::down-arrow {
            image: none;
            width: 0px;
            height: 0px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #8092aa;
        }

        QSpinBox::up-button,
        QSpinBox::down-button,
        QDoubleSpinBox::up-button,
        QDoubleSpinBox::down-button {
            width: 0px;
            border: none;
            background: transparent;
        }

        QSpinBox::up-arrow,
        QSpinBox::down-arrow,
        QDoubleSpinBox::up-arrow,
        QDoubleSpinBox::down-arrow {
            width: 0px;
            height: 0px;
        }

        QComboBox QAbstractItemView {
            background: #ffffff;
            border: 1px solid #dce6f4;
            border-radius: 12px;
            padding: 6px;
            outline: 0;
            selection-background-color: #4d8cff;
            selection-color: #ffffff;
        }

        QLineEdit,
        QTextEdit {
            background: #ffffff;
            border: 1px solid #d9e4f3;
            border-radius: 14px;
            padding: 10px 12px;
            color: #1a2649;
        }

        QTextEdit {
            padding: 12px;
        }

        QDialogButtonBox QPushButton,
        QPushButton#ghostButton,
        QPushButton#inlineAction,
        QPushButton#dangerAction {
            border-radius: 14px;
            padding: 9px 14px;
            font-weight: 600;
        }

        QPushButton#ghostButton,
        QPushButton#inlineAction {
            background: #f8fbff;
            border: 1px solid #d9e4f3;
            color: #203a56;
        }

        QPushButton#ghostButton:hover,
        QPushButton#inlineAction:hover {
            background: #ffffff;
        }

        QPushButton#dangerAction {
            background: #fff1f1;
            border: 1px solid #f2cfd2;
            color: #c04d57;
        }

        QPushButton#dangerAction:hover {
            background: #ffe7e8;
        }

        QPushButton#linkButton {
            background: transparent;
            border: none;
            color: #2c74dd;
            font-size: 15px;
            font-weight: 700;
            padding: 4px 0;
        }

        QPushButton#linkButton:hover {
            color: #185ec7;
        }

        QProgressBar {
            background: #e7eef8;
            border: none;
            border-radius: 6px;
            min-height: 10px;
            max-height: 10px;
        }

        QProgressBar::chunk {
            border-radius: 6px;
            background: #4d8cff;
        }

        QCheckBox {
            color: #1a2649;
            spacing: 10px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 6px;
            border: 1px solid #ccd8ea;
            background: #ffffff;
        }

        QCheckBox::indicator:checked {
            background: #4d8cff;
            border: 1px solid #4d8cff;
        }
        """
    )
