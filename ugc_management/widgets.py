from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def format_currency(value: int | float) -> str:
    formatted = f"{value:,.0f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R${formatted}"


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def add_shadow(widget: QWidget, blur: int = 26, y_offset: int = 8, alpha: int = 28) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(14, 41, 74, alpha))
    widget.setGraphicsEffect(shadow)


def rounded_pixmap(size: int, color: QColor, letter: str | None = None, pen_color: str = "#ffffff") -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(0, 0, size, size)

    if letter:
        font = QFont("Segoe UI", max(9, size // 3))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(pen_color))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, letter[:1].upper())

    painter.end()
    return pixmap


def make_icon(kind: str, color: str, size: int = 22, bg: str | None = None) -> QIcon:
    icon_size = size + 12 if bg else size
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if bg:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg))
        painter.drawEllipse(0, 0, icon_size, icon_size)
        translate = 6
    else:
        translate = 0

    painter.translate(translate, translate)
    pen = QPen(QColor(color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "home":
        path = QPainterPath()
        path.moveTo(3, 10)
        path.lineTo(11, 3)
        path.lineTo(19, 10)
        path.moveTo(5, 9)
        path.lineTo(5, 19)
        path.lineTo(17, 19)
        path.lineTo(17, 9)
        path.moveTo(9, 19)
        path.lineTo(9, 13)
        path.lineTo(13, 13)
        path.lineTo(13, 19)
        painter.drawPath(path)
    elif kind == "search":
        painter.drawEllipse(QRectF(3, 3, 12, 12))
        painter.drawLine(QPointF(14, 14), QPointF(19, 19))
    elif kind == "briefcase":
        painter.drawRoundedRect(QRectF(3, 7, 16, 11), 3, 3)
        painter.drawLine(QPointF(8, 7), QPointF(8, 4))
        painter.drawLine(QPointF(14, 7), QPointF(14, 4))
        painter.drawLine(QPointF(8, 4), QPointF(14, 4))
    elif kind == "wallet":
        painter.drawRoundedRect(QRectF(3, 6, 17, 12), 3, 3)
        painter.drawRoundedRect(QRectF(11, 9, 9, 6), 2, 2)
        painter.drawPoint(QPointF(14.5, 12))
    elif kind == "chart":
        painter.drawLine(QPointF(4, 18), QPointF(19, 18))
        painter.drawLine(QPointF(7, 18), QPointF(7, 11))
        painter.drawLine(QPointF(12, 18), QPointF(12, 7))
        painter.drawLine(QPointF(17, 18), QPointF(17, 4))
    elif kind == "settings":
        painter.drawEllipse(QRectF(7, 7, 8, 8))
        for point_a, point_b in (
            (QPointF(11, 1), QPointF(11, 4)),
            (QPointF(11, 18), QPointF(11, 21)),
            (QPointF(1, 11), QPointF(4, 11)),
            (QPointF(18, 11), QPointF(21, 11)),
            (QPointF(4, 4), QPointF(6, 6)),
            (QPointF(16, 16), QPointF(18, 18)),
            (QPointF(4, 18), QPointF(6, 16)),
            (QPointF(16, 6), QPointF(18, 4)),
        ):
            painter.drawLine(point_a, point_b)
    elif kind == "building":
        painter.drawRoundedRect(QRectF(4, 3, 14, 17), 2, 2)
        for x in (7, 11, 15):
            painter.drawLine(QPointF(x, 7), QPointF(x, 7))
            painter.drawLine(QPointF(x, 11), QPointF(x, 11))
            painter.drawLine(QPointF(x, 15), QPointF(x, 15))
        painter.drawLine(QPointF(10, 20), QPointF(10, 16))
        painter.drawLine(QPointF(12, 20), QPointF(12, 16))
    elif kind == "money":
        painter.drawEllipse(QRectF(3, 5, 18, 12))
        painter.drawLine(QPointF(12, 7), QPointF(12, 15))
        painter.drawLine(QPointF(9, 9), QPointF(14, 9))
        painter.drawLine(QPointF(9, 13), QPointF(14, 13))
    elif kind == "entry":
        painter.drawLine(QPointF(11, 4), QPointF(11, 18))
        painter.drawLine(QPointF(7, 8), QPointF(11, 4))
        painter.drawLine(QPointF(15, 8), QPointF(11, 4))
        painter.drawLine(QPointF(5, 18), QPointF(17, 18))
    elif kind == "target":
        painter.drawEllipse(QRectF(4, 4, 14, 14))
        painter.drawEllipse(QRectF(8, 8, 6, 6))
        painter.drawLine(QPointF(16, 6), QPointF(20, 2))
    elif kind == "chat":
        painter.drawRoundedRect(QRectF(3, 4, 17, 11), 3, 3)
        painter.drawLine(QPointF(8, 15), QPointF(6, 20))
        painter.drawLine(QPointF(10, 15), QPointF(12, 18))
    elif kind == "check":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(QPointF(8, 12), QPointF(10.5, 15))
        painter.drawLine(QPointF(10.5, 15), QPointF(16, 8))
    elif kind == "clock":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(QPointF(12, 7), QPointF(12, 12))
        painter.drawLine(QPointF(12, 12), QPointF(15, 14))
    elif kind == "edit":
        painter.drawLine(QPointF(5, 17), QPointF(17, 5))
        painter.drawLine(QPointF(5, 17), QPointF(4, 20))
        painter.drawLine(QPointF(4, 20), QPointF(7, 19))
        painter.drawLine(QPointF(15, 3), QPointF(19, 7))
    elif kind == "delete":
        painter.drawLine(QPointF(5, 7), QPointF(19, 7))
        painter.drawLine(QPointF(8, 7), QPointF(8, 18))
        painter.drawLine(QPointF(12, 7), QPointF(12, 18))
        painter.drawLine(QPointF(16, 7), QPointF(16, 18))
        painter.drawLine(QPointF(6, 7), QPointF(7, 19))
        painter.drawLine(QPointF(18, 7), QPointF(17, 19))
        painter.drawLine(QPointF(8, 4), QPointF(16, 4))
    elif kind == "convert":
        painter.drawLine(QPointF(4, 7), QPointF(15, 7))
        painter.drawLine(QPointF(12, 4), QPointF(15, 7))
        painter.drawLine(QPointF(12, 10), QPointF(15, 7))
        painter.drawLine(QPointF(19, 17), QPointF(8, 17))
        painter.drawLine(QPointF(11, 14), QPointF(8, 17))
        painter.drawLine(QPointF(11, 20), QPointF(8, 17))
    else:
        painter.drawEllipse(QRectF(7, 7, 8, 8))

    painter.end()
    return QIcon(pixmap)


def make_thumbnail(company: str, colors: tuple[str, str], size: QSize) -> QPixmap:
    pixmap = QPixmap(size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, QColor(colors[0]))
    gradient.setColorAt(1.0, QColor(colors[1]))

    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), 18, 18)
    painter.fillPath(path, gradient)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 110))
    painter.drawRoundedRect(QRectF(size.width() * 0.52, 12, size.width() * 0.36, size.height() * 0.6), 16, 16)
    painter.drawRoundedRect(QRectF(14, size.height() * 0.34, size.width() * 0.42, size.height() * 0.46), 18, 18)

    painter.setBrush(QColor(255, 255, 255, 135))
    painter.drawEllipse(QRectF(size.width() * 0.58, 18, size.width() * 0.14, size.width() * 0.14))
    painter.drawRoundedRect(QRectF(size.width() * 0.56, 32, size.width() * 0.2, size.height() * 0.3), 18, 18)

    painter.setPen(QColor("#1a2649"))
    font = QFont("Segoe UI", max(10, size.width() // 18))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(14, size.height() - 34, size.width() - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, company)

    painter.end()
    return pixmap


class CardFrame(QFrame):
    def __init__(self, object_name: str = "card", shadow: bool = True) -> None:
        super().__init__()
        self.setObjectName(object_name)
        if shadow:
            add_shadow(self)


class DashboardStatCard(CardFrame):
    def __init__(self, title: str, value: str, icon: str) -> None:
        super().__init__("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(18)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        icon_holder = QLabel()
        icon_holder.setPixmap(make_icon(icon, "#96abc7", 18, bg="#f1f6fd").pixmap(QSize(30, 30)))
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")

        top_row.addWidget(icon_holder)
        top_row.addWidget(title_label)
        top_row.addStretch(1)

        value_label = QLabel(value)
        value_label.setObjectName("heroValue")

        layout.addLayout(top_row)
        layout.addWidget(value_label)


class SectionCard(CardFrame):
    def __init__(self, title: str, trailing_widget: QWidget | None = None, compact: bool = False) -> None:
        super().__init__("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 22)
        outer.setSpacing(18 if not compact else 14)

        if title or trailing_widget is not None:
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            if title:
                title_label = QLabel(title)
                title_label.setObjectName("sectionTitle")
                header.addWidget(title_label)
            header.addStretch(1)
            if trailing_widget is not None:
                header.addWidget(trailing_widget)
            outer.addLayout(header)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(14 if compact else 16)
        outer.addLayout(self.content_layout)


class RevenueChart(QWidget):
    def __init__(self, points: Iterable[tuple[str, int]]) -> None:
        super().__init__()
        self._points = list(points)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_points(self, points: Iterable[tuple[str, int]]) -> None:
        self._points = list(points)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._points:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(6, 6, -10, -8)
        chart_rect = QRectF(rect.left() + 76, rect.top() + 18, rect.width() - 104, rect.height() - 72)

        max_value = max(value for _, value in self._points)
        max_value = max(30000, ((max_value + 4999) // 5000) * 5000)
        steps = 3

        painter.setPen(QPen(QColor("#e8eef8"), 1))
        for step in range(steps + 1):
            y = chart_rect.bottom() - (chart_rect.height() / steps) * step
            painter.drawLine(chart_rect.left(), y, chart_rect.right(), y)
            label_rect = QRectF(rect.left(), y - 10, 62, 20)
            value = int(max_value * step / steps)
            painter.setPen(QColor("#7b8da7"))
            painter.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, format_currency(value))
            painter.setPen(QPen(QColor("#e8eef8"), 1))

        slot_width = chart_rect.width() / max(1, len(self._points))
        bar_width = min(38.0, slot_width * 0.48)

        for index, (label, value) in enumerate(self._points):
            ratio = value / max_value if max_value else 0
            bar_height = chart_rect.height() * ratio
            x = chart_rect.left() + slot_width * index + (slot_width - bar_width) / 2
            y = chart_rect.bottom() - bar_height
            fill = QColor("#dbe6f8")
            if index == len(self._points) - 1:
                fill = QColor("#4d8cff")

            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_height), 10, 10)

            painter.setPen(QColor("#6f83a0"))
            painter.drawText(QRectF(x - 12, chart_rect.bottom() + 12, bar_width + 24, 22), Qt.AlignCenter, label)

            if index == len(self._points) - 1:
                bubble_rect = QRectF(x - 30, y - 54, 112, 40)
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#dfe8f5"), 1))
                painter.drawRoundedRect(bubble_rect, 14, 14)
                painter.setPen(QColor("#1a2649"))
                font = QFont("Segoe UI", 11)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(bubble_rect, Qt.AlignCenter, format_currency(value))

        painter.end()


class PipelineStageCard(CardFrame):
    def __init__(self, stage: str, count: int, amount: int, progress: int, icon: str, accent: str, highlighted: bool = False) -> None:
        super().__init__("pipelineHighlight" if highlighted else "pipelineItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)
        icon_label = QLabel()
        icon_label.setPixmap(make_icon(icon, accent, 18, bg="#e9f2ff").pixmap(QSize(36, 36)))

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(3)
        title_label = QLabel(stage)
        title_label.setObjectName("pipelineTitle")
        count_label = QLabel(f"{count} itens")
        count_label.setObjectName("mutedText")
        title_box.addWidget(title_label)
        title_box.addWidget(count_label)

        amount_label = QLabel(format_currency(amount))
        amount_label.setObjectName("amountLabel")

        top_row.addWidget(icon_label)
        top_row.addLayout(title_box)
        top_row.addStretch(1)
        top_row.addWidget(amount_label)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(progress)
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #dbe5f3;
                border: none;
                border-radius: 6px;
                min-height: 10px;
                max-height: 10px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 6px;
            }}
            """
        )

        layout.addLayout(top_row)
        layout.addWidget(progress_bar)


class ActivityRow(CardFrame):
    def __init__(self, project: str, company: str, content_type: str, progress: int, date_text: str, colors: tuple[str, str], accent: str) -> None:
        super().__init__("softCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        preview = QLabel()
        preview.setPixmap(make_thumbnail(company, colors, QSize(94, 74)))
        preview.setFixedSize(94, 74)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(6)
        title = QLabel(project)
        title.setObjectName("smallTitle")
        subtitle = QLabel(content_type)
        subtitle.setObjectName("mutedText")

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(10)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(progress)
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #dde6f4;
                border: none;
                border-radius: 6px;
                min-height: 10px;
                max-height: 10px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 6px;
            }}
            """
        )
        progress_label = QLabel(f"{progress}%")
        progress_label.setObjectName("mutedTextStrong")
        progress_row.addWidget(progress_bar, 1)
        progress_row.addWidget(progress_label)

        center.addWidget(title)
        center.addWidget(subtitle)
        center.addLayout(progress_row)

        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        date_label = QLabel(date_text)
        date_label.setObjectName("dateChip")
        company_label = QLabel(company)
        company_label.setObjectName("mutedText")
        company_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        side.addWidget(date_label, 0, Qt.AlignRight)
        side.addWidget(company_label, 0, Qt.AlignRight)
        side.addStretch(1)

        layout.addWidget(preview)
        layout.addLayout(center, 1)
        layout.addLayout(side)


class FeaturedProjectCard(CardFrame):
    def __init__(self, project: dict) -> None:
        super().__init__("softCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        image = QLabel()
        image.setPixmap(make_thumbnail(project["company"], project["colors"], QSize(360, 150)))
        image.setScaledContents(True)
        image.setFixedHeight(132)

        title = QLabel(project["project_name"])
        title.setObjectName("smallTitle")
        subtitle = QLabel(project["content_type"])
        subtitle.setObjectName("mutedText")

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(10)
        date_label = QLabel(project["due_text"])
        date_label.setObjectName("dateChip")
        progress_label = QLabel(f"{project['progress']}%")
        progress_label.setObjectName("mutedTextStrong")
        footer.addWidget(date_label)
        footer.addStretch(1)
        footer.addWidget(progress_label)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(project["progress"])
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #dde6f4;
                border: none;
                border-radius: 6px;
                min-height: 10px;
                max-height: 10px;
            }}
            QProgressBar::chunk {{
                background: {project['accent']};
                border-radius: 6px;
            }}
            """
        )

        layout.addWidget(image)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(progress_bar)
        layout.addLayout(footer)


class ActionButton(QPushButton):
    def __init__(self, text: str, kind: str = "inlineAction") -> None:
        super().__init__(text)
        self.setObjectName(kind)
        self.setCursor(Qt.PointingHandCursor)


class ProspectCard(CardFrame):
    def __init__(self, prospect: dict, on_edit=None, on_delete=None, on_convert=None) -> None:
        super().__init__("softCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        brand = QLabel()
        brand.setPixmap(rounded_pixmap(26, QColor(prospect["accent"]), prospect["company"][:1]))
        company_label = QLabel(prospect["company"])
        company_label.setObjectName("smallTitle")
        top.addWidget(brand)
        top.addWidget(company_label)
        top.addStretch(1)
        amount_label = QLabel(format_currency(prospect["proposal_value"]))
        amount_label.setObjectName("amountLabel")
        top.addWidget(amount_label)

        contact_label = QLabel(prospect["contact"])
        contact_label.setObjectName("mutedTextStrong")
        note_label = QLabel(prospect["note"])
        note_label.setObjectName("mutedText")
        note_label.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        convert_button = ActionButton("Converter")
        edit_button = ActionButton("Editar")
        delete_button = ActionButton("Excluir", "dangerAction")
        button_row.addWidget(convert_button)
        button_row.addWidget(edit_button)
        button_row.addWidget(delete_button)
        button_row.addStretch(1)

        if on_convert:
            convert_button.clicked.connect(lambda: on_convert(prospect["id"]))
        if on_edit:
            edit_button.clicked.connect(lambda: on_edit(prospect["id"]))
        if on_delete:
            delete_button.clicked.connect(lambda: on_delete(prospect["id"]))

        layout.addLayout(top)
        layout.addWidget(contact_label)
        layout.addWidget(note_label)
        layout.addLayout(button_row)


class JobCard(CardFrame):
    def __init__(self, project: dict, on_edit=None, on_delete=None) -> None:
        super().__init__("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        preview = QLabel()
        preview.setPixmap(make_thumbnail(project["company"], project["colors"], QSize(360, 150)))
        preview.setScaledContents(True)
        preview.setFixedHeight(150)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        company_label = QLabel(project["company"])
        company_label.setObjectName("mutedText")
        project_label = QLabel(project["project_name"])
        project_label.setObjectName("smallTitle")
        text_box.addWidget(company_label)
        text_box.addWidget(project_label)

        status_label = QLabel(project["status"])
        status_label.setObjectName("statusTag")
        status_label.setStyleSheet(
            f"QLabel#statusTag {{ background: {project['accent']}22; color: {project['accent']}; border: 1px solid {project['accent']}33; }}"
        )

        title_row.addLayout(text_box, 1)
        title_row.addWidget(status_label, 0, Qt.AlignTop)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        type_label = QLabel(project["content_type"])
        type_label.setObjectName("mutedText")
        amount_label = QLabel(format_currency(project["total_value"]))
        amount_label.setObjectName("amountLabel")
        meta_row.addWidget(type_label)
        meta_row.addStretch(1)
        meta_row.addWidget(amount_label)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(project["progress"])
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #dde6f4;
                border: none;
                border-radius: 6px;
                min-height: 10px;
                max-height: 10px;
            }}
            QProgressBar::chunk {{
                background: {project['accent']};
                border-radius: 6px;
            }}
            """
        )

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        due_label = QLabel(project["due_text"])
        due_label.setObjectName("dateChip")
        progress_label = QLabel(f"{project['progress']}%")
        progress_label.setObjectName("mutedTextStrong")
        edit_button = ActionButton("Editar")
        delete_button = ActionButton("Excluir", "dangerAction")

        if on_edit:
            edit_button.clicked.connect(lambda: on_edit(project["id"]))
        if on_delete:
            delete_button.clicked.connect(lambda: on_delete(project["id"]))

        footer.addWidget(due_label)
        footer.addWidget(progress_label)
        footer.addStretch(1)
        footer.addWidget(edit_button)
        footer.addWidget(delete_button)

        layout.addWidget(preview)
        layout.addLayout(title_row)
        layout.addLayout(meta_row)
        layout.addWidget(progress_bar)
        layout.addLayout(footer)


class ScheduleRow(CardFrame):
    def __init__(self, company: str, kind: str, due: str, amount: str, status: str, accent: str) -> None:
        super().__init__("softCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        icon = QLabel()
        icon.setPixmap(make_icon("money", accent, 16, bg="#eef5ff").pixmap(QSize(30, 30)))

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(4)
        company_label = QLabel(company)
        company_label.setObjectName("smallTitle")
        detail_label = QLabel(f"{kind} | vence {due}")
        detail_label.setObjectName("mutedText")
        text_box.addWidget(company_label)
        text_box.addWidget(detail_label)

        amount_box = QVBoxLayout()
        amount_box.setContentsMargins(0, 0, 0, 0)
        amount_box.setSpacing(4)
        amount_label = QLabel(amount)
        amount_label.setObjectName("amountLabel")
        status_label = QLabel(status)
        status_label.setObjectName("statusTag")
        amount_box.addWidget(amount_label, 0, Qt.AlignRight)
        amount_box.addWidget(status_label, 0, Qt.AlignRight)

        layout.addWidget(icon)
        layout.addLayout(text_box, 1)
        layout.addLayout(amount_box)


class BreakdownRow(QWidget):
    def __init__(self, label: str, amount_text: str, progress: int, accent: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        title = QLabel(label)
        title.setObjectName("smallTitle")
        value = QLabel(amount_text)
        value.setObjectName("amountLabel")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(value)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(progress)
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #dde6f4;
                border: none;
                border-radius: 6px;
                min-height: 10px;
                max-height: 10px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 6px;
            }}
            """
        )

        layout.addLayout(top)
        layout.addWidget(progress_bar)


class HighlightCard(CardFrame):
    def __init__(self, title: str, description: str) -> None:
        super().__init__("softCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("smallTitle")
        description_label = QLabel(description)
        description_label.setObjectName("mutedText")
        description_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(description_label)


class SettingsRow(CardFrame):
    def __init__(self, label: str, detail: str, control: QWidget) -> None:
        super().__init__("softCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)
        title = QLabel(label)
        title.setObjectName("smallTitle")
        subtitle = QLabel(detail)
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        info.addWidget(title)
        info.addWidget(subtitle)

        layout.addLayout(info, 1)
        layout.addWidget(control)


def build_checkbox(checked: bool) -> QCheckBox:
    checkbox = QCheckBox()
    checkbox.setChecked(checked)
    return checkbox


def build_combo(options: list[str], current: str) -> QComboBox:
    combo = QComboBox()
    combo.addItems(options)
    combo.setCurrentText(current)
    return combo


def build_ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("ghostButton")
    button.setCursor(Qt.PointingHandCursor)
    return button
