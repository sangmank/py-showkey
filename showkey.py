#!/usr/bin/python

import array, fcntl, struct, termios, os, sys, tty
import signal, datetime, time, thread

termios.KDGKBMODE = 0x4B44
termios.KDSKBMODE = 0x4B45
termios.KDGKBTYPE = 0x4B33
termios.K_MEDIUMRAW	= 0x02

def open_a_file(filename, mode):
    try:
        f = os.open(filename, mode, 0)
    except OSError, e:
        return None
    
    return f == -1 and None or f

def is_a_console(f):
    buf = array.array('i', [0])
    try:
        fcntl.ioctl(f, termios.KDGKBTYPE, buf, 1)
    except IOError, e:
        return False
    
    return os.isatty(f) and (buf[0] == 1 or buf[0] == 2)

def open_a_console(filename):
    f = open_a_file(filename, os.O_RDWR) or open_a_file(filename, os.O_WRONLY) or open_a_file(filename, os.O_RDONLY)
    if not f:
        return f
    #print filename
    
    if not is_a_console(f):
        return None
    return f

def getfd():
    f = open_a_console("/proc/self/fd/0") or open_a_console("/dev/tty") or open_a_console("/dev/tty0") or open_a_console("/dev/vc/0") or open_a_console("/dev/console")
    if f:
        return f
    
    for fd in range(3):
        if is_a_console(fd):
            return fd

def cleanup(signum, frame):
    print "Signal %d is caught. Exiting.." % signum
    fcntl.ioctl(fd, termios.KDSKBMODE, old_mode) 
    termios.tcsetattr(fd, 0, old_attr)
    sys.exit(1)


KEY_RELEASE, KEY_PRESS = (0, 1)

NOT_PRESSED = 0
PRESSED = 1

class Key:
    def __init__(self, keycode):
        self.keycode = keycode
        now = datetime.datetime.now()
        self.last_pressed = now
        self.state = NOT_PRESSED

    def pressed(self):
        now = datetime.datetime.now()
        self.last_pressed = now
        self.state = PRESSED

    def released(self):
        self.state = NOT_PRESSED

    def check_pressed(self):
        now = datetime.datetime.now()
        if self.state == PRESSED:
            timediff = now - self.last_pressed
            if timediff.total_seconds() < .2:
                return True
            else:
                self.state = NOT_PRESSED
                return False
        return False

lastTimeCalled = {}

def RateLimited(maxPerSecond):
    minInterval = 1.0 / float(maxPerSecond)

    def decorate(func):
        global lastTimeCalled
        lastTimeCalled[func] = datetime.datetime.now()
        def rateLimitedFunction(*args,**kargs):
            now = datetime.datetime.now()
            elapsed = now - lastTimeCalled[func]
            leftToWait = minInterval - elapsed.total_seconds()
            if leftToWait>0:
                return 0
            lastTimeCalled[func] = now
            ret = func(*args,**kargs)
            return ret
        return rateLimitedFunction
    return decorate


class ShowKey:
    def __init__(self):
        global fd, old_mode, old_attr
        self.fd = getfd()
        fd = self.fd

        if self.fd == None:
            print "ERROR: Could not find appropriate file for monitoring. You might want to try 'sudo'"
            sys.exit(1)
    
        buf = array.array('i', [0])
        #print termios.TIOCGPGRP
        fcntl.ioctl(self.fd, termios.KDGKBMODE, buf, True)
        old_mode = buf[0]

        mode = ["RAW", "XLATE", "MEDIUMRAW", "UNICODE", "OFF"][old_mode]
        print "Current terminal mode: %s" % mode

        old_attr = termios.tcgetattr(self.fd)
        new_attr = termios.tcgetattr(self.fd)
        new_attr[0] = 0 # iflag
        new_attr[3] = new_attr[3] & ~termios.ICANON & ~termios.ECHO & termios.ISIG
        new_attr[-1][termios.VMIN] = 18 # buffer size used by showkey..
        new_attr[-1][termios.VTIME] = 1 # 0.1 sec interchar timeout
        
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, new_attr)
        
        fcntl.ioctl(self.fd, termios.KDSKBMODE, 2) # K_MEDIUMRAW == 2
        
        signal.signal(signal.SIGHUP, cleanup)
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGQUIT, cleanup)
        signal.signal(signal.SIGILL, cleanup)

        self.key_info = {}
        self.key_actions = []
        
    def addKeys(self, keycodes):
        for keycode in keycodes:
            if keycode in self.key_info:
                continue
            
            self.key_info[keycode] = Key(keycode)

    def addKeyAction(self, keycomb, action):
        """keycomb can be either "*p", "*r", or a list of keycodes (list of int).
           "*p" refers to the time when any key is pressed.
           "*r" refers to the time when any key is released.
           a list of keycodes refer to the key combination that triggers the action.
        """
        if type(keycomb) == str:
            assert keycomb == "*p" or keycomb == "*r"
        else:
            assert type(keycomb) == list
            self.addKeys(keycomb)
        
        self.key_actions.append((keycomb, action,))
        
    def _do_key_actions(self, pressed, kc):
        for keycomb, action in self.key_actions:
            if type(keycomb) == str:
                if pressed and keycomb == "*p":
                    thread.start_new_thread(action, (kc,))

                if not pressed and keycomb == "*r":
                    thread.start_new_thread(action, (kc,))

                continue
            
            pressed_info = [self.key_info[key].check_pressed() for key in keycomb]
            result = reduce(lambda x, y: x and y, pressed_info, True)
            if result:
                try:
                    thread.start_new_thread(action, (None,))
                except Exception, e:
                    print e
    
    def run(self):
        while True:
            buf = map(ord, os.read(self.fd, 1))
            #print len(buf)
            i_c = 0
            while i_c < len(buf):
                c = buf[i_c]
                s = (c & 0x80) and KEY_RELEASE or KEY_PRESS

                if i_c + 2 < len(buf) and (c & 0x7f) == 0 and (buf[i_c+1] & 0x80 != 0) and (buf[i_c+2] & 0x80 != 0):
                    kc = (buf[i_c+1] & 0x7f) << 7 | (buf[i_c+2] & 0x7f)
                    i_c += 3
                else:
                    kc = (buf[i_c] & 0x7f)
                    i_c += 1
            
                if s == KEY_RELEASE:
                    if kc in self.key_info:
                        self.key_info[kc].released()
                        
                    self._do_key_actions(False, kc)
                    
                elif s == KEY_PRESS:
                    if kc in self.key_info:
                        self.key_info[kc].pressed()
                        
                    self._do_key_actions(True, kc)

def key_pressed(kc):
    print "Key pressed - keycode: %d" % kc

def key_released(kc):
    print "Key released - keycode: %d" % kc

def alt_q(arg):
    print "Alt Q was pressed"

if __name__ == "__main__":
    sk = ShowKey()
    sk.addKeyAction("*p", key_pressed)
    sk.addKeyAction("*r", key_released)
    sk.addKeyAction([16, 56], alt_q)
    sk.run()
