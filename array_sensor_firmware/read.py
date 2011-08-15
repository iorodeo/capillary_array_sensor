import os
import os.path
import sys
import time
import serial
import matplotlib.pylab as pylab

BACKGROUND_FILE = 'background.txt'
MM2NL = 5.0e3/54.8
PIXEL2MM = 63.5e-3

class ArrayReader(serial.Serial):

    def __init__(self,**kwargs):
        super(ArrayReader,self).__init__(**kwargs)
        time.sleep(2.0)
        

    def getData(self):
        self.write('x\n')
        line_list = []
        data_ok = True
        for line in self.readlines():
            line = line.split()
            if line:
                try:
                    line = [int(x) for x in line]
                    line_list.extend(line)
                except:
                    data_ok = False
        if data_ok:
            return pylab.array(line_list)
        else:
            return None


def get_level(data,slope_threshold=1.5,window_size=15):
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
        


        
        
pylab.ion()
reader = ArrayReader(port='/dev/ttyUSB0',baudrate=115200,timeout=0.05)



# Get background
if 1:
    if os.path.isfile(BACKGROUND_FILE):
        print 'reading background.txt'
        background = pylab.loadtxt(BACKGROUND_FILE)
    else:
        print 'getting new background image for equalization'
        numBackground = 5 
        background = pylab.zeros((768,))
        for i in range(0,numBackground):
            print i 
            data = reader.getData()
            background = background + data
        background = background/numBackground
        print 

    pylab.savetxt('background.txt',background)
    delta = 500.0 - background
else:
    print 'background subtraction disabled'
    delta = 0


i = 0
while 1:
    data = reader.getData()
    if data is None:
        continue
    data = data + delta
    if i == 0:
        pylab.figure(1)
        h_line, = pylab.plot(data,linewidth=2)
        h_level, = pylab.plot([0],[0], 'or')
        h_level.set_visible(False)
        pylab.grid('on')
        pylab.ylim(0,1023)
        pylab.xlim(0,768)
        pylab.xlabel('pixel')
        pylab.ylabel('intensity')
    else:
        h_line.set_ydata(data)
        rval = get_level(data)
        if rval:
            ind, value = rval
            fluid_level = ind*PIXEL2MM*MM2NL
            print ind, fluid_level
            h_level.set_visible(True)
            h_level.set_xdata([ind])
            h_level.set_ydata([value])
        else:
            h_level.set_visible(False)
        
    pylab.draw()
    i += 1

                    
