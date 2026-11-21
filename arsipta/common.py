#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARSIPTA - Sistem Katalog Arsip Perjanjian
Versi: 0.4.0-beta (Fase 4: Konektivitas Hybrid Server Mandiri & Sinkronisasi Tim)
Lisensi: MIT License
Target Platform: Windows 10/11 64-bit (Python 3.14.10, PySide6)
"""

import sys
import os
import csv
import json
import socket
import sqlite3
import hashlib
import shutil
import unittest
import tempfile
import threading
import time
import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

try:
    import openpyxl
    from openpyxl.styles import Font as ExcelFont, PatternFill, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from PySide6.QtCore import (
    Qt, Signal, QObject, QDate, QRect, QRectF, QPoint, QThread
)
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QFrame,
    QStackedWidget, QScrollArea, QDialog, QFormLayout,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QComboBox, QDateEdit, QCheckBox,
    QAbstractItemView, QFileDialog, QProgressBar, QTextEdit
)

# ==============================================================================
# LAYER 1: KONFIGURASI, KONSTANTA, DAN MODEL DATA
# ==============================================================================

APP_NAME = "ARSIPTA"
APP_TAGLINE = "Sistem Katalog Arsip"
APP_VERSION = "0.4.0-beta (Fase 4: Konektivitas Hybrid Server Mandiri & Sinkronisasi Tim)"
DEFAULT_DB_FILENAME = "arsipta_katalog.db"
TEMP_WORK_DIR = "arsipta_temp_work"
DEFAULT_SERVER_PORT = 8080
DEFAULT_SERVER_HOST = "0.0.0.0"
DEFAULT_SERVER_TOKEN = "arsipta_secret_token_2026"
DEFAULT_CLIENT_TIMEOUT = 5.0


