#!/usr/bin/env python

# requieres turing smart screen python
# https://github.com/mathoudebine/turing-smart-screen-python/

# Copyright (C) 2024 Cristina Rosangel Ibañez (crinelam)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import signal
import sys
import locale
from datetime import datetime

import yaml
from PIL import Image
from mutagen.flac import FLAC
from mutagen import File
import io

# modules for LCD communication
from library.lcd.lcd_comm_rev_a import LcdCommRevA, Orientation
from library.lcd.lcd_comm_rev_b import LcdCommRevB
from library.lcd.lcd_comm_rev_c import LcdCommRevC
from library.lcd.lcd_comm_rev_d import LcdCommRevD
from library.lcd.lcd_simulated import LcdSimulated
from library.log import logger

#configuration loading
def loadYaml(configfile):
    with open(configfile, "rt", encoding='utf8') as stream:
        yamlconfig = yaml.safe_load(stream)
        return yamlconfig

# load config files
CONFIG_DATA = loadYaml("config.yaml")
MUSICPLAYER_DATA = loadYaml("musicplayerconfig.yaml")

# Get com port and revision config
COM_PORT = CONFIG_DATA["config"]["COM_PORT"]
REVISION = CONFIG_DATA["display"]["REVISION"]

stop = False

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')

    # Build your LcdComm object based on the HW revision
    lcd_comm = None
    if REVISION == "A":
        logger.info("Selected Hardware Revision A (Turing Smart Screen 3.5\" & UsbPCMonitor 3.5\"/5\")")
        # NOTE: If you have UsbPCMonitor 5" you need to change the width/height to 480x800 below
        lcd_comm = LcdCommRevA(com_port=COM_PORT, display_width=320, display_height=480)
    elif REVISION == "B":
        logger.info("Selected Hardware Revision B (XuanFang screen 3.5\" version B / flagship)")
        lcd_comm = LcdCommRevB(com_port=COM_PORT)
    elif REVISION == "C":
        logger.info("Selected Hardware Revision C (Turing Smart Screen 5\")")
        lcd_comm = LcdCommRevC(com_port=COM_PORT)
    elif REVISION == "D":
        logger.info("Selected Hardware Revision D (Kipye Qiye Smart Display 3.5\")")
        lcd_comm = LcdCommRevD(com_port=COM_PORT)
    elif REVISION == "SIMU":
        logger.info("Selected 3.5\" Simulated LCD")
        lcd_comm = LcdSimulated(display_width=320, display_height=480)
    elif REVISION == "SIMU5":
        logger.info("Selected 5\" Simulated LCD")
        lcd_comm = LcdSimulated(display_width=480, display_height=800)
    else:
        logger.error("Unknown revision")
        try:
            sys.exit(1)
        except:
            os._exit(1)

    def sighandler(signum, frame):
        global stop
        stop = True
        logger.info("Caught signal %d, exiting" % signum)
    
    # Set the signal handlers, to send a complete frame to the LCD before exit
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)
    is_posix = os.name == 'posix'
    if is_posix:
        signal.signal(signal.SIGQUIT, sighandler)

    # Reset screen in case it was in an unstable state (screen is also cleared)
    lcd_comm.Reset()

    # Send initialization commands
    lcd_comm.InitializeComm()

    # Set brightness in % (warning: revision A display can get hot at high brightness! Keep value at 50% max for rev. A)
    lcd_comm.SetBrightness(level=CONFIG_DATA["display"]["BRIGHTNESS"])

    # Set backplate RGB LED color (for supported HW only)
    lcd_comm.SetBackplateLedColor(led_color=(100, 20, 120))

    # Set orientation (screen starts in Portrait)
    if CONFIG_DATA["display"]["DISPLAY_REVERSE"]:
        lcd_comm.SetOrientation(orientation=Orientation.REVERSE_LANDSCAPE)
    else:
        lcd_comm.SetOrientation(orientation=Orientation.LANDSCAPE)

    # Define background picture
    background = f"res/backgrounds/background.png"

    # Multiline text
    def multiLine(textInput):
        text = ""
        if len(textInput) > MUSICPLAYER_DATA["config"]["TEXT_WRAP"]:
            index = textInput[:MUSICPLAYER_DATA["config"]["TEXT_WRAP"]].rindex(' ')
            text += textInput[:index].strip()
            text += "\n"
            textInput = textInput[index:]
            text += textInput
        else:
            text = textInput
        return text

    lastRead = ""
    while not stop:
        try:
            # Order: Artist, Title, Album, Image
            file = MUSICPLAYER_DATA["config"]["INFO_FILE"]
            with open(file, 'r') as file:
                content = file.read()
            
            content = content.replace("\n", "")
            if lastRead != content:
                lastRead = content

                 #Blank everything
                lcd_comm.DisplayBitmap(background)

                songInfo = content.split(";")
                logger.info(songInfo)

                # Image
                image = None
                ext = os.path.splitext(songInfo[3])[-1].lower()
                if ext == ".mp3" or ext == ".mp3:album":
                    songPath = songInfo[3].replace(":album", "")
                    embedImage = File(songPath).tags['APIC:'].data
                    image = Image.open(io.BytesIO(embedImage))
                elif ext == ".flac" or ext == ".flac:album":
                    songPath = songInfo[3].replace(":album", "")
                    embedImage = FLAC(songPath).pictures[0].data
                    image = Image.open(io.BytesIO(embedImage))
                else:
                    image = Image.open(songInfo[3])

                finalImage = image.resize([200, 200], 0)
                lcd_comm.DisplayPILImage(finalImage, 2, 60, 200, 200)

                # Artist
                artist = songInfo[0]
                text = multiLine(artist)
                
                lcd_comm.DisplayText(text, 206, 80,
                                    font="roboto/Roboto-Bold.ttf",
                                    font_size=20,
                                    font_color=(255, 255, 255),
                                    background_image=background)
                
                # Title
                title = songInfo[1]
                text = multiLine(title)

                lcd_comm.DisplayText(text, 206, 130,
                                    font="roboto/Roboto-Bold.ttf",
                                    font_size=20,
                                    font_color=(255, 255, 255),
                                    background_image=background)
                
                # Album
                album = songInfo[2]
                text = multiLine(album)

                lcd_comm.DisplayText(text, 206, 180,
                                    font="roboto/Roboto-Bold.ttf",
                                    font_size=20,
                                    font_color=(255, 255, 255),
                                    background_image=background)
                      
        except Exception as e:
            logger.debug(str(e))
            lcd_comm.DisplayText(str(e), 10, 20,
                                 font="roboto/Roboto-Bold.ttf",
                                 font_size=20,
                                 font_color=(255, 255, 255),
                                 background_image=background)
            
        lcd_comm.DisplayText(str(datetime.now().strftime('%a %d %b %Y')), 10, 2,
                             font="roboto/Roboto-Bold.ttf",
                             font_size=20,
                             font_color=(255, 255, 255),
                             background_image=background)
        
        lcd_comm.DisplayText(str(datetime.now().strftime('%H:%M:%S')), 400, 2,
                             font="roboto/Roboto-Bold.ttf",
                             font_size=20,
                             font_color=(255, 255, 255),
                             background_image=background,
                             align='right')

    # Close serial connection at exit
    lcd_comm.ScreenOff()
    lcd_comm.SetBackplateLedColor(led_color=(0, 0, 0))
    lcd_comm.closeSerial()
    
    try:
        sys.exit(0)
    except:
        os._exit(0)
