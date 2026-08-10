# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ui_login.ui'
##
## Created by: Qt User Interface Compiler version 6.9.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
    QLineEdit, QMainWindow, QMenuBar, QPushButton,
    QSizePolicy, QStatusBar, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(866, 615)
        self.bgLogin = QWidget(MainWindow)
        self.bgLogin.setObjectName(u"bgLogin")
        self.bgLogin.setStyleSheet(u"/* ============================================================\n"
"   HALAMAN LOGIN (MODERN BLUE)\n"
"   ============================================================ */\n"
"\n"
"/* 1. BACKGROUND UTAMA (FULL BIRU GRADASI HALUS) */\n"
"QWidget#bgLogin {\n"
"    background-color: #2563EB; /* Biru Branding */\n"
"    /* Opsional: Jika ingin gradasi, ganti baris atas dengan:\n"
"       background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #1D4ED8); \n"
"    */\n"
"}\n"
"\n"
"/* 2. KARTU LOGIN (PUTIH MELAYANG) */\n"
"QFrame#cardLogin {\n"
"    background-color: #FFFFFF;\n"
"    border-radius: 20px;       /* Sudut sangat bulat */\n"
"    border: 1px solid #E2E8F0;\n"
"    /* Efek Shadow agar timbul */\n"
"    border-bottom: 5px solid #1E40AF; \n"
"}\n"
"\n"
"/* 3. TEKS JUDUL */\n"
"QLabel#lblJudul {\n"
"    color: #2563EB;       /* Biru */\n"
"    font-size: 32px;\n"
"    font-weight: 900;     /* Extra Bold */\n"
"    qproperty-alignment: AlignCenter;\n"
"    margin-bottom: 5px;\n"
""
                        "    margin-top: 10px;\n"
"}\n"
"\n"
"QLabel#lblSubJudul {\n"
"    color: #64748B;       /* Abu-abu */\n"
"    font-size: 14px;\n"
"    qproperty-alignment: AlignCenter;\n"
"    margin-bottom: 25px;\n"
"}\n"
"\n"
"/* 4. INPUT FIELD (USERNAME & PASSWORD) */\n"
"QLineEdit {\n"
"    background-color: #F8FAFC;\n"
"    border: 1px solid #CBD5E1;\n"
"    border-radius: 10px;\n"
"    padding: 12px 15px;\n"
"    font-size: 14px;\n"
"    color: #1E293B;\n"
"    margin-bottom: 15px;\n"
"}\n"
"QLineEdit:focus {\n"
"    border: 2px solid #2563EB; /* Fokus Biru */\n"
"    background-color: #FFFFFF;\n"
"}\n"
"\n"
"/* 5. TOMBOL MASUK (BESAR & TEGAS) */\n"
"QPushButton#btnLogin {\n"
"    background-color: #2563EB;\n"
"    color: white;\n"
"    border: none;\n"
"    border-radius: 10px;\n"
"    font-size: 14px;\n"
"    font-weight: 800;\n"
"    padding: 12px;\n"
"    margin-top: 10px;\n"
"    letter-spacing: 0.5px;\n"
"}\n"
"QPushButton#btnLogin:hover {\n"
"    background-color: #1D4ED8;\n"
"    margin-top: 12px; /* Efek tekan "
                        "*/\n"
"    border-bottom: none;\n"
"}\n"
"QPushButton#btnLogin:pressed {\n"
"    background-color: #1E3A8A;\n"
"}\n"
"\n"
"/* 6. FOOTER (LUPA PASSWORD) */\n"
"QLabel#lblFooter {\n"
"    color: #94A3B8;\n"
"    font-size: 12px;\n"
"    qproperty-alignment: AlignCenter;\n"
"    margin-top: 15px;\n"
"}\n"
"QLabel#lblFooter:hover {\n"
"    color: #2563EB;\n"
"    cursor: pointer;\n"
"}\n"
"\n"
"/* 6. NAVIGASI BAWAH (LINK STYLE) */\n"
"\n"
"/* Tombol ke Daftar & Lupa Password */\n"
"QPushButton#btnKeDaftar, QPushButton#btnLupaPass {\n"
"    background-color: transparent;\n"
"    border: none;\n"
"    color: #94A3B8;       /* Abu-abu soft */\n"
"    font-size: 12px;\n"
"    font-weight: 600;\n"
"    margin-top: 5px;\n"
"    text-align: center;\n"
"}\n"
"\n"
"/* Efek saat mouse mendekat (Hover) */\n"
"QPushButton#btnKeDaftar:hover, QPushButton#btnLupaPass:hover {\n"
"    color: #2563EB;       /* Berubah jadi Biru */\n"
"    text-decoration: underline; /* Ada garis bawah */\n"
"    cursor: pointer;\n"
"}\n"
"\n"
"/* K"
                        "husus Tombol Daftar agar sedikit lebih menonjol */\n"
"QPushButton#btnKeDaftar {\n"
"    font-weight: 700;     /* Lebih tebal dikit */\n"
"    margin-top: 15px;     /* Jarak dari tombol Masuk */\n"
"}")
        self.gridLayout = QGridLayout(self.bgLogin)
        self.gridLayout.setObjectName(u"gridLayout")
        self.cardLogin = QFrame(self.bgLogin)
        self.cardLogin.setObjectName(u"cardLogin")
        self.cardLogin.setMinimumSize(QSize(400, 450))
        self.cardLogin.setFrameShape(QFrame.Shape.StyledPanel)
        self.cardLogin.setFrameShadow(QFrame.Shadow.Raised)
        self.verticalLayout = QVBoxLayout(self.cardLogin)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.lblJudul = QLabel(self.cardLogin)
        self.lblJudul.setObjectName(u"lblJudul")

        self.verticalLayout.addWidget(self.lblJudul)

        self.lblSubJudul = QLabel(self.cardLogin)
        self.lblSubJudul.setObjectName(u"lblSubJudul")

        self.verticalLayout.addWidget(self.lblSubJudul)

        self.inputUser = QLineEdit(self.cardLogin)
        self.inputUser.setObjectName(u"inputUser")

        self.verticalLayout.addWidget(self.inputUser)

        self.inputPass = QLineEdit(self.cardLogin)
        self.inputPass.setObjectName(u"inputPass")

        self.verticalLayout.addWidget(self.inputPass)

        self.btnLogin = QPushButton(self.cardLogin)
        self.btnLogin.setObjectName(u"btnLogin")

        self.verticalLayout.addWidget(self.btnLogin)

        self.btnKeDaftar = QPushButton(self.cardLogin)
        self.btnKeDaftar.setObjectName(u"btnKeDaftar")
        self.btnKeDaftar.setFlat(True)

        self.verticalLayout.addWidget(self.btnKeDaftar)

        self.btnLupaPass = QPushButton(self.cardLogin)
        self.btnLupaPass.setObjectName(u"btnLupaPass")
        self.btnLupaPass.setFlat(True)

        self.verticalLayout.addWidget(self.btnLupaPass)


        self.gridLayout.addWidget(self.cardLogin, 0, 0, 1, 1)

        MainWindow.setCentralWidget(self.bgLogin)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 866, 33))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.lblJudul.setText(QCoreApplication.translate("MainWindow", u"GURU PRO", None))
        self.lblSubJudul.setText(QCoreApplication.translate("MainWindow", u"Silakan buat akun untuk melanjutkan", None))
        self.inputUser.setText("")
        self.inputUser.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Username / NIP", None))
        self.inputPass.setText("")
        self.inputPass.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Kata Sandi", None))
        self.btnLogin.setText(QCoreApplication.translate("MainWindow", u"Masuk Aplikasi", None))
        self.btnKeDaftar.setText(QCoreApplication.translate("MainWindow", u"Belum punya akun? Daftar Sekarang", None))
        self.btnLupaPass.setText(QCoreApplication.translate("MainWindow", u"Lupa password? Hubungi admin", None))
    # retranslateUi

