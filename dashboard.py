import sys
import socket
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QTextEdit, QGroupBox, QSpinBox, QComboBox,
    QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

class CommandThread(QThread):
    """Send commands to Teensy in a separate thread"""
    command_sent = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, host, port, command):
        super().__init__()
        self.host = host
        self.port = port
        self.command = command
    
    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(self.command.encode(), (self.host, self.port))

            response = ""
            sock.settimeout(0.5)
            try:
                data, _ = sock.recvfrom(1024)
                response = data.decode(errors="replace").strip()
            except socket.timeout:
                pass

            if response:
                self.command_sent.emit(f"✓ Sent: {self.command} | Teensy: {response}")
            else:
                self.command_sent.emit(f"✓ Sent: {self.command}")
            sock.close()
        except Exception as e:
            self.error_occurred.emit(f"✗ Error: {str(e)}")


class AntennaControlDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Antenna Rotation Control Dashboard")
        self.setGeometry(100, 100, 900, 700)
        self.setStyleSheet(self.get_stylesheet())
        
        # Teensy connection settings
        self.teensy_ip = "192.168.1.177"
        self.teensy_port = 8888
        
        # State tracking
        self.current_speed = 100
        self.current_angle = 0
        self.is_moving = False
        self.move_direction = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        
        # === Connection Status ===
        status_layout = QHBoxLayout()
        status_label = QLabel("Connection Status:")
        status_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.status_indicator = QLabel("● READY")
        self.status_indicator.setStyleSheet("color: #00AA00; font-weight: bold; font-size: 12px;")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)
        
        # === Control Panel ===
        control_group = QGroupBox("Motor Control")
        control_layout = QVBoxLayout()
        
        # Direction buttons
        buttons_layout = QHBoxLayout()
        
        self.left_btn = QPushButton("← LEFT")
        self.left_btn.setFixedSize(120, 60)
        self.left_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.left_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066CC;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0052A3; }
            QPushButton:pressed { background-color: #003D7A; }
        """)
        self.left_btn.clicked.connect(lambda: self.send_command("LEFT"))
        
        self.stop_btn = QPushButton("⏹ STOP")
        self.stop_btn.setFixedSize(120, 60)
        self.stop_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #990000; }
            QPushButton:pressed { background-color: #660000; }
        """)
        self.stop_btn.clicked.connect(lambda: self.send_command("STOP"))
        
        self.right_btn = QPushButton("RIGHT →")
        self.right_btn.setFixedSize(120, 60)
        self.right_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.right_btn.setStyleSheet("""
            QPushButton {
                background-color: #00AA00;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #008800; }
            QPushButton:pressed { background-color: #006600; }
        """)
        self.right_btn.clicked.connect(lambda: self.send_command("RIGHT"))
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.left_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addWidget(self.right_btn)
        buttons_layout.addStretch()
        control_layout.addLayout(buttons_layout)

        # Target angle control
        target_layout = QHBoxLayout()
        target_label = QLabel("Target Angle:")
        target_label.setFont(QFont("Arial", 10, QFont.Bold))

        self.angle_input = QDoubleSpinBox()
        self.angle_input.setMinimum(0.0)
        self.angle_input.setMaximum(360.0)
        self.angle_input.setDecimals(1)
        self.angle_input.setSingleStep(1.0)
        self.angle_input.setSuffix("°")
        self.angle_input.setValue(0.0)
        self.angle_input.setMinimumWidth(120)

        self.goto_btn = QPushButton("GO TO ANGLE")
        self.goto_btn.setFixedSize(140, 42)
        self.goto_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.goto_btn.clicked.connect(self.send_angle_command)

        self.home_btn = QPushButton("HOME 0°")
        self.home_btn.setFixedSize(110, 42)
        self.home_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.home_btn.clicked.connect(lambda: self.send_command("HOME"))

        target_layout.addStretch()
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.angle_input)
        target_layout.addWidget(self.goto_btn)
        target_layout.addWidget(self.home_btn)
        target_layout.addStretch()
        control_layout.addLayout(target_layout)
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed (%):")
        speed_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(10)
        self.speed_slider.setMaximum(100)
        self.speed_slider.setValue(100)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(10)
        self.speed_slider.valueChanged.connect(self.update_speed_display)
        
        self.speed_display = QLabel("100%")
        self.speed_display.setFont(QFont("Arial", 10, QFont.Bold))
        self.speed_display.setMinimumWidth(50)
        
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_display)
        control_layout.addLayout(speed_layout)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # === Status Panel ===
        status_group = QGroupBox("Status & Feedback")
        status_panel_layout = QVBoxLayout()
        
        # Angle readout
        angle_layout = QHBoxLayout()
        angle_label = QLabel("Current Angle:")
        angle_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.angle_display = QLabel("0°")
        self.angle_display.setFont(QFont("Arial", 14, QFont.Bold))
        self.angle_display.setStyleSheet("color: #0066CC;")
        angle_layout.addWidget(angle_label)
        angle_layout.addWidget(self.angle_display)
        angle_layout.addStretch()
        status_panel_layout.addLayout(angle_layout)
        
        # Motor status
        motor_layout = QHBoxLayout()
        motor_label = QLabel("Motor Status:")
        motor_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.motor_status = QLabel("STOPPED")
        self.motor_status.setFont(QFont("Arial", 10, QFont.Bold))
        self.motor_status.setStyleSheet("color: #00AA00;")
        motor_layout.addWidget(motor_label)
        motor_layout.addWidget(self.motor_status)
        motor_layout.addStretch()
        status_panel_layout.addLayout(motor_layout)
        
        status_group.setLayout(status_panel_layout)
        main_layout.addWidget(status_group)
        
        # === Command History ===
        history_group = QGroupBox("Command History & Logs")
        history_layout = QVBoxLayout()
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        self.log_display.setFont(QFont("Courier", 9))
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00FF00;
                border: 1px solid #333;
            }
        """)
        history_layout.addWidget(self.log_display)
        
        # Clear log button
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        history_layout.addWidget(clear_btn)
        
        history_group.setLayout(history_layout)
        main_layout.addWidget(history_group)
        
        # === Advanced Settings ===
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout()
        
        # Teensy IP and Port
        conn_layout = QHBoxLayout()
        conn_label = QLabel("Teensy Address:")
        conn_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.ip_input = QComboBox()
        self.ip_input.addItem("192.168.1.177")
        self.ip_input.setEditable(True)
        conn_layout.addWidget(conn_label)
        conn_layout.addWidget(self.ip_input)
        
        port_label = QLabel("Port:")
        port_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.port_input = QSpinBox()
        self.port_input.setMinimum(1)
        self.port_input.setMaximum(65535)
        self.port_input.setValue(8888)
        conn_layout.addWidget(port_label)
        conn_layout.addWidget(self.port_input)
        conn_layout.addStretch()
        advanced_layout.addLayout(conn_layout)
        
        advanced_group.setLayout(advanced_layout)
        main_layout.addWidget(advanced_group)
        
        main_widget.setLayout(main_layout)
        self.add_log_entry("Dashboard initialized. Ready to send commands.")
    
    def send_command(self, command):
        """Send command to Teensy via UDP"""
        self.teensy_ip = self.ip_input.currentText()
        self.teensy_port = self.port_input.value()
        
        # Update motor status
        if command == "LEFT":
            self.motor_status.setText("↙ ROTATING LEFT")
            self.motor_status.setStyleSheet("color: #0066CC; font-weight: bold;")
            self.is_moving = True
            self.move_direction = -1
        elif command == "RIGHT":
            self.motor_status.setText("↗ ROTATING RIGHT")
            self.motor_status.setStyleSheet("color: #00AA00; font-weight: bold;")
            self.is_moving = True
            self.move_direction = 1
        elif command == "STOP":
            self.motor_status.setText("STOPPED")
            self.motor_status.setStyleSheet("color: #CC0000; font-weight: bold;")
            self.is_moving = False
            self.move_direction = None
        elif command.startswith("ANGLE:"):
            try:
                target_angle = float(command.split(":", 1)[1])
            except ValueError:
                target_angle = self.angle_input.value()
            self.motor_status.setText(f"MOVING TO {target_angle:.1f}°")
            self.motor_status.setStyleSheet("color: #AA6600; font-weight: bold;")
            self.current_angle = target_angle
            self.angle_display.setText(f"{target_angle:.1f}°")
            self.is_moving = True
            self.move_direction = None
        elif command == "HOME":
            self.motor_status.setText("HOMING TO 0°")
            self.motor_status.setStyleSheet("color: #AA6600; font-weight: bold;")
            self.angle_input.setValue(0.0)
            self.current_angle = 0.0
            self.angle_display.setText("0.0°")
            self.is_moving = True
            self.move_direction = None
        
        # Send command in background thread
        self.command_thread = CommandThread(self.teensy_ip, self.teensy_port, command)
        self.command_thread.command_sent.connect(self.on_command_sent)
        self.command_thread.error_occurred.connect(self.on_command_error)
        self.command_thread.start()

    def send_angle_command(self):
        """Send absolute target angle to Teensy"""
        angle = self.angle_input.value()
        self.send_command(f"ANGLE:{angle:.2f}")
    
    def on_command_sent(self, message):
        """Handle successful command transmission"""
        self.add_log_entry(message)
        self.status_indicator.setText("● ACTIVE")
        self.status_indicator.setStyleSheet("color: #00AA00; font-weight: bold; font-size: 12px;")
        self.update_from_teensy_response(message)
    
    def on_command_error(self, message):
        """Handle command transmission error"""
        self.add_log_entry(message)
        self.status_indicator.setText("● ERROR")
        self.status_indicator.setStyleSheet("color: #CC0000; font-weight: bold; font-size: 12px;")
    
    def update_speed_display(self):
        """Update speed display when slider changes"""
        self.current_speed = self.speed_slider.value()
        self.speed_display.setText(f"{self.current_speed}%")

    def update_from_teensy_response(self, message):
        """Use Teensy status replies to refresh the angle readout"""
        if "Teensy:" not in message:
            return

        sent_command = message.split("Sent:", 1)[1].split("|", 1)[0].strip()
        response = message.split("Teensy:", 1)[1].strip()
        fields = {}
        for token in response.split():
            if ":" in token:
                key, value = token.split(":", 1)
                fields[key] = value

        if "ANGLE" in fields:
            try:
                self.current_angle = float(fields["ANGLE"])
                self.angle_display.setText(f"{self.current_angle:.1f}°")
            except ValueError:
                pass

        if sent_command.startswith("ANGLE:") or sent_command == "HOME":
            try:
                target_angle = float(fields.get("TARGET", "0"))
            except ValueError:
                target_angle = self.angle_input.value()

            self.angle_input.setValue(target_angle)
            if fields.get("MOVING") == "1":
                self.motor_status.setText(f"MOVING TO {target_angle:.1f}°")
                self.motor_status.setStyleSheet("color: #AA6600; font-weight: bold;")
            else:
                self.motor_status.setText("AT TARGET")
                self.motor_status.setStyleSheet("color: #00AA00; font-weight: bold;")
    
    def add_log_entry(self, message):
        """Add timestamped entry to command history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        # Auto-scroll to bottom
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def clear_log(self):
        """Clear command history"""
        self.log_display.clear()
        self.add_log_entry("Log cleared.")
    
    def get_stylesheet(self):
        """Define application stylesheet"""
        return """
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLabel {
                color: #333333;
            }
            QSlider::groove:horizontal {
                background: #cccccc;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0066CC;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #0052A3;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
                background-color: white;
            }
        """


def main():
    app = QApplication(sys.argv)
    dashboard = AntennaControlDashboard()
    dashboard.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
