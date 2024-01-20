import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from time import sleep

load_dotenv()

# Configura Spotipy con le tue credenziali
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('CLIENT_ID'),
                                               client_secret=os.getenv('CLIENT_SECRET'),
                                               redirect_uri="http://localhost",
                                               scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                               open_browser=False))

sp_device_id=os.getenv('DEVICE_ID')

reader = RFID()
uid_old = ""
util = reader.util()
# Set util debug to true - it will print what's going on
util.debug = True

def read_rfid():
    """ Legge la card rfid """
    print("In attesa del tag RFID...")
    reader.wait_for_tag()
    keys = list()
    error, tag_type = reader.request()
    if not error:
        error, uid = reader.anticoll()
        if not error:
            print('New tag detected! UID: {}'.format(uid))

            # Set tag as used in util. This will call RFID.select_tag(uid)
            util.set_tag(uid)
            # Save authorization info (key A) to util. It doesn't call RFID.card_auth(), that's called when needed
            util.auth(reader.auth_a, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            util.dump()
            # Stop crypto
            util.deauth()

            reader.stop_crypto() # always call this when done working key_read = False
            sleep(0.1)
            return uid

def get_spotify_devices(sp):
    """ Restituisce un elenco di dispositivi disponibili su Spotify. """

    print("Dispositivi disponibili:")
    devices = sp.devices()
    print(devices)
    for device in devices:
        print(f"ID: {device['id']}, Nome: {device['name']}, Tipo: {device['type']}, Volume: {device['volume_percent']}%")
    return devices['devices']

def play_track_on_device(track_uri):
    """ Riproduce una traccia su un dispositivo specifico. """
    print("Start playing track" + track_uri)
    sp.start_playback(uris=[track_uri], device_id=sp_device_id)
    sp.volume(30, sp_device_id)

def main():

    #get_spotify_devices(sp)

    try:
        while True:
            uid = read_rfid()

            if uid:
                print(f"UID letto: {uid}")

                if uid != uid_old:
                    # Costruisci l'URI della traccia da riprodurre su Spotify
                    track_uri = f"spotify:track:{''.join(str(i) for i in uid)}"

                    # Riproduce la traccia su Spotify
                    track_uri = 'spotify:track:403vzOZN0tETDpvFipkNIL'
                    play_track_on_device(track_uri)

                    ui_old=uid


    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Script interrotto")

    finally:
        reader.cleanup() # Calls GPIO cleanup

if __name__ == "__main__":
    main()
