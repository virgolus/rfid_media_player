import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

# Configura Spotipy con le tue credenziali
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv(CLIENT_ID),
                                               client_secret=os.getenv(SECRET_ID),
                                               redirect_uri="http://localhost",
                                               scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                               open_browser=False))

sp_device_id="653505de96b5a2742cb24e59794b0bdc15024205"

load_dotenv()
print('[press ctrl+c to end the script]')

def read_rfid():
    rdr = RFID()
    print("In attesa del tag RFID...")
    rdr.wait_for_tag()

    (error, tag_type) = rdr.request()
    if not error:
        print("Tag rilevato!")
        (error, uid) = rdr.anticoll()
        keys = list()
        if not error:
            return uid

def get_spotify_devices(sp):
    """ Restituisce un elenco di dispositivi disponibili su Spotify. """

    print("Dispositivi disponibili:")
    devices = sp.devices()
    for device in devices:
        print(f"ID: {device['id']}, Nome: {device['name']}, Tipo: {device['type']}, Volume: {device['volume_percent']}%")
    return devices['devices']

def play_track_on_device(track_uri):
    """ Riproduce una traccia su un dispositivo specifico. """
    sp.start_playback(uris=[track_uri], sp_device_id)
    sp.volume(10, sp_device_id)

def main():

    try:
        while True:
            uid = read_rfid()
            if uid:
                print(f"UID letto: {uid}")

                # Costruisci l'URI della traccia da riprodurre su Spotify
                track_uri = f"spotify:track:{''.join(str(i) for i in uid)}"

                # Riproduce la traccia su Spotify
                track_uri = 'spotify:track:403vzOZN0tETDpvFipkNIL'
                play_track_on_device(track_uri)

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Script interrotto")

   finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
