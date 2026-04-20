import sys
import os
import cv2
import numpy as np
import json
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QTextEdit, QProgressBar, QMessageBox, QSplitter,
                             QSlider, QComboBox, QSpinBox)
from PyQt5.QtCore import Qt, QRect, QPoint, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QIcon

# Import algorithm functions from the encapsulated module
try:
    import ImageAnalysisAlgorithm
    from ImageAnalysisAlgorithm import (PanoramicImageAnalysis, init_model,
                                   is_available)
    print("Using compiled colony_algorithm module")
except ImportError:
    try:
        import ImageAnalysisAlgorithm
        from ImageAnalysisAlgorithm import (PanoramicImageAnalysis, init_model,
                                       is_available)
        print("Using Python colony_algorithm module")
    except ImportError:
        print("Error: colony_algorithm module not found")
        sys.exit(1)


# Analysis thread class
class AnalysisThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(str, object)
    error_signal = pyqtSignal(str)

    def __init__(self, image_array, dish_type, dish_range, use_model=True):
        super().__init__()
        self.image_array = image_array
        self.dish_type = dish_type
        self.dish_range = dish_range
        self.use_model = use_model and is_available()

    def run(self):
        try:
            def log_callback(msg):
                self.log_signal.emit(msg)

            def progress_callback(current, total):
                self.progress_signal.emit(current, total)

            result_json, result_img = PanoramicImageAnalysis(
                self.image_array, self.dish_type, self.dish_range,
                use_model=self.use_model,
                log_callback=log_callback,
                progress_callback=progress_callback
            )
            self.finished_signal.emit(result_json, result_img)
        except Exception as e:
            self.error_signal.emit(str(e))


# Custom image display widget with circle drawing support
class ImageDisplayWidget(QLabel):
    radius_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        self.setMinimumSize(400, 400)

        self.original_pixmap = None
        self.display_pixmap = None
        self.original_image = None

        # Circle parameters
        self.circle_center = None
        self.circle_radius = 1700
        self.max_radius = 2300
        self.min_radius = 1

        # Zoom related
        self.zoom_factor = 1.0
        self.image_offset = QPoint(0, 0)

        # Interaction state
        self.drawing_mode = False
        self.mouse_pos = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def load_image(self, image_path):
        """Load image from file"""
        self.original_image = cv2.imread(image_path)
        if self.original_image is None:
            return False

        self.display_image(self.original_image)
        return True

    def display_image(self, image):
        """Display image (supports numpy array)"""
        if image is None:
            return

        # Convert BGR to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            if image.dtype == np.uint8:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
        else:
            image_rgb = image

        height, width, channel = image_rgb.shape
        bytes_per_line = 3 * width
        q_image = QImage(image_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)

        self.original_pixmap = QPixmap.fromImage(q_image)
        self.original_image = image
        self.reset_view()

    def reset_view(self):
        """Reset view"""
        if self.original_pixmap:
            widget_size = self.size()
            scaled_pixmap = self.original_pixmap.scaled(widget_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.display_pixmap = scaled_pixmap
            self.setPixmap(self.display_pixmap)

            original_size = self.original_pixmap.size()
            display_size = self.display_pixmap.size()
            self.zoom_factor = display_size.width() / original_size.width()

            x_offset = (widget_size.width() - display_size.width()) // 2
            y_offset = (widget_size.height() - display_size.height()) // 2
            self.image_offset = QPoint(x_offset, y_offset)

    def resizeEvent(self, event):
        self.reset_view()
        self.update()
        super().resizeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.display_pixmap is None:
            return

        painter = QPainter(self)

        if self.circle_center is not None and self.circle_radius > 0:
            display_center = self.image_to_display(self.circle_center)
            display_radius = self.circle_radius * self.zoom_factor

            painter.setPen(QPen(QColor(255, 0, 0), 3, Qt.SolidLine))
            painter.drawEllipse(display_center, display_radius, display_radius)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawEllipse(display_center, 5, 5)

            radius_text = f"R={self.circle_radius}"
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawText(display_center.x() + 10, display_center.y() - 10, radius_text)

        if self.mouse_pos is not None and self.original_image is not None:
            display_pos = self.mouse_pos
            image_pos = self.display_to_image(display_pos)
            if 0 <= image_pos.x() < self.original_image.shape[1] and 0 <= image_pos.y() < self.original_image.shape[0]:
                coord_text = f"({image_pos.x()}, {image_pos.y()})"
                painter.setPen(QPen(QColor(255, 255, 0), 1))
                painter.drawText(display_pos.x() + 10, display_pos.y() - 10, coord_text)

        painter.end()

    def image_to_display(self, image_point):
        x = image_point.x() * self.zoom_factor + self.image_offset.x()
        y = image_point.y() * self.zoom_factor + self.image_offset.y()
        return QPoint(int(x), int(y))

    def display_to_image(self, display_point):
        x = (display_point.x() - self.image_offset.x()) / self.zoom_factor
        y = (display_point.y() - self.image_offset.y()) / self.zoom_factor
        return QPoint(int(x), int(y))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.original_image is not None:
            display_pos = event.pos()
            if self.display_pixmap:
                display_rect = QRect(self.image_offset, self.display_pixmap.size())
                if display_rect.contains(display_pos):
                    self.circle_center = self.display_to_image(display_pos)
                    if self.circle_radius == 0:
                        self.circle_radius = 1700
                    self.drawing_mode = True
                    self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.original_image is not None:
            self.mouse_pos = event.pos()
            if event.buttons() & Qt.LeftButton and self.drawing_mode:
                display_pos = event.pos()
                if self.display_pixmap:
                    display_rect = QRect(self.image_offset, self.display_pixmap.size())
                    if display_rect.contains(display_pos):
                        self.circle_center = self.display_to_image(display_pos)
                        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing_mode:
            self.drawing_mode = False
            self.update()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Wheel event - adjust radius"""
        if self.circle_center is not None and self.original_image is not None:
            delta = event.angleDelta().y()

            step = 20
            if delta > 0:
                new_radius = self.circle_radius + step
            else:
                new_radius = self.circle_radius - step

            old_radius = self.circle_radius
            self.circle_radius = max(self.min_radius, min(new_radius, self.max_radius))

            if old_radius != self.circle_radius:
                self.update()
                self.radius_changed.emit(self.circle_radius)

            event.accept()
        else:
            event.ignore()
            super().wheelEvent(event)

    def get_circle_params(self):
        if self.circle_center is not None and self.circle_radius > 0:
            return (self.circle_center.x(), self.circle_center.y()), self.circle_radius
        return None, 0

    def clear_circle(self):
        self.circle_center = None
        self.circle_radius = 1700
        self.update()

    def set_radius(self, radius):
        old_radius = self.circle_radius
        self.circle_radius = max(self.min_radius, min(radius, self.max_radius))
        if old_radius != self.circle_radius:
            self.update()


# Main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Colony Image Analysis System")
        self.setGeometry(100, 100, 1400, 800)

        self.current_image_path = None
        self.original_image = None
        self.result_image = None
        self.analysis_thread = None
        self.use_model = True

        self.setup_ui()
        self._updating_radius = False
        self.set_window_icon()

        self.init_model()

    def setup_ui(self):
        """Setup user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # Left control panel
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)

        # File selection area
        file_group = QWidget()
        file_layout = QVBoxLayout(file_group)

        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")

        select_btn = QPushButton("Select Image")
        select_btn.clicked.connect(self.select_image)
        select_btn.setStyleSheet("padding: 8px; font-size: 12px;")

        file_layout.addWidget(select_btn)
        file_layout.addWidget(self.file_label)

        # Button area
        button_layout = QHBoxLayout()

        self.show_original_btn = QPushButton("Original")
        self.show_original_btn.clicked.connect(self.show_original_image)
        self.show_original_btn.setEnabled(False)
        button_layout.addWidget(self.show_original_btn)

        self.show_result_btn = QPushButton("Result")
        self.show_result_btn.clicked.connect(self.show_result_image)
        self.show_result_btn.setEnabled(False)
        button_layout.addWidget(self.show_result_btn)

        file_layout.addLayout(button_layout)

        # Circle information display
        circle_group = QWidget()
        circle_layout = QVBoxLayout(circle_group)
        circle_layout.addWidget(QLabel("ROI Settings:"))

        self.circle_info_label = QLabel("No ROI set")
        self.circle_info_label.setStyleSheet("padding: 5px; background-color: #e8e8e8;")
        self.circle_info_label.setWordWrap(True)
        circle_layout.addWidget(self.circle_info_label)

        # Radius slider
        radius_layout = QVBoxLayout()
        radius_layout.addWidget(QLabel("Radius Adjustment:"))

        self.radius_slider = QSlider(Qt.Horizontal)
        self.radius_slider.setRange(1, 2300)
        self.radius_slider.setValue(1700)
        self.radius_slider.setTickPosition(QSlider.TicksBelow)
        self.radius_slider.setTickInterval(100)
        self.radius_slider.valueChanged.connect(self.on_radius_changed)
        radius_layout.addWidget(self.radius_slider)

        self.radius_value_label = QLabel("Current radius: 1700 px (Max: 2300)")
        self.radius_value_label.setStyleSheet("color: #666; font-size: 11px;")
        radius_layout.addWidget(self.radius_value_label)

        circle_layout.addLayout(radius_layout)

        clear_circle_btn = QPushButton("Clear ROI")
        clear_circle_btn.clicked.connect(self.clear_circle)
        clear_circle_btn.setStyleSheet("padding: 5px;")
        circle_layout.addWidget(clear_circle_btn)

        circle_layout.addWidget(QLabel("Instructions:"))
        info_text = QLabel(
            "1. Left click: Set center\n2. Scroll wheel: Adjust radius\n3. Drag: Move center\n4. Slider: Fine-tune radius")
        info_text.setStyleSheet("color: #666; font-size: 11px;")
        info_text.setWordWrap(True)
        circle_layout.addWidget(info_text)

        # Analysis parameters
        param_group = QWidget()
        param_layout = QVBoxLayout(param_group)
        param_layout.addWidget(QLabel("Analysis Parameters:"))

        # Dish type
        dish_layout = QHBoxLayout()
        dish_layout.addWidget(QLabel("Dish Type:"))
        self.dish_type_combo = QComboBox()
        self.dish_type_combo.addItems(["GAM (1)", "PYG (2)", "YCFA (3)", "MS (4)"])
        dish_layout.addWidget(self.dish_type_combo)
        param_layout.addLayout(dish_layout)

        # Dish range
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Dish Range:"))
        self.dish_range_spin = QSpinBox()
        self.dish_range_spin.setRange(0, 5000)
        self.dish_range_spin.setValue(2300)
        self.dish_range_spin.setSuffix(" px")
        range_layout.addWidget(self.dish_range_spin)
        param_layout.addLayout(range_layout)

        # Analysis button
        analyze_btn = QPushButton("Start Analysis")
        analyze_btn.clicked.connect(self.analyze_image)
        analyze_btn.setStyleSheet(
            "padding: 10px; background-color: #4CAF50; color: white; font-size: 14px; font-weight: bold;")
        analyze_btn.setMinimumHeight(50)
        param_layout.addWidget(analyze_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        param_layout.addWidget(self.progress_bar)

        # Log output
        log_group = QWidget()
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(QLabel("Analysis Log:"))

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)

        # Assemble left panel
        left_layout.addWidget(file_group)
        left_layout.addWidget(circle_group)
        left_layout.addWidget(param_group)
        left_layout.addWidget(log_group)
        left_layout.addStretch()

        # Right image display area
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.image_display = ImageDisplayWidget()
        self.image_display.radius_changed.connect(self.update_radius_display)
        right_layout.addWidget(self.image_display)

        self.status_label = QLabel("1. Load image | 2. Set ROI | 3. Select dish type | 4. Start analysis")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-top: 1px solid #ccc;")
        right_layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 1050])

        main_layout.addWidget(splitter)

        self.circle_update_timer = QTimer()
        self.circle_update_timer.timeout.connect(self.update_circle_info)
        self.circle_update_timer.start(100)

    def init_model(self):
        """Initialize  model using the algorithm module"""
        self.log_message("Initializing model...")
        success, message = init_model()
        if success:
            self.log_message(f"✓ {message}")
            self.use_mdoel = True
            self.status_label.setText("Ready | model loaded")
        else:
            self.log_message(f"⚠ {message}")
            self.log_message("Continuing in simplified mode (without adherent colony splitting)")
            self.use_mdoel = False
            self.status_label.setText("Ready | Simplified mode (not available)")

    def set_window_icon(self):
        """Set window icon"""
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
                icon_path = os.path.join(base_path, 'icon.ico')
            else:
                icon_path = 'icon.ico'

            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

    def log_message(self, message):
        """Output log to interface"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def update_radius_display(self, radius):
        """Update radius display"""
        if not self._updating_radius:
            self._updating_radius = True
            self.radius_slider.blockSignals(True)
            self.radius_slider.setValue(radius)
            self.radius_slider.blockSignals(False)
            self.radius_value_label.setText(f"Current radius: {radius} px (Max: 2300)")
            self._updating_radius = False

    def on_radius_changed(self, value):
        """Slider changed"""
        if not self._updating_radius and self.image_display:
            self._updating_radius = True
            self.image_display.blockSignals(True)
            self.image_display.set_radius(value)
            self.image_display.blockSignals(False)
            self.radius_value_label.setText(f"Current radius: {value} px (Max: 2300)")
            self._updating_radius = False

    def show_original_image(self):
        """Show original image"""
        if self.original_image is not None:
            self.image_display.display_image(self.original_image)
            self.status_label.setText("Showing original image")
            self.log_message("Switched to original image")

    def show_result_image(self):
        """Show result image"""
        if self.result_image is not None:
            self.image_display.display_image(self.result_image)
            self.status_label.setText("Showing result image (annotated)")
            self.log_message("Switched to result image")

    def select_image(self):
        """Select image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*.*)"
        )

        if file_path:
            self.current_image_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")

            if self.image_display.load_image(file_path):
                self.log_message(f"Image loaded successfully: {file_path}")
                self.status_label.setText(f"Loaded: {os.path.basename(file_path)}")
                self.original_image = cv2.imread(file_path)
                self.result_image = None
                self.image_display.clear_circle()
                self.radius_slider.setValue(1700)
                self.show_original_btn.setEnabled(True)
                self.show_result_btn.setEnabled(False)
            else:
                self.log_message(f"Failed to load image: {file_path}")

    def clear_circle(self):
        """Clear circle"""
        self.image_display.clear_circle()
        self.radius_slider.setValue(1700)
        self.log_message("ROI cleared, radius reset to default 1700")

    def update_circle_info(self):
        """Update circle information"""
        center, radius = self.image_display.get_circle_params()
        if center and radius > 0:
            self.circle_info_label.setText(f"Center: ({center[0]}, {center[1]})\nRadius: {radius} px\nMax: 2300 px")
        else:
            self.circle_info_label.setText("No ROI set\n(Left click to set center)")

    def update_progress(self, current, total):
        """Update progress bar"""
        if total > 0:
            progress_value = int((current / total) * 100)
            self.progress_bar.setValue(progress_value)
            self.status_label.setText(f"Processing: {current}/{total} ({progress_value}%)")

    def on_analysis_log(self, msg):
        """Receive analysis thread log"""
        self.log_message(msg)

    def on_analysis_progress(self, current, total):
        """Receive analysis thread progress"""
        self.update_progress(current, total)

    def on_analysis_finished(self, result_json, result_img):
        """Analysis finished"""
        try:
            result = json.loads(result_json)

            if result.get('return') == 1:
                colony_count = result.get('ColonyCount', 0)
                result_name = result.get('name', 'N/A')

                self.result_image = result_img
                self.image_display.display_image(result_img)
                self.show_result_btn.setEnabled(True)

                self.log_message(f"✓ Analysis complete! Total colonies detected: {colony_count}")
                self.log_message(f"✓ Result image saved to: {result_name}")

                colony_info = result.get('ColoyInfo', [])
                if colony_info:
                    self.log_message("Colony location info (first 10):")
                    for i, colony in enumerate(colony_info[:10]):
                        state = "Adherent" if colony.get('nColonyState', 0) == 1 else "Single"
                        self.log_message(f"  {i + 1}. Position: ({colony['x']}, {colony['y']}), Type: {state}")
                    if len(colony_info) > 10:
                        self.log_message(f"  ... {len(colony_info)} colonies total")

                self.log_message("=" * 50)
                QMessageBox.information(self, "Analysis Complete",
                                        f"Detected {colony_count} colonies\nResult image saved and displayed")
            else:
                error_msg = "Analysis failed"
                if result.get('return') == -1:
                    error_msg = "Dish range not detected"
                elif result.get('return') == -2:
                    error_msg = "Lighting condition unqualified, please adjust image or ROI"
                self.log_message(f"✗ {error_msg}")
                self.log_message("=" * 50)
                QMessageBox.warning(self, "Analysis Failed", error_msg)

        except Exception as e:
            self.log_message(f"✗ Error processing result: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to process result: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)
            self.status_label.setText("Ready | Analysis complete")
            self.analysis_thread = None

    def on_analysis_error(self, error_msg):
        """Analysis error"""
        self.log_message(f"✗ Analysis error: {error_msg}")
        self.log_message("=" * 50)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready | Analysis error")
        QMessageBox.critical(self, "Error", f"Analysis failed: {error_msg}")
        self.analysis_thread = None

    def analyze_image(self):
        """Execute analysis"""
        if self.original_image is None:
            QMessageBox.warning(self, "Warning", "Please select an image first")
            return

        center, radius = self.image_display.get_circle_params()
        if center is None or radius <= 0:
            QMessageBox.warning(self, "Warning",
                                "Please set ROI first (Left click to set center, scroll wheel to adjust radius)")
            return

        if radius > 2300:
            QMessageBox.warning(self, "Warning", f"Radius {radius} exceeds maximum limit of 2300")
            return

        if self.analysis_thread is not None and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Analysis already running, please wait")
            return

        self.log_message("=" * 50)
        self.log_message("Starting macroscopic analysis...")
        self.log_message(f"ROI: Center({center[0]}, {center[1]}), Radius={radius}")
        self.log_message(f"Dish type: {self.dish_type_combo.currentText()}")
        self.log_message(f"model mode: {'Enabled' if self.use_model else 'Disabled (simplified mode)'}")

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        dish_type = self.dish_type_combo.currentIndex() + 1
        dish_range = [radius, center[0], center[1]]

        self.analysis_thread = AnalysisThread(
            self.original_image, dish_type, dish_range, self.use_model
        )
        self.analysis_thread.log_signal.connect(self.on_analysis_log)
        self.analysis_thread.progress_signal.connect(self.on_analysis_progress)
        self.analysis_thread.finished_signal.connect(self.on_analysis_finished)
        self.analysis_thread.error_signal.connect(self.on_analysis_error)
        self.analysis_thread.start()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()