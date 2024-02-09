import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
from time import sleep
import json

load_dotenv()

# Configura Spotipy con le tue credenziali
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('CLIENT_ID'),
                                                client_secret=os.getenv('CLIENT_SECRET'),
                                                redirect_uri="http://localhost",
                                                scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                                open_browser=False))

sp_device_id=os.getenv('DEVICE_ID')

# Set rfid reader
rdr = RFID()
util = rdr.util()
util.debug = False

def read_rfid():
    """ Read rfid card """

    try:

        tag_records = []
        rdr.wait_for_tag()

        (error, data) = rdr.request()
        if not error: 
            print("\nCard detected")

            (error, uid) = rdr.anticoll()
            if not error:
                print("UID: " + str(uid))

                # Seleziona la card con UID
                if not rdr.select_tag(uid):
                    # Leggi tutti i 16 settori (ognuno con 4 blocchi)
                    for sector in range(16):
                        # Prova a autenticare il settore
                        if not rdr.card_auth(rdr.auth_b, sector * 4, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], uid):
                            for block in range(4):
                                block_addr = sector * 4 + block
                                (error, data) = rdr.read(block_addr)
                                if not error:
                                    # Converti i dati in una stringa
                                    data = bytes_to_utf8_string(data)
                                    # print(f"Sector {sector}, Block {block}: {data}")

                                    tag_records.append(data)
                                #else:
                                   # print(f"Errore durante la lettura del Blocco {block} del Settore {sector}")
                    return (str(uid), tag_records)
    except TypeError:
        print("TypeError")       

def get_spotify_devices():
    """ Get spotify connect devices from API """

    print("Dispositivi disponibili:")
    devices = sp.devices()
    print(json.dumps(devices, indent=1))

def get_spotify_target_device():
    """ Get device id from device name in .env, searching trough devices """

    #print("Dispositivi disponibili:")
    devices = sp.devices()
    #print(json.dumps(devices, indent=1))

    data = json.loads(json.dumps(devices))

    for item in data['devices']:
        if item['name'] == os.getenv('DEVICE_NAME'):
            #print(item['id'])
            return item['id']

def play_track_on_device(track_uri, device):
    """ Call Play track Spotify API """

    print(f"Start playing track {track_uri}")
    try:
        sp.start_playback(uris=[track_uri], device_id=device)
        sleep(2)
        sp.volume(40, sp_device_id)
    except spotipy.exceptions.SpotifyException as e:
        print(e)

def bytes_to_utf8_string(byte_data):
    """ Clean string readed from rfid tags """

    clean_data = bytes(byte for byte in byte_data if 32 <= byte <= 126)
    try:
        # Decodifica i dati usando UTF-8
        clean_data = clean_data.decode('utf-8').rstrip('\x00')

        return clean_data
    except UnicodeDecodeError:
        return "Errore nella decodifica UTF-8"

def get_uri_from_rfid_tag(tag_records):
    """ Search track id. It's a string delimited by $$ """

    track_uri = ""
    #print(tag_records)
    sequence = 0
    for record in tag_records:
        #print(f"record: {record}")
        
        if "$$" in record and sequence == 0:
            track_uri += record.partition("$$")[2]
            sequence += 1
        elif "$$" not in record and sequence > 0:
            track_uri += record
            sequence += 1
        elif "$$" in record and sequence > 0:
            track_uri += record.partition("$$")[0]
            break

    print(f"track_uri: {track_uri}")
    return track_uri


def main():
    print(f"Script started\n")

    # Print spotify connect devices
    get_spotify_devices()
    
    # Search id of target device
    device_id = get_spotify_target_device()
    if not device_id:
        print(f"Spotify device connect target NOT FOUND!")
    else:
        print(f"Found spotify connect device with id {device_id}")

    print(f"Waiting for rfid tag")

    try:
        uid_old = ""
        uid = ""

        while True:
            try:
                uid, tag_records = read_rfid()
            except TypeError:
                pass

            if uid and uid != uid_old:

                track_uri = get_uri_from_rfid_tag(tag_records)
                if track_uri:
                    # Costruisci l'URI della traccia da riprodurre su Spotify
                    track_uri = f"spotify:track:{track_uri}"

                    # Riproduce la traccia su Spotify
                    # track_uri = 'spotify:track:403vzOZN0tETDpvFipkNIL'
                    if (track_uri):
                        play_track_on_device(track_uri, device_id)
                        uid_old = uid
            else:
                print("Same rfid card")

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Script terminated")

    finally:
        rdr.cleanup() # Calls GPIO cleanup

if __name__ == "__main__":
    main()