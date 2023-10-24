# Catmon
*Catmon* is a cat flap monitor application written in python. 
It takes a picture when a cat enters through the cat flap, uploads the picture to google drive 
and tweets it on [@boosimba](https://twitter.com/boosimba).
The application was written in 2015 and has been continuously running on a raspberry pi since then, 
tweeting over 30,000 times!

*Catmon* was updated in October 2023 to include the catmon image classifier (aka *Catmonic*) and a port 
to a 64-bit raspberry pi 3b+, giving *Catmon* the ability to identify Boo or Simba.
*Catmonic* is a pytorch deep learning module that classifies a catmon image with the cat's name and a probability.

# Set-up
![](https://lh6.googleusercontent.com/-Qu-Tn-N6oao/VPs_fvNICHI/AAAAAAAAAE0/_0T2GnQsqpw/w916-h553-no/catmon%2Bsolution%2Boverview.jpg "Catmon Solution Overview")

See [Terry's original blog about *Catmon*](https://terrysmusings.blogspot.com/2015/03/catmon.html) for information 
on how to set-up and some of the learning along the way.
It also includes a summary of the major enhancements.

# Run Catmon
*Catmon* needs root privilege because it accesses the raspberry pi's GPIO:
```
pi@raspberrypi ~/project-catmon $ sudo python catmon.py
```
*Catmon* will continue to run until you tell it to stop using CTRL-C. By default it logs to *catmon.log* 
and *stdout*.

# Component List
*Catmon* uses the following software and hardware components:
- software: python, RPi.GPIO, picamera2, tweepy, pydrive, pillow, torch, torchvision, logging, 
configparser, oath2client, httplib2, ...
- hardware: raspberry pi, wi-fi adapter, cobbler, breadboard and electronic components, reed switch, 
small magnet, camera module, camera mount, camera tripod, ...

## Related Catmon Projects
1. *Catmonic*: a pytorch deep learning module that classifies a cat image with the cat's name and a 
probability. The classifier returns a label and a probability; there are 3 possible labels: 
'boo', 'simba' or 'unknown'. 
The model uses 'transfer learning' with a  pre-trained MobileNetV2 model applied to the catmon dataset.  
[Catmonic repo](https://github.com/terrydolan/catmon-img-classifier)
2. *Catmon Image Tagger*: a web app that provides a UI to help tag a set of 
catmon images as either 'Boo' or 'Simba' or 'Unknown'.
The results are saved to google drive.  
[Catmon Image Tagger repo](https://github.com/terrydolan/catmon-img-tag)
3. *Catmon Last Seen*: an application that shows when Boo or Simba were 
last seen, using the output from *Catmon* and the *Catmon Image Classifier*.  
[Catmon Last Seen repo](https://github.com/terrydolan/catmon-lastseen)

Terry Dolan  
October 2023
