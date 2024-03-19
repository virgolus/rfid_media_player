import time
import RPi.GPIO as GPIO
from pirc522 import RFID
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv
import requests
import logging

""" Log """
logger = logging.getLogger(__name__)
logging.basicConfig(filename='rfid_media_player.log',
                    format= '[%(asctime)s] %(levelname)s - %(message)s',
                    level=logging.INFO)

""" Globals """
load_dotenv()
GPIO.setwarnings(False)

# spotipy
sp = False

# Set rfid reader
rdr = RFID()

btn_play_pin = 10
btn_next_pin = 18

playing = False
progress_ms = 0
retry_num = 0
max_retry = 3 
last_rfid_tag_readed_s = 0
last_pause_btn_pressed_s = 0

track_uri = ""
device_id = ""

def init_spotipy():
    """ Setup spotipy connection and auth """
    global sp
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('SP_CLIENT_ID'),
                                                client_secret=os.getenv('SP_CLIENT_SECRET'),
                                                redirect_uri="http://localhost",
                                                scope="streaming user-library-read user-read-playback-state user-modify-playback-state",
                                                open_browser=False))
        return True
    except requests.exceptions.HTTPError as e:
        logging(e)
        return False

def read_rfid():
    """ Read rfid card """

    try:
        tag_records = []
        rdr.wait_for_tag()

        (error, data) = rdr.request()
        
        if not error:
            (error, uid) = rdr.anticoll()

            if not error:
                logger.info("\ndetected rfid tag with UID: " + str(uid))

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
                                    # logger.info(f"Sector {sector}, Block {block}: {data}")

                                    tag_records.append(data)
                    return (True, str(uid), tag_records)
    except TypeError:
        pass

def get_spotify_devices():
    """ Get spotify connect devices from API """

    devices = sp.devices()
    #logger.info("Dispositivi disponibili:")
    #logger.info(json.dumps(devices, indent=1))
    return devices

def get_spotify_target_device():
    """ Get device id from device name in .env, searching trough devices """

    devices_json = get_spotify_devices()
    for item in devices_json['devices']:
        if item['name'] == os.getenv('SP_DEVICE_NAME'):
            #logger.info(item['id'])
            return item['id']

def play_track_on_device(track_uri, device_id, new):
    """ Call Play track Spotify API """

    try:
        global progress_ms
        global playing
        global max_retry

        if not new:
            logger.info(f"Resume playing track {track_uri}")
            sp.start_playback(uris=[track_uri], device_id=device_id, position_ms=progress_ms)
        else:
            logger.info(f"Start playing track {track_uri}")
            sp.start_playback(uris=[track_uri], device_id=device_id)
            logger.info_song_info()
        
        sp.volume(80, device_id)
        playing = True

    except requests.exceptions.HTTPError as e:
        logger.info("requests.exceptions.HTTPError!!!!!!")
        logger.info(e)
    except requests.exceptions.RequestException as e:
        logger.info("requests.exceptions.RequestException!!!!!!")
        logger.info(e)
        retry_play(track_uri, device_id, new)
    except spotipy.exceptions.SpotifyException as e:
        logger.info("spotipy.exceptions.SpotifyException!!!!!!")
        logger.info(e)
        retry_play(track_uri, device_id, new)

def retry_play(track_uri, device_id, new):
    """ Spotify APIs are a pain in the ass, retry play if return an unattended 404 """
    global retry_num
    global max_retry

    if retry_num < max_retry:
        time.sleep(3)
        play_track_on_device(track_uri, device_id, new)
        retry_num += 1
    else:
        init_spotipy()
        find_device_id()
        retry_num = 0

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
    logger.info(f"Playing {trackName}, from the album {album} by {artist}")

def find_device_id():
    """ Polling on getdevices from Spotify API """
    while True:
        try:
            logger.info(f"Try to find Spotify connect device with name {os.getenv('SP_DEVICE_NAME'):}")
        
            # Search id of target device
            device_id = get_spotify_target_device()
            if not device_id:
                logger.info(f"Spotify device connect target NOT FOUND!")
            else:
                logger.info(f"Found spotify connect device with id {device_id}")
                return device_id

        except requests.exceptions.RequestException as e:
            logger.info(e)
        finally:
            time.sleep(10)

def btn_play_callback(channel):
    """ Play button callback """

    global device_id
    global progress_ms
    global playing
    global track_uri
    global last_pause_btn_pressed_s
    long_press = False

    # Callback doesn't work well, added last button time pressed control
    if track_uri:

        start_time = time.time()
        while GPIO.input(channel) == GPIO.HIGH:
            if time.time() - start_time >= 0.5:
                long_press = True

        if long_press:
            """ Button long press -> restart song"""
            progress_ms = 0
            play_track_on_device(track_uri, device_id, True)
            logger.info("Restart song")

        if (time.time() - last_pause_btn_pressed_s) > 0.5:
            if not long_press and playing:
                """ If a song is playing, pause"""
                sp.pause_playback(device_id)
                track_info = sp.current_user_playing_track()
                progress_ms = track_info['progress_ms']
                playing = False
                logger.info("Pause song")
            else:
                """ If a song paused, resume"""
                play_track_on_device(track_uri, device_id, False)

        last_pause_btn_pressed_s = time.time()

def play_or_not(uid, uid_old, track_uri):
    """ check the status of device and choose if play a track or not """
    
    # validate track uri
    if len(track_uri) < 10:
        logger.info(f"Track uri not valid! -> {track_uri}")
        return False

    # tag uid changed or at least 5 second has passed
    if uid and uid != uid_old:
        return True
    elif uid == uid_old and (time.time() - last_rfid_tag_readed_s > 10):
        logger.info("five second passed")
        return True
    else:
        return False
    
def main():


    logger.info('Started')
    logger.info('Finished')

    logger.info(f"Script started\n")

    while not init_spotipy():
        logger.info("Unable to retrive spotify token, maybe network issue... Sleep for five seconds")
        time.sleep(5)

    uid_old = ""
    uid = ""
    rfid_tag_detected = False

    GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
    GPIO.setup(btn_play_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(btn_play_pin, GPIO.FALLING, callback=btn_play_callback, bouncetime=400)
    
    global playing
    global progress_ms
    global track_uri

    global device_id
    device_id = find_device_id()

    logger.info("\nWaiting for rfid tag")

    try:
        while True:
            if device_id:

                try:
                    rfid_tag_detected, uid, tag_records = read_rfid()
                except TypeError:
                    pass

                if rfid_tag_detected:
                    track_uri_str = get_uri_from_rfid_tag(tag_records)

                    if play_or_not(uid, uid_old, track_uri_str):

                        # Build spotify URI
                        track_uri = f"spotify:track:{track_uri_str}"

                        # Play track on device
                        if (track_uri):
                            play_track_on_device(track_uri, device_id, True)
                            uid_old = uid
                            rfid_tag_detected = False
                    else:
                        logger.info("Hold on rfid tag\n")
                    
                    global last_rfid_tag_readed_s
                    last_rfid_tag_readed_s = time.time()
            else:
                device_id = find_device_id()

    except KeyboardInterrupt:
        GPIO.cleanup()
        logger.info("Script terminated")

    finally:
        rdr.cleanup() # Calls GPIO cleanup

if __name__ == "__main__":
    main()