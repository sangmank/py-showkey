py-showkey
==========

A python library that listens to key types on a terminal and handles
key combinations. This is an addition of key combination handling
feature on top of what `showkey` does in `kbd` package.

Useful for handling HID devices that generate key types.

In most case, `sudo` would be necessary.

usage (code snippet from showkey.py):
    from showkey import ShowKey

    sk = ShowKey()
    sk.addKeyAction("*p", key_pressed)  # adds handler for all key press
    sk.addKeyAction("*r", key_released) # adds handler for all key release
    sk.addKeyAction([16, 56], alt_q)    # adds handler for Alt-Q comb.
    sk.run()

Reference
=========
* [Linux key code table](http://www.comptechdoc.org/os/linux/howlinuxworks/linux_hlkeycodes.html)
