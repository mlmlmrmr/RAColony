import sys
import os
import pandas as pd
import numpy as np
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QFileDialog, QComboBox, QProgressBar, QMessageBox,
                             QGroupBox, QGridLayout, QCheckBox, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
import warnings

warnings.filterwarnings('ignore')

# Import compiled algorithm module
try:
    import colony_picking_algorithm
    from colony_picking_algorithm import ColonyPicking, calPickedCount, run_analysis, clean_numeric_data

    print("Using compiled colony_picking_algorithm module")
except ImportError:
    try:
        import colony_picking_algorithm
        from colony_picking_algorithm import ColonyPicking, calPickedCount, run_analysis, clean_numeric_data

        print("Using Python colony_picking_algorithm module")
    except ImportError:
        print("Error: colony_picking_algorithm module not found")
        sys.exit(1)


def get_icon_path():
    """Get icon file path"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_path = os.path.join(base_path, 'icon.ico')

    if not os.path.exists(icon_path):
        icon_path = os.path.join(os.path.dirname(base_path), 'icon.ico')

    return icon_path if os.path.exists(icon_path) else None


class AnalysisThread(QThread):
    """Analysis thread to avoid UI freezing"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, object, object, int)
    error = pyqtSignal(str)

    def __init__(self, file_path, data_type, picked_count, auto_calc=False):
        super().__init__()
        self.file_path = file_path
        self.data_type = data_type
        self.picked_count = picked_count
        self.auto_calc = auto_calc

    def run(self):
        try:
            def progress_callback(value):
                self.progress.emit(value)

            # Use the compiled run_analysis function
            result_df, X_tsne, choices, actual_count = run_analysis(
                self.file_path, self.data_type, self.picked_count,
                self.auto_calc, progress_callback
            )

            self.finished.emit(result_df, X_tsne, choices, actual_count)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error details: {error_detail}")
            self.error.emit(f"Analysis failed: {str(e)}")


class MplCanvas(FigureCanvas):
    """Matplotlib canvas with scroll support"""

    def __init__(self, parent=None, width=20, height=16, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='white')
        super(MplCanvas, self).__init__(self.fig)
        self.axes = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.08)

    def set_figure_size(self, width, height):
        self.fig.set_size_inches(width, height)
        self.fig.subplots_adjust(left=0.08, right=0.95, top=0.95, bottom=0.08)
        self.draw()


class ScrollableCanvas(QScrollArea):
    """Scrollable canvas container"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = MplCanvas(self, width=20, height=16)
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def resize_canvas(self, width, height):
        self.canvas.set_figure_size(width, height)
        self.canvas.setFixedSize(int(width * self.canvas.fig.dpi),
                                 int(height * self.canvas.fig.dpi))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.analysis_thread = None
        self.current_df = None
        self.current_tsne = None
        self.current_choices = None
        self.initUI()

    def initUI(self):
        # Set window icon
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
            print(f"Icon loaded from: {icon_path}")
        else:
            print("Icon file not found: icon.ico")

        self.setWindowTitle('RAColony Duplicate Removal Analysis System')
        self.setGeometry(100, 100, 1500, 1000)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)

        # Control panel
        control_group = QGroupBox("Control Panel")
        control_layout = QGridLayout()

        control_layout.addWidget(QLabel("File Path:"), 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select Excel file path...")
        control_layout.addWidget(self.path_edit, 0, 1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_file)
        control_layout.addWidget(self.browse_btn, 0, 2)

        control_layout.addWidget(QLabel("Analysis Type:"), 1, 0)
        self.analysis_type = QComboBox()
        self.analysis_type.addItems(["Raman Features", "Image Features"])
        self.analysis_type.currentTextChanged.connect(self.on_analysis_type_changed)
        control_layout.addWidget(self.analysis_type, 1, 1)

        self.auto_calc_checkbox = QCheckBox("Auto Calculate Pick Count")
        self.auto_calc_checkbox.setEnabled(False)
        self.auto_calc_checkbox.stateChanged.connect(self.on_auto_calc_changed)
        control_layout.addWidget(self.auto_calc_checkbox, 2, 0, 1, 2)

        control_layout.addWidget(QLabel("Pick Count:"), 3, 0)
        self.picked_count = QLineEdit()
        self.picked_count.setText("10")
        self.picked_count.setPlaceholderText("0 for auto calculation")
        control_layout.addWidget(self.picked_count, 3, 1)

        self.actual_count_label = QLabel("Actual Pick Count: --")
        self.actual_count_label.setStyleSheet("QLabel { color: #4CAF50; font-weight: bold; }")
        control_layout.addWidget(self.actual_count_label, 3, 2)

        self.analyze_btn = QPushButton("Start Analysis")
        self.analyze_btn.clicked.connect(self.start_analysis)
        self.analyze_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-size: 14px; padding: 8px; }")
        control_layout.addWidget(self.analyze_btn, 4, 0, 1, 3)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar, 5, 0, 1, 3)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Image display area
        image_group = QGroupBox("TSNE Visualization Results")
        image_layout = QVBoxLayout()

        self.scrollable_canvas = ScrollableCanvas()
        image_layout.addWidget(self.scrollable_canvas)

        info_label = QLabel(
            "Tip: Use mouse wheel or scroll bars to view the complete image. Gray dots: all samples, Red dots: selected samples")
        info_label.setStyleSheet("QLabel { color: #666; font-size: 12px; padding: 5px; background-color: #f0f0f0; }")
        info_label.setWordWrap(True)
        image_layout.addWidget(info_label)

        button_layout = QHBoxLayout()

        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_in_btn.setEnabled(False)

        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_out_btn.setEnabled(False)

        self.fit_btn = QPushButton("Fit to Window")
        self.fit_btn.clicked.connect(self.fit_to_window)
        self.fit_btn.setEnabled(False)

        self.save_btn = QPushButton("Save Figure")
        self.save_btn.clicked.connect(self.save_figure)
        self.save_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.zoom_in_btn)
        button_layout.addWidget(self.zoom_out_btn)
        button_layout.addWidget(self.fit_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()

        image_layout.addLayout(button_layout)

        image_group.setLayout(image_layout)
        main_layout.addWidget(image_group)

        main_layout.setStretchFactor(control_group, 1)
        main_layout.setStretchFactor(image_group, 5)

        self.zoom_level = 1.0

    def on_analysis_type_changed(self):
        if self.analysis_type.currentText() == "Image Features":
            self.auto_calc_checkbox.setEnabled(True)
            if self.auto_calc_checkbox.isChecked():
                self.picked_count.setEnabled(False)
                self.picked_count.setPlaceholderText("Auto calculating...")
            else:
                self.picked_count.setEnabled(True)
                self.picked_count.setPlaceholderText("0 for auto calculation")
        else:
            self.auto_calc_checkbox.setEnabled(False)
            self.auto_calc_checkbox.setChecked(False)
            self.picked_count.setEnabled(True)
            self.picked_count.setPlaceholderText("0 for auto calculation")

    def on_auto_calc_changed(self):
        if self.auto_calc_checkbox.isChecked():
            self.picked_count.setEnabled(False)
            self.picked_count.setPlaceholderText("Auto calculating...")
            self.picked_count.setText("0")
        else:
            self.picked_count.setEnabled(True)
            self.picked_count.setPlaceholderText("0 for auto calculation")
            self.picked_count.setText("10")

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.path_edit.setText(file_path)

    def start_analysis(self):
        file_path = self.path_edit.text()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", "Please select a valid Excel file!")
            return

        analysis_type = self.analysis_type.currentText()
        auto_calc = self.auto_calc_checkbox.isChecked() if analysis_type == "Image Features" else False
        data_type = 0 if analysis_type == "Image Features" else 1

        picked_count = 0
        if not auto_calc:
            try:
                picked_count = int(self.picked_count.text())
                if picked_count < 0:
                    QMessageBox.warning(self, "Warning", "Pick count cannot be negative!")
                    return
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid number!")
                return

        self.actual_count_label.setText("Actual Pick Count: --")
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.analysis_thread = AnalysisThread(file_path, data_type, picked_count, auto_calc)
        self.analysis_thread.progress.connect(self.update_progress)
        self.analysis_thread.finished.connect(self.analysis_finished)
        self.analysis_thread.error.connect(self.analysis_error)
        self.analysis_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def analysis_finished(self, df, X_tsne, choices, actual_count):
        self.current_df = df
        self.current_tsne = X_tsne
        self.current_choices = choices

        self.actual_count_label.setText(f"Actual Pick Count: {actual_count}")

        if self.auto_calc_checkbox.isChecked() and self.analysis_type.currentText() == "Image Features":
            self.picked_count.setText(str(actual_count))

        self.update_plot()

        self.analyze_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.save_btn.setEnabled(True)
        self.zoom_in_btn.setEnabled(True)
        self.zoom_out_btn.setEnabled(True)
        self.fit_btn.setEnabled(True)

        QMessageBox.information(
            self, "Analysis Complete",
            f"Analysis completed!\nTotal samples: {len(df)}\nSelected samples: {len(choices)}"
        )

    def analysis_error(self, error_msg):
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Error during analysis:\n{error_msg}")

    def update_plot(self):
        if self.current_df is None or self.current_tsne is None:
            return

        self.scrollable_canvas.canvas.axes.clear()

        x_coords = self.current_df['x'].values
        y_coords = self.current_df['y'].values

        x_range = x_coords.max() - x_coords.min()
        y_range = y_coords.max() - y_coords.min()
        max_range = max(x_range, y_range)

        self.scrollable_canvas.canvas.axes.scatter(x_coords, y_coords, c='gray', alpha=0.6, s=20, label='All Samples')

        if self.current_choices is not None and len(self.current_choices) > 0:
            selected_x = [x_coords[i] for i in self.current_choices if i < len(x_coords)]
            selected_y = [y_coords[i] for i in self.current_choices if i < len(y_coords)]
            self.scrollable_canvas.canvas.axes.scatter(selected_x, selected_y, c='red', alpha=0.8, s=30,
                                                       marker='o', edgecolors='darkred', linewidth=1.5,
                                                       label='Selected Samples')

        self.scrollable_canvas.canvas.axes.set_xlabel('TSNE Component 1', fontsize=12)
        self.scrollable_canvas.canvas.axes.set_ylabel('TSNE Component 2', fontsize=12)
        self.scrollable_canvas.canvas.axes.legend(loc='best', fontsize=10, framealpha=0.9)
        self.scrollable_canvas.canvas.axes.grid(True, alpha=0.3)

        center_x = (x_coords.min() + x_coords.max()) / 2
        center_y = (y_coords.min() + y_coords.max()) / 2
        margin = max_range * 0.1
        self.scrollable_canvas.canvas.axes.set_xlim(center_x - max_range / 2 - margin,
                                                    center_x + max_range / 2 + margin)
        self.scrollable_canvas.canvas.axes.set_ylim(center_y - max_range / 2 - margin,
                                                    center_y + max_range / 2 + margin)
        self.scrollable_canvas.canvas.axes.set_aspect('equal', adjustable='box')

        self.scrollable_canvas.canvas.draw()
        self.zoom_level = 1.0
        self.fit_to_window()

    def zoom_in(self):
        self.zoom_level *= 1.2
        current_size = self.scrollable_canvas.canvas.fig.get_size_inches()
        self.scrollable_canvas.resize_canvas(current_size[0] * 1.2, current_size[1] * 1.2)

    def zoom_out(self):
        self.zoom_level *= 0.8
        current_size = self.scrollable_canvas.canvas.fig.get_size_inches()
        self.scrollable_canvas.resize_canvas(current_size[0] * 0.8, current_size[1] * 0.8)

    def fit_to_window(self):
        viewport_size = self.scrollable_canvas.viewport().size()
        width_inches = viewport_size.width() / self.scrollable_canvas.canvas.fig.dpi * 0.9
        height_inches = viewport_size.height() / self.scrollable_canvas.canvas.fig.dpi * 0.9
        self.scrollable_canvas.resize_canvas(max(10, width_inches), max(8, height_inches))
        self.zoom_level = 1.0

    def save_figure(self):
        if self.current_df is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Figure", "", "PNG Files (*.png);;JPG Files (*.jpg);;All Files (*)"
        )

        if file_path:
            try:
                self.scrollable_canvas.canvas.fig.savefig(file_path, dpi=300, bbox_inches='tight', facecolor='white')
                QMessageBox.information(self, "Success", f"Figure saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save figure:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
