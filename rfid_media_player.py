import time
from time import sleep
import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
import json
import socket
import requests

load_dotenv()

# Setup spotipy connection and auth
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('SP_CLIENT_ID'),
                                                client_secret=os.getenv('SP_CLIENT_SECRET'),
                                                redirect_uri="http://localhost",
                                                scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                                open_browser=False))

# Set rfid reader
rdr = RFID()

GPIO.setwarnings(False)

btn_play_pin = 10
btn_next_pin = 18

playing = False
progress_ms = 0

track_uri = ""
device_id = ""

def read_rfid():
    """ Read rfid card """

    try:
        tag_records = []
        rdr.wait_for_tag()

        (error, data) = rdr.request()
        
        if not error:
            (error, uid) = rdr.anticoll()

            if not error:
                print("\ndetected rfid tag with UID: " + str(uid))

                # Select UID
                if not rdr.select_tag(uid):
                    # Read all 16 sector (4 block each one)
                    for sector in range(16):
                        # Sector Auth
                        if not rdr.card_auth(rdr.auth_b, sector * 4, [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF], uid):
                            for block in range(4):
                                block_addr = sector * 4 + block
                                (error, data) = rdr.read(block_addr)
                                if not error:
                                    # Convert data to string
                                    data = bytes_to_utf8_string(data)
                                    # print(f"Sector {sector}, Block {block}: {data}")

                                    tag_records.append(data)
                    time.sleep(0.1)
                    return (True, str(uid), tag_records)
    except TypeError:
        pass

def get_spotify_devices():
    """ Get spotify connect devices from API """

    devices = sp.devices()
    #print("Dispositivi disponibili:")
    #print(json.dumps(devices, indent=1))
    return devices

def get_spotify_target_device():
    """ Get device id from device name in .env, searching trough devices """

    devices_json = get_spotify_devices()
    for item in devices_json['devices']:
        if item['name'] == os.getenv('SP_DEVICE_NAME'):
            #print(item['id'])
            return item['id']

def play_track_on_device(track_uri, device_id):
    """ Call Play track Spotify API """

    try:
        global progress_ms

        if progress_ms != 0:
            print(f"Resume playing track {track_uri}")
            sp.start_playback(uris=[track_uri], device_id=device_id, position_ms=progress_ms)
            progress_ms = 0
        else:
            print(f"Start playing track {track_uri}")
            sp.start_playback(uris=[track_uri], device_id=device_id)
            print_song_info()
        
        sp.volume(80, device_id)
        
        global playing
        playing = True
    except spotipy.exceptions.SpotifyException as e:
        print(e)
    except socket.timeout as e:
        print(e)

def bytes_to_utf8_string(byte_data):
    """ Clean string readed from rfid tags """

    clean_data = bytes(byte for byte in byte_data if 32 <= byte <= 126)
    try:
        # UTF-8 Docode
        clean_data = clean_data.decode('utf-8').rstrip('\x00')

        return clean_data
    except UnicodeDecodeError:
        return "Errore nella decodifica UTF-8"

def get_uri_from_rfid_tag(tag_records):
    """ Search track id. It's a string delimited by $$ """

    track_uri = ""

    sequence = 0
    for record in tag_records:
        if "$$" in record and sequence == 0:
            track_uri += record.partition("$$")[2]
            sequence += 1
        elif "$$" not in record and sequence > 0:
            track_uri += record
            sequence += 1
        elif "$$" in record and sequence > 0:
            track_uri += record.partition("$$")[0]
            break

    return track_uri

def print_song_info():
    track_info = sp.current_user_playing_track()
    artist = track_info['item']['artists'][0]['name'] 
    album = track_info['item']['album']['name']
    trackName = track_info['item']['name']
    print(f"Playing {trackName}, from the album {album} by {artist}")

def find_device_id():
    """ Polling on getdevices from Spotify API """
    while True:
        try:
            print(f"Try to find Spotify connect device with name {os.getenv('SP_DEVICE_NAME'):}")
        
            # Search id of target device
            device_id = get_spotify_target_device()
            if not device_id:
                print(f"Spotify device connect target NOT FOUND!")
            else:
                print(f"Found spotify connect device with id {device_id}")
                return device_id
        except spotipy.exceptions.SpotifyException as e:
            print(e)
        except socket.timeout as e:
            print(e)
        except requests.exceptions.RequestException as e:
            print(e)
        finally:
            time.sleep(5)

def btn_play_callback(channel):
    """ Play button callback """

    global device_id
    global progress_ms
    global playing
    global track_uri

    long_press = False

    time.sleep(0.1)

    if track_uri:
        start_time = time.time()
        while GPIO.input(channel) == GPIO.HIGH:
            if time.time() - start_time >= 2:
                long_press = True

        if long_press:
            """ Button long press -> restart song"""
            progress_ms = 0
            play_track_on_device(track_uri, device_id)
        elif not long_press and playing:
            """ If a song is playing, pause"""
            sp.pause_playback(device_id)
            track_info = sp.current_user_playing_track()
            progress_ms = track_info['progress_ms']
            playing = False
            print("Pause song")
        else:
            """ If a song paused, resume"""
            play_track_on_device(track_uri, device_id)

    time.sleep(0.1)

def main():

    print(f"Script started\n")

    uid_old = ""
    uid = ""
    rfid_tag_detected = False

    GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
    GPIO.setup(btn_play_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(btn_play_pin, GPIO.FALLING, callback=btn_play_callback, bouncetime=500)
    
    global playing
    global progress_ms
    global track_uri

    global device_id
    device_id = find_device_id()

    print("\nWaiting for rfid tag")

    try:
        while True:
            if device_id:

                try:
                    rfid_tag_detected, uid, tag_records = read_rfid()
                except TypeError:
                    pass

                if rfid_tag_detected:
                    if uid and uid != uid_old:

                        track_uri_str = get_uri_from_rfid_tag(tag_records)
                        if track_uri_str:
                            # Build spotify URI
                            track_uri = f"spotify:track:{track_uri_str}"

                            # Play track on device
                            if (track_uri):
                                play_track_on_device(track_uri, device_id)
                                uid_old = uid
                                rfid_tag_detected = False
                    else:
                        print("Hold on rfid tag\n")
            else:
                device_id = find_device_id()

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("Script terminated")

    finally:
        rdr.cleanup() # Calls GPIO cleanup

if __name__ == "__main__":
    main()