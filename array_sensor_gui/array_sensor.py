import sys
import os
import os.path
import platform
import time
import serial
import pylab
from PyQt4 import QtCore
from PyQt4 import QtGui
from array_sensor_ui import Ui_ArraySensorMainWindow
from array_reader import ArrayReader

FAKE_DATA_DEBUG = False

# Conversions
#MM2NL = 5.0e3/54.8
DEFAULT_CALIBRATION = 5.0e3/54.8
PIXEL2MM = 63.5e-3
ADC2VOLTS = 5.0/1024.0

# Constants
NUM_PIXEL = 768
ADC_INT_MAX = 1024
ADC_VOLTS_MAX = 5.0
DEFAULT_LOG_FILE = 'array_sensor_data.txt'
DEFAULT_BACKGROUND_FILE = 'background_data.txt'
NUM_BACKGROUND_AVG = 5
BASELINE_PIXEL_LEVEL = 1.0
DEFAULT_THRESHOLD = 1.5
DETECTION_WINDOW = 15
STREAM_STYLE = 'new'

# Select timer interval based on new of old streaming style
if STREAM_STYLE == 'new':
    TIMER_INTERVAL_MS =  500 
else:
    TIMER_INTERVAL_MS =  1000 

class Sensor_MainWindow(QtGui.QMainWindow, Ui_ArraySensorMainWindow):

    def __init__(self,parent=None):
        super(Sensor_MainWindow,self).__init__(parent)
        self.setupUi(self)
        self.connectActions()
        self.setupTimer()
        self.initialize()

    def connectActions(self):
        """
        Connect pushbuttons to their actions
        """
        try:
            # New style signals and slots
            self.startPushButton.pressed.connect(self.startPressed_Callback)
            self.startPushButton.clicked.connect(self.startClicked_Callback)
            self.stopPushButton.clicked.connect(self.stopClicked_Callback)
            self.serialPortLineEdit.editingFinished.connect(self.serialPortLineEdit_Callback)
            self.thresholdLineEdit.editingFinished.connect(self.thresholdLineEdit_Callback)
            self.takeBackgroundPushButton.clicked.connect(self.takeBackground_Callback)
            self.saveBackgroundPushButton.clicked.connect(self.saveBackground_Callback)
            self.loadBackgroundPushButton.clicked.connect(self.loadBackground_Callback)
            self.deleteBackgroundPushButton.clicked.connect(self.deleteBackground_Callback)
            self.setLogPushButton.clicked.connect(self.setLog_Callback)
            self.startLogPushButton.clicked.connect(self.startLog_Callback)
            self.debugRadioButton.clicked.connect(self.debug_Callback)
            self.stopLogPushButton.clicked.connect(self.stopLog_Callback)
            self.calibrationLineEdit.editingFinished.connect(self.calibrationLineEdit_Callback)
        except AttributeError:
            # Didn't work try old style signals and slots
            self.connect(self.startPushButton,QtCore.SIGNAL("pressed()"), self.startPressed_Callback)
            self.connect(self.startPushButton, QtCore.SIGNAL("clicked()"), self.startClicked_Callback)
            self.connect(self.stopPushButton, QtCore.SIGNAL("clicked()"), self.stopClicked_Callback)
            self.connect(self.serialPortLineEdit, QtCore.SIGNAL("edittingFinished()"), self.serialPortLineEdit_Callback)
            self.connect(self.thresholdLineEdit,QtCore.SIGNAL("edittingFinished()"), self.thresholdLineEdit_Callback)
            self.connect(self.takeBackgroundPushButton, QtCore.SIGNAL("clicked()"), self.takeBackground_Callback)
            self.connect(self.saveBackgroundPushButton, QtCore.SIGNAL("clicked()"), self.saveBackground_Callback)
            self.connect(self.loadBackgroundPushButton, QtCore.SIGNAL("clicked()"), self.loadBackground_Callback)
            self.connect(self.deleteBackgroundPushButton, QtCore.SIGNAL("clicked()"), self.deleteBackground_Callback)
            self.connect(self.setLogPushButton, QtCore.SIGNAL("clicked()"), self.setLog_Callback)
            self.connect(self.startLogPushButton, QtCore.SIGNAL("clicked()"), self.startLog_Callback)
            self.connect(self.debugRadioButton, QtCore.SIGNAL("clicked()"), self.debug_Callback)
            self.connect(self.stopLogPushButton, QtCore.SIGNAL("clicked()"), self.stopLog_Callback)
            self.connect(self.calibrationLineEdit, QtCore.SIGNAL("edittingFinished()"), self.calibrationLineEdit_Callback)

    def setupTimer(self):
        """
        Setup timer object
        """
        self.timer = QtCore.QTimer()
        self.timer.setInterval(TIMER_INTERVAL_MS)
        try:
            self.timer.timeout.connect(self.timer_Callback)
        except AttributeError:
            self.connect(self.timer,QtCore.SIGNAL("timeout()"),self.timer_Callback)

    def initialize(self):

        # Set initial state
        self.running = False
        self.logging = False
        self.isFirstLogging = False
        self.haveBackground = False
        self.debugLogging = False

        # Background varialbles 
        self.takeBackground = False
        self.backgroungCount = 0
        self.backgroundData = pylab.zeros((NUM_PIXEL,))

        # Sensor data
        self.sensor = None
        self.pixelPosArray = pylab.arange(0,NUM_PIXEL)*PIXEL2MM

        # Logging data
        self.startTime = time.time()
        self.logFileFid = None

        # Threshold data
        self.threshold = DEFAULT_THRESHOLD
        self.thresholdLineEdit.setText('%1.2f'%(self.threshold,))

        # Set default log and background files
        self.userHome = os.getenv('USERPROFILE')
        if self.userHome is None:
            self.userHome = os.getenv('HOME')
        self.defaultLogPath = os.path.join(self.userHome, DEFAULT_LOG_FILE)
        self.defaultBackgroundPath = os.path.join(self.userHome, DEFAULT_BACKGROUND_FILE)
        self.logPath = self.defaultLogPath
        self.backgroundPath = self.defaultBackgroundPath
        self.logFileLabel.setText('Log File: %s'%(self.logPath))

        # Set last directories
        self.lastLogDir = self.userHome
        self.lastBackgroundDir = self.userHome

        # Set default com port
        osType = platform.system()
        if osType == 'Linux':
            self.port = '/dev/ttyUSB0'
        else:
            self.port = 'com1'
        self.serialPortLineEdit.setText(self.port)

        # Set capillary calibration
        self.calibration = DEFAULT_CALIBRATION 
        self.calibrationLineEdit.setText('%1.3f'%(self.calibration,))


        #  Initialize plot
        self.pixelPlot, = self.mpl.canvas.ax.plot([],[],linewidth=2)
        self.levelPlot, = self.mpl.canvas.ax.plot([0],[0],'or')
        self.pixelPlot.set_visible(False)
        self.levelPlot.set_visible(False)
        self.mpl.canvas.ax.set_autoscale_on(False)
        self.mpl.canvas.ax.grid('on')
        self.mpl.canvas.ax.set_xlim(0,NUM_PIXEL*PIXEL2MM)
        self.mpl.canvas.ax.set_ylim(0,ADC_INT_MAX*ADC2VOLTS)
        self.mpl.canvas.ax.set_xlabel('pixel (mm)')
        self.mpl.canvas.ax.set_ylabel('intensity (V)')
        self.mpl.canvas.ax.set_title('Stopped')

        # Create lists for enabling disabling widgets and apply to current state 
        self.createEnableDisableLists()
        self.enableDisableWidgets()


    def createEnableDisableLists(self):
        self.runningEnableList = [
                'takeBackgroundPushButton',
                'loadBackgroundPushButton',
                'startLogPushButton',
                'stopLogPushButton',
                'stopPushButton',
                ]
        self.runningDisableList = [
                'startPushButton',
                'serialPortLineEdit',
                ]

        self.backgroundEnableList = [
                'saveBackgroundPushButton',
                'deleteBackgroundPushButton'
                ]
        self.backgroundDisableList = []

        self.loggingEnableList = [
                'stopLogPushButton'
                ]
        self.loggingDisableList = [
                'stopPushButton',
                'setLogPushButton',
                'startLogPushButton',
                'takeBackgroundPushButton',
                'saveBackgroundPushButton',
                'loadBackgroundPushButton',
                'deleteBackgroundPushButton',
                'debugRadioButton',
                'thresholdLineEdit',
                ]

    def enableDisableWidgets(self): 
        """
        Enable and disable widgtes based on system state. I'm not real happy with this 
        at present - definitely not the cleanest or clearest way to do things.
        """

        # Set widgets base on whether the device is running or not
        for name in self.runningEnableList:
            widget = getattr(self,name)
            widget.setEnabled(self.running)
        for name in self.runningDisableList:
            widget = getattr(self,name)
            widget.setEnabled(not self.running)

        # Set widgets based on logging state
        if self.running:
            for name in self.loggingEnableList:
                widget = getattr(self,name)
                widget.setEnabled(self.logging)
            for name in self.loggingDisableList:
                widget = getattr(self,name)
                widget.setEnabled((not self.logging))

        # Set widgets based on whether or not we have a background image loaded
        if not self.logging:
            for name in self.backgroundEnableList:
                widget = getattr(self,name)
                widget.setEnabled(self.haveBackground)
            for name in self.backgroundDisableList:
                widget = getattr(self,name)
                widget.setEnabled((not self.haveBackground) and self.running)

    def timer_Callback(self):
        """
        Grab data from sensor, display, find fluid level and write to log file.
        """
        # Get data from sensor
        if FAKE_DATA_DEBUG: 
            data = self.sensor.getFakeData()
        else:
            data = self.sensor.getData()

        if data is None:
            return 

        # Check shape of data
        if data.shape[0] != NUM_PIXEL:
            return

        # Convert data to voltages
        data = ADC2VOLTS*data

        # Get background data 
        if self.takeBackground:
            self.backgroundData += data
            self.backgroundCount += 1
            self.mpl.canvas.ax.set_title('taking background image: %d'%(self.backgroundCount,))
            if self.backgroundCount == NUM_BACKGROUND_AVG:
                self.takeBackground = False
                self.haveBackground = True
                self.backgroundCount = 0
                self.backgroundData = self.backgroundData/NUM_BACKGROUND_AVG
                self.enableDisableWidgets()
        else:
            if self.logging:
                self.mpl.canvas.ax.set_title('Logging')
            else:
                self.mpl.canvas.ax.set_title('Running')

        # Perform background subtraction
        if self.haveBackground:
            data = data + (BASELINE_PIXEL_LEVEL- self.backgroundData)

        # Plot pixel data
        self.pixelPlot.set_visible(True)
        self.pixelPlot.set_data(self.pixelPosArray,data)

        # Find fluid level
        slope_threshold = self.threshold*ADC_VOLTS_MAX/NUM_PIXEL
        rval = getFluidLevel(data,slope_threshold=slope_threshold,window_size=DETECTION_WINDOW)
        if rval:
            ind, value = rval
            pixel_pos = ind*PIXEL2MM
            fluid_level = self.getSensorRange() - pixel_pos*self.calibration
            self.levelLabel.setText('Fluid Level: %1.0f(nl)'%(fluid_level,))
            self.levelPlot.set_visible(True)
            self.levelPlot.set_data([pixel_pos],[value])
        else:
            fluid_level = None
            self.levelPlot.set_visible(False)
            self.levelLabel.setText('Fluid Level: ________')

        self.mpl.canvas.fig.canvas.draw()

        # Reset start time if is first log data point 
        if self.isFirstLogging:
            self.startTime = time.time()
            self.isFirstLogging = False

        # Get time and update label 
        currentTime  = time.time()
        dt = currentTime - self.startTime
        self.timeLabel.setText('Time: %1.0f (s)'%(dt,))

        # Update log file
        if self.logging:
            if fluid_level is not None:
                self.logFileFid.write('%f %f\n'%(dt,fluid_level))
                self.logFileFid.flush()

        #time_end = time.time()
        #print 'dt = ', time_end - currentTime 

    def startPressed_Callback(self):
        self.serialPortLineEdit.setEnabled(False)

    def startClicked_Callback(self):
        """
        Start serial communications with sensor
        """
        # Try to open serial port
        try:
            self.sensor = ArrayReader(
                    port=self.port,
                    baudrate=115200,
                    timeout=0.05,
                    stream_style=STREAM_STYLE
                    )
        except serial.serialutil.SerialException, e:
            QtGui.QMessageBox.critical(self,'Error', '%s'%(e,))
            self.sensor = None
            self.serialPortLineEdit.setEnabled(True)
            return

        # Start timer, set state and update widgets enable values
        self.timer.start()
        self.startTime = time.time()
        self.running = True
        self.enableDisableWidgets()

    def stopClicked_Callback(self):
        """
        Stop serial communications with sensor
        """
        self.stopSensor()
        self.timer.stop()
        self.running = False 
        self.enableDisableWidgets()
        self.mpl.canvas.ax.set_title('Stopped')
        self.mpl.canvas.draw()

    def stopSensor(self):
        """
        Close sensor and delete.
        """
        try:
            self.sensor.close()
            del self.sensor
            self.sensor = None 
        except:
            pass

    def serialPortLineEdit_Callback(self):
        """
        Set serial port sting.
        """
        self.port = str(self.serialPortLineEdit.text())

    def thresholdLineEdit_Callback(self):
        """
        Get Threshold setting
        """
        thresholdStr = str(self.thresholdLineEdit.text())
        try:
            threshold = float(thresholdStr)
            self.threshold = threshold
        except ValueError, e:
            QtGui.QMessageBox.critical(self,'Error', 'Input must be a float, %s'%(e,))
            return
        self.thresholdLineEdit.setText('%1.2f'%(self.threshold,))

    def calibrationLineEdit_Callback(self):
        """
        Set capillary calibration
        """
        calibrationStr = str(self.calibrationLineEdit.text())
        try:
            calibration = float(calibrationStr)
            self.calibration = calibration
        except ValueError, e:
            QtGui.QMessageBox.critical(self,'Error', 'Input must be a float, %s'%(e,))
            return
        self.calibrationLineEdit.setText('%1.3f'%(self.calibration,))


    def debug_Callback(self):
        """
        For setting up debuging data
        """
        pass

    def takeBackground_Callback(self):
        self.haveBackground = False
        self.takeBackground = True
        self.backgroundCount = 0
        self.backgroundData = 0.0*self.backgroundData

    def saveBackground_Callback(self):
        filename = QtGui.QFileDialog.getSaveFileName(None,'Select background file',self.lastBackgroundDir)
        filename = str(filename)
        if filename:
            # save background data
            pylab.savetxt(filename,self.backgroundData)
            self.backgroundPath = filename
            self.lastBackgroundDir =  os.path.split(filename)[0]

    def loadBackground_Callback(self):
        """
        Load background data from file
        """
        filename = QtGui.QFileDialog.getOpenFileName(None,'Select background file',self.lastBackgroundDir)
        filename = str(filename)
        if filename:
            # Try to load background data 
            try:
                data = pylab.loadtxt(filename)
            except Exception, e:
                QtGui.QMessageBox.critical(self,'Error', '%s'%(e,))
                return

            # Check size of array
            if not len(data.shape) == 1 and data.shape[0] == NUM_PIXEL:
                QtGui.QMessageBox.critical(self,'Error', 'background data shape must be (768,)')
                return

            self.backgroundPath = filename
            self.lastBackgroundDir =  os.path.split(filename)[0]
            self.backgroundData = data
            self.haveBackground = True
        self.enableDisableWidgets()

    def deleteBackground_Callback(self):
        """
        Delete current background data
        """
        self.haveBackground = False
        self.enableDisableWidgets()

    def setLog_Callback(self):
        """
        Set the log file.
        """
        filename = QtGui.QFileDialog.getSaveFileName(None,'Select log file',self.lastLogDir)
        filename = str(filename)
        if filename:
            # Set new log file
            self.logPath = filename
            self.lastLogDir =  os.path.split(filename)[0]
            self.logFileLabel.setText('Log File: %s'%(self.logPath))

    def startLog_Callback(self):
        """
        Start logging data to log file.
        """
        # Check to see if file already exists
        if os.path.isfile(self.logPath):
            msgString = 'Log file %s already exists - do you want to overwrite thie file?'%(self.logPath,)
            reply = QtGui.QMessageBox.question(
                    self,
                    'File Exists', 
                    msgString, 
                    QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, 
                    QtGui.QMessageBox.No,
                    )
            if reply == QtGui.QMessageBox.No:
                return
            
        try:
            self.logFileFid = open(self.logPath,'w')
        except Exception, e:
            QtGui.QMessageBox.critical(self,'Error', '%s'%(e,))
            return
        
        self.logging = True
        self.isFirstLogging = True
        self.enableDisableWidgets()

    def stopLog_Callback(self):
        """
        Stop logging data to log file. 
        """
        self.logFileFid.close()
        self.logFileFid = None
        self.logging = False
        self.enableDisableWidgets()

    def getSensorRange(self):
        return NUM_PIXEL*PIXEL2MM*self.calibration
        

    def main(self):
        self.show()


def getFluidLevel(data,slope_threshold=1.5,window_size=15):
    """
    Automatically determine the fluid level from the slope change
    """
    found = False
    n = data.shape[0]
    for i in range(window_size,n-window_size):
        window_ind  = range(i-window_size,i+window_size)
        window_data = data[i-window_size:i+window_size]
        fit = pylab.polyfit(window_ind, window_data,1)
        if fit[0] > slope_threshold:
            found = True
            break
    if found:
        return i, data[i]
    else:
        return None

# -----------------------------------------------------------------------
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    sensor = Sensor_MainWindow()
    sensor.main()
    app.exec_()
