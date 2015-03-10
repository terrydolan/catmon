# Catmon
Catmon is a simple cat flap monitor application written in python. It takes a picture when a cat enters through the cat flap, uploads the picture to google drive and tweets it.

# Set-up
![](https://lh6.googleusercontent.com/-Qu-Tn-N6oao/VPs_fvNICHI/AAAAAAAAAE0/_0T2GnQsqpw/w916-h553-no/catmon%2Bsolution%2Boverview.jpg "Catmon Solution Overview")

See [Terry's blog about catmon](http://terrydolan.blogspot.com/2015/03/catmon.html) for information on how to set-up and some of the learning along the way.

# Run catmon
Catmon needs root privilege because it accesses the raspberry pi's gpio:
```
pi@raspberrypi ~/project-catmon $ **sudo python catmon.py**
```
Catmon will continue to run until you tell it to stop using CTRL-C. By default it logs to *catmon.log* and *stdout*.

# Component List

Catmon uses the following software and hardware components:
- software: python, RPi.GPIO, picamera, tweepy, pydrive, logging, configparser, oath2client, git, github, ...
- hardware: raspberry pi, wi-fi adapter, cobbler, breadboard, connecting wires, reed switch, small magnet, camera module, camera mount, camera tripod, ...

