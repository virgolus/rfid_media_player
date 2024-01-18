import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Configura Spotipy con le tue credenziali
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="3226a28c823c4a4785dc9993e8898da1",
                                               client_secret="fdc50d8da06b48688017c9b6cdd6f26a",
                                               redirect_uri="http://localhost",
                                               scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                               open_browser=False))

sp_device_id="653505de96b5a2742cb24e59794b0bdc15024205"

def read_rfid():
    rdr = RFID()
    print("In attesa del tag RFID...")
    rdr.wait_for_tag()

    (error, tag_type) = rdr.request()
    if not error:
        print("Tag rilevato!")
        (error, uid) = rdr.anticoll()
        if not error:
            return uid

def get_spotify_devices(sp):
    """ Restituisce un elenco di dispositivi disponibili su Spotify. """
    devices = sp.devices()
    return devices['devices']

def play_track_on_device(track_uri, device_id):
    """ Riproduce una traccia su un dispositivo specifico. """
    sp.start_playback(uris=[track_uri], device_id=device_id)

def main():

    devices = get_spotify_devices(sp)

    print("Dispositivi disponibili:")
    for device in devices:
        print(f"ID: {device['id']}, Nome: {device['name']}, Tipo: {device['type']}, Volume: {device['volume_percent']}%")

    track_uri = 'spotify:track:403vzOZN0tETDpvFipkNIL'

    sp.volume(10, device_id=sp_device_id)
    play_track_on_device(track_uri, sp_device_id)

    try:
        while True:
            uid = read_rfid()
            if uid:
                print(f"UID letto: {uid}")

                # Costruisci l'URI della traccia da riprodurre su Spotify
                track_uri = f"spotify:track:{''.join(str(i) for i in uid)}"

                # Riproduce la traccia su Spotify
                sp.start_playback(uris=[track_uri])

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Script interrotto")

if __name__ == "__main__":
    main()
