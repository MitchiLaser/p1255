from PyQt5.QtWidgets import QApplication
import sys
from p1255.gui import MainWindow




def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()